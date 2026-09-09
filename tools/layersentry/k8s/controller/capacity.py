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

"""Read-only native capacity discovery and conservative single-host POC admission.

This is not a scheduler or production sizing policy. CAPC retains placement.
Missing/ambiguous measurements never authorize a lab cluster create.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .cloudstack import CloudStackResolver, _list_all
from .model import InvalidRequestError

GIB = 1024 ** 3
MIB = 1024 ** 2


def integer(value, field, minimum=0):
    if type(value) is not int or value < minimum:
        raise InvalidRequestError("CloudStack capacity field is missing or invalid: " + field)
    return value


def ratio(value):
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 1:
            raise ValueError
        return number
    except (InvalidOperation, ValueError):
        raise InvalidRequestError("CloudStack overcommit ratio is unknown") from None


def capacity_row(rows, capacity_type, zone_id):
    # Types 0/1/90 are bytes/MHz/cores respectively (Capacity.java).
    selected = [row for row in rows if row.get("type") == capacity_type
                and not row.get("tag")]
    if len(selected) != 1 or selected[0].get("zoneid") != zone_id:
        raise InvalidRequestError("CloudStack capacity scope is missing or ambiguous")
    row = selected[0]
    total = integer(row.get("capacitytotal"), "capacitytotal", 1)
    used = integer(row.get("capacityused"), "capacityused")
    allocated = row.get("capacityallocated")
    if allocated is not None:
        allocated = integer(allocated, "capacityallocated")
    # capacityused includes reserved allocation for compute, not sampled CPU load.
    available = None if allocated is None else max(0, total - max(used, allocated))
    return {"total": total, "used": used, "allocated": allocated, "available": available}


def plan_cluster(resolver: CloudStackResolver, request: Mapping[str, Any]):
    resolved = resolver.resolve_cluster(request)
    cp = integer(request.get("control_plane_replicas"), "control_plane_replicas", 3)
    pools = request.get("node_pools")
    if cp % 2 != 1 or not isinstance(pools, list) or not pools:
        raise InvalidRequestError("POC must preserve the supported production topology")
    groups = [(cp, request["control_plane_service_offering_id"], request["control_plane_image_id"])]
    for pool in pools:
        if pool.get("direct_node_disks", 0) or pool.get("node_disk_set_id"):
            raise InvalidRequestError("POC additional node disk requirements are not qualified")
        groups.append((integer(pool.get("replicas"), "worker replicas", 1),
                       pool["service_offering_id"], pool["image_id"]))
    cpu = memory = disk = nodes = mhz = max_speed = 0
    for replicas, offering_id, template_id in groups:
        offering = resolver._exact("listServiceOfferings", "serviceoffering", offering_id)
        template = resolver._exact("listTemplates", "template", template_id,
                                   templatefilter="executable", zoneid=resolved.zone_id, projectid=resolved.project_id)
        cores = integer(offering.get("cpunumber"), "offering cpunumber", 2)
        speed = integer(offering.get("cpuspeed"), "offering cpuspeed", 1)
        max_speed = max(max_speed, speed)
        mhz += replicas * cores * speed
        ram = integer(offering.get("memory"), "offering memory", 4096) * MIB
        # TemplateResponse.size is virtual bytes; physicalsize is compressed bytes.
        root = integer(template.get("size"), "template size", 1)
        root = max(root, integer(offering.get("rootdisksize"), "offering rootdisksize") * GIB)
        for field in ("iscustomized", "iscustomizediops"):
            if offering.get(field) is not None and offering[field] is not False:
                raise InvalidRequestError("POC customized compute/IOPS is not qualified")
        if offering.get("storagetype") != "shared":
            raise InvalidRequestError("POC local storage placement is not qualified")
        if offering.get("provisioningtype") != "thin":
            raise InvalidRequestError("POC storage provisioning type is not qualified")
        linked_disk = offering.get("diskofferingid")
        if linked_disk is not None:
            if (not isinstance(linked_disk, str) or not linked_disk.strip()
                    or offering.get("diskofferingstrictness") is not False):
                raise InvalidRequestError("POC linked disk offering semantics are not qualified")
            visible = _list_all(resolver.client, "listDiskOfferings", "diskoffering",
                                {"id": linked_disk, "state": "all"})
            if visible:
                raise InvalidRequestError("POC externally selectable disk offering is not qualified")
            # CloudStack 4.22 filters computeOnly=true from listDiskOfferings.
            # Only a successful empty lookup plus stable ServiceOffering properties
            # permits the internal link; API errors must propagate, never mean empty.
            current = resolver._exact("listServiceOfferings", "serviceoffering", offering_id)
            fields = ("diskofferingid", "diskofferingstrictness", "iscustomized",
                      "iscustomizediops", "rootdisksize", "storagetype", "provisioningtype",
                      "cpunumber", "cpuspeed", "memory", "state")
            if any(current.get(field) != offering.get(field) for field in fields):
                raise InvalidRequestError("POC service offering changed during disk discovery")
        cpu += replicas * cores
        memory += replicas * ram
        disk += replicas * root
        nodes += replicas
    return resolved, {"control_planes": cp, "workers": nodes - cp, "nodes": nodes,
                      "cpu": cpu, "cpu_mhz": mhz, "minimum_host_speed_mhz": max_speed,
                      "ram_bytes": memory, "storage_bytes": disk}


def discover_capacity(resolver, resolved, cluster_id, host_id, pool_id):
    client = resolver.client
    cluster = resolver._exact("listClusters", "cluster", cluster_id,
                              zoneid=resolved.zone_id, showcapacities=True)
    if (cluster.get("zoneid") != resolved.zone_id or cluster.get("hypervisortype") != "KVM"
            or cluster.get("allocationstate") != "Enabled" or cluster.get("managedstate") != "Managed"):
        raise InvalidRequestError("CloudStack compute cluster is not usable")
    hosts = _list_all(client, "listHosts", "host", {"zoneid": resolved.zone_id, "type": "Routing"})
    # The known nested lab is one host. Never admit by summing fragmented capacity.
    if len(hosts) != 1 or hosts[0].get("id") != host_id:
        raise InvalidRequestError("Single-host POC placement cannot be proven")
    host = hosts[0]
    if (host.get("clusterid") != cluster_id or host.get("zoneid") != resolved.zone_id
            or host.get("hypervisor") != "KVM" or host.get("state") != "Up"
            or host.get("resourcestate") != "Enabled"):
        raise InvalidRequestError("CloudStack KVM host is not Up and Enabled")
    pool = resolver._exact("listStoragePools", "storagepool", pool_id, zoneid=resolved.zone_id)
    if (pool.get("zoneid") != resolved.zone_id or pool.get("state") != "Up"
            or pool.get("scope") != "CLUSTER" or pool.get("clusterid") != cluster_id):
        raise InvalidRequestError("Selected shared primary storage is not usable in the compute cluster")
    # CAPC has no pool selector in this profile: require exactly one eligible pool.
    pools = _list_all(client, "listStoragePools", "storagepool", {"zoneid": resolved.zone_id})
    if len(pools) != 1 or pools[0].get("id") != pool_id:
        raise InvalidRequestError("CAPC primary storage placement is ambiguous for this POC")
    capacities = []
    for kind in (0, 1, 90, 2, 3, 6, 9):
        capacities.extend(_list_all(client, "listCapacity", "capacity", {
            "zoneid": resolved.zone_id, "type": kind, "fetchlatest": True,
        }))
    cpu = capacity_row(capacities, 90, resolved.zone_id)
    mhz = capacity_row(capacities, 1, resolved.zone_id)
    memory = capacity_row(capacities, 0, resolved.zone_id)
    secondary = capacity_row(capacities, 6, resolved.zone_id)
    total = integer(pool.get("disksizetotal"), "disksizetotal", 1)
    used = integer(pool.get("disksizeused"), "disksizeused")
    allocated = integer(pool.get("disksizeallocated"), "disksizeallocated")
    systems = _list_all(client, "listSystemVms", "systemvm", {"zoneid": resolved.zone_id})
    if not systems or any(vm.get("zoneid") != resolved.zone_id or vm.get("state") != "Running" for vm in systems):
        raise InvalidRequestError("CloudStack System VM health is unknown or unhealthy")
    # Customer VM inventory is project-scoped; host/zone allocation includes all tenants.
    vms = _list_all(client, "listVirtualMachines", "virtualmachine", {
        "zoneid": resolved.zone_id, "projectid": resolved.project_id,
    })
    if any(vm.get("projectid") != resolved.project_id or vm.get("zoneid") != resolved.zone_id for vm in vms):
        raise InvalidRequestError("CloudStack VM inventory scope is invalid")
    return {"host_id": host_id, "host_state": "UP", "cpu": cpu, "cpu_mhz": mhz, "memory": memory,
            "host_speed_mhz": integer(host.get("cpuspeed"), "host cpuspeed", 1),
            "host_cpu": integer(host.get("cpunumber"), "host cpunumber", 1),
            "cpu_overcommit_ratio": str(ratio(cluster.get("cpuovercommitratio"))),
            "memory_overcommit_ratio": str(ratio(cluster.get("memoryovercommitratio"))),
            "primary": {"total": total, "used": used, "allocated": allocated,
                        "available": max(0, total - max(used, allocated))},
            "secondary": secondary, "local_storage": "NOT_APPLICABLE_SHARED_PROFILE",
            "system_vm_count": len(systems), "project_vm_count": len(vms)}


def assess_capacity(snapshot, plan, host_evidence, now=None, *, allocated_compute=None):
    """Admission requires fresh operator-collected host reality as well as IaaS data.

    host_evidence is a trusted host/console receipt, never tenant request data.
    CPU reservation is unallocated cores; RAM additionally uses MemAvailable.
    """
    result = {"decision": "PROVISION_BLOCKED_CAPACITY", "reason": "UNKNOWN",
              "nested_virtualization": host_evidence.get("nested_virtualization", "UNKNOWN"),
              "cloudstack_host": snapshot.get("host_state", "UNKNOWN"),
              "planned_topology": plan, "cloudstack": snapshot,
              "post_deployment_cpu_headroom": None, "post_deployment_ram_headroom_gib": None,
              "post_deployment_storage_headroom_gib": None}
    try:
        observed = datetime.fromisoformat(host_evidence["observed_at"].replace("Z", "+00:00"))
        current = now or datetime.now(timezone.utc)
        age = (current - observed).total_seconds()
        if not 0 <= age <= 300 or host_evidence.get("host_id") != snapshot["host_id"]:
            raise InvalidRequestError("Host measurement is stale or belongs to another host")
        if host_evidence.get("nested_virtualization") != "PASS":
            raise InvalidRequestError("LIVE_PROVISIONING_BLOCKED_NESTED_VIRTUALIZATION")
        if snapshot.get("host_state") != "UP":
            raise InvalidRequestError("CloudStack host is not Up")
        cpu_total = integer(host_evidence.get("total_cpu"), "measured total_cpu", 1)
        ram_total = integer(host_evidence.get("total_ram_bytes"), "measured total_ram_bytes", 1)
        ram_free = integer(host_evidence.get("available_ram_bytes"), "measured available_ram_bytes")
        cpu_reserve = max(2, integer(host_evidence.get("management_cpu_reserve"), "management_cpu_reserve"))
        ram_reserve = max(8 * GIB, integer(host_evidence.get("management_ram_reserve_bytes"), "management_ram_reserve_bytes"))
        if cpu_total != snapshot["host_cpu"] or ram_free > ram_total:
            raise InvalidRequestError("CloudStack and host physical capacity disagree")
        cpu, ram, primary = snapshot["cpu"], snapshot["memory"], snapshot["primary"]
        mhz = snapshot["cpu_mhz"]
        if any(item.get("available") is None for item in (cpu, ram, primary, mhz)):
            raise InvalidRequestError("CloudStack allocation is UNKNOWN")
        # Do not spend overcommit: intersect physical and CloudStack capacities.
        cpu_available = min(cpu["available"], cpu_total - max(cpu["used"], cpu["allocated"]))
        ram_available = min(ram["available"], ram_total - max(ram["used"], ram["allocated"]), ram_free)
        # Only the bounded qualifier supplies this independently observed CAPC
        # allocation. RAM/storage remain conservatively reserved in full.
        credit = allocated_compute or {"cpu": 0, "cpu_mhz": 0}
        if set(credit) != {"cpu", "cpu_mhz"}:
            raise InvalidRequestError("Invalid allocated compute observation")
        credited_cpu = integer(credit["cpu"], "allocated control-plane CPU")
        credited_mhz = integer(credit["cpu_mhz"], "allocated control-plane MHz")
        if (credited_cpu > min(cpu["allocated"], plan["cpu"] - 2)
                or credited_mhz > min(mhz["allocated"], plan["cpu_mhz"])
                or bool(credited_cpu) != bool(credited_mhz)):
            raise InvalidRequestError("Control-plane allocation is not reflected in native capacity")
        cpu_head = cpu_available - (integer(plan["cpu"], "planned cpu", 1) - credited_cpu)
        ram_head = ram_available - integer(plan["ram_bytes"], "planned memory", 1)
        disk_head = primary["available"] - integer(plan["storage_bytes"], "planned storage", 1)
        result.update(post_deployment_cpu_headroom=cpu_head,
                      post_deployment_ram_headroom_gib=ram_head / GIB,
                      post_deployment_storage_headroom_gib=disk_head / GIB,
                      available_cpu=cpu_available, available_ram_gib=ram_available / GIB,
                      management_cpu_reserve=cpu_reserve, management_ram_reserve_gib=ram_reserve / GIB,
                      already_allocated_control_plane_compute=credit)
        if (snapshot["host_speed_mhz"] < plan["minimum_host_speed_mhz"]
                or mhz["available"] - (plan["cpu_mhz"] - credited_mhz) < cpu_reserve * snapshot["host_speed_mhz"]):
            raise InvalidRequestError("Insufficient CPU MHz or host speed after reserve")
        if cpu_head < cpu_reserve:
            raise InvalidRequestError("Insufficient CPU after management/system reserve")
        if ram_head < ram_reserve:
            raise InvalidRequestError("Insufficient RAM after management/system reserve")
        if disk_head * 5 < primary["total"]:
            raise InvalidRequestError("Insufficient primary storage after 20% reserve")
        secondary = snapshot["secondary"]
        if (secondary["total"] - secondary["used"]) * 5 < secondary["total"]:
            raise InvalidRequestError("Insufficient secondary storage reserve")
        # Capacity is permission for an immediate POC decision, not durable approval.
        result.update(decision="PROVISION_ALLOWED", reason="Fresh native and host measurements preserve POC reserves")
    except (KeyError, TypeError, ValueError):
        result["reason"] = "Required host/capacity measurement is UNKNOWN or malformed"
    except InvalidRequestError as exc:
        result["reason"] = str(exc)
    return result
