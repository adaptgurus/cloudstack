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

import io
import json
import tempfile
import unittest
from pathlib import Path

from controller.bff import BFFApplication
from controller.model import (
    InvalidRequestError,
    Actor,
    AmbiguousMutationError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    OperationStatus,
)
from controller.service import ControllerService, StepOutcome, StepResult
from controller.store import SagaStore
from layersentry_k8s_policy import ReleaseGates


ACTOR = Actor("user-1", "account-1", "domain-1", ("project-1",), ("DepartmentAdmin",))


def cluster_payload(**overrides):
    payload = {
        "name": "cluster-a",
        "zone_id": "zone-1",
        "network_id": "network-1",
        "cluster_class": "layersentry-standard-rke2",
        "channel": "certified",
        "cni": "cilium",
        "control_plane_replicas": 3,
        "control_plane_service_offering_id": "offering-control",
        "control_plane_image_id": "image-rke2",
        "project_id": "project-1",
        "api_frontend_id": "public-ip-1",
        "node_pools": [{
            "name": "workers", "replicas": 3, "service_offering_id": "offering-worker",
            "image_id": "image-rke2", "storage_profile_ids": [],
        }],
    }
    payload.update(overrides)
    return payload


class ProjectAuthorizer:
    def require(self, actor, action, project_id):
        if project_id != "*" and project_id not in actor.project_ids:
            raise AuthorizationError("project access denied")
        if not action.startswith("kubernetes."):
            raise AuthorizationError("action denied")


class QueueExecutor:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [StepResult(StepOutcome.CONVERGED)])
        self.calls = 0

    def reconcile(self, operation, step):
        del operation, step
        self.calls += 1
        result = self.outcomes.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def observe_ambiguous(self, operation, step):
        del operation, step
        self.calls += 1
        return self.outcomes.pop(0)

    def cluster_status(self, namespace, name, project_id):
        return {"namespace": namespace, "name": name, "projectId": project_id, "ready": False}


