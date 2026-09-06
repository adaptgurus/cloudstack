# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Small WSGI BFF boundary for the LayerSentry Kubernetes controller.

Authentication must be supplied by the deployment integration. Browser
identity headers are never trusted by the default authenticator.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from http import HTTPStatus
from typing import Any, Callable, Mapping, Protocol

from .model import (
    Actor,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    InvalidRequestError,
    NotFoundError,
)
from .service import ControllerService, parse_cluster_request


MAX_BODY_BYTES = 1024 * 1024
_CLUSTER_PATH = re.compile(r"^/v1/kubernetes/clusters/([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(/scale)?$")


class Authenticator(Protocol):
    def authenticate(self, environ: Mapping[str, Any]) -> Actor: ...


class DenyAllAuthenticator:
    def authenticate(self, environ: Mapping[str, Any]) -> Actor:
        del environ
        raise AuthorizationError("authentication is not configured")


class BFFApplication:
    def __init__(self, service: ControllerService, authenticator: Authenticator | None = None):
        self.service = service
        self.authenticator = authenticator or DenyAllAuthenticator()

    @staticmethod
    def _response(start_response: Callable, status: HTTPStatus, payload: Mapping[str, Any]):
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ]
        start_response(f"{status.value} {status.phrase}", headers)
        return [body]

    @staticmethod
    def _body(environ: Mapping[str, Any]) -> Mapping[str, Any]:
        content_type = str(environ.get("CONTENT_TYPE", "")).split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise InvalidRequestError("Content-Type must be application/json")
        try:
            length = int(environ.get("CONTENT_LENGTH") or "0")
        except ValueError as exc:
            raise InvalidRequestError("invalid Content-Length") from exc
        if length < 1 or length > MAX_BODY_BYTES:
            raise InvalidRequestError("request body size is invalid")
        raw = environ["wsgi.input"].read(length)
        if len(raw) != length:
            raise InvalidRequestError("request body is incomplete")
        try:
            payload = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidRequestError("request body is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise InvalidRequestError("request body must be a JSON object")
        return payload

    def __call__(self, environ: Mapping[str, Any], start_response: Callable):
        try:
            actor = self.authenticator.authenticate(environ)
            method = str(environ.get("REQUEST_METHOD", "GET")).upper()
            path = str(environ.get("PATH_INFO", ""))
            if method == "GET" and path == "/v1/kubernetes/readiness":
                return self._response(start_response, HTTPStatus.OK, self.service.readiness(actor))
            if method == "GET" and path == "/v1/kubernetes/images":
                try:
                    query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")),
                        strict_parsing=True, keep_blank_values=True, max_num_fields=2)
                except ValueError as exc:
                    raise InvalidRequestError("image query is malformed") from exc
                if set(query) != {"projectId", "zoneId"} or any(len(v) != 1 or not v[0] for v in query.values()):
                    raise InvalidRequestError("projectId and zoneId must occur exactly once")
                project_id = query["projectId"][0]
                self.service.authorizer.require(actor, "kubernetes.cluster.read", project_id)
                reader = getattr(self.authenticator, "qualified_node_images", None)
                if reader is None:
                    raise AuthorizationError("native image scope verification is not configured")
                images = reader(environ, actor, project_id, query["zoneId"][0], self.service.qualified_images)
                return self._response(start_response, HTTPStatus.OK, {"images": images})
            if method == "GET" and path in {"/v1/kubernetes/operations", "/v1/kubernetes/clusters"}:
                try:
                    query = urllib.parse.parse_qs(str(environ.get("QUERY_STRING", "")),
                                                 strict_parsing=True, keep_blank_values=True, max_num_fields=3)
                except ValueError as exc:
                    raise InvalidRequestError("query string is malformed") from exc
                allowed = {"projectId", "limit", "after"} if path.endswith("operations") else {"projectId"}
                if not query.get("projectId") or set(query) - allowed or any(len(v) != 1 or not v[0] for v in query.values()):
                    raise InvalidRequestError("projectId is required and query fields must occur exactly once")
                if path.endswith("operations"):
                    limit = query.get("limit", ["50"])[0]
                    after = query.get("after", [None])[0]
                    if not re.fullmatch(r"[0-9]{1,3}", limit) or (after and not re.fullmatch(r"[0-9a-f-]{36}", after)):
                        raise InvalidRequestError("operation limit or cursor is invalid")
                    payload = self.service.list_operations(actor, query["projectId"][0], int(limit), after)
                else:
                    payload = self.service.list_clusters(actor, query["projectId"][0])
                return self._response(start_response, HTTPStatus.OK, payload)
            if method == "POST" and path == "/v1/kubernetes/clusters":
                payload = self._body(environ)
                request = parse_cluster_request(payload)
                self.service.authorizer.require(actor, "kubernetes.cluster.create", request.project_id or actor.account_id)
                verifier = getattr(self.authenticator, "require_cluster_access", None)
                if verifier is None:
                    raise AuthorizationError("native resource scope verification is not configured")
                verifier(environ, actor, request)
                operation, created = self.service.submit_cluster_create(
                    actor, payload, str(environ.get("HTTP_IDEMPOTENCY_KEY", "")),
                )
                status = HTTPStatus.ACCEPTED if created else HTTPStatus.OK
                return self._response(start_response, status, {"operation": operation.public_dict()})
            match = _CLUSTER_PATH.fullmatch(path)
            if match and method in {"POST", "DELETE"}:
                payload = dict(self._body(environ))
                if payload.get("cluster_name") != match.group(1):
                    raise InvalidRequestError("cluster_name must exactly match the request path")
                key = str(environ.get("HTTP_IDEMPOTENCY_KEY", ""))
                if method == "POST" and match.group(2) == "/scale":
                    operation, created = self.service.submit_cluster_scale(actor, payload, key)
                elif method == "DELETE" and match.group(2) is None:
                    operation, created = self.service.submit_cluster_delete(actor, payload, key)
                else:
                    return self._response(start_response, HTTPStatus.NOT_FOUND, {"error": "route not found"})
                status = HTTPStatus.ACCEPTED if created else HTTPStatus.OK
                return self._response(start_response, status, {"operation": operation.public_dict()})
            if match and method == "GET" and match.group(2) is None:
                try:
                    query = urllib.parse.parse_qs(
                        str(environ.get("QUERY_STRING", "")),
                        strict_parsing=True,
                        keep_blank_values=True,
                    )
                except ValueError as exc:
                    raise InvalidRequestError("query string is malformed") from exc
                if set(query) != {"namespace", "projectId"} or any(len(value) != 1 for value in query.values()):
                    raise InvalidRequestError("namespace and projectId query parameters are required exactly once")
                status = self.service.cluster_status(
                    actor, namespace=query["namespace"][0], name=match.group(1), project_id=query["projectId"][0],
                )
                return self._response(start_response, HTTPStatus.OK, {"cluster": status})
            prefix = "/v1/kubernetes/operations/"
            if method == "GET" and path.startswith(prefix) and "/" not in path[len(prefix):]:
                operation_id = path[len(prefix):]
                operation = self.service.get_operation(actor, operation_id)
                return self._response(start_response, HTTPStatus.OK, {
                    "operation": operation.public_dict(),
                    "events": self.service.store.events(operation.id),
                })
            return self._response(start_response, HTTPStatus.NOT_FOUND, {"error": "route not found"})
        except AuthenticationError as exc:
            return self._response(start_response, HTTPStatus.UNAUTHORIZED, {"error": str(exc)})
        except AuthorizationError as exc:
            return self._response(start_response, HTTPStatus.FORBIDDEN, {"error": str(exc)})
        except InvalidRequestError as exc:
            return self._response(start_response, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except ConflictError as exc:
            return self._response(start_response, HTTPStatus.CONFLICT, {"error": str(exc)})
        except NotFoundError as exc:
            return self._response(start_response, HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except Exception:
            # Do not return stack traces, provider payloads or credentials.
            return self._response(start_response, HTTPStatus.INTERNAL_SERVER_ERROR, {
                "error": "LayerSentry controller request failed",
            })
