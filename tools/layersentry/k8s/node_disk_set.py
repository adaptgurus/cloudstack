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

"""Ownership-safe plans for LayerSentry per-node CloudStack data disks.

This module does not manage Kubernetes PVCs. It produces deterministic,
idempotency-keyed CloudStack API operations for explicitly owned node disks.
Every destructive operation requires both a recorded volume ID and the complete
ownership tag set; ambiguous or unowned inventory fails closed.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple


class NodeDiskError(ValueError):
    """The requested node-disk lifecycle is unsafe or ambiguous."""


class DiskPurpose(str, Enum):
    SCRATCH = "scratch"
    CACHE = "cache"
    CONTAINER_DATA = "container-data"


class RetainPolicy(str, Enum):
    RETAIN = "retain"
    DELETE = "delete"


class ResizePolicy(str, Enum):
    DISABLED = "disabled"
    EXPAND_ONLY = "expand-only"


class ReplacementPolicy(str, Enum):
    REATTACH = "reattach"
    RECREATE = "recreate"


class ActionKind(str, Enum):
    CREATE_VOLUME = "create-volume"
    TAG_VOLUME = "tag-volume"
    ATTACH_VOLUME = "attach-volume"
    DETACH_VOLUME = "detach-volume"
    RESIZE_VOLUME = "resize-volume"
    DELETE_VOLUME = "delete-volume"
    REPLACE_TAGS = "replace-tags"


@dataclass(frozen=True)
class NodeDiskSpec:
    id: str
    disk_offering_id: str
    size_gib: int
    purpose: DiskPurpose
    retain_policy: RetainPolicy
    resize_policy: ResizePolicy = ResizePolicy.DISABLED
    replacement_policy: ReplacementPolicy = ReplacementPolicy.REATTACH


@dataclass(frozen=True)
class NodeDiskSet:
    uid: str
    node_pool_uid: str
    project_id: str
    zone_id: str
    disks: Tuple[NodeDiskSpec, ...]


@dataclass(frozen=True)
class MachineTarget:
    uid: str
    vm_id: str


@dataclass(frozen=True)
class VolumeView:
    id: str
    project_id: str
    zone_id: str
    disk_offering_id: str
    size_gib: int
    attached_vm_id: Optional[str]
    tags: Mapping[str, str]


@dataclass(frozen=True)
class VolumeBinding:
    disk_id: str
    machine_uid: str
    volume_id: str


@dataclass(frozen=True)
class NodeDiskAction:
    kind: ActionKind
    idempotency_key: str
    disk_id: str
    machine_uid: str
    volume_id: Optional[str] = None
    parameters: Mapping[str, Any] = field(default_factory=dict)
    required_tags: Mapping[str, str] = field(default_factory=dict)
    destructive: bool = False

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["kind"] = self.kind.value
        return result


@dataclass(frozen=True)
class NodeDiskPlan:
    actions: Tuple[NodeDiskAction, ...]
    blockers: Tuple[str, ...] = ()

    @property
    def executable(self) -> bool:
        return not self.blockers


TAG_OWNER = "layersentry.io/owner"
TAG_DISK_SET = "layersentry.io/node-disk-set"
TAG_NODE_POOL = "layersentry.io/node-pool"
TAG_MACHINE = "layersentry.io/machine"
TAG_DISK = "layersentry.io/disk"
TAG_RETAIN = "layersentry.io/retain-policy"
OWNER_VALUE = "NodeDiskSet"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _required_identifier(value: str, name: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise NodeDiskError(f"{name} is missing or invalid")
    return value


def validate_node_disk_set(disk_set: NodeDiskSet) -> None:
    _required_identifier(disk_set.uid, "NodeDiskSet uid")
    _required_identifier(disk_set.node_pool_uid, "node pool uid")
    _required_identifier(disk_set.project_id, "project id")
    _required_identifier(disk_set.zone_id, "zone id")
    if not disk_set.disks:
        raise NodeDiskError("NodeDiskSet must contain at least one disk")
    seen = set()
    for disk in disk_set.disks:
        _required_identifier(disk.id, "disk id")
        _required_identifier(disk.disk_offering_id, "disk offering id")
        if disk.id in seen:
            raise NodeDiskError(f"duplicate disk id: {disk.id}")
        seen.add(disk.id)
        if disk.size_gib < 1:
            raise NodeDiskError(f"disk {disk.id} size must be positive")
        if disk.purpose not in {DiskPurpose.SCRATCH, DiskPurpose.CACHE}:
            raise NodeDiskError(
                f"disk {disk.id} purpose {disk.purpose.value} is not enabled; durable data must use CSI/PVC"
            )
        if disk.replacement_policy == ReplacementPolicy.RECREATE and disk.retain_policy == RetainPolicy.RETAIN:
            raise NodeDiskError(f"disk {disk.id} cannot combine recreate with retain")


def ownership_tags(disk_set: NodeDiskSet, disk: NodeDiskSpec, machine: MachineTarget) -> dict[str, str]:
    return {
        TAG_OWNER: OWNER_VALUE,
        TAG_DISK_SET: disk_set.uid,
        TAG_NODE_POOL: disk_set.node_pool_uid,
        TAG_MACHINE: machine.uid,
        TAG_DISK: disk.id,
        TAG_RETAIN: disk.retain_policy.value,
    }


def _key(disk_set: NodeDiskSet, disk: NodeDiskSpec, machine: MachineTarget, action: ActionKind) -> str:
    raw = f"{disk_set.uid}:{disk.id}:{machine.uid}:{action.value}".encode()
    return hashlib.sha256(raw).hexdigest()


def _owned(volume: VolumeView, expected: Mapping[str, str]) -> bool:
    return all(volume.tags.get(key) == value for key, value in expected.items())


def _verify_volume_contract(volume: VolumeView, disk_set: NodeDiskSet, disk: NodeDiskSpec) -> None:
    if volume.project_id != disk_set.project_id or volume.zone_id != disk_set.zone_id:
        raise NodeDiskError(f"owned volume {volume.id} escaped project or Site scope")
    if volume.disk_offering_id != disk.disk_offering_id:
        raise NodeDiskError(f"owned volume {volume.id} has an unexpected disk offering")


def _binding_map(bindings: Iterable[VolumeBinding]) -> dict[tuple[str, str], str]:
    result = {}
    for binding in bindings:
        key = (binding.disk_id, binding.machine_uid)
        if key in result and result[key] != binding.volume_id:
            raise NodeDiskError(f"conflicting recorded bindings for disk {binding.disk_id}")
        result[key] = binding.volume_id
    return result


def plan_reconcile(
    disk_set: NodeDiskSet,
    machines: Sequence[MachineTarget],
    volumes: Sequence[VolumeView],
    bindings: Sequence[VolumeBinding],
) -> NodeDiskPlan:
    """Plan create/tag/attach/expand operations without adopting by name."""

    try:
        validate_node_disk_set(disk_set)
        recorded = _binding_map(bindings)
        actions = []
        seen_machines = set()
        seen_vms = set()
        for machine in machines:
            _required_identifier(machine.uid, "machine uid")
            _required_identifier(machine.vm_id, "VM id")
            if machine.uid in seen_machines or machine.vm_id in seen_vms:
                raise NodeDiskError("duplicate Machine or VM target")
            seen_machines.add(machine.uid)
            seen_vms.add(machine.vm_id)
            for disk in disk_set.disks:
                expected = ownership_tags(disk_set, disk, machine)
                candidates = [volume for volume in volumes if _owned(volume, expected)]
                if len(candidates) > 1:
                    raise NodeDiskError(f"multiple owned volumes found for {machine.uid}/{disk.id}")
                recorded_id = recorded.get((disk.id, machine.uid))
                if not candidates:
                    if recorded_id:
                        raise NodeDiskError(f"recorded volume {recorded_id} is missing or has invalid ownership tags")
                    actions.append(NodeDiskAction(
                        ActionKind.CREATE_VOLUME,
                        _key(disk_set, disk, machine, ActionKind.CREATE_VOLUME),
                        disk.id,
                        machine.uid,
                        parameters={
                            "name": f"ls-{disk_set.node_pool_uid}-{machine.uid}-{disk.id}"[:255],
                            "project_id": disk_set.project_id,
                            "zone_id": disk_set.zone_id,
                            "disk_offering_id": disk.disk_offering_id,
                            "size_gib": disk.size_gib,
                            "desired_tags": expected,
                            "record_binding": True,
                        },
                        required_tags=expected,
                    ))
                    continue

                volume = candidates[0]
                if recorded_id != volume.id:
                    raise NodeDiskError(f"owned volume {volume.id} lacks its exact durable binding")
                _verify_volume_contract(volume, disk_set, disk)
                if volume.size_gib > disk.size_gib:
                    raise NodeDiskError(f"disk {disk.id} shrink is prohibited")
                if volume.size_gib < disk.size_gib:
                    if disk.resize_policy != ResizePolicy.EXPAND_ONLY:
                        raise NodeDiskError(f"disk {disk.id} resize policy is disabled")
                    actions.append(NodeDiskAction(
                        ActionKind.RESIZE_VOLUME,
                        _key(disk_set, disk, machine, ActionKind.RESIZE_VOLUME) + f":{disk.size_gib}",
                        disk.id,
                        machine.uid,
                        volume.id,
                        {"size_gib": disk.size_gib, "shrink_ok": False},
                        expected,
                    ))
                if volume.attached_vm_id is None:
                    actions.append(NodeDiskAction(
                        ActionKind.ATTACH_VOLUME,
                        _key(disk_set, disk, machine, ActionKind.ATTACH_VOLUME),
                        disk.id,
                        machine.uid,
                        volume.id,
                        {"virtual_machine_id": machine.vm_id},
                        expected,
                    ))
                elif volume.attached_vm_id != machine.vm_id:
                    raise NodeDiskError(f"owned volume {volume.id} is attached to an unexpected VM")
        return NodeDiskPlan(tuple(actions))
    except NodeDiskError as exc:
        return NodeDiskPlan((), (str(exc),))


def plan_delete(
    disk_set: NodeDiskSet,
    machine: MachineTarget,
    volumes: Sequence[VolumeView],
    bindings: Sequence[VolumeBinding],
) -> NodeDiskPlan:
    """Plan deletion/retention using IDs plus complete ownership tags."""

    try:
        validate_node_disk_set(disk_set)
        recorded = _binding_map(bindings)
        by_id = {volume.id: volume for volume in volumes}
        actions = []
        for disk in disk_set.disks:
            volume_id = recorded.get((disk.id, machine.uid))
            if not volume_id:
                raise NodeDiskError(f"disk {disk.id} has no durable volume binding")
            volume = by_id.get(volume_id)
            expected = ownership_tags(disk_set, disk, machine)
            if volume is None or not _owned(volume, expected):
                raise NodeDiskError(f"volume {volume_id} failed destructive ownership verification")
            _verify_volume_contract(volume, disk_set, disk)
            if volume.attached_vm_id:
                actions.append(NodeDiskAction(
                    ActionKind.DETACH_VOLUME,
                    _key(disk_set, disk, machine, ActionKind.DETACH_VOLUME),
                    disk.id,
                    machine.uid,
                    volume.id,
                    {"virtual_machine_id": volume.attached_vm_id},
                    expected,
                    destructive=True,
                ))
            if disk.retain_policy == RetainPolicy.DELETE:
                actions.append(NodeDiskAction(
                    ActionKind.DELETE_VOLUME,
                    _key(disk_set, disk, machine, ActionKind.DELETE_VOLUME),
                    disk.id,
                    machine.uid,
                    volume.id,
                    {},
                    expected,
                    destructive=True,
                ))
        return NodeDiskPlan(tuple(actions))
    except NodeDiskError as exc:
        return NodeDiskPlan((), (str(exc),))


def plan_replacement(
    disk_set: NodeDiskSet,
    old_machine: MachineTarget,
    new_machine: MachineTarget,
    volumes: Sequence[VolumeView],
    bindings: Sequence[VolumeBinding],
) -> NodeDiskPlan:
    """Plan explicit reattach/recreate semantics for a Machine replacement."""

    try:
        validate_node_disk_set(disk_set)
        recorded = _binding_map(bindings)
        by_id = {volume.id: volume for volume in volumes}
        actions = []
        for disk in disk_set.disks:
            volume_id = recorded.get((disk.id, old_machine.uid))
            if not volume_id:
                raise NodeDiskError(f"disk {disk.id} has no old-Machine binding")
            volume = by_id.get(volume_id)
            old_tags = ownership_tags(disk_set, disk, old_machine)
            if volume is None or not _owned(volume, old_tags):
                raise NodeDiskError(f"volume {volume_id} failed replacement ownership verification")
            _verify_volume_contract(volume, disk_set, disk)
            if disk.replacement_policy == ReplacementPolicy.RECREATE:
                if volume.attached_vm_id:
                    actions.append(NodeDiskAction(
                        ActionKind.DETACH_VOLUME,
                        _key(disk_set, disk, old_machine, ActionKind.DETACH_VOLUME),
                        disk.id,
                        old_machine.uid,
                        volume.id,
                        {"virtual_machine_id": volume.attached_vm_id},
                        old_tags,
                        destructive=True,
                    ))
                actions.append(NodeDiskAction(
                    ActionKind.DELETE_VOLUME,
                    _key(disk_set, disk, old_machine, ActionKind.DELETE_VOLUME),
                    disk.id,
                    old_machine.uid,
                    volume.id,
                    {},
                    old_tags,
                    destructive=True,
                ))
                new_tags = ownership_tags(disk_set, disk, new_machine)
                actions.append(NodeDiskAction(
                    ActionKind.CREATE_VOLUME,
                    _key(disk_set, disk, new_machine, ActionKind.CREATE_VOLUME),
                    disk.id,
                    new_machine.uid,
                    parameters={
                        "name": f"ls-{disk_set.node_pool_uid}-{new_machine.uid}-{disk.id}"[:255],
                        "project_id": disk_set.project_id,
                        "zone_id": disk_set.zone_id,
                        "disk_offering_id": disk.disk_offering_id,
                        "size_gib": disk.size_gib,
                        "desired_tags": new_tags,
                        "record_binding": True,
                    },
                    required_tags=new_tags,
                ))
                continue

            if volume.attached_vm_id:
                actions.append(NodeDiskAction(
                    ActionKind.DETACH_VOLUME,
                    _key(disk_set, disk, old_machine, ActionKind.DETACH_VOLUME),
                    disk.id,
                    old_machine.uid,
                    volume.id,
                    {"virtual_machine_id": volume.attached_vm_id},
                    old_tags,
                    destructive=True,
                ))
            new_tags = ownership_tags(disk_set, disk, new_machine)
            actions.append(NodeDiskAction(
                ActionKind.REPLACE_TAGS,
                _key(disk_set, disk, new_machine, ActionKind.REPLACE_TAGS),
                disk.id,
                new_machine.uid,
                volume.id,
                {"remove": old_tags, "add": new_tags},
                old_tags,
                destructive=True,
            ))
            actions.append(NodeDiskAction(
                ActionKind.ATTACH_VOLUME,
                _key(disk_set, disk, new_machine, ActionKind.ATTACH_VOLUME),
                disk.id,
                new_machine.uid,
                volume.id,
                {"virtual_machine_id": new_machine.vm_id},
                new_tags,
            ))
        return NodeDiskPlan(tuple(actions))
    except NodeDiskError as exc:
        return NodeDiskPlan((), (str(exc),))


def plan_json(plan: NodeDiskPlan) -> str:
    return json.dumps({
        "executable": plan.executable,
        "blockers": list(plan.blockers),
        "actions": [action.to_dict() for action in plan.actions],
    }, sort_keys=True)
