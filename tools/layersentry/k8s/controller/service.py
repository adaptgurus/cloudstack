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

"""Fail-closed LayerSentry Kubernetes controller service."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Protocol, Sequence

from layersentry_k8s_policy import (
    ClusterRequest,
    NodePoolRequest,
    ReleaseChannel,
    ReleaseGates,
    StorageProfile,
    plan_cluster_create,
    release_readiness,
)

from .model import (
    Actor,
    AmbiguousMutationError,
    AuthorizationError,
    InvalidRequestError,
    Operation,
    OperationStatus,
)
from .store import SagaStore


_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{15,127}$")
_RESOURCE_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_CREATE_FIELDS = {
    "name", "zone_id", "network_id", "cluster_class", "channel", "cni",
    "control_plane_replicas", "control_plane_service_offering_id",
    "control_plane_image_id", "node_pools", "project_id", "api_frontend_id", "air_gapped",
}
_NODE_POOL_FIELDS = {
    "name", "replicas", "service_offering_id", "image_id", "role",
    "storage_profile_ids", "direct_node_disks", "node_disk_set_id", "gpu",
}
_SECRET_FIELD = re.compile(r"(password|secret|token|private.?key|api.?key)", re.IGNORECASE)
_SAFE_SECRET_REFERENCE_FIELDS = {"cloudstack_secret_name", "cloudstack_secret_namespace"}


class Authorizer(Protocol):
    def require(self, actor: Actor, action: str, project_id: str) -> None: ...


class DenyAllAuthorizer:
    def require(self, actor: Actor, action: str, project_id: str) -> None:
        del actor, action, project_id
        raise AuthorizationError("authorization is not configured")


class StepOutcome(str, Enum):
    CONVERGED = "CONVERGED"
    PENDING = "PENDING"
    RETRYABLE = "RETRYABLE"
    AMBIGUOUS = "AMBIGUOUS"
    FAILED = "FAILED"


@dataclass(frozen=True)
class StepResult:
    outcome: StepOutcome
    resources: Mapping[str, Any] = field(default_factory=dict)
    detail: str = ""
    recovery: str | None = None


class StepExecutor(Protocol):
    """Adapter boundary implemented by CloudStack/CAPI/Kubernetes/Flux clients."""

    def reconcile(self, operation: Operation, step: Mapping[str, Any]) -> StepResult: ...

    def observe_ambiguous(self, operation: Operation, step: Mapping[str, Any]) -> StepResult: ...

    def cluster_status(self, namespace: str, name: str, project_id: str) -> Mapping[str, Any]: ...


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _reject_unknown(value: Mapping[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise InvalidRequestError(f"unsupported {context} fields: {', '.join(unknown)}")


def _integer(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvalidRequestError(f"{field_name} must be an integer")
    return value


def _contains_secret_field(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            (_SECRET_FIELD.search(str(key)) and str(key) not in _SAFE_SECRET_REFERENCE_FIELDS)
            or _contains_secret_field(nested)
            for key, nested in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_secret_field(item) for item in value)
    return False


def parse_cluster_request(payload: Mapping[str, Any]) -> ClusterRequest:
    if not isinstance(payload, Mapping):
        raise InvalidRequestError("request body must be a JSON object")
    _reject_unknown(payload, _CREATE_FIELDS, "cluster")
    raw_pools = payload.get("node_pools")
    if not isinstance(raw_pools, list):
        raise InvalidRequestError("node_pools must be an array")
    pools = []
    for index, raw in enumerate(raw_pools):
        if not isinstance(raw, Mapping):
            raise InvalidRequestError(f"node_pools[{index}] must be an object")
        _reject_unknown(raw, _NODE_POOL_FIELDS, f"node_pools[{index}]")
        profile_ids = raw.get("storage_profile_ids", [])
        if not isinstance(profile_ids, list) or not all(isinstance(item, str) for item in profile_ids):
            raise InvalidRequestError(f"node_pools[{index}].storage_profile_ids must be a string array")
        pools.append(NodePoolRequest(
            name=raw.get("name", ""), replicas=_integer(raw.get("replicas"), f"node_pools[{index}].replicas"),
            service_offering_id=raw.get("service_offering_id", ""), image_id=raw.get("image_id", ""),
            role=raw.get("role", "general"), storage_profile_ids=tuple(profile_ids),
            direct_node_disks=_integer(raw.get("direct_node_disks", 0), f"node_pools[{index}].direct_node_disks"),
            node_disk_set_id=raw.get("node_disk_set_id"), gpu=raw.get("gpu", False) is True,
        ))
    try:
        channel = ReleaseChannel(payload.get("channel", "certified"))
    except ValueError as exc:
        raise InvalidRequestError("unsupported release channel") from exc
    return ClusterRequest(
        name=payload.get("name", ""), zone_id=payload.get("zone_id", ""),
        network_id=payload.get("network_id", ""), cluster_class=payload.get("cluster_class", ""),
        channel=channel, cni=payload.get("cni", ""),
        control_plane_replicas=_integer(payload.get("control_plane_replicas"), "control_plane_replicas"),
        control_plane_service_offering_id=payload.get("control_plane_service_offering_id", ""),
        control_plane_image_id=payload.get("control_plane_image_id", ""), node_pools=tuple(pools),
        project_id=payload.get("project_id"), api_frontend_id=payload.get("api_frontend_id"),
        air_gapped=payload.get("air_gapped", False) is True,
    )


class ControllerService:
    def __init__(
        self, store: SagaStore, authorizer: Authorizer, executor: StepExecutor,
        gates: ReleaseGates, storage_profiles: Sequence[StorageProfile] = (),
    ):
        self.store = store
        self.authorizer = authorizer
        self.executor = executor
        self.gates = gates
        self.storage_profiles = tuple(storage_profiles)

    def readiness(self, actor: Actor) -> Mapping[str, Any]:
        self.authorizer.require(actor, "kubernetes.readiness.read", "*")
        return release_readiness(self.gates)

    def submit_cluster_create(
        self, actor: Actor, payload: Mapping[str, Any], idempotency_key: str,
    ) -> tuple[Operation, bool]:
        if not _IDEMPOTENCY_KEY.fullmatch(idempotency_key or ""):
            raise InvalidRequestError("Idempotency-Key must contain 16-128 safe characters")
        request = parse_cluster_request(payload)
        project_id = request.project_id or actor.account_id
        self.authorizer.require(actor, "kubernetes.cluster.create", project_id)
        plan = plan_cluster_create(request, self.gates, self.storage_profiles)
        if not plan.executable:
            raise InvalidRequestError("; ".join(plan.blockers))
        normalized = asdict(request)
        normalized["channel"] = request.channel.value
        fingerprint = hashlib.sha256(_canonical({
            "actor": actor.subject, "action": "kubernetes.cluster.create", "request": normalized,
        })).hexdigest()
        steps = [asdict(step) for step in plan.steps]
        return self.store.create_or_get(
            idempotency_key=idempotency_key, request_sha256=fingerprint,
            kind="kubernetes.cluster.create", target_name=request.name,
            project_id=project_id, actor_subject=actor.subject,
            request=normalized, plan=steps,
        )

    @staticmethod
    def _mutation_identity(actor: Actor, action: str, payload: Mapping[str, Any], idempotency_key: str) -> str:
        if not _IDEMPOTENCY_KEY.fullmatch(idempotency_key or ""):
            raise InvalidRequestError("Idempotency-Key must contain 16-128 safe characters")
        return hashlib.sha256(_canonical({
            "actor": actor.subject, "action": action, "request": payload,
        })).hexdigest()

    def submit_cluster_scale(
        self, actor: Actor, payload: Mapping[str, Any], idempotency_key: str,
    ) -> tuple[Operation, bool]:
        allowed = {"cluster_name", "namespace", "node_pool", "replicas", "project_id"}
        if not isinstance(payload, Mapping):
            raise InvalidRequestError("request body must be a JSON object")
        _reject_unknown(payload, allowed, "scale")
        for name in ("cluster_name", "namespace", "node_pool"):
            if not isinstance(payload.get(name), str) or not _RESOURCE_NAME.fullmatch(payload[name]):
                raise InvalidRequestError(f"{name} is invalid")
        replicas = _integer(payload.get("replicas"), "replicas")
        if replicas < 1:
            raise InvalidRequestError("replicas must be at least 1")
        project_id = payload.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            raise InvalidRequestError("project_id is required")
        self.authorizer.require(actor, "kubernetes.cluster.scale", project_id)
        normalized = dict(payload)
        fingerprint = self._mutation_identity(actor, "kubernetes.cluster.scale", normalized, idempotency_key)
        step = {
            "owner": "CAPI", "action": "scale-worker-pool",
            "resource": f"{payload['cluster_name']}-{payload['node_pool']}",
            "idempotency_key": f"cluster:{payload['cluster_name']}:scale:{payload['node_pool']}:{replicas}",
            "destructive": False, "prerequisites": [],
        }
        return self.store.create_or_get(
            idempotency_key=idempotency_key, request_sha256=fingerprint,
            kind="kubernetes.cluster.scale", target_name=payload["cluster_name"],
            project_id=project_id, actor_subject=actor.subject, request=normalized, plan=[step],
        )

    def submit_cluster_delete(
        self, actor: Actor, payload: Mapping[str, Any], idempotency_key: str,
    ) -> tuple[Operation, bool]:
        allowed = {"cluster_name", "namespace", "project_id", "confirm_cluster_name", "retain_workload_volumes"}
        if not isinstance(payload, Mapping):
            raise InvalidRequestError("request body must be a JSON object")
        _reject_unknown(payload, allowed, "delete")
        for name in ("cluster_name", "namespace"):
            if not isinstance(payload.get(name), str) or not _RESOURCE_NAME.fullmatch(payload[name]):
                raise InvalidRequestError(f"{name} is invalid")
        if payload.get("confirm_cluster_name") != payload["cluster_name"]:
            raise InvalidRequestError("confirm_cluster_name must exactly match cluster_name")
        if payload.get("retain_workload_volumes") is not True:
            raise InvalidRequestError("E1 deletion requires retain_workload_volumes=true")
        if not self.gates.capc_volume_ownership_safe:
            raise InvalidRequestError("cluster deletion is blocked until CAPC volume ownership is live-verified")
        project_id = payload.get("project_id")
        if not isinstance(project_id, str) or not project_id:
            raise InvalidRequestError("project_id is required")
        self.authorizer.require(actor, "kubernetes.cluster.delete", project_id)
        normalized = dict(payload)
        fingerprint = self._mutation_identity(actor, "kubernetes.cluster.delete", normalized, idempotency_key)
        step = {
            "owner": "CAPI", "action": "delete-cluster", "resource": payload["cluster_name"],
            "idempotency_key": f"cluster:{payload['cluster_name']}:delete",
            "destructive": True, "prerequisites": [],
        }
        return self.store.create_or_get(
            idempotency_key=idempotency_key, request_sha256=fingerprint,
            kind="kubernetes.cluster.delete", target_name=payload["cluster_name"],
            project_id=project_id, actor_subject=actor.subject, request=normalized, plan=[step],
        )

    def cluster_status(
        self, actor: Actor, *, namespace: str, name: str, project_id: str,
    ) -> Mapping[str, Any]:
        if not _RESOURCE_NAME.fullmatch(namespace or "") or not _RESOURCE_NAME.fullmatch(name or ""):
            raise InvalidRequestError("namespace or cluster name is invalid")
        if not project_id:
            raise InvalidRequestError("project_id is required")
        self.authorizer.require(actor, "kubernetes.cluster.read", project_id)
        return self.executor.cluster_status(namespace, name, project_id)

    def get_operation(self, actor: Actor, operation_id: str) -> Operation:
        operation = self.store.get(operation_id)
        self.authorizer.require(actor, "kubernetes.operation.read", operation.project_id)
        return operation

    def advance(self, operation_id: str) -> Operation:
        operation = self.store.get(operation_id)
        if operation.done:
            return operation
        if operation.status == OperationStatus.UNKNOWN:
            raise AmbiguousMutationError("operation requires observation before it can continue")
        if operation.step_index >= len(operation.plan):
            return self.store.update(
                operation, status=OperationStatus.READY, step_index=operation.step_index,
                detail="all workflow steps converged",
            )
        step = operation.plan[operation.step_index]
        try:
            result = self.executor.reconcile(operation, step)
        except AmbiguousMutationError as exc:
            return self.store.update(
                operation, status=OperationStatus.UNKNOWN, step_index=operation.step_index,
                last_error=str(exc), recovery="observe authoritative controller/resource state; do not replay",
                detail="adapter returned an ambiguous mutation outcome",
            )
        return self._apply_result(operation, step, result)

    def reconcile_unknown(self, operation_id: str) -> Operation:
        operation = self.store.get(operation_id)
        if operation.status != OperationStatus.UNKNOWN:
            raise InvalidRequestError("operation is not in UNKNOWN state")
        if operation.step_index >= len(operation.plan):
            raise InvalidRequestError("operation has no ambiguous step")
        result = self.executor.observe_ambiguous(operation, operation.plan[operation.step_index])
        if result.outcome == StepOutcome.AMBIGUOUS:
            return self.store.update(
                operation, status=OperationStatus.UNKNOWN, step_index=operation.step_index,
                resources={**operation.resources, **result.resources},
                last_error=result.detail or operation.last_error,
                recovery=result.recovery or operation.recovery,
                detail="authoritative state remains ambiguous",
            )
        return self._apply_result(operation, operation.plan[operation.step_index], result)

    def _apply_result(
        self, operation: Operation, step: Mapping[str, Any], result: StepResult,
    ) -> Operation:
        if _contains_secret_field(result.resources):
            result = StepResult(
                StepOutcome.FAILED,
                detail="adapter returned prohibited secret-bearing resource metadata",
                recovery="remove secret material from controller state and rotate the exposed credential",
            )
        resources = {**operation.resources, **dict(result.resources)}
        detail = result.detail or f"{step.get('owner')}:{step.get('action')} {result.outcome.value}"
        if result.outcome == StepOutcome.CONVERGED:
            next_index = operation.step_index + 1
            if next_index == len(operation.plan):
                status = (
                    OperationStatus.DELETED
                    if operation.kind == "kubernetes.cluster.delete"
                    else OperationStatus.READY
                )
            else:
                status = OperationStatus.RUNNING
            return self.store.update(
                operation, status=status, step_index=next_index, resources=resources, detail=detail,
            )
        if result.outcome == StepOutcome.PENDING:
            return self.store.update(
                operation, status=OperationStatus.RUNNING, step_index=operation.step_index,
                resources=resources, detail=detail,
            )
        if result.outcome == StepOutcome.RETRYABLE:
            return self.store.update(
                operation, status=OperationStatus.FAILED_RETRYABLE, step_index=operation.step_index,
                resources=resources, last_error=detail, recovery=result.recovery, detail=detail,
            )
        if result.outcome == StepOutcome.AMBIGUOUS:
            return self.store.update(
                operation, status=OperationStatus.UNKNOWN, step_index=operation.step_index,
                resources=resources, last_error=detail,
                recovery=result.recovery or "observe authoritative state; do not replay", detail=detail,
            )
        return self.store.update(
            operation, status=OperationStatus.FAILED, step_index=operation.step_index,
            resources=resources, last_error=detail, recovery=result.recovery, detail=detail,
        )
