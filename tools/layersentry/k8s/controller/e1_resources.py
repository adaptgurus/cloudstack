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
import shlex
from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from layersentry_k8s_policy import ClusterRequest

from .model import InvalidRequestError
from .components import validate_qualification_templates, rke2_artifacts


CAPC_ENDPOINT_ANNOTATION = "infrastructure.cluster.x-k8s.io/layersentry-rke2-endpoint"
CAPC_VOLUME_ANNOTATION = "infrastructure.cluster.x-k8s.io/layersentry-volume-ownership"
MANAGED_LABEL = "layersentry.io/managed"
PROJECT_LABEL = "layersentry.io/project"
RKE2_VERSION = "v1.36.4+rke2r1"
# A stopped containerd can leave etcd blocked on its stdout/stderr pipes,
# preventing RKE2's local-datastore-first restart. Use etcd's bounded file sink
# inside the existing, protected data-directory mount (no extra host mounts).
# RKE2 converts log-outputs to a YAML string array, so preserve JSON brackets.
ETCD_LOG_ARGS = (
    'log-outputs=["/var/lib/rancher/rke2/server/db/etcd/etcd.log"]',
    'enable-log-rotation=true',
    'log-rotation-config-json={"maxsize":20,"maxage":7,"maxbackups":3,"localtime":false,"compress":true}',
)
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
    name: str, resolved: ResolvedInfrastructure, offering_id: str, template_id: str, *, cpu_mode=None,
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
                **({"details": {"guest.cpu.mode": cpu_mode}} if cpu_mode else {}),
            },
        }},
    }


def qualification_bootstrap(lock):
    """Render supported CAPRKE2 fields only; readiness still gates any apply."""
    assets = rke2_artifacts(lock)
    commands = ["set -eu", "umask 077",
        "for d in /opt /opt/rke2-artifacts /etc/rancher /etc/rancher/rke2 /etc/rancher/rke2/config.yaml.d; do test ! -L \"$d\"; done",
        "install -d -o root -g root -m 0700 /opt/rke2-artifacts /etc/rancher/rke2/config.yaml.d",
        "tmp=$(mktemp -d /opt/rke2-artifacts/.qualification.XXXXXX)",
        "trap 'rm -rf \"$tmp\"' EXIT"]
    policy = assets["selinuxPrerequisites"]
    # Include the pinned Rocky networking dependencies required by CNI portmap.
    rpm_paths = " ".join('"$tmp/' + item["filename"] + '"'
                         for item in policy["assets"] if item["filename"].endswith(".rpm"))
    for item in policy["assets"]:
        name = item["filename"]
        commands += [
            "curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' "
            "--connect-timeout 15 --max-time 300 --retry 2 --output \"$tmp/" + name + "\" " + shlex.quote(item["url"]),
            "printf '%s  %s\\n' " + item["sha256"] + " \"$tmp/" + name + "\" | sha256sum --check --status",
            "chown root:root \"$tmp/" + name + "\"",
            "chmod 0600 \"$tmp/" + name + "\"",
        ]
    commands += [
        '. /etc/os-release; test "$ID" = rocky; test "${VERSION_ID%%.*}" = 9',
        'test "$(uname -m)" = x86_64',
        'test "$(getenforce)" = Enforcing',
        "printf '%s  %s\\n' " + policy["rockyKeySha256"] + " /etc/pki/rpm-gpg/RPM-GPG-KEY-Rocky-9 | sha256sum --check --status",
        'rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-Rocky-9 "$tmp/rancher-public.key"',
        'rpm --checksig ' + rpm_paths,
        'dnf -y --disablerepo="*" --setopt=localpkg_gpgcheck=1 --setopt=install_weak_deps=False install '
        + rpm_paths,
    ]
    for package in policy["packages"]:
        name = package.rsplit("-", 2)[0]
        commands.append('test "$(rpm -q --qf \'%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\\n\' '
                        + name + ')" = ' + shlex.quote(package))
    commands += ['test "$(getenforce)" = Enforcing',
        'command -v iptables; command -v ip6tables',
        'version=$(iptables --version); case "$version" in *"(nf_tables)"*) ;; *) exit 1 ;; esac',
        'version=$(ip6tables --version); case "$version" in *"(nf_tables)"*) ;; *) exit 1 ;; esac']
    for item in assets["assets"]:
        name = item["filename"]
        target = "/opt/install.sh" if name == "install.sh" else "/opt/rke2-artifacts/" + name
        commands += [
            "curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' "
            "--connect-timeout 15 --max-time 1800 --retry 2 --output \"$tmp/" + name + "\" " + shlex.quote(item["url"]),
            "printf '%s  %s\\n' " + item["sha256"] + " \"$tmp/" + name + "\" | sha256sum --check --status",
            "chown root:root \"$tmp/" + name + "\"",
            "chmod " + ("0700" if name == "install.sh" else "0600") + " \"$tmp/" + name + "\"",
            "test ! -L " + target,
            "mv -T \"$tmp/" + name + "\" " + target,
        ]
    commands += [
        "printf '%s\\n' 'disable-default-registry-endpoint: true' > \"$tmp/99-layersentry-qualification.yaml\"",
        "chmod 0600 \"$tmp/99-layersentry-qualification.yaml\"",
        "test ! -L /etc/rancher/rke2/config.yaml.d/99-layersentry-qualification.yaml",
        "mv -T \"$tmp/99-layersentry-qualification.yaml\" /etc/rancher/rke2/config.yaml.d/99-layersentry-qualification.yaml",
    ]
    script = "\n".join(commands)
    return {"agentConfig": {"airGapped": True,
            "airGappedChecksum": assets["assets"][0]["sha256"]},
            # Exit the surrounding cloud-init runcmd script too, not merely a child.
            "preRKE2Commands": ["sh -eu -c " + shlex.quote(script) + " || exit 1"],
            "privateRegistriesConfig": {"mirrors": {
                "*": {"endpoint": ["https://127.0.0.1:1"]},
                "docker.io": {"endpoint": ["https://127.0.0.1:1"]},
            }}}


