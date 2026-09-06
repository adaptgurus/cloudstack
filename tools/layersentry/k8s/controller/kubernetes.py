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

"""Restricted Kubernetes REST client for exact Workstream E API kinds."""

from __future__ import annotations

import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .model import AmbiguousMutationError, ConflictError, InvalidRequestError, NotFoundError


_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_KINDS = {
    ("v1", "Namespace"): ("api", "", "v1", "namespaces", False),
    ("cluster.x-k8s.io/v1beta2", "Cluster"): ("apis", "cluster.x-k8s.io", "v1beta2", "clusters", True),
    ("cluster.x-k8s.io/v1beta2", "MachineDeployment"): ("apis", "cluster.x-k8s.io", "v1beta2", "machinedeployments", True),
    ("infrastructure.cluster.x-k8s.io/v1beta3", "CloudStackCluster"): (
        "apis", "infrastructure.cluster.x-k8s.io", "v1beta3", "cloudstackclusters", True,
    ),
    ("infrastructure.cluster.x-k8s.io/v1beta3", "CloudStackMachineTemplate"): (
        "apis", "infrastructure.cluster.x-k8s.io", "v1beta3", "cloudstackmachinetemplates", True,
    ),
    ("controlplane.cluster.x-k8s.io/v1beta2", "RKE2ControlPlane"): (
        "apis", "controlplane.cluster.x-k8s.io", "v1beta2", "rke2controlplanes", True,
    ),
    ("bootstrap.cluster.x-k8s.io/v1beta2", "RKE2ConfigTemplate"): (
        "apis", "bootstrap.cluster.x-k8s.io", "v1beta2", "rke2configtemplates", True,
    ),
    ("source.toolkit.fluxcd.io/v1", "GitRepository"): (
        "apis", "source.toolkit.fluxcd.io", "v1", "gitrepositories", True,
    ),
    ("kustomize.toolkit.fluxcd.io/v1", "Kustomization"): (
        "apis", "kustomize.toolkit.fluxcd.io", "v1", "kustomizations", True,
    ),
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


@dataclass(frozen=True)
class KubernetesConfig:
    server: str
    ca_file: Path
    token_file: Path
    timeout_seconds: int = 30
    field_manager: str = "layersentry-controller"


class KubernetesClient:
    def __init__(self, config: KubernetesConfig):
        parsed = urllib.parse.urlsplit(config.server)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise InvalidRequestError("Kubernetes API server must be an HTTPS origin without userinfo")
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise InvalidRequestError("Kubernetes API server must not include a path, query or fragment")
        if not config.ca_file.is_file() or not config.token_file.is_file():
            raise InvalidRequestError("Kubernetes CA or token file is missing")
        if config.token_file.stat().st_mode & 0o077:
            raise InvalidRequestError("Kubernetes token file must have mode 0600 or stricter")
        self.config = config
        self.origin = config.server.rstrip("/")
        context = ssl.create_default_context(cafile=str(config.ca_file))
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context), _NoRedirect(),
        )

    def _token(self) -> str:
        token = self.config.token_file.read_text(encoding="utf-8").strip()
        if not token or len(token) > 16384 or any(ch.isspace() for ch in token):
            raise InvalidRequestError("Kubernetes service-account token is invalid")
        return token

    @staticmethod
    def _resource_path(resource: Mapping[str, Any]) -> tuple[str, str]:
        identity = (resource.get("apiVersion"), resource.get("kind"))
        route = _KINDS.get(identity)
        if route is None:
            raise InvalidRequestError(f"unsupported Kubernetes resource kind: {identity}")
        prefix, group, version, plural, namespaced = route
        metadata = resource.get("metadata")
        if not isinstance(metadata, Mapping):
            raise InvalidRequestError("Kubernetes resource metadata is missing")
        name = metadata.get("name")
        namespace = metadata.get("namespace")
        if not isinstance(name, str) or not _DNS_LABEL.fullmatch(name):
            raise InvalidRequestError("Kubernetes resource name is invalid")
        base = f"/{prefix}/" + (f"{group}/" if group else "") + version
        if namespaced:
            if not isinstance(namespace, str) or not _DNS_LABEL.fullmatch(namespace):
                raise InvalidRequestError("Kubernetes resource namespace is invalid")
            base += f"/namespaces/{namespace}"
        return f"{base}/{plural}/{name}", name

    def request(
        self, method: str, path: str, *, body: Mapping[str, Any] | None = None,
        content_type: str = "application/json",
    ) -> Mapping[str, Any]:
        if not path.startswith("/") or ".." in path:
            raise InvalidRequestError("invalid Kubernetes API path")
        encoded = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.origin + path, data=encoded, method=method,
            headers={
                "Authorization": "Bearer " + self._token(),
                "Accept": "application/json",
                "Content-Type": content_type,
            },
        )
        try:
            with self.opener.open(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise InvalidRequestError("Kubernetes response exceeds safety limit")
                return {} if not raw else json.loads(raw)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFoundError("Kubernetes resource not found") from exc
            if exc.code == 409:
                raise ConflictError("Kubernetes resource conflict") from exc
            raise InvalidRequestError(f"Kubernetes API rejected request with HTTP {exc.code}") from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            if method in {"POST", "PUT", "PATCH", "DELETE"}:
                raise AmbiguousMutationError("Kubernetes mutation outcome is unknown") from exc
            raise InvalidRequestError("Kubernetes API is unavailable") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidRequestError("Kubernetes API returned invalid JSON") from exc

    def apply(self, resource: Mapping[str, Any]) -> Mapping[str, Any]:
        path, _ = self._resource_path(resource)
        query = urllib.parse.urlencode({"fieldManager": self.config.field_manager, "force": "false"})
        return self.request(
            "PATCH", path + "?" + query, body=resource,
            content_type="application/apply-patch+yaml",
        )

    def get(self, resource: Mapping[str, Any]) -> Mapping[str, Any]:
        path, _ = self._resource_path(resource)
        return self.request("GET", path)

    def patch_merge(self, resource: Mapping[str, Any], patch: Mapping[str, Any]) -> Mapping[str, Any]:
        path, _ = self._resource_path(resource)
        return self.request("PATCH", path, body=patch, content_type="application/merge-patch+json")

    def delete(self, resource: Mapping[str, Any]) -> Mapping[str, Any]:
        path, _ = self._resource_path(resource)
        return self.request("DELETE", path, body={"apiVersion": "v1", "kind": "DeleteOptions"})
