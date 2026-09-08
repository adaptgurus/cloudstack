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
import http.client
import ipaddress
import json
import os
import re
import stat
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
    "listCapacity", "listClusters", "listHosts", "listStoragePools",
    "listSystemVms", "listVirtualMachines",
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
    namespace_prefix: str
    cloudstack_secret_name: str
    cloudstack_secret_namespace: str


class CloudStackClient:
    def __init__(self, config: CloudStackConfig, clock: Callable[[], datetime] | None = None):
        if not isinstance(config.endpoint, str) or type(config.allow_insecure_http) is not bool or type(config.timeout_seconds) is not int or not 1 <= config.timeout_seconds <= 120:
            raise InvalidRequestError("CloudStack transport bounds are invalid")
        try:
            parsed = urllib.parse.urlsplit(config.endpoint)
            parsed.port
        except (ValueError, TypeError):
            raise InvalidRequestError("CloudStack API endpoint is invalid") from None
        allowed_scheme = parsed.scheme == "https" or (config.allow_insecure_http and parsed.scheme == "http")
        if not allowed_scheme or not parsed.hostname or parsed.username or parsed.password:
            raise InvalidRequestError("CloudStack API endpoint is not an approved HTTP(S) origin")
        if parsed.query or parsed.fragment or not parsed.path.endswith("/client/api"):
            raise InvalidRequestError("CloudStack API endpoint must end in /client/api without query or fragment")
        for path in (config.api_key_file, config.secret_key_file):
            self._credential(path)
        if parsed.scheme == "https":
            try:
                context = ssl.create_default_context(cafile=str(config.ca_file) if config.ca_file else None)
            except (OSError, ValueError):
                raise InvalidRequestError("CloudStack CA configuration is invalid") from None
            handler = urllib.request.HTTPSHandler(context=context)
        else:
            handler = urllib.request.HTTPHandler()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), handler, _NoRedirect())
        self.config = config
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _credential(path: Path) -> str:
        # Open once, reject symlinks and recheck mode on every signed request,
        # including after credential rotation. Bound reads before decoding.
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                metadata = os.fstat(stream.fileno())
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
                    raise InvalidRequestError("CloudStack credential files must exist with mode 0600 or stricter")
                raw = stream.read(4097)
            value = raw.decode("utf-8").strip()
        except (OSError, UnicodeError):
            raise InvalidRequestError("CloudStack credential file is unavailable or invalid") from None
        if not value or len(raw) > 4096 or any(ch.isspace() for ch in value):
            raise InvalidRequestError("CloudStack credential file is invalid")
        return value

    def _signed_query(self, command: str, params: Mapping[str, Any]) -> str:
        if command not in _READ_COMMANDS:
            raise InvalidRequestError("CloudStack command is not allowed by the preflight client")
        reserved = {"command", "apikey", "secretkey", "signature", "signatureversion", "expires", "response", "sessionkey"}
        if any(not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9]*", key)
               or key.lower() in reserved for key in params):
            raise InvalidRequestError("CloudStack API parameters contain reserved or invalid keys")
        if any(not isinstance(value, (str, int, bool)) for value in params.values()):
            raise InvalidRequestError("CloudStack API parameter values are invalid")
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
        except (OSError, urllib.error.URLError, http.client.HTTPException):
            raise InvalidRequestError("CloudStack API preflight is unavailable") from None
        if len(raw) > 4 * 1024 * 1024:
            raise InvalidRequestError("CloudStack API response exceeds safety limit")
        try:
            decoded = json.loads(raw, object_pairs_hook=_unique_json_object)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
            raise InvalidRequestError("CloudStack API returned invalid JSON") from None
        if not isinstance(decoded, Mapping):
            raise InvalidRequestError("CloudStack API returned an invalid JSON envelope")
        if "errorresponse" in decoded:
            error = decoded["errorresponse"]
            _reject_error(command, error)
        key = command.lower() + "response"
        result = decoded.get(key)
        if not isinstance(result, Mapping):
            raise InvalidRequestError(f"CloudStack API omitted {key}")
        if "errorcode" in result or "errortext" in result:
            _reject_error(command, result)
        return result

    def list_all(self, command: str, collection: str, params: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        return _list_all(self, command, collection, params)


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidRequestError("CloudStack API returned duplicate JSON keys")
        result[key] = value
    return result


def _reject_error(command, error):
    code = error.get("errorcode") if isinstance(error, Mapping) else None
    code = code if type(code) is int and 100 <= code <= 9999 else "unknown"
    raise InvalidRequestError(f"CloudStack API rejected {command} with code {code}")


def _list_all(client, command, collection, params):
    """Bounded pagination, including APIs that omit count on empty results."""
    result, seen = [], set()
    expected = None
    for page in range(1, 101):
        response = client.call(command, {**params, "page": page, "pagesize": 100})
        rows = response.get(collection, [])
        count = response.get("count")
        if (not isinstance(rows, list) or any(not isinstance(row, Mapping) for row in rows)
                or (count is not None and (type(count) is not int or count < 0))):
            raise InvalidRequestError("CloudStack inventory is malformed")
        if expected is not None and count != expected:
            raise InvalidRequestError("CloudStack inventory changed during pagination; retry read")
        expected = count
        for row in rows:
            identity = json.dumps(row, sort_keys=True)
            # IDs detect an inventory changing between pages as well as repeated pages.
            identity = row.get("id", identity)
            if not isinstance(identity, str) or identity in seen:
                raise InvalidRequestError("CloudStack inventory is ambiguous")
            seen.add(identity)
            result.append(row)
        if count is not None and len(result) > count:
            raise InvalidRequestError("CloudStack inventory count is inconsistent")
        if count is not None and len(result) == count:
            return result
        if not rows:
            if count is not None:
                raise InvalidRequestError("CloudStack inventory is incomplete")
            return result
        # Without a count, read until an empty page (server page limits may be smaller).
    raise InvalidRequestError("CloudStack inventory exceeds pagination safety limit")


class CloudStackResolver:
    def __init__(self, client: CloudStackClient, profile: ClusterProfile):
        self.client = client
        self.profile = profile

    def _exact(self, command: str, collection: str, resource_id: str, **params) -> Mapping[str, Any]:
        response = self.client.call(command, {"id": resource_id, **params})
        items = response.get(collection, [])
        if not isinstance(items, list) or len(items) != 1 or not isinstance(items[0], Mapping) or items[0].get("id") != resource_id:
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
        if network.get("projectid") != project_id or network.get("zoneid") != zone["id"] or network.get("state") != "Implemented":
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
                templatefilter="executable", zoneid=zone["id"], projectid=project_id,
            )
            if (template.get("isready") is not True or template.get("hypervisor") != "KVM"
                    or template.get("zoneid") != zone["id"]):
                raise InvalidRequestError("Kubernetes node image is not Ready for KVM")

        endpoint_public_ip_id = request.get("api_frontend_id")
        if not endpoint_public_ip_id:
            raise InvalidRequestError("api_frontend_id is required for managed Kubernetes")
        endpoint = self._exact(
            "listPublicIpAddresses", "publicipaddress", endpoint_public_ip_id,
            projectid=project_id,
        )
        if (
            endpoint.get("projectid") != project_id
            or endpoint.get("zoneid") != zone["id"]
            or endpoint.get("associatednetworkid") != network["id"]
            or endpoint.get("state") != "Allocated"
        ):
            raise InvalidRequestError("Kubernetes frontend IP is not Allocated in the selected project/Site")
        try:
            endpoint_host = str(ipaddress.ip_address(endpoint.get("ipaddress", "")))
        except ValueError as exc:
            raise InvalidRequestError("reserved CloudStack public IP is invalid") from exc

        prefix = self.profile.namespace_prefix
        if (
            not prefix
            or len(prefix) > 40
            or not prefix[0].isalnum()
            or not prefix[-1].isalnum()
            or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in prefix)
        ):
            raise InvalidRequestError("management namespace prefix is invalid")
        project_suffix = hashlib.sha256(project_id.encode("utf-8")).hexdigest()[:12]
        return ResolvedInfrastructure(
            namespace=f"{prefix}-{project_suffix}", endpoint_host=endpoint_host,
            endpoint_public_ip_id=endpoint_public_ip_id,
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
        endpoint = self._exact("listPublicIpAddresses", "publicipaddress",
                               resolved.endpoint_public_ip_id, projectid=resolved.project_id)
        if (endpoint.get("projectid") != resolved.project_id
                or endpoint.get("zoneid") != resolved.zone_id
                or endpoint.get("associatednetworkid") != resolved.network_id
                or endpoint.get("ipaddress") != resolved.endpoint_host
                or endpoint.get("state") != "Allocated"):
            raise InvalidRequestError("CloudStack frontend scope or allocation changed")
        rules = _list_all(self.client, "listLoadBalancerRules", "loadbalancerrule", {
            "publicipid": resolved.endpoint_public_ip_id, "projectid": resolved.project_id,
        })
        by_port: dict[str, list[Mapping[str, Any]]] = {"6443": [], "9345": []}
        for rule in rules:
            port = str(rule.get("publicport", ""))
            if (rule.get("projectid") != resolved.project_id
                    or rule.get("publicipid") != resolved.endpoint_public_ip_id
                    or rule.get("networkid") != resolved.network_id):
                raise InvalidRequestError("CloudStack endpoint rule scope is invalid")
            if port in by_port:
                by_port[port].append(rule)
        if any(len(by_port[port]) > 1 for port in by_port):
            raise InvalidRequestError("CloudStack endpoint rule inventory is ambiguous")
        rule_6443 = by_port["6443"][0] if by_port["6443"] else None
        rule_9345 = by_port["9345"][0] if by_port["9345"] else None
        return {
            "endpoint6443": bool(rule_6443 and _endpoint_active(rule_6443, "6443")),
            "endpoint9345": bool(rule_9345 and _endpoint_active(rule_9345, "9345")),
            "publicIpId": resolved.endpoint_public_ip_id,
            "endpoint6443RuleId": rule_6443.get("id") if rule_6443 else None,
            "endpoint9345RuleId": rule_9345.get("id") if rule_9345 else None,
        }

    def observe_vm(self, vm_id: str, resolved: ResolvedInfrastructure) -> Mapping[str, Any]:
        """Observe an exact CAPC-provided VM ID; never discover ownership by name."""
        rows = _list_all(self.client, "listVirtualMachines", "virtualmachine", {
            "id": vm_id, "projectid": resolved.project_id,
        })
        if not rows:
            return {"id": vm_id, "state": "ABSENT"}
        if len(rows) != 1 or rows[0].get("id") != vm_id:
            raise InvalidRequestError("CloudStack VM inventory is ambiguous")
        vm = rows[0]
        if vm.get("projectid") != resolved.project_id or vm.get("zoneid") != resolved.zone_id:
            raise InvalidRequestError("CloudStack VM scope is invalid")
        state = vm.get("state")
        if state not in {"Starting", "Running", "Stopping", "Stopped", "Destroyed", "Expunging", "Error", "Migrating", "Shutdowned"}:
            raise InvalidRequestError("CloudStack VM state is unknown")
        # Do not return native VM user-data, credentials or unrelated inventory.
        return {"id": vm_id, "state": state}


def _endpoint_active(rule, port):
    return bool(rule.get("id") and rule.get("state") == "Active"
                and str(rule.get("privateport")) == port
                and str(rule.get("protocol", "")).lower() == "tcp")
