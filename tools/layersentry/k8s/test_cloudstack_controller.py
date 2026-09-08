#!/usr/bin/env python3
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

import json
import base64
import hashlib
import hmac
import ssl
import urllib.error
from dataclasses import replace
from unittest.mock import patch
import os
import tempfile
import unittest
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from controller.cloudstack import (
    CloudStackClient,
    CloudStackConfig,
    CloudStackResolver,
    ClusterProfile,
)
from controller.model import InvalidRequestError


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        del limit
        return self.payload


class RecordingOpener:
    def __init__(self, payload):
        self.payload = payload
        self.request = None

    def open(self, request, timeout):
        del timeout
        self.request = request
        return FakeResponse(self.payload)


class InventoryClient:
    def __init__(self, rules=None):
        self.rules = rules if rules is not None else [
            {"id": "lb-6443", "publicport": "6443", "networkid": "network-1", "state": "Active"},
            {"id": "lb-9345", "publicport": "9345", "networkid": "network-1", "state": "Active"},
        ]

        self.rules = [{"projectid": "project-1", "publicipid": "public-ip-1", "protocol": "tcp",
                       "privateport": rule["publicport"], **rule} for rule in self.rules]

    def call(self, command, params):
        resource_id = params.get("id")
        if command == "listProjects":
            return {"project": [{"id": resource_id, "name": "project-one", "state": "Active"}]}
        if command == "listZones":
            return {"zone": [{"id": resource_id, "name": "site-one", "allocationstate": "Enabled"}]}
        if command == "listNetworks":
            return {"network": [{
                "id": resource_id, "name": "network-one", "zoneid": "zone-1", "state": "Implemented", "projectid": params.get("projectid"),
            }]}
        if command == "listServiceOfferings":
            return {"serviceoffering": [{"id": resource_id, "name": "compute", "issystem": False}]}
        if command == "listTemplates":
            return {"template": [{"id": resource_id, "name": "rke2", "isready": True, "hypervisor": "KVM", "zoneid": "zone-1"}]}
        if command == "listPublicIpAddresses":
            return {"publicipaddress": [{
                "id": resource_id, "ipaddress": "192.0.2.10", "projectid": params.get("projectid"),
                "zoneid": "zone-1", "state": "Allocated", "associatednetworkid": "network-1",
            }]}
        if command == "listLoadBalancerRules":
            return {"loadbalancerrule": self.rules, "count": len(self.rules)}
        raise AssertionError(command)


def request():
    return {
        "name": "cluster-a", "project_id": "project-1", "zone_id": "zone-1", "network_id": "network-1",
        "api_frontend_id": "public-ip-1",
        "control_plane_service_offering_id": "cp-offering", "control_plane_image_id": "image-1",
        "node_pools": [{"name": "workers", "service_offering_id": "worker-offering", "image_id": "image-1"}],
    }


def profile():
    return ClusterProfile(
        namespace_prefix="lsk8s",
        cloudstack_secret_name="capc-credentials", cloudstack_secret_namespace="capc-system",
    )


