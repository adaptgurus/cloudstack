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
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

from controller.capacity import GIB, assess_capacity, capacity_row, discover_capacity, plan_cluster
from controller.cloudstack import CloudStackResolver, _list_all
from controller.model import InvalidRequestError
from test_cloudstack_controller import InventoryClient, profile, request

NOW = datetime(2026, 9, 8, tzinfo=timezone.utc)


def evidence():
    return {"observed_at": NOW.isoformat(), "host_id": "host-1", "nested_virtualization": "PASS",
            "total_cpu": 12, "total_ram_bytes": 40 * GIB, "available_ram_bytes": 30 * GIB,
            "management_cpu_reserve": 2, "management_ram_reserve_bytes": 8 * GIB}


class CapacityClient(InventoryClient):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.rows = {
            "listClusters": ("cluster", [{"id": "cluster-1", "zoneid": "zone-1", "hypervisortype": "KVM",
                "allocationstate": "Enabled", "managedstate": "Managed", "cpuovercommitratio": "1.0",
                "memoryovercommitratio": "1.0"}]),
            "listHosts": ("host", [{"id": "host-1", "zoneid": "zone-1", "clusterid": "cluster-1",
                "hypervisor": "KVM", "state": "Up", "resourcestate": "Enabled", "cpunumber": 12, "cpuspeed": 2000}]),
            "listStoragePools": ("storagepool", [{"id": "pool-1", "zoneid": "zone-1", "clusterid": "cluster-1",
                "scope": "CLUSTER", "state": "Up", "disksizetotal": 500 * GIB,
                "disksizeused": 40 * GIB, "disksizeallocated": 50 * GIB}]),
            "listSystemVms": ("systemvm", [{"id": "system-1", "zoneid": "zone-1", "state": "Running"}]),
            "listVirtualMachines": ("virtualmachine", []),
        }
        self.capacities = {}
        for kind, total, allocated, used in ((90, 12, 2, 2), (1, 24000, 4000, 4000),
                (0, 40 * GIB, 6 * GIB, 6 * GIB), (2, 500 * GIB, None, 40 * GIB),
                (3, 500 * GIB, None, 50 * GIB), (6, 200 * GIB, None, 40 * GIB)):
            self.capacities[kind] = [{"type": kind, "zoneid": "zone-1", "capacitytotal": total,
                "capacityused": used, **({"capacityallocated": allocated} if allocated is not None else {})}]
        self.capacities[9] = []

    def call(self, command, params):
        self.calls.append((command, params))
        if command == "listCapacity":
            rows = self.capacities[params["type"]]
            return {"capacity": rows, "count": len(rows)}
        if command in self.rows:
            key, rows = self.rows[command]
            return {key: rows, "count": len(rows)}
        result = super().call(command, params)
        if command == "listServiceOfferings":
            result["serviceoffering"][0].update(cpunumber=2, cpuspeed=2000, memory=4096, storagetype="shared")
        if command == "listTemplates":
            result["template"][0].update(size=20 * GIB, physicalsize=3 * GIB)
        return result


