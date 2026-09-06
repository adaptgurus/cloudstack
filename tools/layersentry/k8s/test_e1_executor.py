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

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from controller.e1_executor import E1Executor
from controller.e1_resources import ResolvedInfrastructure
from controller.flux_resources import FluxBaseline, build_flux_baseline
from controller.model import Actor, AuthorizationError, InvalidRequestError, NotFoundError, OperationStatus
from controller.service import ControllerService
from controller.store import SagaStore
from layersentry_k8s_policy import ReleaseGates


ACTOR = Actor("user-1", "account-1", "domain-1", ("project-1",), ("DepartmentAdmin",))
GATES = ReleaseGates(
    tuple_reconciliation=True, endpoint_6443=True, endpoint_9345=True,
    flux_remote_reconcile=True,
)


def payload():
    return {
        "name": "cluster-a", "zone_id": "zone-1", "network_id": "network-1",
        "cluster_class": "layersentry-standard-rke2", "channel": "certified", "cni": "cilium",
        "control_plane_replicas": 3, "control_plane_service_offering_id": "cp-offering",
        "control_plane_image_id": "rke2-image", "project_id": "project-1",
        "api_frontend_id": "public-ip-id",
        "node_pools": [{
            "name": "workers", "replicas": 3, "service_offering_id": "worker-offering",
            "image_id": "rke2-image", "storage_profile_ids": [],
        }],
    }


class Authorizer:
    def require(self, actor, action, project_id):
        del action
        if project_id != "*" and project_id not in actor.project_ids:
            raise AuthorizationError("denied")


class Resolver:
    def namespace_for_project(self, project_id):
        return "tenant-a"

    def resolve_cluster(self, request):
        self.last_request = request
        return ResolvedInfrastructure(
            namespace="tenant-a", endpoint_host="k8s.example.test",
            cloudstack_secret_name="capc-credentials", cloudstack_secret_namespace="capc-system",
            project_id="project-1", project_name="project-one",
            zone_id="zone-1", zone_name="site-one", network_id="network-1", network_name="network-one",
            control_plane_offering_id="cp-offering", control_plane_template_id="rke2-image",
            endpoint_public_ip_id="public-ip-id",
            worker_offering_ids={"workers": "worker-offering"},
            worker_template_ids={"workers": "rke2-image"},
        )

    def verify_endpoints(self, resolved):
        del resolved
        return {
            "endpoint6443": True, "endpoint9345": True, "publicIpId": "ip-1",
            "endpoint6443RuleId": "rule-6443", "endpoint9345RuleId": "rule-9345",
        }


class FakeKubernetes:
    def __init__(self, unready_kinds=None):
        self.applied = []
        self.unready_kinds = set(unready_kinds or ())
        self.objects = {}

    @staticmethod
    def _key(resource):
        return (
            resource["apiVersion"], resource["kind"],
            resource["metadata"].get("namespace"), resource["metadata"]["name"],
        )

    def apply(self, resource):
        self.applied.append(resource)
        stored = deepcopy(resource)
        stored["metadata"] = {
            **stored["metadata"], "uid": "uid-" + resource["metadata"]["name"], "generation": 1,
        }
        if "replicas" in stored.get("spec", {}):
            stored["status"] = {"availableReplicas": stored["spec"]["replicas"]}
        self.objects[self._key(resource)] = stored
        return stored

    def get(self, resource):
        if self._key(resource) not in self.objects:
            raise NotFoundError("missing")
        stored = deepcopy(self.objects[self._key(resource)])
        generation = 1
        ready = resource["kind"] not in self.unready_kinds
        status = {**stored.get("status", {}), "ready": ready, "conditions": [{
                "type": "Ready", "status": "True" if ready else "False", "observedGeneration": generation,
            }]}
        return {**stored, "status": status}

    def list_owned(self, api_version, kind, namespace, project_id):
        return [self.get(value) for key, value in self.objects.items()
                if key[:3] == (api_version, kind, namespace)
                and value["metadata"].get("labels", {}).get("layersentry.io/project") == project_id
                and value["metadata"].get("labels", {}).get("layersentry.io/managed") == "true"]

    def patch_merge(self, resource, patch):
        stored = self.objects[self._key(resource)]
        stored.setdefault("spec", {}).update(patch.get("spec", {}))
        if "replicas" in patch.get("spec", {}):
            stored.setdefault("status", {})["availableReplicas"] = patch["spec"]["replicas"]
        return deepcopy(stored)

    def delete(self, resource):
        self.objects.pop(self._key(resource), None)
        return {}