class CloudStackControllerTest(unittest.TestCase):
    def credential_config(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        api = root / "api"
        secret = root / "secret"
        api.write_text("api-key", encoding="utf-8")
        secret.write_text("secret-key", encoding="utf-8")
        os.chmod(api, 0o600)
        os.chmod(secret, 0o600)
        return CloudStackConfig("https://cloud.example/client/api", api, secret)

    def test_signature_v3_is_posted_without_credentials_in_url(self):
        config = self.credential_config()
        client = CloudStackClient.__new__(CloudStackClient)
        client.config = config
        client.clock = lambda: datetime(2026, 9, 6, tzinfo=timezone.utc)
        client.opener = RecordingOpener({"listzonesresponse": {"count": 0, "zone": []}})
        result = client.call("listZones", {"id": "zone-1"})
        self.assertEqual(result["count"], 0)
        self.assertEqual(client.opener.request.full_url, config.endpoint)
        self.assertNotIn("api-key", client.opener.request.full_url)
        posted = urllib.parse.parse_qs(client.opener.request.data.decode())
        self.assertEqual(posted["signatureversion"], ["3"])
        self.assertEqual(posted["expires"], ["2026-09-06T00:05:00Z"])
        self.assertTrue(posted["signature"][0])

    def test_resolver_requires_exact_healthy_cloudstack_resources(self):
        resolver = CloudStackResolver(InventoryClient(), profile())
        resolved = resolver.resolve_cluster(request())
        self.assertEqual(resolved.project_id, "project-1")
        self.assertEqual(resolved.namespace, "lsk8s-a33e35d30212")
        self.assertEqual(resolved.endpoint_public_ip_id, "public-ip-1")
        endpoints = resolver.verify_endpoints(resolved)
        self.assertTrue(endpoints["endpoint6443"])
        self.assertTrue(endpoints["endpoint9345"])

    def test_endpoint_ambiguity_and_unhealthy_image_fail_closed(self):
        rules = [
            {"id": "a", "publicport": "9345", "networkid": "network-1", "state": "Active"},
            {"id": "b", "publicport": "9345", "networkid": "network-1", "state": "Active"},
        ]
        resolver = CloudStackResolver(InventoryClient(rules), profile())
        resolved = resolver.resolve_cluster(request())
        with self.assertRaisesRegex(InvalidRequestError, "ambiguous"):
            resolver.verify_endpoints(resolved)

        class BadImage(InventoryClient):
            def call(self, command, params):
                result = super().call(command, params)
                if command == "listTemplates":
                    result["template"][0]["isready"] = False
                return result

        with self.assertRaisesRegex(InvalidRequestError, "not Ready"):
            CloudStackResolver(BadImage(), profile()).resolve_cluster(request())

        class ForeignFrontend(InventoryClient):
            def call(self, command, params):
                result = super().call(command, params)
                if command == "listPublicIpAddresses":
                    result["publicipaddress"][0]["projectid"] = "foreign"
                return result

        with self.assertRaisesRegex(InvalidRequestError, "project/Site"):
            CloudStackResolver(ForeignFrontend(), profile()).resolve_cluster(request())

    def test_project_namespace_is_stable_isolated_and_prefix_validated(self):
        resolver = CloudStackResolver(InventoryClient(), profile())
        first = resolver.resolve_cluster(request())
        second = resolver.resolve_cluster(request())
        other_request = request()
        other_request["project_id"] = "project-2"
        other = resolver.resolve_cluster(other_request)
        self.assertEqual(first.namespace, second.namespace)
        self.assertNotEqual(first.namespace, other.namespace)

        bad = ClusterProfile(
            namespace_prefix="INVALID", cloudstack_secret_name="capc-credentials",
            cloudstack_secret_namespace="capc-system",
        )
        with self.assertRaisesRegex(InvalidRequestError, "namespace prefix"):
            CloudStackResolver(InventoryClient(), bad).resolve_cluster(request())

    def test_reserved_params_cannot_override_read_only_command(self):
        client = CloudStackClient(self.credential_config())
        for params in ({"command": "deployVirtualMachine"}, {"Command": "deployVirtualMachine"},
                       {"apikey": "stolen"}, {"signatureversion": "1"}, {"expires": "never"},
                       {"response": "xml"}, {"id": {"nested": "object"}}):
            with self.subTest(params=params), self.assertRaises(InvalidRequestError):
                client._signed_query("listZones", params)
        for command in ("deployVirtualMachine", "destroyVirtualMachine", "createKubernetesCluster"):
            with self.assertRaises(InvalidRequestError):
                client._signed_query(command, {})

    def test_disk_offering_discovery_is_read_only(self):
        from controller.cloudstack import _READ_COMMANDS
        self.assertEqual(_READ_COMMANDS, {
            "listApis", "listProjects", "listZones", "listNetworks", "listServiceOfferings",
            "listTemplates", "listPublicIpAddresses", "listLoadBalancerRules",
            "listCapacity", "listClusters", "listHosts", "listStoragePools",
            "listSystemVms", "listVirtualMachines", "listDiskOfferings", "listVolumes",
        })
        client = CloudStackClient(self.credential_config())
        query = urllib.parse.parse_qs(client._signed_query(
            "listDiskOfferings", {"id": "synthetic-linked-disk", "state": "all"}))
        self.assertEqual(query["command"], ["listDiskOfferings"])
        self.assertEqual(query["state"], ["all"])
        for command in ("createDiskOffering", "updateDiskOffering", "deleteDiskOffering",
                        "createServiceOffering", "deployVirtualMachine"):
            with self.subTest(command=command), self.assertRaises(InvalidRequestError):
                client._signed_query(command, {})

    def test_hmac_signature_matches_cloudstack_canonical_form(self):
        client = CloudStackClient(self.credential_config(), lambda: datetime(2026, 9, 6, tzinfo=timezone.utc))
        actual = urllib.parse.parse_qs(client._signed_query("listZones", {"id": "A B+"}))
        signature = actual.pop("signature")[0]
        canonical = "&".join(f"{key}={urllib.parse.quote(actual[key][0], safe='')}" for key in sorted(actual)).lower()
        expected = base64.b64encode(hmac.new(b"secret-key", canonical.encode(), hashlib.sha1).digest()).decode()
        self.assertEqual(signature, expected)

    def test_tls_http_timeout_and_redirect_policy(self):
        config = self.credential_config()
        for config_bad in (replace(config, endpoint="http://cloud.example/client/api"),
                           replace(config, timeout_seconds=0), replace(config, timeout_seconds=True),
                           replace(config, endpoint="https://cloud.example:invalid/client/api")):
            with self.assertRaises(InvalidRequestError):
                CloudStackClient(config_bad)
        CloudStackClient(replace(config, endpoint="http://cloud.example/client/api", allow_insecure_http=True))
        client = CloudStackClient(config)
        handler = next(item for item in client.opener.handlers if isinstance(item, __import__('urllib.request').request.HTTPSHandler))
        self.assertEqual(handler._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(handler._context.check_hostname)
        from controller.cloudstack import _NoRedirect
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, None, None, "https://evil.example"))
        with patch("controller.cloudstack.ssl.create_default_context", wraps=ssl.create_default_context) as create:
            CloudStackClient(config)
            create.assert_called_once_with(cafile=None)

    def test_credential_rotation_rechecks_mode_and_rejects_symlink(self):
        config = self.credential_config()
        client = CloudStackClient(config)
        config.secret_key_file.chmod(0o644)
        with self.assertRaisesRegex(InvalidRequestError, "0600"):
            client._signed_query("listZones", {})
        config.secret_key_file.chmod(0o600)
        config.api_key_file.unlink()
        config.api_key_file.symlink_to(config.secret_key_file)
        with self.assertRaises(InvalidRequestError):
            client._signed_query("listZones", {})

    def test_transport_failures_are_bounded_and_sanitized(self):
        client = CloudStackClient(self.credential_config())
        for raw in (b"[]", b"null", b"{", b"x" * (4 * 1024 * 1024 + 1),
                    b'{"listzonesresponse":{},"listzonesresponse":{}}',
                    b'{"errorresponse":{"errorcode":"secret-key","errortext":"api-key"}}',
                    b'{"listzonesresponse":{"errorcode":401,"errortext":"secret-key"}}'):
            with self.subTest(raw=raw[:40]):
                response = FakeResponse({})
                response.payload = raw
                with patch.object(client.opener, "open", return_value=response):
                    with self.assertRaises(InvalidRequestError) as caught:
                        client.call("listZones")
                self.assertNotIn("secret-key", str(caught.exception))
                self.assertNotIn("api-key", str(caught.exception))
        with patch.object(client.opener, "open", side_effect=urllib.error.URLError("secret-key")):
            with self.assertRaises(InvalidRequestError) as caught:
                client.call("listZones")
            self.assertTrue(caught.exception.__suppress_context__)
            self.assertIsNone(caught.exception.__cause__)

    def test_resolver_rejects_unhealthy_and_foreign_resources(self):
        for command, collection, changes in (
            ("listProjects", "project", {"state": "Disabled"}),
            ("listZones", "zone", {"allocationstate": "Disabled"}),
            ("listNetworks", "network", {"projectid": "foreign"}),
            ("listNetworks", "network", {"zoneid": "foreign"}),
            ("listNetworks", "network", {"state": "Allocated"}),
            ("listServiceOfferings", "serviceoffering", {"issystem": True}),
            ("listTemplates", "template", {"hypervisor": "VMware"}),
            ("listTemplates", "template", {"zoneid": "foreign"}),
            ("listPublicIpAddresses", "publicipaddress", {"associatednetworkid": "foreign"}),
            ("listPublicIpAddresses", "publicipaddress", {"zoneid": "foreign"}),
        ):
            class Bad(InventoryClient):
                def call(self, cmd, params):
                    result = super().call(cmd, params)
                    if cmd == command:
                        result[collection][0].update(changes)
                    return result
            with self.subTest(command=command, changes=changes), self.assertRaises(InvalidRequestError):
                CloudStackResolver(Bad(), profile()).resolve_cluster(request())

    def test_endpoint_requires_both_active_ports_and_exact_scope(self):
        for port in ("6443", "9345"):
            for change in ({"state": "Add"}, {"privateport": "443"}, {"protocol": "udp"}):
                client = InventoryClient()
                next(rule for rule in client.rules if rule["publicport"] == port).update(change)
                resolver = CloudStackResolver(client, profile())
                self.assertFalse(resolver.verify_endpoints(resolver.resolve_cluster(request()))["endpoint" + port])
            client = InventoryClient()
            client.rules = [rule for rule in client.rules if rule["publicport"] != port]
            resolver = CloudStackResolver(client, profile())
            self.assertFalse(resolver.verify_endpoints(resolver.resolve_cluster(request()))["endpoint" + port])
            client.rules.append(dict(client.rules[0], id="duplicate"))
            with self.assertRaisesRegex(InvalidRequestError, "ambiguous"):
                resolver.verify_endpoints(resolver.resolve_cluster(request()))
        for field in ("projectid", "networkid", "publicipid"):
            client = InventoryClient()
            client.rules[0][field] = "foreign"
            resolver = CloudStackResolver(client, profile())
            with self.assertRaisesRegex(InvalidRequestError, "scope"):
                resolver.verify_endpoints(resolver.resolve_cluster(request()))

    def test_exact_vm_observation_is_scoped_and_does_not_return_secrets(self):
        client = InventoryClient()
        resolver = CloudStackResolver(client, profile())
        resolved = resolver.resolve_cluster(request())
        vm = {"id": "vm-1", "projectid": "project-1", "zoneid": "zone-1", "state": "Running", "password": "synthetic"}
        with patch.object(client, "call", return_value={"virtualmachine": [vm], "count": 1}):
            self.assertEqual(resolver.observe_vm("vm-1", resolved), {"id": "vm-1", "state": "Running"})
            vm["projectid"] = "foreign"
            with self.assertRaisesRegex(InvalidRequestError, "scope"):
                resolver.observe_vm("vm-1", resolved)
            vm["projectid"] = "project-1"
            vm["id"] = "different"
            with self.assertRaisesRegex(InvalidRequestError, "ambiguous"):
                resolver.observe_vm("vm-1", resolved)
        with patch.object(client, "call", return_value={"count": 0}):
            self.assertEqual(resolver.observe_vm("vm-1", resolved)["state"], "ABSENT")

    def test_credentials_with_broad_permissions_are_rejected(self):
        config = self.credential_config()
        os.chmod(config.secret_key_file, 0o644)
        with self.assertRaisesRegex(InvalidRequestError, "0600"):
            CloudStackClient(config)


if __name__ == "__main__":
    unittest.main()
