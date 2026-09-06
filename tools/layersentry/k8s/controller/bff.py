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
from http import HTTPStatus
from typing import Any, Callable, Mapping, Protocol

from .model import Actor, AuthorizationError, ConflictError, InvalidRequestError, NotFoundError
from .service import ControllerService


MAX_BODY_BYTES = 1024 * 1024


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
            if method == "POST" and path == "/v1/kubernetes/clusters":
                operation, created = self.service.submit_cluster_create(
                    actor, self._body(environ), str(environ.get("HTTP_IDEMPOTENCY_KEY", "")),
                )
                status = HTTPStatus.ACCEPTED if created else HTTPStatus.OK
                return self._response(start_response, status, {"operation": operation.public_dict()})
            prefix = "/v1/kubernetes/operations/"
            if method == "GET" and path.startswith(prefix) and "/" not in path[len(prefix):]:
                operation_id = path[len(prefix):]
                operation = self.service.get_operation(actor, operation_id)
                return self._response(start_response, HTTPStatus.OK, {
                    "operation": operation.public_dict(),
                    "events": self.service.store.events(operation.id),
                })
            return self._response(start_response, HTTPStatus.NOT_FOUND, {"error": "route not found"})
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
