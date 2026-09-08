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

import hashlib
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
    capc_image: str | None = None
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


_MANAGEMENT_PATH = "tools/layersentry/k8s/artifacts/management-lock.json"
_QUALIFICATION_PATH = "tools/layersentry/k8s/artifacts/qualification-lock.json"
_MANAGEMENT_COMPONENTS = {
    "capi": "1.13.5", "capc": "0.6.1", "caprke2-bootstrap": "0.25.2",
    "caprke2-control-plane": "0.25.2", "cert-manager-controller": "1.21.1",
    "cert-manager-cainjector": "1.21.1", "cert-manager-webhook": "1.21.1",
    "coredns": "1.14.2", "management-node": "1.36.4",
}


def read_artifact_lock(binding, approved_path, artifact_root=None):
    # Resolve a single approved installed path, never a caller-supplied path.
    root = artifact_root if artifact_root is not None else Path(__file__).resolve().parents[1]
    if (not isinstance(binding, Mapping) or binding.get("path") != approved_path
            or not _SHA256.fullmatch(str(binding.get("sha256", "")))):
        raise InvalidRequestError("artifact lock binding is invalid")
    path = root / "artifacts" / Path(approved_path).name
    if (path.is_symlink() or path.parent.is_symlink() or not path.is_file()
            or path.stat().st_mode & 0o022 or path.stat().st_size > 1048576):
        raise InvalidRequestError("artifact lock file is missing or unsafe")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != binding["sha256"]:
        raise InvalidRequestError("artifact lock SHA256 mismatch")
    data = json.loads(raw, object_pairs_hook=_unique_object)
    if not isinstance(data, Mapping) or data.get("schemaVersion") != "1.0":
        raise InvalidRequestError("artifact lock schema is invalid")
    return data


def _management_lock(manifest, blockers, artifact_root):
    try:
        data = read_artifact_lock(manifest.get("managementArtifactLock"), _MANAGEMENT_PATH, artifact_root)
        rows = data.get("components")
        if not isinstance(rows, list) or len(rows) != len(_MANAGEMENT_COMPONENTS):
            raise InvalidRequestError("required management components are missing or duplicated")
        seen = set()
        for row in rows:
            if not isinstance(row, Mapping):
                raise InvalidRequestError("management component is invalid")
            name = row.get("name")
            if (not isinstance(name, str) or name not in _MANAGEMENT_COMPONENTS or name in seen
                    or row.get("version") != _MANAGEMENT_COMPONENTS[name]
                    or not isinstance(row.get("image"), str) or not _IMAGE.fullmatch(row["image"])):
                raise InvalidRequestError("management component identity is invalid")
            if name == "capc" and row["image"] != manifest.get("capcDownstream", {}).get("image"):
                raise InvalidRequestError("management CAPC image differs from release contract")
            seen.add(name)
    except (InvalidRequestError, OSError, ValueError, TypeError):
        blockers.append("Management artifact lock is invalid")


def qualification_template(manifest, artifact_root=None):
    data = read_artifact_lock(manifest.get("qualificationArtifactLock"), _QUALIFICATION_PATH, artifact_root)
    template = data.get("template")
    uuid = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
    if (not isinstance(template, Mapping)
            or not uuid.fullmatch(str(data.get("projectId", "")))
            or not uuid.fullmatch(str(template.get("id", "")))
            or not _SHA256.fullmatch(str(template.get("qcow2Sha256", "")))
            or type(template.get("virtualSize")) is not int or template["virtualSize"] <= 0
            or not isinstance(template.get("name"), str) or not template["name"]
            or data.get("rke2") != "v1.36.4+rke2r1" or data.get("cni") != "canal"):
        raise InvalidRequestError("qualification template identity is invalid")
    return data


def validate_qualification_templates(project_id, template_ids, manifest=None, artifact_root=None):
    """Bind the reserved qualification project before generating any CAPI objects.

    This checks the locked artifact receipt, not a fresh measurement of CloudStack
    QCOW2 bytes. Other projects retain normal production template validation.
    """
    root = artifact_root if artifact_root is not None else Path(__file__).resolve().parents[1]
    if manifest is None:
        manifest = json.loads((root / "release-candidate-lane-b.json").read_bytes(), object_pairs_hook=_unique_object)
    lock = qualification_template(manifest, root)
    if project_id == lock["projectId"] and set(template_ids) != {lock["template"]["id"]}:
        raise InvalidRequestError("qualification template UUID differs from approved artifact lock")


def evaluate_component_readiness(manifest: Mapping[str, Any], *, artifact_root: Path | None = None) -> ComponentReadiness:
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

    capc_image = _image(capc.get("image"), "downstream CAPC", blockers)
    _management_lock(manifest, blockers, artifact_root)
    try:
        qualification_template(manifest, artifact_root)
    except (InvalidRequestError, OSError, ValueError, TypeError):
        blockers.append("Qualification artifact lock is invalid")
    ccm_image = _image(ccm.get("image"), "CloudStack CCM", blockers)
    csi_image = _image(csi.get("image"), "downstream CloudStack CSI", blockers)
    if ccm.get("version") != "1.2.0" or not _COMMIT.fullmatch(str(ccm.get("upstreamCommit", ""))):
        blockers.append("CloudStack CCM exact source is unresolved")
    if not _SHA256.fullmatch(str(ccm.get("downstreamPatchSha256", ""))):
        blockers.append("CloudStack CCM downstream patch digest is unresolved")
    if ccm.get("kubernetes136Qualified") is not True:
        blockers.append("CloudStack CCM v1.2.0 is not qualified with Kubernetes 1.36")
    if csi.get("projectLifecycleQualified") is not True:
        blockers.append("CloudStack CSI project lifecycle is not qualified")
    if csi.get("resizeIdempotencyQualified") is not True:
        blockers.append("CloudStack CSI resize idempotency is not live-qualified")
    if csi.get("apkPackageLayerDeterministic") is not True:
        blockers.append("CloudStack CSI runtime package layer is not deterministic")

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
    if not isinstance(flux.get("contentSha256"), str) or not _SHA256.fullmatch(flux["contentSha256"]):
        blockers.append("Flux catalog content SHA256 is unresolved")
    if flux.get("contentDigestVerified") is not True:
        blockers.append("Flux catalog content digest is not verified")

    for gate in _E1_GATES:
        if gates.get(gate) is not True:
            blockers.append(f"E1 evidence gate {gate} is false")
    return ComponentReadiness(
        deployable=not blockers,
        blockers=tuple(blockers),
        capc_image=capc_image,
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
