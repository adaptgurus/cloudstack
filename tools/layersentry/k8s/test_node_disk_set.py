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

import unittest

from node_disk_set import (
    ActionKind,
    DiskPurpose,
    MachineTarget,
    NodeDiskSet,
    NodeDiskSpec,
    ReplacementPolicy,
    ResizePolicy,
    RetainPolicy,
    VolumeBinding,
    VolumeView,
    ownership_tags,
    plan_delete,
    plan_reconcile,
    plan_replacement,
)


MACHINE = MachineTarget("machine-a", "vm-a")
NEW_MACHINE = MachineTarget("machine-b", "vm-b")


def disk(**overrides):
    values = dict(
        id="scratch",
        disk_offering_id="offering-fast",
        size_gib=20,
        purpose=DiskPurpose.SCRATCH,
        retain_policy=RetainPolicy.DELETE,
        resize_policy=ResizePolicy.EXPAND_ONLY,
        replacement_policy=ReplacementPolicy.REATTACH,
    )
    values.update(overrides)
    return NodeDiskSpec(**values)


def disk_set(selected=None):
    return NodeDiskSet("set-a", "pool-a", "project-a", "zone-a", (selected or disk(),))


def volume(selected=None, machine=MACHINE, **overrides):
    selected = selected or disk()
    values = dict(
        id="volume-a",
        project_id="project-a",
        zone_id="zone-a",
        disk_offering_id=selected.disk_offering_id,
        size_gib=20,
        attached_vm_id="vm-a",
        tags=ownership_tags(disk_set(selected), selected, machine),
    )
    values.update(overrides)
    return VolumeView(**values)


class NodeDiskSetTest(unittest.TestCase):
    def test_new_disk_plan_has_explicit_scope_and_tags(self):
        plan = plan_reconcile(disk_set(), [MACHINE], [], [])
        self.assertTrue(plan.executable)
        self.assertEqual([action.kind for action in plan.actions], [ActionKind.CREATE_VOLUME])
        params = plan.actions[0].parameters
        self.assertEqual(params["project_id"], "project-a")
        self.assertEqual(params["zone_id"], "zone-a")
        self.assertTrue(params["record_binding"])
        self.assertEqual(params["desired_tags"]["layersentry.io/machine"], "machine-a")

    def test_existing_owned_disk_is_idempotent(self):
        current = volume()
        binding = VolumeBinding("scratch", "machine-a", current.id)
        plan = plan_reconcile(disk_set(), [MACHINE], [current], [binding])
        self.assertTrue(plan.executable)
        self.assertEqual(plan.actions, ())

    def test_unbound_tagged_disk_is_not_adopted(self):
        current = volume()
        plan = plan_reconcile(disk_set(), [MACHINE], [current], [])
        self.assertFalse(plan.executable)
        self.assertIn("durable binding", plan.blockers[0])

    def test_resize_is_expand_only_and_idempotent(self):
        selected = disk(size_gib=40)
        current = volume(selected, size_gib=20)
        binding = VolumeBinding("scratch", "machine-a", current.id)
        plan = plan_reconcile(disk_set(selected), [MACHINE], [current], [binding])
        self.assertEqual([action.kind for action in plan.actions], [ActionKind.RESIZE_VOLUME])
        self.assertFalse(plan.actions[0].parameters["shrink_ok"])

        too_large = volume(selected, size_gib=80)
        plan = plan_reconcile(disk_set(selected), [MACHINE], [too_large], [binding])
        self.assertFalse(plan.executable)
        self.assertIn("shrink", plan.blockers[0])

    def test_retain_policy_never_deletes(self):
        selected = disk(retain_policy=RetainPolicy.RETAIN)
        current = volume(selected)
        binding = VolumeBinding("scratch", "machine-a", current.id)
        plan = plan_delete(disk_set(selected), MACHINE, [current], [binding])
        self.assertEqual([action.kind for action in plan.actions], [ActionKind.DETACH_VOLUME])

    def test_delete_requires_id_and_complete_tags(self):
        selected = disk()
        current = volume(selected)
        binding = VolumeBinding("scratch", "machine-a", current.id)
        plan = plan_delete(disk_set(selected), MACHINE, [current], [binding])
        self.assertEqual(
            [action.kind for action in plan.actions],
            [ActionKind.DETACH_VOLUME, ActionKind.DELETE_VOLUME],
        )
        self.assertTrue(all(action.destructive for action in plan.actions))

        wrong_tags = volume(selected, tags={})
        blocked = plan_delete(disk_set(selected), MACHINE, [wrong_tags], [binding])
        self.assertFalse(blocked.executable)
        self.assertIn("ownership", blocked.blockers[0])

    def test_destructive_paths_require_project_site_and_offering_scope(self):
        selected = disk()
        binding = VolumeBinding("scratch", "machine-a", "volume-a")
        for override in (
            {"project_id": "project-b"},
            {"zone_id": "zone-b"},
            {"disk_offering_id": "offering-other"},
        ):
            plan = plan_delete(disk_set(selected), MACHINE, [volume(selected, **override)], [binding])
            self.assertFalse(plan.executable)

    def test_duplicate_machine_or_vm_target_is_rejected(self):
        duplicate_vm = MachineTarget("machine-b", "vm-a")
        plan = plan_reconcile(disk_set(), [MACHINE, duplicate_vm], [], [])
        self.assertFalse(plan.executable)
        self.assertIn("duplicate", plan.blockers[0])

    def test_reattach_replacement_changes_owner_before_attach(self):
        selected = disk(replacement_policy=ReplacementPolicy.REATTACH)
        current = volume(selected)
        binding = VolumeBinding("scratch", "machine-a", current.id)
        plan = plan_replacement(disk_set(selected), MACHINE, NEW_MACHINE, [current], [binding])
        self.assertEqual(
            [action.kind for action in plan.actions],
            [ActionKind.DETACH_VOLUME, ActionKind.REPLACE_TAGS, ActionKind.ATTACH_VOLUME],
        )
        self.assertEqual(plan.actions[-1].required_tags["layersentry.io/machine"], "machine-b")

    def test_durable_node_data_is_fail_closed(self):
        selected = disk(purpose=DiskPurpose.CONTAINER_DATA)
        plan = plan_reconcile(disk_set(selected), [MACHINE], [], [])
        self.assertFalse(plan.executable)
        self.assertIn("CSI/PVC", plan.blockers[0])

    def test_multiple_matching_volumes_is_ambiguous(self):
        first = volume()
        second = volume(id="volume-b")
        plan = plan_reconcile(disk_set(), [MACHINE], [first, second], [])
        self.assertFalse(plan.executable)
        self.assertIn("multiple owned volumes", plan.blockers[0])


if __name__ == "__main__":
    unittest.main()
