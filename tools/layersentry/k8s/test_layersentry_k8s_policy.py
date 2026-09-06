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

import unittest

from layersentry_k8s_policy import (
    ApplicationRequest,
    ClusterRequest,
    DatabaseRequest,
    NodePoolRequest,
    ReleaseChannel,
    ReleaseGates,
    StorageAccess,
    StorageProfile,
    StoragePurpose,
    ValidationError,
    plan_application_create,
    plan_cluster_create,
    plan_database_create,
    release_readiness,
    validate_cluster_request,
    validate_database_request,
)


SAFE_NVME = StorageProfile(
    id="nvme-db",
    name="NVMe Database",
    provisioner="cloudstack-csi",
    access_modes=(StorageAccess.RWO,),
    purposes=(StoragePurpose.DATABASE,),
    certified=True,
    nvme=True,
)

GENERAL = StorageProfile(
    id="general",
    name="General Block",
    provisioner="cloudstack-csi",
    access_modes=(StorageAccess.RWO,),
    purposes=(StoragePurpose.GENERAL,),
    certified=True,
)

NON_NVME_DB = StorageProfile(
    id="standard-db",
    name="Standard Database",
    provisioner="cloudstack-csi",
    access_modes=(StorageAccess.RWO,),
    purposes=(StoragePurpose.DATABASE,),
    certified=True,
    nvme=False,
)

DIRECT = StorageProfile(
    id="node-scratch",
    name="Node Scratch",
    provisioner="cloudstack-volume",
    access_modes=(StorageAccess.RWO,),
    purposes=(StoragePurpose.SCRATCH,),
    certified=False,
    direct_node_disk=True,
)


def base_cluster(**overrides):
    values = dict(
        name="team-a",
        zone_id="zone-1",
        network_id="network-1",
        cluster_class="layersentry-standard-rke2",
        channel=ReleaseChannel.PREVIEW,
        cni="cilium",
        control_plane_replicas=3,
        control_plane_service_offering_id="cp-offering",
        control_plane_image_id="rke2-image",
        node_pools=(
            NodePoolRequest(
                name="workers",
                replicas=3,
                service_offering_id="worker-offering",
                image_id="rke2-image",
                storage_profile_ids=("general",),
            ),
        ),
    )
    values.update(overrides)
    return ClusterRequest(**values)


def base_db(**overrides):
    values = dict(
        name="orders-db",
        engine="postgresql",
        version="17",
        cluster_id="cluster-1",
        storage_profile_id="nvme-db",
        storage_size_gib=200,
        replicas=3,
    )
    values.update(overrides)
    return DatabaseRequest(**values)


class ClusterPolicyTest(unittest.TestCase):
    def test_9345_gate_is_mandatory(self):
        gates = ReleaseGates(
            tuple_reconciliation=True,
            endpoint_6443=True,
            endpoint_9345=False,
            flux_remote_reconcile=True,
        )
        with self.assertRaisesRegex(ValidationError, "6443 and 9345"):
            validate_cluster_request(base_cluster(), gates, [GENERAL])

    def test_safe_base_cluster_builds_owned_controller_plan(self):
        gates = ReleaseGates(
            tuple_reconciliation=True,
            endpoint_6443=True,
            endpoint_9345=True,
            flux_remote_reconcile=True,
        )
        plan = plan_cluster_create(base_cluster(), gates, [GENERAL])
        self.assertTrue(plan.executable)
        owners = {step.owner for step in plan.steps}
        self.assertIn("CloudStack", owners)
        self.assertIn("CAPI/CAPC", owners)
        self.assertIn("CAPRKE2", owners)
        self.assertIn("Flux", owners)
        self.assertNotIn("LayerSentry-VM-Scheduler", owners)

    def test_direct_node_disk_is_fail_closed(self):
        request = base_cluster(node_pools=(
            NodePoolRequest(
                name="workers",
                replicas=3,
                service_offering_id="worker-offering",
                image_id="rke2-image",
                direct_node_disks=1,
            ),
        ))
        gates = ReleaseGates(
            tuple_reconciliation=True,
            endpoint_6443=True,
            endpoint_9345=True,
            flux_remote_reconcile=True,
        )
        plan = plan_cluster_create(request, gates, [GENERAL, DIRECT])
        self.assertFalse(plan.executable)
        self.assertIn("NodeDiskSet", plan.blockers[0])

    def test_direct_node_disk_requires_an_explicit_disk_set_id(self):
        request = base_cluster(node_pools=(
            NodePoolRequest(
                name="workers",
                replicas=3,
                service_offering_id="worker-offering",
                image_id="rke2-image",
                direct_node_disks=1,
            ),
        ))
        gates = ReleaseGates(
            tuple_reconciliation=True,
            endpoint_6443=True,
            endpoint_9345=True,
            flux_remote_reconcile=True,
            node_disk_set_ownership=True,
        )
        plan = plan_cluster_create(request, gates, [GENERAL, DIRECT])
        self.assertFalse(plan.executable)
        self.assertIn("node_disk_set_id", plan.blockers[0])