class CloudStackCapacityTest(unittest.TestCase):
    def setUp(self):
        self.client = CapacityClient()
        self.resolver = CloudStackResolver(self.client, profile())
        self.request = request()
        self.request["control_plane_replicas"] = 3
        self.request["node_pools"][0]["replicas"] = 1
        self.resolved, self.plan = plan_cluster(self.resolver, self.request)

    def snapshot(self):
        return discover_capacity(self.resolver, self.resolved, "cluster-1", "host-1", "pool-1")

    def test_native_units_plan_and_healthy_admission(self):
        snapshot = self.snapshot()
        self.assertEqual(self.plan["cpu"], 8)
        self.assertEqual(self.plan["ram_bytes"], 16 * GIB)
        self.assertEqual(self.plan["storage_bytes"], 80 * GIB)
        self.assertEqual(snapshot["cpu"]["available"], 10)
        self.assertEqual(snapshot["cpu_mhz"]["available"], 20000)
        self.assertEqual(snapshot["memory"]["available"], 34 * GIB)
        self.assertEqual(snapshot["primary"]["available"], 450 * GIB)
        result = assess_capacity(snapshot, self.plan, evidence(), NOW)
        self.assertEqual(result["decision"], "PROVISION_ALLOWED")
        self.assertEqual(result["post_deployment_cpu_headroom"], 2)
        for command, params in self.client.calls:
            self.assertTrue(command.startswith("list"))
            if command == "listCapacity":
                self.assertTrue(params["fetchlatest"])
                self.assertEqual(params["page"], 1)
                self.assertEqual(params["pagesize"], 100)
            if command == "listClusters":
                self.assertTrue(params["showcapacities"])

    def test_insufficient_cpu_ram_storage_and_exact_fit_block(self):
        for section, field, value in (("cpu", "available", 7), ("cpu", "available", 8),
                ("memory", "available", 15 * GIB), ("memory", "available", 16 * GIB),
                ("primary", "available", 79 * GIB), ("primary", "available", 80 * GIB),
                ("cpu_mhz", "available", 15999)):
            snapshot = self.snapshot()
            snapshot[section][field] = value
            with self.subTest(section=section, value=value):
                self.assertEqual(assess_capacity(snapshot, self.plan, evidence(), NOW)["decision"], "PROVISION_BLOCKED_CAPACITY")

    def test_measured_management_and_linux_memory_reserves_win(self):
        for field, value in (("management_cpu_reserve", 3), ("management_ram_reserve_bytes", 20 * GIB),
                             ("available_ram_bytes", 20 * GIB), ("total_cpu", 10)):
            receipt = evidence()
            receipt[field] = value
            self.assertEqual(assess_capacity(self.snapshot(), self.plan, receipt, NOW)["decision"], "PROVISION_BLOCKED_CAPACITY")

    def test_unknown_stale_foreign_or_broken_host_evidence_blocks(self):
        for field, value in (("nested_virtualization", "UNKNOWN"), ("nested_virtualization", "FAIL"),
                             ("observed_at", "2026-09-07T00:00:00Z"), ("host_id", "foreign"),
                             ("available_ram_bytes", None), ("total_cpu", True)):
            receipt = evidence()
            receipt[field] = value
            self.assertEqual(assess_capacity(self.snapshot(), self.plan, receipt, NOW)["decision"], "PROVISION_BLOCKED_CAPACITY")
        self.assertEqual(assess_capacity(self.snapshot(), self.plan, {}, NOW)["decision"], "PROVISION_BLOCKED_CAPACITY")

    def test_unknown_allocation_never_means_zero(self):
        del self.client.capacities[90][0]["capacityallocated"]
        snapshot = self.snapshot()
        self.assertIsNone(snapshot["cpu"]["available"])
        self.assertEqual(assess_capacity(snapshot, self.plan, evidence(), NOW)["decision"], "PROVISION_BLOCKED_CAPACITY")

    def test_overcommit_does_not_increase_physical_budget(self):
        self.client.rows["listClusters"][1][0]["cpuovercommitratio"] = "4.0"
        self.client.capacities[90][0].update(capacitytotal=48, capacityallocated=4, capacityused=4)
        self.assertEqual(assess_capacity(self.snapshot(), self.plan, evidence(), NOW)["decision"], "PROVISION_BLOCKED_CAPACITY")

    def test_malformed_capacity_and_scope_rejected(self):
        good = self.client.capacities[0]
        for changes in ({"capacitytotal": "40"}, {"capacityused": -1}, {"capacityallocated": True}, {"zoneid": "foreign"}):
            with self.assertRaises(InvalidRequestError):
                capacity_row([{**good[0], **changes}], 0, "zone-1")
        with self.assertRaises(InvalidRequestError):
            capacity_row(good * 2, 0, "zone-1")
        for command, field, value in (("listHosts", "state", "Down"), ("listHosts", "resourcestate", "Disabled"),
                ("listClusters", "allocationstate", "Disabled"), ("listClusters", "memoryovercommitratio", "NaN"),
                ("listStoragePools", "scope", "HOST"), ("listSystemVms", "state", "Stopped")):
            old = self.client.rows[command][1][0][field]
            self.client.rows[command][1][0][field] = value
            with self.subTest(command=command), self.assertRaises(InvalidRequestError):
                self.snapshot()
            self.client.rows[command][1][0][field] = old

    def test_no_production_topology_or_disk_cheating(self):
        for cp in (1, 2, 4):
            self.request["control_plane_replicas"] = cp
            with self.assertRaises(InvalidRequestError):
                plan_cluster(self.resolver, self.request)
        self.request["control_plane_replicas"] = 3
        self.request["node_pools"][0]["replicas"] = 0
        with self.assertRaises(InvalidRequestError):
            plan_cluster(self.resolver, self.request)
        self.request["node_pools"][0]["replicas"] = 1
        self.request["node_pools"][0]["direct_node_disks"] = 1
        with self.assertRaises(InvalidRequestError):
            plan_cluster(self.resolver, self.request)

    def test_pagination_truncation_duplicate_and_malformed_fail_closed(self):
        with patch.object(self.client, "call", side_effect=[{"count": 2, "host": [{"id": "a"}]},
                                                            {"count": 2, "host": [{"id": "b"}]}]):
            self.assertEqual(len(_list_all(self.client, "listHosts", "host", {})), 2)
        for responses in ([{"count": 2, "host": [{"id": "a"}]}, {"count": 2}],
                          [{"count": 2, "host": [{"id": "a"}]}, {"count": 2, "host": [{"id": "a"}]}],
                          [{"count": "bad", "host": []}], [{"host": [None]}]):
            with patch.object(self.client, "call", side_effect=responses), self.assertRaises(InvalidRequestError):
                _list_all(self.client, "listHosts", "host", {})


if __name__ == "__main__":
    unittest.main()