class E1ExecutorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SagaStore(Path(self.temp.name) / "saga.sqlite")
        self.kubernetes = FakeKubernetes()
        self.flux = FluxBaseline("https://git.example.test/catalog.git", "a" * 40, "./clusters/e1")
        self.executor = E1Executor(self.kubernetes, Resolver(), GATES, self.flux)
        self.service = ControllerService(self.store, Authorizer(), self.executor, GATES)

    def test_cluster_inventory_and_node_pools_recover_from_native_resources(self):
        self.assertEqual(self.executor.list_clusters("project-1"), [])
        operation, _ = self.service.submit_cluster_create(ACTOR, payload(), "inventory-native-001")
        for _ in operation.plan:
            operation = self.service.advance(operation.id)
        clusters = self.executor.list_clusters("project-1")
        self.assertEqual([row["name"] for row in clusters], ["cluster-a"])
        status = self.executor.cluster_status("tenant-a", "cluster-a", "project-1")
        self.assertEqual(status["nodePools"][0]["name"], "workers")
        self.assertEqual(status["nodePools"][0]["replicas"], 3)
        namespace = self.kubernetes.objects[("v1", "Namespace", None, "tenant-a")]
        namespace["metadata"]["labels"]["layersentry.io/project"] = "foreign"
        with self.assertRaisesRegex(InvalidRequestError, "namespace ownership"):
            self.executor.list_clusters("project-1")

    def test_full_create_reconciliation_reaches_ready(self):
        operation, _ = self.service.submit_cluster_create(ACTOR, payload(), "e1-cluster-create-001")
        for _ in range(len(operation.plan)):
            operation = self.service.advance(operation.id)
        self.assertEqual(operation.status, OperationStatus.READY)
        kinds = [item["kind"] for item in self.kubernetes.applied]
        for expected in (
            "Namespace", "CloudStackCluster", "CloudStackMachineTemplate", "Cluster", "RKE2ControlPlane",
            "RKE2ConfigTemplate", "MachineDeployment", "GitRepository", "Kustomization",
        ):
            self.assertIn(expected, kinds)
        self.assertEqual(operation.resources["release"]["caprke2"], "0.25.2")
        self.assertEqual(operation.resources["resolvedInfrastructure"]["project_id"], "project-1")
        self.assertEqual(operation.resources["endpoint"]["endpoint9345RuleId"], "rule-9345")

    def test_readiness_waits_without_advancing(self):
        self.kubernetes.unready_kinds.add("Cluster")
        operation, _ = self.service.submit_cluster_create(ACTOR, payload(), "e1-cluster-pending-01")
        for _ in range(len(operation.plan) - 1):
            operation = self.service.advance(operation.id)
        self.assertEqual(operation.step_index, len(operation.plan) - 1)
        pending = self.service.advance(operation.id)
        self.assertEqual(pending.status, OperationStatus.RUNNING)
        self.assertEqual(pending.step_index, operation.step_index)

    def test_flux_catalog_is_commit_pinned_and_cluster_scoped(self):
        source, reconciliation = build_flux_baseline("cluster-a", "tenant-a", "project-1", self.flux)
        self.assertEqual(source["spec"]["ref"]["commit"], "a" * 40)
        self.assertNotIn("layersentry.io/cluster", source["metadata"]["labels"])
        self.assertEqual(reconciliation["metadata"]["labels"]["layersentry.io/cluster"], "cluster-a")
        self.assertEqual(reconciliation["metadata"]["labels"]["layersentry.io/project"], "project-1")
        self.assertTrue(reconciliation["spec"]["prune"])
        self.assertTrue(reconciliation["spec"]["wait"])

    def test_scale_up_converges_and_scale_down_is_gate_blocked(self):
        create, _ = self.service.submit_cluster_create(ACTOR, payload(), "e1-scale-base-create")
        for _ in range(len(create.plan)):
            create = self.service.advance(create.id)
        scale_payload = {
            "cluster_name": "cluster-a", "namespace": "tenant-a", "node_pool": "workers",
            "replicas": 5, "project_id": "project-1",
        }
        scale, _ = self.service.submit_cluster_scale(ACTOR, scale_payload, "e1-scale-up-00001")
        self.assertEqual(self.service.advance(scale.id).status, OperationStatus.RUNNING)
        self.assertEqual(self.service.advance(scale.id).status, OperationStatus.READY)

        scale_payload["replicas"] = 2
        down, _ = self.service.submit_cluster_scale(ACTOR, scale_payload, "e1-scale-down-001")
        self.assertEqual(self.service.advance(down.id).status, OperationStatus.FAILED)

    def test_delete_requires_live_volume_gate_and_exact_confirmation(self):
        delete_payload = {
            "cluster_name": "cluster-a", "namespace": "tenant-a", "project_id": "project-1",
            "confirm_cluster_name": "cluster-a", "retain_workload_volumes": True,
        }
        with self.assertRaisesRegex(InvalidRequestError, "volume ownership"):
            self.service.submit_cluster_delete(ACTOR, delete_payload, "e1-delete-blocked-01")

        enabled_gates = ReleaseGates(
            tuple_reconciliation=True, endpoint_6443=True, endpoint_9345=True,
            flux_remote_reconcile=True, capc_volume_ownership_safe=True,
        )
        enabled_executor = E1Executor(self.kubernetes, Resolver(), enabled_gates, self.flux)
        enabled = ControllerService(self.store, Authorizer(), enabled_executor, enabled_gates)
        create, _ = enabled.submit_cluster_create(ACTOR, payload(), "e1-delete-base-create")
        for _ in range(len(create.plan)):
            create = enabled.advance(create.id)
        deletion, _ = enabled.submit_cluster_delete(ACTOR, delete_payload, "e1-delete-enabled-01")
        self.assertEqual(enabled.advance(deletion.id).status, OperationStatus.RUNNING)
        self.assertEqual(enabled.advance(deletion.id).status, OperationStatus.DELETED)

    def test_status_rejects_project_label_tampering(self):
        create, _ = self.service.submit_cluster_create(ACTOR, payload(), "e1-status-base-create")
        for _ in range(len(create.plan)):
            create = self.service.advance(create.id)
        status = self.service.cluster_status(
            ACTOR, namespace="tenant-a", name="cluster-a", project_id="project-1",
        )
        self.assertTrue(status["ready"])
        cluster = next(item for item in self.kubernetes.objects.values() if item["kind"] == "Cluster")
        cluster["metadata"]["labels"]["layersentry.io/project"] = "foreign"
        with self.assertRaisesRegex(InvalidRequestError, "project"):
            self.service.cluster_status(
                ACTOR, namespace="tenant-a", name="cluster-a", project_id="project-1",
            )

    def test_reconciliation_never_adopts_foreign_namespace(self):
        self.kubernetes.objects[("v1", "Namespace", None, "tenant-a")] = {
            "apiVersion": "v1", "kind": "Namespace",
            "metadata": {
                "name": "tenant-a", "uid": "foreign", "generation": 1,
                "labels": {"layersentry.io/managed": "true", "layersentry.io/project": "foreign"},
            },
        }
        operation, _ = self.service.submit_cluster_create(ACTOR, payload(), "e1-foreign-namespace")
        operation = self.service.advance(operation.id)
        operation = self.service.advance(operation.id)
        failed = self.service.advance(operation.id)
        self.assertEqual(failed.status, OperationStatus.FAILED)
        self.assertIn("ownership", failed.last_error)


if __name__ == "__main__":
    unittest.main()