def build_cluster_resources(
    request: ClusterRequest, resolved: ResolvedInfrastructure,
    *, qualification_manifest=None,
) -> Tuple[Mapping[str, Any], ...]:
    """Build the exact pinned provider resources without embedding secrets."""

    if request.project_id and request.project_id != resolved.project_id:
        raise InvalidRequestError("resolved project does not match the authorized request")
    if request.zone_id != resolved.zone_id or request.network_id != resolved.network_id:
        raise InvalidRequestError("resolved CloudStack Site/network does not match the request")
    qualification = validate_qualification_templates(
        resolved.project_id,
        [resolved.control_plane_template_id, *resolved.worker_template_ids.values()],
        manifest=qualification_manifest,
    )
    bootstrap = {}
    if resolved.project_id == qualification["projectId"]:
        if request.cni != qualification["cni"]:
            raise InvalidRequestError("qualification CNI differs from approved artifact lock")
        bootstrap = qualification_bootstrap(qualification)
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
    cpu_mode = "host-model" if resolved.project_id == qualification["projectId"] else None
    cp_template_name = control_plane_name + ("-cpu-v2" if cpu_mode else "")
    resources: list[Mapping[str, Any]] = [
        {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": resolved.namespace,
                "labels": {MANAGED_LABEL: "true", PROJECT_LABEL: resolved.project_id},
            },
        },
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
            cp_template_name, resolved,
            resolved.control_plane_offering_id, resolved.control_plane_template_id, cpu_mode=cpu_mode,
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
                **bootstrap,
                "agentConfig": {
                    "airGapped": request.air_gapped,
                    **bootstrap.get("agentConfig", {}),
                    "nodeName": "{{ ds.meta_data.local_hostname }}",
                    "kubelet": {"extraArgs": ["provider-id=cloudstack:///{{ ds.meta_data.instance_id }}"]},
                    "enableContainerdSElinux": True,
                },
                "serverConfig": {
                    "cni": request.cni,
                    "disableComponents": {"kubernetesComponents": ["cloudController"]},
                    "etcd": {"customConfig": {"extraArgs": list(ETCD_LOG_ARGS)}},
                },
                "machineTemplate": {"spec": {
                    "infrastructureRef": {
                        "apiGroup": "infrastructure.cluster.x-k8s.io",
                        "kind": "CloudStackMachineTemplate",
                        "name": cp_template_name,
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
        worker_template_name = machine_template_name + ("-cpu-v2" if cpu_mode else "")
        resources.extend((
            _machine_template(worker_template_name, resolved, offering_id, template_id, cpu_mode=cpu_mode),
            {
                "apiVersion": "bootstrap.cluster.x-k8s.io/v1beta2",
                "kind": "RKE2ConfigTemplate",
                "metadata": _metadata(bootstrap_name, resolved),
                "spec": {"template": {"spec": {
                    "gzipUserData": False,
                        **bootstrap,
                    "agentConfig": {
                    "airGapped": request.air_gapped,
                    **bootstrap.get("agentConfig", {}),
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
                            "kind": "CloudStackMachineTemplate", "name": worker_template_name,
                        },
                    }},
                },
            },
        ))
    return tuple(resources)
