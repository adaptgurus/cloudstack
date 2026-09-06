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

"""CloudStack-session authentication and capability authorization.

The browser's readable identity/role cookies are deliberately ignored. The
HttpOnly CloudStack session cookie and session-key CSRF token are replayed to
the exact configured CloudStack API, which remains authoritative for the
caller's API permissions and visible projects.
"""

from __future__ import annotations

import hashlib
import hmac
import http.cookies
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .model import Actor, AuthenticationError, AuthorizationError, InvalidRequestError


_SESSION_ID = re.compile(r"^[A-Za-z0-9._:-]{16,256}$")
_SESSION_KEY = re.compile(r"^[A-Za-z0-9_-]{20,256}$")
_READ_COMMANDS = frozenset({"listApis", "listProjects", "listZones", "listNetworks",
                            "listServiceOfferings", "listTemplates", "listPublicIpAddresses"})
_ACTION_CAPABILITIES = {
    "kubernetes.readiness.read": (),
    "kubernetes.cluster.read": ("listProjects", "listVirtualMachines"),
    "kubernetes.operation.read": ("listProjects",),
    "kubernetes.cluster.create": (
        "listProjects", "deployVirtualMachine", "createLoadBalancerRule", "createVolume",
    ),
    "kubernetes.cluster.scale": (
        "listProjects", "deployVirtualMachine", "destroyVirtualMachine",
    ),
    "kubernetes.cluster.delete": ("listProjects", "destroyVirtualMachine"),
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


@dataclass(frozen=True)
class CloudStackSessionConfig:
    endpoint: str
    trusted_origins: tuple[str, ...]
    ca_file: str | None = None
    timeout_seconds: int = 15
    allow_insecure_http: bool = False
    max_projects: int = 1000


class CloudStackSessionAuthenticator:
    """Validate a UI caller against its existing CloudStack login session."""

    def __init__(self, config: CloudStackSessionConfig, opener=None):
        parsed = urllib.parse.urlsplit(config.endpoint)
        allowed_scheme = parsed.scheme == "https" or (
            config.allow_insecure_http and parsed.scheme == "http"
        )
        if (
            not allowed_scheme
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.endswith("/client/api")
        ):
            raise InvalidRequestError("CloudStack session endpoint is not an approved API origin")
        if config.timeout_seconds < 1 or config.timeout_seconds > 60:
            raise InvalidRequestError("CloudStack session timeout must be between 1 and 60 seconds")
        if config.max_projects < 1 or config.max_projects > 10000:
            raise InvalidRequestError("CloudStack project inventory limit is invalid")
        normalized_origins = tuple(self._normalize_origin(value) for value in config.trusted_origins)
        if not normalized_origins or len(set(normalized_origins)) != len(normalized_origins):
            raise InvalidRequestError("trusted browser origins must be non-empty and unique")
        if not config.allow_insecure_http and any(value.startswith("http://") for value in normalized_origins):
            raise InvalidRequestError("HTTP browser origins require the explicit insecure development override")
        if parsed.scheme == "https":
            context = ssl.create_default_context(cafile=config.ca_file)
            handler = urllib.request.HTTPSHandler(context=context)
        else:
            handler = urllib.request.HTTPHandler()
        self.config = config
        self.trusted_origins = frozenset(normalized_origins)
        self.opener = opener or urllib.request.build_opener(handler, _NoRedirect())

    @staticmethod
    def _normalize_origin(value: str) -> str:
        parsed = urllib.parse.urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise InvalidRequestError("trusted browser origin is invalid")
        host = parsed.hostname.lower()
        default_port = (parsed.scheme == "https" and parsed.port == 443) or (
            parsed.scheme == "http" and parsed.port == 80
        )
        authority = host if parsed.port is None or default_port else f"{host}:{parsed.port}"
        return f"{parsed.scheme}://{authority}"

    @staticmethod
    def _cookies(environ: Mapping[str, Any]) -> tuple[str, str]:
        raw = str(environ.get("HTTP_COOKIE", ""))
        if "\r" in raw or "\n" in raw:
            raise AuthenticationError("CloudStack session cookies are invalid")
        cookie_names = [part.split("=", 1)[0].strip() for part in raw.split(";") if "=" in part]
        if cookie_names.count("JSESSIONID") != 1 or cookie_names.count("sessionkey") != 1:
            raise AuthenticationError("CloudStack session cookies are missing or ambiguous")
        jar = http.cookies.SimpleCookie()
        try:
            jar.load(raw)
        except http.cookies.CookieError as exc:
            raise AuthenticationError("CloudStack session cookies are invalid") from exc
        session_id = jar.get("JSESSIONID")
        cookie_key = jar.get("sessionkey")
        header_key = str(environ.get("HTTP_X_LAYERSENTRY_SESSION_KEY", ""))
        if session_id is None or cookie_key is None or not header_key:
            raise AuthenticationError("CloudStack session credentials are missing")
        if not _SESSION_ID.fullmatch(session_id.value) or not _SESSION_KEY.fullmatch(header_key):
            raise AuthenticationError("CloudStack session credentials are invalid")
        if not hmac.compare_digest(cookie_key.value, header_key):
            raise AuthenticationError("CloudStack session-key confirmation failed")
        return session_id.value, header_key

    def _check_origin(self, environ: Mapping[str, Any]) -> None:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        origin = str(environ.get("HTTP_ORIGIN", ""))
        if method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not origin:
                raise AuthenticationError("an approved browser Origin is required for mutations")
            try:
                normalized = self._normalize_origin(origin)
            except InvalidRequestError as exc:
                raise AuthenticationError("browser Origin is invalid") from exc
            if normalized not in self.trusted_origins:
                raise AuthenticationError("browser Origin is not approved")
        elif origin:
            try:
                normalized = self._normalize_origin(origin)
            except InvalidRequestError as exc:
                raise AuthenticationError("browser Origin is invalid") from exc
            if normalized not in self.trusted_origins:
                raise AuthenticationError("browser Origin is not approved")

    def _call(
        self, command: str, session_id: str, session_key: str, params: Mapping[str, Any] | None = None,
        *, timeout_seconds: float | None = None,
    ) -> Mapping[str, Any]:
        if command not in _READ_COMMANDS:
            raise InvalidRequestError("session authenticator command is not allowed")
        values = {
            "command": command,
            "response": "json",
            "sessionkey": session_key,
            **{str(key): str(value) for key, value in (params or {}).items()},
        }
        body = urllib.parse.urlencode(values).encode("ascii")
        request = urllib.request.Request(
            self.config.endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Cookie": f"JSESSIONID={session_id}; sessionkey={session_key}",
            },
        )
        try:
            with self.opener.open(request, timeout=self.config.timeout_seconds if timeout_seconds is None else timeout_seconds) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
        except (TimeoutError, urllib.error.HTTPError, urllib.error.URLError) as exc:
            raise AuthenticationError("CloudStack session validation failed") from exc
        if len(raw) > 4 * 1024 * 1024:
            raise AuthenticationError("CloudStack session response exceeds the safety limit")
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AuthenticationError("CloudStack session response is invalid") from exc
        if not isinstance(decoded, Mapping) or "errorresponse" in decoded:
            raise AuthenticationError("CloudStack rejected the current session")
        key = command.lower() + "response"
        result = decoded.get(key)
        if not isinstance(result, Mapping):
            raise AuthenticationError("CloudStack session response is incomplete")
        return result

    @staticmethod
    def _capabilities(response: Mapping[str, Any]) -> tuple[str, ...]:
        items = response.get("api", [])
        if not isinstance(items, list):
            raise AuthenticationError("CloudStack API permissions are invalid")
        names = []
        for item in items:
            if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
                raise AuthenticationError("CloudStack API permissions are invalid")
            names.append(item["name"])
        if len(names) != len(set(names)):
            raise AuthenticationError("CloudStack API permissions are ambiguous")
        return tuple(sorted(names))

    def _projects(self, session_id: str, session_key: str) -> tuple[str, ...]:
        response = self._call(
            "listProjects", session_id, session_key,
            {"listall": "true", "page": "1", "pagesize": str(self.config.max_projects)},
        )
        items = response.get("project", [])
        if not isinstance(items, list):
            raise AuthenticationError("CloudStack project scope is invalid")
        count = response.get("count", len(items))
        if not isinstance(count, int) or count > self.config.max_projects or count != len(items):
            raise AuthenticationError("CloudStack project scope is incomplete")
        project_ids = []
        for item in items:
            if (
                not isinstance(item, Mapping)
                or not isinstance(item.get("id"), str)
                or item.get("state") != "Active"
            ):
                continue
            project_ids.append(item["id"])
        if len(project_ids) != len(set(project_ids)):
            raise AuthenticationError("CloudStack project scope is ambiguous")
        return tuple(sorted(project_ids))

    def require_cluster_access(self, environ: Mapping[str, Any], actor: Actor, request) -> None:
        """Verify submitted resource IDs using the caller, before privileged reconciliation."""
        project_id = request.project_id
        if not project_id or project_id not in actor.project_ids:
            raise AuthorizationError("CloudStack project access is denied")
        if len(request.node_pools) > 32:
            raise InvalidRequestError("at most 32 node pools are allowed")
        session_id, session_key = self._cookies(environ)
        checks = [("listZones", "zone", request.zone_id, {}),
                  ("listNetworks", "network", request.network_id, {"projectid": project_id}),
                  ("listPublicIpAddresses", "publicipaddress", request.api_frontend_id, {"projectid": project_id})]
        offerings = [request.control_plane_service_offering_id, *(pool.service_offering_id for pool in request.node_pools)]
        images = [request.control_plane_image_id, *(pool.image_id for pool in request.node_pools)]
        if any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", value)
               for value in [*(item[2] for item in checks), *offerings, *images]):
            raise InvalidRequestError("managed Kubernetes resource ID is invalid")
        checks.extend(("listServiceOfferings", "serviceoffering", value, {"projectid": project_id}) for value in sorted(set(offerings)))
        checks.extend(("listTemplates", "template", value,
                       {"projectid": project_id, "zoneid": request.zone_id, "templatefilter": "executable"}) for value in sorted(set(images)))
        deadline = time.monotonic() + 30
        for command, collection, resource_id, params in checks:
            if not isinstance(resource_id, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", resource_id):
                raise InvalidRequestError("managed Kubernetes resource ID is invalid")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AuthorizationError("CloudStack resource scope verification timed out")
            response = self._call(command, session_id, session_key, {"id": resource_id, **params},
                                  timeout_seconds=min(remaining, self.config.timeout_seconds))
            rows = response.get(collection, [])
            if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], Mapping)
                    or rows[0].get("id") != resource_id or response.get("count", 1) != 1):
                raise AuthorizationError("selected CloudStack resource is unavailable in caller scope")

    def authenticate(self, environ: Mapping[str, Any]) -> Actor:
        self._check_origin(environ)
        session_id, session_key = self._cookies(environ)
        capabilities = self._capabilities(self._call("listApis", session_id, session_key))
        projects = self._projects(session_id, session_key)
        subject = "cloudstack-session:" + hashlib.sha256(session_id.encode("ascii")).hexdigest()
        # Account/domain headers and readable UI cookies are intentionally not
        # accepted. Managed Kubernetes is project-scoped, and project access is
        # established from the authenticated listProjects response above.
        return Actor(
            subject=subject,
            account_id="",
            domain_id="",
            project_ids=projects,
            roles=(),
            capabilities=capabilities,
        )


class CloudStackCapabilityAuthorizer:
    """Authorize composite actions using CloudStack's effective API grants."""

    def __init__(self, action_capabilities: Mapping[str, Sequence[str]] | None = None):
        self.action_capabilities = {
            key: tuple(value) for key, value in (action_capabilities or _ACTION_CAPABILITIES).items()
        }

    def require(self, actor: Actor, action: str, project_id: str) -> None:
        required = self.action_capabilities.get(action)
        if required is None:
            raise AuthorizationError("LayerSentry action is not authorized")
        if project_id != "*" and (not project_id or project_id not in actor.project_ids):
            raise AuthorizationError("CloudStack project access is denied")
        missing = sorted(set(required) - set(actor.capabilities))
        if missing:
            raise AuthorizationError("CloudStack permissions do not authorize this action")
