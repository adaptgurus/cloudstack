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

"""Exact Lane-B CAPI/CAPC/CAPRKE2 resource builders."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from layersentry_k8s_policy import ClusterRequest

from .model import InvalidRequestError


CAPC_ENDPOINT_ANNOTATION = "infrastructure.cluster.x-k8s.io/layersentry-rke2-endpoint"
CAPC_VOLUME_ANNOTATION = "infrastructure.cluster.x-k8s.io/layersentry-volume-ownership"
MANAGED_LABEL = "layersentry.io/managed"
PROJECT_LABEL = "layersentry.io/project"
RKE2_VERSION = "v1.36.4+rke2r1"
_DNS_NAME = re.compile(r"^(?=.{1,253}\.?$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.?$")


@dataclass(frozen=True)
class ResolvedInfrastructure:
    namespace: str
    endpoint_host: str
    cloudstack_secret_name: str
    cloudstack_secret_namespace: str
    project_id: str
    project_name: str
    zone_id: str
    zone_name: str
    network_id: str
    network_name: str
    control_plane_offering_id: str
    control_plane_template_id: str
    endpoint_public_ip_id: str
    worker_offering_ids: Mapping[str, str]
    worker_template_ids: Mapping[str, str]


def _endpoint_host(value: str) -> str:
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        if not _DNS_NAME.fullmatch(value or ""):
            raise InvalidRequestError("control-plane endpoint must be an IP address or DNS name")
        return value.rstrip(".")


def _metadata(name: str, resolved: ResolvedInfrastructure, *, annotations=None) -> dict[str, Any]:
    metadata = {
        "name": name,
        "namespace": resolved.namespace,
        "labels": {MANAGED_LABEL: "true", PROJECT_LABEL: resolved.project_id},
    }
    if annotations:
        metadata["annotations"] = dict(annotations)
    return metadata


def _machine_template(
    name: str, resolved: ResolvedInfrastructure, offering_id: str, template_id: str,
) -> dict[str, Any]:
    return {
        "apiVersion": "infrastructure.cluster.x-k8s.io/v1beta3",
        "kind": "CloudStackMachineTemplate",
        "metadata": _metadata(name, resolved),
        "spec": {"template": {
            "metadata": {"annotations": {CAPC_VOLUME_ANNOTATION: "true"}},
            "spec": {
                "offering": {"id": offering_id},
                "template": {"id": template_id},
                "failureDomainName": "primary",
            },
        }},
    }


def build_cluster_resources(
    request: ClusterRequest, resolved: ResolvedInfrastructure,
) -> Tuple[Mapping[str, Any], ...]:
    """Build the exact pinned provider resources without embedding secrets."""

    if request.project_id and request.project_id != resolved.project_id:
        raise InvalidRequestError("resolved project does not match the authorized request")
    if request.zone_id != resolved.zone_id or request.network_id != resolved.network_id:
        raise InvalidRequestError("resolved CloudStack Site/network does not match the request")
    for field_name in (
        "namespace", "cloudstack_secret_name", "cloudstack_secret_namespace", "project_id",
        "project_name", "zone_id", "zone_name", "network_id", "network_name",
        "control_plane_offering_id", "control_plane_template_id",
    ):
        if not getattr(resolved, field_name):
            raise InvalidRequestError(f"resolved {field_name} is required")
    endpoint = _endpoint_host(resolved.endpoint_host)
    cluster_name = request.name
    control_plane_name = f"{cluster_name}-control-plane"
    resources: list[Mapping[str, Any]] = [
        {
            "apiVersion": "infrastructure.cluster.x-k8s.io/v1beta3",
            "kind": "CloudStackCluster",
            "metadata": _metadata(cluster_name, resolved, annotations={CAPC_ENDPOINT_ANNOTATION: "true"}),
            "spec": {
                "syncWithACS": False,
                "controlPlaneEndpoint": {"host": endpoint, "port": 6443},
                "failureDomains": [{
                    "name": "primary",
                    "acsEndpoint": {
                        "name": resolved.cloudstack_secret_name,
                        "namespace": resolved.cloudstack_secret_namespace,
                    },
                    "project": resolved.project_name,
                    "zone": {
                        "id": resolved.zone_id,
                        "name": resolved.zone_name,
                        "network": {"id": resolved.network_id, "name": resolved.network_name},
                    },
                }],
            },
        },
        _machine_template(
            control_plane_name, resolved,
            resolved.control_plane_offering_id, resolved.control_plane_template_id,
        ),
        {
            "apiVersion": "controlplane.cluster.x-k8s.io/v1beta2",
            "kind": "RKE2ControlPlane",
            "metadata": _metadata(control_plane_name, resolved),
            "spec": {
                "replicas": request.control_plane_replicas,
                "version": RKE2_VERSION,
                "registrationMethod": "control-plane-endpoint",
                "rolloutStrategy": {"type": "RollingUpdate", "rollingUpdate": {"maxSurge": 1}},
                "gzipUserData": False,
                "airGapped": request.air_gapped,
                "agentConfig": {
                    "nodeName": "{{ ds.meta_data.local_hostname }}",
                    "kubelet": {"extraArgs": ["provider-id=cloudstack:///{{ ds.meta_data.instance_id }}"]},
                    "enableContainerdSElinux": True,
                },
                "serverConfig": {
                    "cni": request.cni,
                    "disableComponents": {"kubernetesComponents": ["cloudController"]},
                },
                "machineTemplate": {"spec": {
                    "infrastructureRef": {
                        "apiGroup": "infrastructure.cluster.x-k8s.io",
                        "kind": "CloudStackMachineTemplate",
                        "name": control_plane_name,
                    },
                    "deletion": {
                        "nodeDrainTimeoutSeconds": 600,
                        "nodeVolumeDetachTimeoutSeconds": 600,
                        "nodeDeletionTimeoutSeconds": 120,
                    },
                }},
            },
        },
        {
            "apiVersion": "cluster.x-k8s.io/v1beta2",
            "kind": "Cluster",
            "metadata": _metadata(cluster_name, resolved),
            "spec": {
                "clusterNetwork": {
                    "pods": {"cidrBlocks": ["10.42.0.0/16"]},
                    "services": {"cidrBlocks": ["10.43.0.0/16"]},
                    "serviceDomain": "cluster.local",
                },
                "controlPlaneRef": {
                    "apiGroup": "controlplane.cluster.x-k8s.io",
                    "kind": "RKE2ControlPlane", "name": control_plane_name,
                },
                "infrastructureRef": {
                    "apiGroup": "infrastructure.cluster.x-k8s.io",
                    "kind": "CloudStackCluster", "name": cluster_name,
                },
            },
        },
    ]
    for pool in request.node_pools:
        offering_id = resolved.worker_offering_ids.get(pool.name)
        template_id = resolved.worker_template_ids.get(pool.name)
        if not offering_id or not template_id:
            raise InvalidRequestError(f"worker pool {pool.name} has unresolved CloudStack IDs")
        machine_template_name = f"{cluster_name}-{pool.name}"
        bootstrap_name = f"{machine_template_name}-rke2"
        resources.extend((
            _machine_template(machine_template_name, resolved, offering_id, template_id),
            {
                "apiVersion": "bootstrap.cluster.x-k8s.io/v1beta2",
                "kind": "RKE2ConfigTemplate",
                "metadata": _metadata(bootstrap_name, resolved),
                "spec": {"template": {"spec": {
                    "gzipUserData": False,
                    "airGapped": request.air_gapped,
                    "agentConfig": {
                        "nodeName": "{{ ds.meta_data.local_hostname }}",
                        "kubelet": {"extraArgs": ["provider-id=cloudstack:///{{ ds.meta_data.instance_id }}"]},
                        "enableContainerdSElinux": True,
                    },
                }}},
            },
            {
                "apiVersion": "cluster.x-k8s.io/v1beta2",
                "kind": "MachineDeployment",
                "metadata": _metadata(machine_template_name, resolved),
                "spec": {
                    "clusterName": cluster_name,
                    "replicas": pool.replicas,
                    "selector": {"matchLabels": {"cluster.x-k8s.io/cluster-name": cluster_name}},
                    "template": {"spec": {
                        "clusterName": cluster_name,
                        "version": RKE2_VERSION,
                        "bootstrap": {"configRef": {
                            "apiGroup": "bootstrap.cluster.x-k8s.io",
                            "kind": "RKE2ConfigTemplate", "name": bootstrap_name,
                        }},
                        "infrastructureRef": {
                            "apiGroup": "infrastructure.cluster.x-k8s.io",
                            "kind": "CloudStackMachineTemplate", "name": machine_template_name,
                        },
                    }},
                },
            },
        ))
    return tuple(resources)
