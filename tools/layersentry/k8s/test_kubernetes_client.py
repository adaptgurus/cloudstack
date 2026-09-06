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
import urllib.parse
from copy import deepcopy
import tempfile
import unittest
import urllib.error
from pathlib import Path

from controller.kubernetes import KubernetesClient, KubernetesConfig
from controller.model import AmbiguousMutationError, InvalidRequestError


RESOURCE = {
    "apiVersion": "cluster.x-k8s.io/v1beta2", "kind": "Cluster",
    "metadata": {"name": "cluster-a", "namespace": "tenant-a"}, "spec": {},
}


class FakeResponse:
    def __init__(self, body=b"{}"):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit):
        del limit
        return self.body


class RecordingOpener:
    def __init__(self, result=None):
        self.result = result or FakeResponse()
        self.request = None

    def open(self, request, timeout):
        del timeout
        self.request = request
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class KubernetesClientTest(unittest.TestCase):
    def client(self, result=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        token = Path(directory.name) / "token"
        token.write_text("runtime-service-account-token", encoding="utf-8")
        client = KubernetesClient.__new__(KubernetesClient)
        client.config = KubernetesConfig("https://kube.example", Path("/ca"), token)
        client.origin = "https://kube.example"
        client.opener = RecordingOpener(result)
        return client

    def test_apply_uses_exact_resource_path_and_server_side_apply(self):
        client = self.client()
        client.apply(RESOURCE)
        self.assertIn(
            "/apis/cluster.x-k8s.io/v1beta2/namespaces/tenant-a/clusters/cluster-a?",
            client.opener.request.full_url,
        )
        self.assertEqual(client.opener.request.method, "PATCH")
        self.assertEqual(client.opener.request.get_header("Content-type"), "application/apply-patch+yaml")
        self.assertNotIn("runtime-service-account-token", client.opener.request.full_url)

    def test_mutation_transport_failure_is_ambiguous(self):
        client = self.client(urllib.error.URLError("timeout"))
        with self.assertRaises(AmbiguousMutationError):
            client.apply(RESOURCE)

    def test_scale_patch_uses_merge_patch_without_force(self):
        client = self.client()
        client.patch_merge(RESOURCE, {"spec": {"replicas": 5}})
        self.assertNotIn("fieldManager", client.opener.request.full_url)
        self.assertEqual(client.opener.request.get_header("Content-type"), "application/merge-patch+json")

    def test_owned_list_uses_native_pagination_and_rejects_cross_project_rows(self):
        row = deepcopy(RESOURCE)
        row["metadata"]["labels"] = {"layersentry.io/managed": "true", "layersentry.io/project": "project-1"}
        next_row = deepcopy(row)
        next_row["metadata"]["name"] = "cluster-b"
        client = self.client()
        requests = []
        pages = [{"items": [row], "metadata": {"continue": "cursor+/="}}, {"items": [next_row]}]
        def request(method, path):
            requests.append((method, path))
            return pages.pop(0)
        client.request = request
        self.assertEqual(len(client.list_owned(RESOURCE["apiVersion"], "Cluster", "tenant-a", "project-1")), 2)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(requests[1][1]).query)
        self.assertEqual(query["continue"], ["cursor+/="])
        self.assertEqual(query["limit"], ["100"])
        self.assertIn("layersentry.io/project=project-1", query["labelSelector"][0])
        row["metadata"]["labels"]["layersentry.io/project"] = "foreign"
        client.request = lambda *args: {"items": [row]}
        with self.assertRaisesRegex(InvalidRequestError, "ownership"):
            client.list_owned(RESOURCE["apiVersion"], "Cluster", "tenant-a", "project-1")

    def test_owned_list_rejects_malformed_repeated_or_unbounded_results(self):
        client = self.client()
        for response in ([], {"items": [], "metadata": []}, {"items": [None]},
                         {"items": [{"metadata": None}]}, {"items": [] , "metadata": {"continue": 0}},
                         {"items": [RESOURCE] * 101}, {"items": [], "metadata": {"continue": "repeat"}}):
            client.request = lambda *args: response
            with self.assertRaises(InvalidRequestError):
                client.list_owned(RESOURCE["apiVersion"], "Cluster", "tenant-a", "project-1")
        count = [0]
        def unbounded(*args):
            count[0] += 1
            return {"items": [], "metadata": {"continue": str(count[0])}}
        client.request = unbounded
        with self.assertRaisesRegex(InvalidRequestError, "bounded"):
            client.list_owned(RESOURCE["apiVersion"], "Cluster", "tenant-a", "project-1")
        self.assertEqual(count[0], 10)

    def test_unknown_kind_and_unsafe_origin_fail_closed(self):
        with self.assertRaisesRegex(InvalidRequestError, "unsupported"):
            KubernetesClient._resource_path({
                "apiVersion": "evil.example/v1", "kind": "Danger",
                "metadata": {"name": "x", "namespace": "y"},
            })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "ca").write_text("invalid", encoding="utf-8")
            (path / "token").write_text("token", encoding="utf-8")
            with self.assertRaisesRegex(InvalidRequestError, "HTTPS origin"):
                KubernetesClient(KubernetesConfig("http://kube.example", path / "ca", path / "token"))


if __name__ == "__main__":
    unittest.main()
