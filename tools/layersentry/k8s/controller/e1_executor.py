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

"""One-step reconciler for the E1 CAPI/CAPC/CAPRKE2/Flux vertical slice."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping, Protocol

from layersentry_k8s_policy import ReleaseGates

from .e1_resources import ResolvedInfrastructure, build_cluster_resources
from .flux_resources import FluxBaseline, build_flux_baseline
from .kubernetes import KubernetesClient
from .model import InvalidRequestError, NotFoundError, Operation
from .service import StepOutcome, StepResult, parse_cluster_request


class InfrastructureResolver(Protocol):
    """Read-only CloudStack/profile resolution; implementations must enforce caller project scope."""

    def resolve_cluster(self, request: Mapping[str, Any]) -> ResolvedInfrastructure: ...

    def verify_endpoints(self, resolved: ResolvedInfrastructure) -> Mapping[str, Any]: ...


def _ready_condition(resource: Mapping[str, Any], condition_type: str = "Ready") -> bool:
    status = resource.get("status")
    if not isinstance(status, Mapping):
        return False
    if status.get("ready") is True and condition_type == "Ready":
        return True
    conditions = status.get("conditions", [])
    return any(
        isinstance(item, Mapping)
        and item.get("type") == condition_type
        and item.get("status") == "True"
        and item.get("observedGeneration", resource.get("metadata", {}).get("generation"))
            == resource.get("metadata", {}).get("generation")
        for item in conditions
    )


class E1Executor:
    def __init__(
        self, kubernetes: KubernetesClient, resolver: InfrastructureResolver,
        gates: ReleaseGates, flux: FluxBaseline,
    ):
        self.kubernetes = kubernetes
        self.resolver = resolver
        self.gates = gates
        self.flux = flux

    def _resolved(self, operation: Operation) -> ResolvedInfrastructure:
        value = operation.resources.get("resolvedInfrastructure")
        if not isinstance(value, Mapping):
            raise InvalidRequestError("CloudStack infrastructure has not been resolved")
        try:
            return ResolvedInfrastructure(**value)
        except TypeError as exc:
            raise InvalidRequestError("stored infrastructure resolution is invalid") from exc

    def _resources(self, operation: Operation):
        return build_cluster_resources(parse_cluster_request(operation.request), self._resolved(operation))

    def _apply(self, resources, detail: str) -> StepResult:
        applied = []
        for resource in resources:
            result = self.kubernetes.apply(resource)
            metadata = result.get("metadata", {})
            applied.append({
                "apiVersion": resource["apiVersion"], "kind": resource["kind"],
                "namespace": resource["metadata"].get("namespace"), "name": resource["metadata"]["name"],
                "uid": metadata.get("uid"), "generation": metadata.get("generation"),
            })
        return StepResult(StepOutcome.CONVERGED, {"lastApplied": applied}, detail)

    def reconcile(self, operation: Operation, step: Mapping[str, Any]) -> StepResult:
        action = step.get("action")
        if action == "scale-worker-pool":
            request = operation.request
            resource = {
                "apiVersion": "cluster.x-k8s.io/v1beta2", "kind": "MachineDeployment",
                "metadata": {
                    "name": f"{request['cluster_name']}-{request['node_pool']}",
                    "namespace": request["namespace"],
                },
            }
            actual = self.kubernetes.get(resource)
            labels = actual.get("metadata", {}).get("labels", {})
            if labels.get("layersentry.io/managed") != "true" or labels.get("layersentry.io/project") != operation.project_id:
                return StepResult(StepOutcome.FAILED, detail="MachineDeployment ownership/project verification failed")
            current = actual.get("spec", {}).get("replicas")
            desired = request["replicas"]
            if not isinstance(current, int):
                return StepResult(StepOutcome.FAILED, detail="MachineDeployment current replica count is missing")
            if desired < current and not self.gates.capc_volume_ownership_safe:
                return StepResult(StepOutcome.FAILED, detail="scale-down is blocked until CAPC volume ownership is live-verified")
            if current != desired:
                self.kubernetes.patch_merge(resource, {"spec": {"replicas": desired}})
                return StepResult(StepOutcome.PENDING, detail="MachineDeployment replica target updated")
            available = actual.get("status", {}).get("availableReplicas", 0)
            if available != desired:
                return StepResult(StepOutcome.PENDING, detail="waiting for worker replicas to become available")
            return StepResult(StepOutcome.CONVERGED, {
                "scale": {"nodePool": request["node_pool"], "replicas": desired},
            }, "worker pool scale converged")
        if action == "delete-cluster":
            request = operation.request
            resource = {
                "apiVersion": "cluster.x-k8s.io/v1beta2", "kind": "Cluster",
                "metadata": {"name": request["cluster_name"], "namespace": request["namespace"]},
            }
            try:
                actual = self.kubernetes.get(resource)
            except NotFoundError:
                return StepResult(StepOutcome.CONVERGED, detail="CAPI Cluster is absent")
            labels = actual.get("metadata", {}).get("labels", {})
            if labels.get("layersentry.io/managed") != "true" or labels.get("layersentry.io/project") != operation.project_id:
                return StepResult(StepOutcome.FAILED, detail="Cluster ownership/project verification failed")
            if actual.get("metadata", {}).get("deletionTimestamp"):
                return StepResult(StepOutcome.PENDING, detail="CAPI Cluster deletion is in progress")
            self.kubernetes.delete(resource)
            return StepResult(StepOutcome.PENDING, detail="CAPI Cluster deletion requested; CAPC remains VM authority")
        if action == "resolve-certified-release":
            if not self.gates.kubernetes_ready():
                return StepResult(StepOutcome.FAILED, detail="release evidence gates are no longer satisfied")
            return StepResult(StepOutcome.CONVERGED, {
                "release": {
                    "cloudstack": "4.22.1.1", "capi": "1.13.5", "capc": "0.6.1",
                    "caprke2": "0.25.2", "rke2": "v1.36.4+rke2r1",
                },
            }, "release tuple selected")
        if action == "resolve-iaas-inputs":
            resolved = self.resolver.resolve_cluster(operation.request)
            return StepResult(
                StepOutcome.CONVERGED, {"resolvedInfrastructure": asdict(resolved)},
                "CloudStack inputs resolved by exact IDs",
            )

        resources = self._resources(operation)
        if action == "reconcile-infrastructure":
            selected = [item for item in resources if item["kind"] in {
                "CloudStackCluster", "CloudStackMachineTemplate", "Cluster",
            }]
            return self._apply(selected, "CAPI/CAPC infrastructure desired state applied")
        if action == "reconcile-control-plane":
            return self._apply(
                [item for item in resources if item["kind"] == "RKE2ControlPlane"],
                "CAPRKE2 control plane desired state applied",
            )
        if action == "reconcile-6443-and-9345":
            cluster = next(item for item in resources if item["kind"] == "CloudStackCluster")
            actual = self.kubernetes.get(cluster)
            if not _ready_condition(actual):
                return StepResult(StepOutcome.PENDING, detail="CAPC endpoint infrastructure is not Ready")
            endpoint = self.resolver.verify_endpoints(self._resolved(operation))
            if endpoint.get("endpoint6443") is not True or endpoint.get("endpoint9345") is not True:
                return StepResult(StepOutcome.PENDING, detail="waiting for exact CAPC-owned 6443 and 9345 rules")
            safe = {
                key: endpoint.get(key)
                for key in ("publicIpId", "endpoint6443RuleId", "endpoint9345RuleId")
                if endpoint.get(key)
            }
            return StepResult(StepOutcome.CONVERGED, {"endpoint": safe}, "both CAPC-owned endpoint rules resolved")
        if action == "reconcile-worker-pools":
            return self._apply(
                [item for item in resources if item["kind"] in {"RKE2ConfigTemplate", "MachineDeployment"}],
                "CAPI worker pools desired state applied",
            )
        if action == "reconcile-cloud-provider":
            flux = build_flux_baseline(operation.target_name, self._resolved(operation).namespace, self.flux)
            return self._apply(flux[:1], "immutable central Flux source applied for CCM/CSI baseline")
        if action == "reconcile-baseline-packages":
            flux = build_flux_baseline(operation.target_name, self._resolved(operation).namespace, self.flux)
            return self._apply(flux[1:], "central Flux baseline reconciliation applied")
        if action == "verify-cluster-readiness":
            required = [item for item in resources if item["kind"] in {
                "Cluster", "RKE2ControlPlane", "MachineDeployment",
            }]
            pending = []
            for desired in required:
                actual = self.kubernetes.get(desired)
                if not _ready_condition(actual, "Available") and not _ready_condition(actual):
                    pending.append(f"{desired['kind']}/{desired['metadata']['name']}")
            flux = build_flux_baseline(operation.target_name, self._resolved(operation).namespace, self.flux)[1]
            if not _ready_condition(self.kubernetes.get(flux)):
                pending.append(f"Kustomization/{flux['metadata']['name']}")
            if pending:
                return StepResult(StepOutcome.PENDING, detail="waiting for: " + ", ".join(pending))
            return StepResult(StepOutcome.CONVERGED, detail="CAPI, CAPRKE2 and Flux report current generations Ready")
        return StepResult(StepOutcome.FAILED, detail=f"unsupported workflow action: {action}")

    def observe_ambiguous(self, operation: Operation, step: Mapping[str, Any]) -> StepResult:
        action = step.get("action")
        if action in {"scale-worker-pool", "delete-cluster"}:
            # Both paths begin with an authoritative GET and converge from
            # observed desired/deletion state before issuing another mutation.
            return self.reconcile(operation, step)
        if action in {"resolve-certified-release", "resolve-iaas-inputs"}:
            return StepResult(StepOutcome.RETRYABLE, detail="read-only resolution may be retried")
        resources = self._resources(operation)
        kinds = {
            "reconcile-infrastructure": {"CloudStackCluster", "CloudStackMachineTemplate", "Cluster"},
            "reconcile-control-plane": {"RKE2ControlPlane"},
            "reconcile-worker-pools": {"RKE2ConfigTemplate", "MachineDeployment"},
        }.get(action)
        if kinds is None and action in {"reconcile-cloud-provider", "reconcile-baseline-packages"}:
            flux = build_flux_baseline(operation.target_name, self._resolved(operation).namespace, self.flux)
            resources = flux[:1] if action == "reconcile-cloud-provider" else flux[1:]
        elif kinds is not None:
            resources = [item for item in resources if item["kind"] in kinds]
        else:
            return StepResult(StepOutcome.RETRYABLE, detail="non-mutating status step may be retried")
        missing = []
        observed = []
        for resource in resources:
            try:
                actual = self.kubernetes.get(resource)
            except NotFoundError:
                missing.append(f"{resource['kind']}/{resource['metadata']['name']}")
                continue
            observed.append({
                "kind": resource["kind"], "name": resource["metadata"]["name"],
                "uid": actual.get("metadata", {}).get("uid"),
            })
        if missing:
            return StepResult(
                StepOutcome.RETRYABLE, {"observedAfterUnknown": observed},
                "authoritative GET proved resources absent: " + ", ".join(missing),
            )
        return StepResult(
            StepOutcome.CONVERGED, {"observedAfterUnknown": observed},
            "authoritative GET found every resource after ambiguous apply",
        )

    def cluster_status(self, namespace: str, name: str, project_id: str) -> Mapping[str, Any]:
        cluster_ref = {
            "apiVersion": "cluster.x-k8s.io/v1beta2", "kind": "Cluster",
            "metadata": {"namespace": namespace, "name": name},
        }
        control_plane_ref = {
            "apiVersion": "controlplane.cluster.x-k8s.io/v1beta2", "kind": "RKE2ControlPlane",
            "metadata": {"namespace": namespace, "name": f"{name}-control-plane"},
        }
        cluster = self.kubernetes.get(cluster_ref)
        labels = cluster.get("metadata", {}).get("labels", {})
        if labels.get("layersentry.io/managed") != "true" or labels.get("layersentry.io/project") != project_id:
            raise InvalidRequestError("cluster ownership/project verification failed")
        try:
            control_plane = self.kubernetes.get(control_plane_ref)
        except NotFoundError:
            control_plane = {}
        return {
            "name": name,
            "namespace": namespace,
            "ready": _ready_condition(cluster, "Available") or _ready_condition(cluster),
            "phase": cluster.get("status", {}).get("phase", "UNKNOWN"),
            "controlPlaneReady": bool(control_plane) and (
                _ready_condition(control_plane, "Available") or _ready_condition(control_plane)
            ),
            "conditions": cluster.get("status", {}).get("conditions", []),
            "observedGeneration": cluster.get("metadata", {}).get("generation"),
        }
