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

"""Fail-closed validation of the immutable Workstream E component tuple."""

from __future__ import annotations

import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from layersentry_k8s_policy import ReleaseGates

from .model import InvalidRequestError


_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IMAGE = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$")
_EXACT_TUPLE = {
    "cloudstack": "4.22.1.1",
    "capi": "1.13.5",
    "capc": "0.6.1",
    "caprke2": "0.25.2",
    "rke2": "1.36.4+rke2r1",
    "kubernetes": "1.36.x",
    "cloudstackCsi": "3.0.2",
}
_E1_GATES = ("tupleReconciliation", "endpoint6443", "endpoint9345", "fluxRemoteReconcile")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidRequestError(f"release manifest contains duplicate key: {key}")
        result[key] = value
    return result


@dataclass(frozen=True)
class ComponentReadiness:
    deployable: bool
    blockers: tuple[str, ...]
    ccm_image: str | None = None
    csi_image: str | None = None
    flux_repository: str | None = None
    flux_commit: str | None = None

    def require_deployable(self) -> None:
        if not self.deployable:
            raise InvalidRequestError("E1 component tuple is blocked: " + "; ".join(self.blockers))


@dataclass(frozen=True)
class ReleaseContract:
    manifest: Mapping[str, Any]
    readiness: ComponentReadiness
    gates: ReleaseGates


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidRequestError(f"release manifest {name} must be an object")
    return value


def _image(value: Any, name: str, blockers: list[str]) -> str | None:
    if not isinstance(value, str) or not _IMAGE.fullmatch(value):
        blockers.append(f"{name} immutable image digest is unresolved")
        return None
    return value


def evaluate_component_readiness(manifest: Mapping[str, Any]) -> ComponentReadiness:
    blockers: list[str] = []
    for key, expected in _EXACT_TUPLE.items():
        if manifest.get(key) != expected:
            blockers.append(f"release tuple {key} must equal {expected}")

    capc = _mapping(manifest.get("capcDownstream"), "capcDownstream")
    csi = _mapping(manifest.get("cloudstackCsiDownstream"), "cloudstackCsiDownstream")
    ccm = _mapping(manifest.get("cloudstackCcm"), "cloudstackCcm")
    flux = _mapping(manifest.get("fluxCatalog"), "fluxCatalog")
    gates = _mapping(manifest.get("hardGates"), "hardGates")

    if not _COMMIT.fullmatch(str(manifest.get("capcUpstreamCommit", ""))):
        blockers.append("CAPC source commit is unresolved")
    if not _SHA256.fullmatch(str(capc.get("patchSha256", ""))):
        blockers.append("CAPC downstream patch digest is unresolved")
    if not _COMMIT.fullmatch(str(manifest.get("cloudstackCsiUpstreamCommit", ""))):
        blockers.append("CloudStack CSI source commit is unresolved")
    if not _SHA256.fullmatch(str(csi.get("patchSha256", ""))):
        blockers.append("CloudStack CSI downstream patch digest is unresolved")

    ccm_image = _image(ccm.get("image"), "CloudStack CCM", blockers)
    csi_image = _image(csi.get("image"), "downstream CloudStack CSI", blockers)
    if ccm.get("version") != "1.2.0" or not _COMMIT.fullmatch(str(ccm.get("upstreamCommit", ""))):
        blockers.append("CloudStack CCM exact source is unresolved")
    if ccm.get("kubernetes136Qualified") is not True:
        blockers.append("CloudStack CCM v1.2.0 is not qualified with Kubernetes 1.36")
    if csi.get("projectLifecycleQualified") is not True:
        blockers.append("CloudStack CSI project lifecycle is not qualified")
    if csi.get("resizeIdempotencyQualified") is not True:
        blockers.append("CloudStack CSI resize idempotency is not live-qualified")

    repository = flux.get("repository")
    parsed = urllib.parse.urlsplit(repository) if isinstance(repository, str) else None
    if (
        parsed is None
        or parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        blockers.append("Flux catalog HTTPS repository is unresolved")
        repository = None
    commit = flux.get("commit")
    if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
        blockers.append("Flux catalog commit is unresolved")
        commit = None
    if flux.get("contentDigestVerified") is not True:
        blockers.append("Flux catalog content digest is not verified")

    for gate in _E1_GATES:
        if gates.get(gate) is not True:
            blockers.append(f"E1 evidence gate {gate} is false")
    return ComponentReadiness(
        deployable=not blockers,
        blockers=tuple(blockers),
        ccm_image=ccm_image,
        csi_image=csi_image,
        flux_repository=repository,
        flux_commit=commit,
    )


def load_release_contract(path: Path | str) -> ReleaseContract:
    manifest_path = Path(path)
    if not manifest_path.is_file() or manifest_path.stat().st_mode & 0o022:
        raise InvalidRequestError("release manifest must exist and not be group/world writable")
    try:
        manifest = json.loads(
            manifest_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidRequestError("release manifest is unreadable or invalid") from exc
    root = _mapping(manifest, "root")
    hard_gates = _mapping(root.get("hardGates"), "hardGates")
    gate_fields = {
        "tuple_reconciliation": "tupleReconciliation",
        "endpoint_6443": "endpoint6443",
        "endpoint_9345": "endpoint9345",
        "capc_volume_ownership_safe": "capcVolumeOwnershipSafe",
        "node_disk_set_ownership": "nodeDiskSetOwnership",
        "csi_project_scope": "csiProjectScope",
        "csi_resize_idempotent": "csiResizeIdempotent",
        "airgap_create_scale_repair": "airgapCreateScaleRepair",
        "stateful_machine_replacement": "statefulMachineReplacement",
        "flux_remote_reconcile": "fluxRemoteReconcile",
        "backup_restore": "backupRestore",
        "pitr_restore": "pitrRestore",
    }
    values = {}
    for field, key in gate_fields.items():
        value = hard_gates.get(key)
        if not isinstance(value, bool):
            raise InvalidRequestError(f"release evidence gate {key} must be boolean")
        values[field] = value
    return ReleaseContract(root, evaluate_component_readiness(root), ReleaseGates(**values))


def load_component_readiness(path: Path | str) -> ComponentReadiness:
    return load_release_contract(path).readiness