class DatabasePolicyTest(unittest.TestCase):
    def test_dbaas_blocked_until_capc_volume_ownership_safe(self):
        gates = ReleaseGates(
            tuple_reconciliation=True,
            endpoint_6443=True,
            endpoint_9345=True,
            flux_remote_reconcile=True,
            csi_project_scope=True,
            stateful_machine_replacement=True,
            backup_restore=True,
            capc_volume_ownership_safe=False,
        )
        plan = plan_database_create(base_db(), gates, [SAFE_NVME])
        self.assertFalse(plan.executable)
        self.assertIn("CAPC volume ownership", plan.blockers[0])

    def test_dbaas_rejects_non_nvme_profile(self):
        gates = ReleaseGates(
            tuple_reconciliation=True,
            endpoint_6443=True,
            endpoint_9345=True,
            flux_remote_reconcile=True,
            capc_volume_ownership_safe=True,
            csi_project_scope=True,
            stateful_machine_replacement=True,
            backup_restore=True,
        )
        with self.assertRaisesRegex(ValidationError, "NVMe"):
            validate_database_request(
                base_db(storage_profile_id="standard-db"), gates, [NON_NVME_DB]
            )

    def test_pitr_requires_restore_evidence(self):
        gates = ReleaseGates(
            tuple_reconciliation=True,
            endpoint_6443=True,
            endpoint_9345=True,
            flux_remote_reconcile=True,
            capc_volume_ownership_safe=True,
            csi_project_scope=True,
            stateful_machine_replacement=True,
            backup_restore=True,
            pitr_restore=False,
        )
        plan = plan_database_create(base_db(pitr_enabled=True), gates, [SAFE_NVME])
        self.assertFalse(plan.executable)
        self.assertIn("PITR", plan.blockers[0])

    def test_dbaas_plan_delegates_to_operator(self):
        gates = ReleaseGates(
            tuple_reconciliation=True,
            endpoint_6443=True,
            endpoint_9345=True,
            flux_remote_reconcile=True,
            capc_volume_ownership_safe=True,
            csi_project_scope=True,
            stateful_machine_replacement=True,
            backup_restore=True,
        )
        plan = plan_database_create(base_db(), gates, [SAFE_NVME])
        self.assertTrue(plan.executable)
        self.assertIn("OpenEverest", [step.owner for step in plan.steps])


class ApplicationPolicyTest(unittest.TestCase):
    def test_openbao_plan_requires_base_kubernetes_gates(self):
        request = ApplicationRequest(
            name="vault",
            package="openbao",
            version="2.4.0",
            cluster_id="cluster-1",
        )
        plan = plan_application_create(request, ReleaseGates(), [GENERAL])
        self.assertFalse(plan.executable)

    def test_external_frontend_requires_frontend_id(self):
        request = ApplicationRequest(
            name="registry",
            package="harbor",
            version="2.14.0",
            cluster_id="cluster-1",
            expose_mode="gateway",
        )
        gates = ReleaseGates(
            tuple_reconciliation=True,
            endpoint_6443=True,
            endpoint_9345=True,
            flux_remote_reconcile=True,
        )
        plan = plan_application_create(request, gates, [GENERAL])
        self.assertFalse(plan.executable)
        self.assertIn("Frontend", plan.blockers[0])

    def test_readiness_reports_hard_blockers(self):
        readiness = release_readiness(ReleaseGates(endpoint_6443=True))
        self.assertFalse(readiness["kubernetes"])
        self.assertIn("endpoint_9345", readiness["hard_blockers"])
        self.assertIn("capc_volume_ownership_safe", readiness["hard_blockers"])


if __name__ == "__main__":
    unittest.main()