class StaticAuthenticator:
    def authenticate(self, environ):
        del environ
        return ACTOR


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SagaStore(Path(self.temp.name) / "controller.sqlite")
        self.gates = ReleaseGates(
            tuple_reconciliation=True, endpoint_6443=True, endpoint_9345=True,
            flux_remote_reconcile=True,
        )

    def tearDown(self):
        self.temp.cleanup()

    def service(self, executor=None):
        return ControllerService(
            self.store, ProjectAuthorizer(), executor or QueueExecutor(), self.gates,
        )

    def test_inventory_pagination_is_durable_project_scoped_and_stable(self):
        service = self.service()
        ids = [service.submit_cluster_create(ACTOR, cluster_payload(name="cluster-" + str(i)),
               "inventory-create-%04d" % i)[0].id for i in range(5)]
        foreign, _ = self.store.create_or_get(
            idempotency_key="foreign-inventory-001", request_sha256="foreign", kind="kubernetes.cluster.create",
            target_name="foreign", project_id="project-foreign", actor_subject="foreign",
            request={}, plan=[])
        with self.store._connect() as connection:
            connection.execute("UPDATE operations SET created_at=?", ("2026-09-06T00:00:00Z",))
        self.store = SagaStore(Path(self.store.path))
        service = self.service()
        first = service.list_operations(ACTOR, "project-1", limit=2)
        second = service.list_operations(ACTOR, "project-1", limit=2, after=first["nextCursor"])
        third = service.list_operations(ACTOR, "project-1", limit=2, after=second["nextCursor"])
        actual = [row["id"] for page in (first, second, third) for row in page["operations"]]
        self.assertEqual(actual, sorted(ids, reverse=True))
        self.assertIsNone(third["nextCursor"])
        with self.assertRaises(InvalidRequestError):
            service.list_operations(ACTOR, "project-1", after=foreign.id)
        with self.assertRaises(AuthorizationError):
            service.list_operations(ACTOR, "project-foreign")
        for limit in (0, 101, True, "2"):
            with self.assertRaises(InvalidRequestError):
                service.list_operations(ACTOR, "project-1", limit=limit)

    def test_bff_collection_query_validation_and_authorization(self):
        app = BFFApplication(self.service(), StaticAuthenticator())
        for query in ("", "projectId=", "projectId=project-1&projectId=project-foreign",
                      "projectId=project-1&limit=0", "projectId=project-1&limit=101",
                      "projectId=project-1&after=bad", "projectId=project-1&secret=x"):
            status, _ = self._request(app, "GET", "/v1/kubernetes/operations", query=query)
            self.assertEqual(status, 400, query)
        status, data = self._request(app, "GET", "/v1/kubernetes/operations", query="projectId=project-1")
        self.assertEqual((status, data), (200, {"operations": [], "nextCursor": None}))
        for path in ("operations", "clusters"):
            status, _ = self._request(app, "GET", "/v1/kubernetes/" + path, query="projectId=project-foreign")
            self.assertEqual(status, 403)

    def test_create_is_durably_idempotent_and_collision_safe(self):
        service = self.service()
        first, created = service.submit_cluster_create(ACTOR, cluster_payload(), "create-cluster-a-0001")
        second, created_again = service.submit_cluster_create(ACTOR, cluster_payload(), "create-cluster-a-0001")
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.id, second.id)
        with self.assertRaises(ConflictError):
            service.submit_cluster_create(
                ACTOR, cluster_payload(name="cluster-b"), "create-cluster-a-0001",
            )

    def test_authorization_and_release_gate_fail_before_persistence(self):
        service = self.service()
        with self.assertRaises(AuthorizationError):
            service.submit_cluster_create(
                ACTOR, cluster_payload(project_id="project-foreign"), "create-foreign-00001",
            )
        blocked = ControllerService(self.store, ProjectAuthorizer(), QueueExecutor(), ReleaseGates())
        with self.assertRaisesRegex(Exception, "release tuple"):
            blocked.submit_cluster_create(ACTOR, cluster_payload(), "blocked-cluster-0001")

    def test_ambiguous_mutation_requires_observation_not_replay(self):
        executor = QueueExecutor([
            AmbiguousMutationError("CloudStack async timeout"),
            StepResult(StepOutcome.CONVERGED, {"capiCluster": "cluster-a"}),
        ])
        service = self.service(executor)
        operation, _ = service.submit_cluster_create(ACTOR, cluster_payload(), "unknown-cluster-001")
        unknown = service.advance(operation.id)
        self.assertEqual(unknown.status, OperationStatus.UNKNOWN)
        with self.assertRaises(AmbiguousMutationError):
            service.advance(operation.id)
        reconciled = service.reconcile_unknown(operation.id)
        self.assertEqual(reconciled.status, OperationStatus.RUNNING)
        self.assertEqual(executor.calls, 2)
        self.assertEqual(reconciled.resources["capiCluster"], "cluster-a")

    def test_optimistic_store_version_rejects_stale_writer(self):
        service = self.service()
        operation, _ = service.submit_cluster_create(ACTOR, cluster_payload(), "stale-cluster-00001")
        current = self.store.update(
            operation, status=OperationStatus.RUNNING, step_index=0, detail="claimed",
        )
        self.assertEqual(current.version, 1)
        with self.assertRaises(ConflictError):
            self.store.update(operation, status=OperationStatus.FAILED, step_index=0)

    def test_restart_queue_excludes_terminal_and_unknown_operations(self):
        service = self.service()
        requested, _ = service.submit_cluster_create(ACTOR, cluster_payload(), "queue-requested-0001")
        terminal, _ = service.submit_cluster_create(ACTOR, cluster_payload(name="cluster-b"), "queue-terminal-00001")
        terminal = self.store.update(
            terminal, status=OperationStatus.READY, step_index=len(terminal.plan), detail="done",
        )
        unknown, _ = service.submit_cluster_create(ACTOR, cluster_payload(name="cluster-c"), "queue-unknown-000001")
        self.store.update(unknown, status=OperationStatus.UNKNOWN, step_index=0, detail="observe")
        self.assertEqual(self.store.actionable_ids(), [requested.id])
        self.assertEqual(self.store.path, str(Path(self.temp.name) / "controller.sqlite"))
        self.assertEqual(Path(self.store.path).stat().st_mode & 0o777, 0o600)

    def test_worker_records_redacted_retryable_adapter_failure(self):
        service = self.service()
        operation, _ = service.submit_cluster_create(ACTOR, cluster_payload(), "worker-failure-00001")
        failed = service.record_retryable_adapter_failure(operation.id)
        self.assertEqual(failed.status, OperationStatus.FAILED_RETRYABLE)
        self.assertNotIn("secret", failed.last_error)

    def test_adapter_secret_metadata_is_not_persisted(self):
        executor = QueueExecutor([
            StepResult(StepOutcome.CONVERGED, {"apiSecret": "never-store-this"}),
        ])
        service = self.service(executor)
        operation, _ = service.submit_cluster_create(ACTOR, cluster_payload(), "secret-output-00001")
        result = service.advance(operation.id)
        self.assertEqual(result.status, OperationStatus.FAILED)
        self.assertEqual(result.resources, {})
        self.assertNotIn("never-store-this", json.dumps(result.public_dict()))

    def test_bff_defaults_to_deny_and_requires_idempotency_key(self):
        denied_status, denied = self._request(BFFApplication(self.service()), "GET", "/v1/kubernetes/readiness")
        self.assertEqual(denied_status, 403)
        self.assertIn("authentication", denied["error"])

        app = BFFApplication(self.service(), StaticAuthenticator())
        status, response = self._request(app, "POST", "/v1/kubernetes/clusters", cluster_payload())
        self.assertEqual(status, 400)
        self.assertIn("Idempotency-Key", response["error"])

        status, response = self._request(
            app, "POST", "/v1/kubernetes/clusters", cluster_payload(), "bff-cluster-create-01",
        )
        self.assertEqual(status, 202)
        self.assertEqual(response["operation"]["status"], "REQUESTED")

    def test_bff_maps_authentication_failure_and_malformed_query(self):
        class MissingSession:
            def authenticate(self, environ):
                del environ
                raise AuthenticationError("CloudStack session credentials are missing")

        status, response = self._request(
            BFFApplication(self.service(), MissingSession()), "GET", "/v1/kubernetes/readiness",
        )
        self.assertEqual(status, 401)
        self.assertIn("session", response["error"])

        app = BFFApplication(self.service(), StaticAuthenticator())
        status, response = self._request(
            app, "GET", "/v1/kubernetes/clusters/cluster-a", query="namespace",
        )
        self.assertEqual(status, 400)
        self.assertIn("query", response["error"])

    def test_bff_scale_status_and_path_tampering(self):
        app = BFFApplication(self.service(), StaticAuthenticator())
        scale = {
            "cluster_name": "cluster-a", "namespace": "tenant-a", "node_pool": "workers",
            "replicas": 5, "project_id": "project-1",
        }
        status, response = self._request(
            app, "POST", "/v1/kubernetes/clusters/cluster-a/scale", scale, "bff-scale-cluster-01",
        )
        self.assertEqual(status, 202)
        self.assertEqual(response["operation"]["kind"], "kubernetes.cluster.scale")

        status, response = self._request(
            app, "POST", "/v1/kubernetes/clusters/cluster-b/scale", scale, "bff-scale-tamper-01",
        )
        self.assertEqual(status, 400)
        self.assertIn("request path", response["error"])

        status, response = self._request(
            app, "GET", "/v1/kubernetes/clusters/cluster-a", query="namespace=tenant-a&projectId=project-1",
        )
        self.assertEqual(status, 200)
        self.assertFalse(response["cluster"]["ready"])

    @staticmethod
    def _request(app, method, path, payload=None, key=None, query=""):
        raw = b"" if payload is None else json.dumps(payload).encode()
        environ = {
            "REQUEST_METHOD": method, "PATH_INFO": path, "CONTENT_TYPE": "application/json",
            "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw),
            "QUERY_STRING": query,
        }
        if key:
            environ["HTTP_IDEMPOTENCY_KEY"] = key
        captured = {}

        def start_response(status, headers):
            captured["status"] = int(status.split()[0])
            captured["headers"] = headers

        body = b"".join(app(environ, start_response))
        return captured["status"], json.loads(body)


if __name__ == "__main__":
    unittest.main()
