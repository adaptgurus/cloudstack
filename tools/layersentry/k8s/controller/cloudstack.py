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

"""Restricted, signed CloudStack 4.22.1.1 read-only preflight client."""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from .e1_resources import ResolvedInfrastructure
from .model import InvalidRequestError, NotFoundError


_READ_COMMANDS = {
    "listProjects", "listZones", "listNetworks", "listServiceOfferings",
    "listTemplates", "listPublicIpAddresses", "listLoadBalancerRules",
}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        del req, fp, code, msg, headers, newurl
        return None


@dataclass(frozen=True)
class CloudStackConfig:
    endpoint: str
    api_key_file: Path
    secret_key_file: Path
    ca_file: Path | None = None
    timeout_seconds: int = 30
    allow_insecure_http: bool = False


@dataclass(frozen=True)
class ClusterProfile:
    namespace: str
    endpoint_host: str
    endpoint_public_ip_id: str
    cloudstack_secret_name: str
    cloudstack_secret_namespace: str


class CloudStackClient:
    def __init__(self, config: CloudStackConfig, clock: Callable[[], datetime] | None = None):
        parsed = urllib.parse.urlsplit(config.endpoint)
        allowed_scheme = parsed.scheme == "https" or (config.allow_insecure_http and parsed.scheme == "http")
        if not allowed_scheme or not parsed.hostname or parsed.username or parsed.password:
            raise InvalidRequestError("CloudStack API endpoint is not an approved HTTP(S) origin")
        if parsed.query or parsed.fragment or not parsed.path.endswith("/client/api"):
            raise InvalidRequestError("CloudStack API endpoint must end in /client/api without query or fragment")
        for path in (config.api_key_file, config.secret_key_file):
            if not path.is_file() or path.stat().st_mode & 0o077:
                raise InvalidRequestError("CloudStack credential files must exist with mode 0600 or stricter")
        if parsed.scheme == "https":
            context = ssl.create_default_context(cafile=str(config.ca_file) if config.ca_file else None)
            handler = urllib.request.HTTPSHandler(context=context)
        else:
            handler = urllib.request.HTTPHandler()
        self.opener = urllib.request.build_opener(handler, _NoRedirect())
        self.config = config
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _credential(path: Path) -> str:
        value = path.read_text(encoding="utf-8").strip()
        if not value or len(value) > 4096 or any(ch.isspace() for ch in value):
            raise InvalidRequestError("CloudStack credential file is invalid")
        return value

    def _signed_query(self, command: str, params: Mapping[str, Any]) -> str:
        if command not in _READ_COMMANDS:
            raise InvalidRequestError("CloudStack command is not allowed by the preflight client")
        expires = (self.clock().astimezone(timezone.utc) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        values = {
            "apikey": self._credential(self.config.api_key_file),
            "command": command,
            "expires": expires,
            "response": "json",
            "signatureversion": "3",
            **{str(key): str(value).lower() if isinstance(value, bool) else str(value) for key, value in params.items()},
        }
        unsigned = "&".join(
            f"{key}={urllib.parse.quote(values[key], safe='')}" for key in sorted(values)
        ).lower()
        signature = base64.b64encode(hmac.new(
            self._credential(self.config.secret_key_file).encode("utf-8"),
            unsigned.encode("utf-8"), hashlib.sha1,
        ).digest()).decode("ascii")
        return urllib.parse.urlencode({**values, "signature": signature}, quote_via=urllib.parse.quote)

    def call(self, command: str, params: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        query = self._signed_query(command, params or {})
        request = urllib.request.Request(
            self.config.endpoint, data=query.encode("ascii"), method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        try:
            with self.opener.open(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
        except (TimeoutError, urllib.error.URLError) as exc:
            raise InvalidRequestError("CloudStack API preflight is unavailable") from exc
        if len(raw) > 4 * 1024 * 1024:
            raise InvalidRequestError("CloudStack API response exceeds safety limit")
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidRequestError("CloudStack API returned invalid JSON") from exc
        if "errorresponse" in decoded:
            error = decoded["errorresponse"]
            code = error.get("errorcode", "unknown") if isinstance(error, Mapping) else "unknown"
            raise InvalidRequestError(f"CloudStack API rejected {command} with code {code}")
        key = command.lower() + "response"
        result = decoded.get(key)
        if not isinstance(result, Mapping):
            raise InvalidRequestError(f"CloudStack API omitted {key}")
        return result


class CloudStackResolver:
    def __init__(self, client: CloudStackClient, profile: ClusterProfile):
        self.client = client
        self.profile = profile

    def _exact(self, command: str, collection: str, resource_id: str, **params) -> Mapping[str, Any]:
        response = self.client.call(command, {"id": resource_id, **params})
        items = response.get(collection, [])
        if not isinstance(items, list) or len(items) != 1 or items[0].get("id") != resource_id:
            raise NotFoundError(f"CloudStack {collection} resource is unavailable in caller scope")
        return items[0]

    def resolve_cluster(self, request: Mapping[str, Any]) -> ResolvedInfrastructure:
        project_id = request.get("project_id")
        if not project_id:
            raise InvalidRequestError("CloudStack project_id is required for managed Kubernetes")
        project = self._exact("listProjects", "project", project_id)
        if project.get("state") != "Active":
            raise InvalidRequestError("CloudStack project is not Active")
        zone = self._exact("listZones", "zone", request["zone_id"])
        if zone.get("allocationstate") != "Enabled":
            raise InvalidRequestError("CloudStack Site allocation is not Enabled")
        network = self._exact(
            "listNetworks", "network", request["network_id"], projectid=project_id,
        )
        if network.get("zoneid") != zone["id"] or network.get("state") != "Implemented":
            raise InvalidRequestError("CloudStack network is not Implemented in the selected Site")

        offering_ids = {request["control_plane_service_offering_id"]}
        offering_ids.update(pool["service_offering_id"] for pool in request["node_pools"])
        for offering_id in offering_ids:
            offering = self._exact("listServiceOfferings", "serviceoffering", offering_id)
            if offering.get("issystem") is True:
                raise InvalidRequestError("system service offering cannot be used for Kubernetes nodes")

        template_ids = {request["control_plane_image_id"]}
        template_ids.update(pool["image_id"] for pool in request["node_pools"])
        for template_id in template_ids:
            template = self._exact(
                "listTemplates", "template", template_id,
                templatefilter="executable", zoneid=zone["id"],
            )
            if template.get("isready") is not True or template.get("hypervisor") != "KVM":
                raise InvalidRequestError("Kubernetes node image is not Ready for KVM")

        endpoint = self._exact(
            "listPublicIpAddresses", "publicipaddress", self.profile.endpoint_public_ip_id,
            projectid=project_id,
        )
        try:
            host_ip = str(ipaddress.ip_address(self.profile.endpoint_host))
        except ValueError:
            host_ip = None
        if host_ip and endpoint.get("ipaddress") != host_ip:
            raise InvalidRequestError("endpoint host does not match the reserved CloudStack public IP")

        return ResolvedInfrastructure(
            namespace=self.profile.namespace, endpoint_host=self.profile.endpoint_host,
            endpoint_public_ip_id=self.profile.endpoint_public_ip_id,
            cloudstack_secret_name=self.profile.cloudstack_secret_name,
            cloudstack_secret_namespace=self.profile.cloudstack_secret_namespace,
            project_id=project_id, project_name=project.get("name", ""),
            zone_id=zone["id"], zone_name=zone.get("name", ""),
            network_id=network["id"], network_name=network.get("name", ""),
            control_plane_offering_id=request["control_plane_service_offering_id"],
            control_plane_template_id=request["control_plane_image_id"],
            worker_offering_ids={pool["name"]: pool["service_offering_id"] for pool in request["node_pools"]},
            worker_template_ids={pool["name"]: pool["image_id"] for pool in request["node_pools"]},
        )

    def verify_endpoints(self, resolved: ResolvedInfrastructure) -> Mapping[str, Any]:
        response = self.client.call("listLoadBalancerRules", {
            "publicipid": resolved.endpoint_public_ip_id, "projectid": resolved.project_id,
        })
        rules = response.get("loadbalancerrule", [])
        if not isinstance(rules, list):
            raise InvalidRequestError("CloudStack load-balancer rule inventory is invalid")
        by_port: dict[str, list[Mapping[str, Any]]] = {"6443": [], "9345": []}
        for rule in rules:
            port = str(rule.get("publicport", ""))
            if port in by_port and rule.get("networkid") == resolved.network_id:
                by_port[port].append(rule)
        if any(len(by_port[port]) > 1 for port in by_port):
            raise InvalidRequestError("CloudStack endpoint rule inventory is ambiguous")
        rule_6443 = by_port["6443"][0] if by_port["6443"] else None
        rule_9345 = by_port["9345"][0] if by_port["9345"] else None
        return {
            "endpoint6443": bool(rule_6443 and rule_6443.get("state") == "Active"),
            "endpoint9345": bool(rule_9345 and rule_9345.get("state") == "Active"),
            "publicIpId": resolved.endpoint_public_ip_id,
            "endpoint6443RuleId": rule_6443.get("id") if rule_6443 else None,
            "endpoint9345RuleId": rule_9345.get("id") if rule_9345 else None,
        }
