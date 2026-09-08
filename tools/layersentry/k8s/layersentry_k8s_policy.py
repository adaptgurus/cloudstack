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

"""LayerSentry Kubernetes/Data Services policy and workflow contract.

This module intentionally does not create a second VM, Kubernetes, storage,
quota or RBAC authority. It validates LayerSentry requests and produces a
bounded controller plan whose steps are executed by the owning controller:
CloudStack, CAPI/CAPC/CAPRKE2, Flux or an application operator.

The fail-closed release gates mirror Workstream E. Stateful DBaaS is rejected
until CAPC attached-volume deletion is ownership-safe and the release has
passed the required destructive data-survival evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


class ValidationError(ValueError):
    """Raised when a customer request violates the certified product contract."""


class ServiceKind(str, Enum):
    KUBERNETES = "kubernetes"
    DBAAS = "dbaas"
    APAAS = "apaas"
    STREAMING = "streaming"


class ReleaseChannel(str, Enum):
    CERTIFIED = "certified"
    PREVIEW = "preview"
    EXTENDED = "extended"


class StorageAccess(str, Enum):
    RWO = "RWO"
    RWX = "RWX"


class StoragePurpose(str, Enum):
    GENERAL = "general"
    DATABASE = "database"
    SHARED = "shared"
    SCRATCH = "scratch"
    CACHE = "cache"


@dataclass(frozen=True)
class ReleaseTuple:
    cloudstack: str
    capi: str
    capc: str
    caprke2: str
    rke2: str
    kubernetes: str
    cloudstack_csi: Optional[str] = None
    openeverest: Optional[str] = None


@dataclass(frozen=True)
class ReleaseGates:
    """Evidence gates. Defaults are deliberately fail closed."""

    tuple_reconciliation: bool = False
    endpoint_6443: bool = False
    endpoint_9345: bool = False
    capc_volume_ownership_safe: bool = False
    node_disk_set_ownership: bool = False
    csi_project_scope: bool = False
    csi_resize_idempotent: bool = False
    airgap_create_scale_repair: bool = False
    stateful_machine_replacement: bool = False
    flux_remote_reconcile: bool = False
    backup_restore: bool = False
    pitr_restore: bool = False

    def kubernetes_ready(self) -> bool:
        return all(
            (
                self.tuple_reconciliation,
                self.endpoint_6443,
                self.endpoint_9345,
                self.flux_remote_reconcile,
            )
        )

    def stateful_ready(self) -> bool:
        return all(
            (
                self.kubernetes_ready(),
                self.capc_volume_ownership_safe,
                self.csi_project_scope,
                self.stateful_machine_replacement,
                self.backup_restore,
            )
        )


@dataclass(frozen=True)
class StorageProfile:
    id: str
    name: str
    provisioner: str
    access_modes: Tuple[StorageAccess, ...]
    purposes: Tuple[StoragePurpose, ...]
    certified: bool
    nvme: bool = False
    shared_filesystem: bool = False
    expandable: bool = False
    direct_node_disk: bool = False


@dataclass(frozen=True)
class NodePoolRequest:
    name: str
    replicas: int
    service_offering_id: str
    image_id: str
    role: str = "general"
    storage_profile_ids: Tuple[str, ...] = ()
    direct_node_disks: int = 0
    node_disk_set_id: Optional[str] = None
    gpu: bool = False


@dataclass(frozen=True)
class ClusterRequest:
    name: str
    zone_id: str
    network_id: str
    cluster_class: str
    channel: ReleaseChannel
    cni: str
    control_plane_replicas: int
    control_plane_service_offering_id: str
    control_plane_image_id: str
    node_pools: Tuple[NodePoolRequest, ...]
    project_id: Optional[str] = None
    api_frontend_id: Optional[str] = None
    air_gapped: bool = False


@dataclass(frozen=True)
class DatabaseRequest:
    name: str
    engine: str
    version: str
    cluster_id: str
    storage_profile_id: str
    storage_size_gib: int
    replicas: int
    backup_enabled: bool = True
    pitr_enabled: bool = False
    expose_publicly: bool = False


@dataclass(frozen=True)
class ApplicationRequest:
    name: str
    package: str
    version: str
    cluster_id: str
    storage_profile_id: Optional[str] = None
    replicas: int = 3
    expose_mode: str = "private"
    frontend_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowStep:
    owner: str
    action: str
    resource: str
    idempotency_key: str
    destructive: bool = False
    prerequisites: Tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowPlan:
    service: ServiceKind
    request_name: str
    steps: Tuple[WorkflowStep, ...]
    blockers: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()

    @property
    def executable(self) -> bool:
        return not self.blockers

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["service"] = self.service.value
        result["executable"] = self.executable
        return result


SUPPORTED_CLUSTER_CLASSES = {
    "layersentry-standard-rke2",
    "layersentry-secure-rke2",
    "layersentry-dbaas-rke2",
    "layersentry-kafka-rke2",
    "layersentry-gpu-rke2",
    "layersentry-custom-rke2",
}

SUPPORTED_CNIS = {"cilium", "canal", "calico"}
SUPPORTED_DATABASE_ENGINES = {"postgresql", "mysql", "mongodb", "redis", "valkey"}
SUPPORTED_APAAS_PACKAGES = {"openbao", "harbor"}
SUPPORTED_STREAMING_PACKAGES = {"strimzi-kafka"}


def _required(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field_name} is required")
    return value.strip()


def _validate_dns_label(name: str) -> None:
    value = _required(name, "name")
    if len(value) > 63:
        raise ValidationError("name must be 63 characters or fewer")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    if value.lower() != value or any(ch not in allowed for ch in value):
        raise ValidationError("name must be a lowercase DNS label")
    if value.startswith("-") or value.endswith("-"):
        raise ValidationError("name must not start or end with '-'")


def _profile_map(profiles: Iterable[StorageProfile]) -> Dict[str, StorageProfile]:
    result: Dict[str, StorageProfile] = {}
    for profile in profiles:
        if profile.id in result:
            raise ValidationError(f"duplicate StorageProfile id: {profile.id}")
        result[profile.id] = profile
    return result


def validate_cluster_request(
    request: ClusterRequest,
    gates: ReleaseGates,
    storage_profiles: Sequence[StorageProfile] = (),
) -> List[str]:
    """Validate an RKE2/CAPI cluster request and return non-blocking warnings."""

    _validate_dns_label(request.name)
    _required(request.zone_id, "zone_id")
    _required(request.network_id, "network_id")
    _required(request.project_id, "project_id")
    _required(request.api_frontend_id, "api_frontend_id")
    _required(request.control_plane_service_offering_id, "control_plane_service_offering_id")
    _required(request.control_plane_image_id, "control_plane_image_id")

    if request.cluster_class not in SUPPORTED_CLUSTER_CLASSES:
        raise ValidationError(f"unsupported ClusterClass: {request.cluster_class}")
    if request.cni not in SUPPORTED_CNIS:
        raise ValidationError(f"unsupported primary CNI: {request.cni}")
    if request.control_plane_replicas < 3 or request.control_plane_replicas % 2 == 0:
        raise ValidationError("managed production control plane requires an odd replica count of at least 3")
    if not request.node_pools:
        raise ValidationError("at least one worker node pool is required")

    profile_by_id = _profile_map(storage_profiles)
    seen_pool_names = set()
    for pool in request.node_pools:
        _validate_dns_label(pool.name)
        if pool.name in seen_pool_names:
            raise ValidationError(f"duplicate node pool name: {pool.name}")
        seen_pool_names.add(pool.name)
        if pool.replicas < 1:
            raise ValidationError(f"node pool {pool.name} must contain at least one node")
        _required(pool.service_offering_id, f"node pool {pool.name} service_offering_id")
        _required(pool.image_id, f"node pool {pool.name} image_id")
        if pool.direct_node_disks:
            if not gates.node_disk_set_ownership:
                raise ValidationError(
                    "direct node disks are not enabled until NodeDiskSet ownership is implemented and certified"
                )
            _required(pool.node_disk_set_id, f"node pool {pool.name} node_disk_set_id")
        for profile_id in pool.storage_profile_ids:
            profile = profile_by_id.get(profile_id)
            if profile is None:
                raise ValidationError(f"unknown StorageProfile: {profile_id}")
            if not profile.certified:
                raise ValidationError(f"StorageProfile {profile.name} is not certified")
            if profile.direct_node_disk:
                raise ValidationError(
                    f"StorageProfile {profile.name} is a direct node-disk profile and is not production-enabled"
                )

    if not gates.tuple_reconciliation:
        raise ValidationError("release tuple has not passed CAPI/CAPC/CAPRKE2 reconciliation")
    if not (gates.endpoint_6443 and gates.endpoint_9345):
        raise ValidationError("RKE2 control-plane frontend must own and reconcile both TCP 6443 and 9345")
    if not gates.flux_remote_reconcile:
        raise ValidationError("central Flux remote-cluster reconciliation has not passed the release gate")
    if request.air_gapped and not gates.airgap_create_scale_repair:
        raise ValidationError("air-gapped create/scale/repair has not passed the release gate")

    warnings: List[str] = []
    if request.channel == ReleaseChannel.PREVIEW:
        warnings.append("Preview channel is not a production certification statement.")
    if request.cluster_class == "layersentry-custom-rke2":
        warnings.append("Custom ClusterClass requires elevated/admin policy review.")
    return warnings


def validate_database_request(
    request: DatabaseRequest,
    gates: ReleaseGates,
    storage_profiles: Sequence[StorageProfile],
) -> List[str]:
    """Validate DBaaS request. This is intentionally stricter than generic K8s."""

    _validate_dns_label(request.name)
    engine = _required(request.engine, "engine").lower()
    if engine not in SUPPORTED_DATABASE_ENGINES:
        raise ValidationError(f"unsupported database engine: {engine}")
    _required(request.version, "version")
    _required(request.cluster_id, "cluster_id")
    if request.storage_size_gib < 1:
        raise ValidationError("storage_size_gib must be positive")
    if request.replicas < 1:
        raise ValidationError("replicas must be positive")

    if not gates.stateful_ready():
        raise ValidationError(
            "stateful DBaaS is blocked until CAPC volume ownership, CSI project scope, "
            "Machine replacement and backup/restore gates pass"
        )

    profile = _profile_map(storage_profiles).get(request.storage_profile_id)
    if profile is None:
        raise ValidationError("selected StorageProfile does not exist")
    if not profile.certified:
        raise ValidationError("selected StorageProfile is not certified")
    if StoragePurpose.DATABASE not in profile.purposes:
        raise ValidationError("selected StorageProfile is not certified for database workloads")
    if StorageAccess.RWO not in profile.access_modes:
        raise ValidationError("DBaaS requires a certified RWO block storage profile")
    if profile.direct_node_disk:
        raise ValidationError("durable DBaaS data must not use direct node disks")
    if not profile.nvme:
        raise ValidationError("current production DBaaS profile requires NVMe-backed storage")
    if profile.expandable and not gates.csi_resize_idempotent:
        raise ValidationError("automatic database storage growth is blocked until CSI resize is idempotent")
    if request.pitr_enabled and not gates.pitr_restore:
        raise ValidationError("PITR cannot be enabled until an older retained recovery point has been restored")

    warnings = []
    if request.expose_publicly:
        warnings.append("Database protocols default to private L4; public exposure requires explicit policy approval.")
    if engine in {"redis", "valkey"} and request.replicas < 3:
        warnings.append("A single/dual replica cache topology is not an HA production profile.")
    return warnings


def validate_application_request(
    request: ApplicationRequest,
    gates: ReleaseGates,
    storage_profiles: Sequence[StorageProfile],
) -> Tuple[ServiceKind, List[str]]:
    _validate_dns_label(request.name)
    package = _required(request.package, "package").lower()
    _required(request.version, "version")
    _required(request.cluster_id, "cluster_id")
    if request.replicas < 1:
        raise ValidationError("replicas must be positive")
    if not gates.kubernetes_ready():
        raise ValidationError("base LayerSentry Kubernetes release gates have not passed")

    if package in SUPPORTED_APAAS_PACKAGES:
        kind = ServiceKind.APAAS
    elif package in SUPPORTED_STREAMING_PACKAGES:
        kind = ServiceKind.STREAMING
    else:
        raise ValidationError(f"unsupported LayerSentry package: {package}")

    profile_by_id = _profile_map(storage_profiles)
    if request.storage_profile_id:
        profile = profile_by_id.get(request.storage_profile_id)
        if profile is None or not profile.certified:
            raise ValidationError("selected package StorageProfile is unavailable or uncertified")
        if profile.direct_node_disk:
            raise ValidationError("durable APaaS/Streaming data must not use direct node disks")
        if not gates.capc_volume_ownership_safe:
            raise ValidationError("stateful package deployment is blocked until CAPC volume ownership is safe")

    if request.expose_mode not in {"private", "l4", "gateway"}:
        raise ValidationError("expose_mode must be private, l4 or gateway")
    if request.expose_mode != "private" and not request.frontend_ids:
        raise ValidationError("external exposure requires at least one LayerSentry Frontend id")

    warnings: List[str] = []
    if package == "harbor":
        warnings.append("Harbor bootstrap must not depend on the registry instance being created.")
    if package == "strimzi-kafka" and request.expose_mode == "gateway":
        warnings.append("Kafka exposure must use a protocol-correct listener/VIP design, not generic HTTP routing.")
    return kind, warnings


def plan_cluster_create(request: ClusterRequest, gates: ReleaseGates, storage_profiles: Sequence[StorageProfile]) -> WorkflowPlan:
    try:
        warnings = validate_cluster_request(request, gates, storage_profiles)
    except ValidationError as exc:
        return WorkflowPlan(ServiceKind.KUBERNETES, request.name, (), (str(exc),), ())

    prefix = f"cluster:{request.name}"
    steps = (
        WorkflowStep("LayerSentry", "resolve-certified-release", request.name, f"{prefix}:release"),
        WorkflowStep("CloudStack", "resolve-iaas-inputs", request.zone_id, f"{prefix}:iaas"),
        WorkflowStep("CAPI/CAPC", "reconcile-infrastructure", request.name, f"{prefix}:infra", prerequisites=("release", "iaas")),
        WorkflowStep("CAPRKE2", "reconcile-control-plane", request.name, f"{prefix}:rke2", prerequisites=("infra",)),
        WorkflowStep("endpoint-authority", "reconcile-6443-and-9345", request.name, f"{prefix}:endpoint", prerequisites=("rke2",)),
        WorkflowStep("CAPI", "reconcile-worker-pools", request.name, f"{prefix}:workers", prerequisites=("endpoint",)),
        WorkflowStep("CloudStack-CCM", "reconcile-cloud-provider", request.name, f"{prefix}:ccm", prerequisites=("workers",)),
        WorkflowStep("Flux", "reconcile-baseline-packages", request.name, f"{prefix}:flux", prerequisites=("ccm",)),
        WorkflowStep("LayerSentry", "verify-cluster-readiness", request.name, f"{prefix}:ready", prerequisites=("flux",)),
    )
    return WorkflowPlan(ServiceKind.KUBERNETES, request.name, steps, (), tuple(warnings))


def plan_database_create(request: DatabaseRequest, gates: ReleaseGates, storage_profiles: Sequence[StorageProfile]) -> WorkflowPlan:
    try:
        warnings = validate_database_request(request, gates, storage_profiles)
    except ValidationError as exc:
        return WorkflowPlan(ServiceKind.DBAAS, request.name, (), (str(exc),), ())

    prefix = f"database:{request.name}"
    operator = "OpenEverest" if request.engine.lower() in {"postgresql", "mysql", "mongodb"} else "LayerSentry-Redis-Valkey-Provider"
    steps = (
        WorkflowStep("LayerSentry", "authorize-and-resolve-profile", request.name, f"{prefix}:policy"),
        WorkflowStep("Flux", "ensure-database-provider", request.cluster_id, f"{prefix}:provider", prerequisites=("policy",)),
        WorkflowStep(operator, "reconcile-database", request.name, f"{prefix}:database", prerequisites=("provider",)),
        WorkflowStep(operator, "reconcile-backup-policy", request.name, f"{prefix}:backup", prerequisites=("database",)),
        WorkflowStep("LayerSentry", "verify-database-health-and-recovery", request.name, f"{prefix}:verify", prerequisites=("backup",)),
    )
    return WorkflowPlan(ServiceKind.DBAAS, request.name, steps, (), tuple(warnings))


def plan_application_create(request: ApplicationRequest, gates: ReleaseGates, storage_profiles: Sequence[StorageProfile]) -> WorkflowPlan:
    try:
        kind, warnings = validate_application_request(request, gates, storage_profiles)
    except ValidationError as exc:
        return WorkflowPlan(ServiceKind.APAAS, request.name, (), (str(exc),), ())

    prefix = f"package:{request.name}"
    steps = (
        WorkflowStep("LayerSentry", "authorize-and-resolve-package", request.package, f"{prefix}:policy"),
        WorkflowStep("Flux", "reconcile-package", request.name, f"{prefix}:package", prerequisites=("policy",)),
        WorkflowStep("Gateway/API-or-L4-owner", "reconcile-frontends", request.name, f"{prefix}:frontend", prerequisites=("package",)),
        WorkflowStep("LayerSentry", "verify-package-readiness", request.name, f"{prefix}:verify", prerequisites=("frontend",)),
    )
    return WorkflowPlan(kind, request.name, steps, (), tuple(warnings))


def release_readiness(gates: ReleaseGates) -> Mapping[str, Any]:
    """Small API-friendly readiness projection for UI/BFF integration."""

    return {
        "kubernetes": gates.kubernetes_ready(),
        "stateful": gates.stateful_ready(),
        "gates": asdict(gates),
        "hard_blockers": [
            name
            for name, value in asdict(gates).items()
            if not value and name in {
                "tuple_reconciliation",
                "endpoint_6443",
                "endpoint_9345",
                "capc_volume_ownership_safe",
            }
        ],
    }
