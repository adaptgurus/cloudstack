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

from controller.e1_resources import (
    CAPC_ENDPOINT_ANNOTATION,
    CAPC_VOLUME_ANNOTATION,
    RKE2_VERSION,
    ResolvedInfrastructure,
    build_cluster_resources,
)
from controller.model import InvalidRequestError
from layersentry_k8s_policy import ClusterRequest, NodePoolRequest, ReleaseChannel


def request(**overrides):
    values = dict(
        name="cluster-a", zone_id="zone-id", network_id="network-id",
        cluster_class="layersentry-standard-rke2", channel=ReleaseChannel.CERTIFIED,
        cni="cilium", control_plane_replicas=3,
        control_plane_service_offering_id="cp-offering-id",
        control_plane_image_id="image-id",
        node_pools=(NodePoolRequest("workers", 3, "worker-offering-id", "image-id"),),
        project_id="project-id",
        api_frontend_id="public-ip-id",
    )
    values.update(overrides)
    return ClusterRequest(**values)


def resolved(**overrides):
    values = dict(
        namespace="ls-project-a", endpoint_host="k8s.example.test",
        cloudstack_secret_name="capc-credentials", cloudstack_secret_namespace="capc-system",
        project_id="project-id", project_name="project-a", zone_id="zone-id", zone_name="site-a",
        network_id="network-id", network_name="workload-a",
        control_plane_offering_id="cp-offering-id", control_plane_template_id="image-id",
        endpoint_public_ip_id="public-ip-id",
        worker_offering_ids={"workers": "worker-offering-id"},
        worker_template_ids={"workers": "image-id"},
    )
    values.update(overrides)
    return ResolvedInfrastructure(**values)


class E1ResourceTest(unittest.TestCase):
    def test_exact_mixed_provider_contract_and_automatic_join(self):
        resources = build_cluster_resources(request(), resolved())
        by_kind = {item["kind"]: item for item in resources if item["kind"] != "CloudStackMachineTemplate"}
        self.assertNotIn("namespace", by_kind["Namespace"]["metadata"])
        self.assertEqual(by_kind["Namespace"]["metadata"]["labels"]["layersentry.io/project"], "project-id")
        self.assertEqual(by_kind["Cluster"]["apiVersion"], "cluster.x-k8s.io/v1beta2")
        self.assertEqual(by_kind["CloudStackCluster"]["apiVersion"], "infrastructure.cluster.x-k8s.io/v1beta3")
        self.assertEqual(by_kind["RKE2ControlPlane"]["apiVersion"], "controlplane.cluster.x-k8s.io/v1beta2")
        control_plane = by_kind["RKE2ControlPlane"]
        self.assertEqual(control_plane["spec"]["registrationMethod"], "control-plane-endpoint")
        self.assertEqual(control_plane["spec"]["version"], RKE2_VERSION)
        self.assertEqual(control_plane["spec"]["serverConfig"]["cni"], "cilium")
        self.assertIn("cloudController", control_plane["spec"]["serverConfig"]["disableComponents"]["kubernetesComponents"])

    def test_capc_endpoint_and_machine_volume_annotations_are_exact(self):
        resources = build_cluster_resources(request(), resolved())
        cluster = next(item for item in resources if item["kind"] == "CloudStackCluster")
        self.assertEqual(cluster["metadata"]["annotations"][CAPC_ENDPOINT_ANNOTATION], "true")
        self.assertEqual(cluster["spec"]["controlPlaneEndpoint"]["port"], 6443)
        templates = [item for item in resources if item["kind"] == "CloudStackMachineTemplate"]
        self.assertGreaterEqual(len(templates), 2)
        for template in templates:
            annotations = template["spec"]["template"]["metadata"]["annotations"]
            self.assertEqual(annotations[CAPC_VOLUME_ANNOTATION], "true")
            self.assertTrue(template["spec"]["template"]["spec"]["offering"]["id"])
            self.assertTrue(template["spec"]["template"]["spec"]["template"]["id"])

    def test_resolved_project_site_network_and_endpoint_must_match(self):
        with self.assertRaisesRegex(InvalidRequestError, "project"):
            build_cluster_resources(request(), resolved(project_id="foreign"))
        with self.assertRaisesRegex(InvalidRequestError, "Site/network"):
            build_cluster_resources(request(), resolved(network_id="foreign"))
        with self.assertRaisesRegex(InvalidRequestError, "endpoint"):
            build_cluster_resources(request(), resolved(endpoint_host="http://unsafe.example"))

    def test_worker_resolution_fails_closed(self):
        with self.assertRaisesRegex(InvalidRequestError, "unresolved"):
            build_cluster_resources(request(), resolved(worker_offering_ids={}))


if __name__ == "__main__":
    unittest.main()
