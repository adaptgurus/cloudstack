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
        self.rules = rules or [
            {"id": "lb-6443", "publicport": "6443", "networkid": "network-1", "state": "Active"},
            {"id": "lb-9345", "publicport": "9345", "networkid": "network-1", "state": "Active"},
        ]

    def call(self, command, params):
        resource_id = params.get("id")
        if command == "listProjects":
            return {"project": [{"id": resource_id, "name": "project-one", "state": "Active"}]}
        if command == "listZones":
            return {"zone": [{"id": resource_id, "name": "site-one", "allocationstate": "Enabled"}]}
        if command == "listNetworks":
            return {"network": [{
                "id": resource_id, "name": "network-one", "zoneid": "zone-1", "state": "Implemented",
            }]}
        if command == "listServiceOfferings":
            return {"serviceoffering": [{"id": resource_id, "name": "compute", "issystem": False}]}
        if command == "listTemplates":
            return {"template": [{"id": resource_id, "name": "rke2", "isready": True, "hypervisor": "KVM"}]}
        if command == "listPublicIpAddresses":
            return {"publicipaddress": [{
                "id": resource_id, "ipaddress": "192.0.2.10", "projectid": params.get("projectid"),
                "zoneid": "zone-1", "state": "Allocated",
            }]}
        if command == "listLoadBalancerRules":
            return {"loadbalancerrule": self.rules}
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

    def test_credentials_with_broad_permissions_are_rejected(self):
        config = self.credential_config()
        os.chmod(config.secret_key_file, 0o644)
        with self.assertRaisesRegex(InvalidRequestError, "0600"):
            CloudStackClient(config)


if __name__ == "__main__":
    unittest.main()
