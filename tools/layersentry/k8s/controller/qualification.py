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

"""Explicit, expiring first-cluster lane; production readiness is never promoted."""
from __future__ import annotations
import hashlib
import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from layersentry_k8s_policy import ValidationError
from .components import load_release_contract, qualification_template
from .model import InvalidRequestError, NotFoundError


def allocated_control_plane_compute(kubernetes, resolver, resolved, request, host_id):
    """Read exact CAPI -> CAPC -> native VM identities, never infer by VM name.

    Only existing Running control planes count. Workers, RAM and storage remain
    fully reserved, making interrupted/restarted admission conservative.
    """
    from urllib.parse import urlencode
    from .capacity import integer
    if kubernetes is None:
        return {}
    namespace, name = resolved.namespace, request["name"]
    def get(group, version, plural, object_name):
        if any(not isinstance(v, str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", v)
               for v in (namespace, object_name)):
            raise InvalidRequestError("Invalid qualification object identity")
        return kubernetes.request("GET", f"/apis/{group}/{version}/namespaces/{namespace}/{plural}/{object_name}")
    def owned(child, kind, parent):
        refs = [r for r in child.get("metadata", {}).get("ownerReferences", []) if r.get("kind") == kind]
        meta = parent.get("metadata", {})
        return (bool(meta.get("uid")) and len(refs) == 1 and refs[0].get("uid") == meta["uid"]
                and refs[0].get("name") == meta.get("name"))
    def managed(resource):
        meta = resource.get("metadata", {})
        return (meta.get("namespace") == namespace and not meta.get("deletionTimestamp")
                and meta.get("labels", {}).get("layersentry.io/managed") == "true"
                and meta.get("labels", {}).get("layersentry.io/project") == resolved.project_id)
    try:
        cluster = get("cluster.x-k8s.io", "v1beta2", "clusters", name)
    except NotFoundError:
        return {}
    if not managed(cluster):
        raise InvalidRequestError("Qualification Cluster ownership mismatch")
    try:
        cp = get("controlplane.cluster.x-k8s.io", "v1beta2", "rke2controlplanes", name+"-control-plane")
    except NotFoundError:
        return {}
    if (not managed(cp) or not owned(cp, "Cluster", cluster)
            or cp.get("spec", {}).get("replicas") != request["control_plane_replicas"]):
        raise InvalidRequestError("Qualification control-plane ownership mismatch")
    query = urlencode({"labelSelector": f"cluster.x-k8s.io/cluster-name={name},cluster.x-k8s.io/control-plane", "limit": 4})
    rows = kubernetes.request("GET", f"/apis/cluster.x-k8s.io/v1beta2/namespaces/{namespace}/machines?{query}")
    if (not isinstance(rows.get("items"), list) or rows.get("metadata", {}).get("continue")
            or len(rows["items"]) > request["control_plane_replicas"]):
        raise InvalidRequestError("Qualification control-plane inventory is ambiguous")
    offering = resolver._exact("listServiceOfferings", "serviceoffering", request["control_plane_service_offering_id"])
    cores = integer(offering.get("cpunumber"), "control-plane CPU", 2)
    speed = integer(offering.get("cpuspeed"), "control-plane MHz", 1)
    observed, seen = {}, set()
    for machine in rows["items"]:
        meta, spec = machine.get("metadata", {}), machine.get("spec", {})
        ref = spec.get("infrastructureRef", {})
        if (meta.get("namespace") != namespace or meta.get("deletionTimestamp")
                or not meta.get("uid") or meta["uid"] in seen or not owned(machine, "RKE2ControlPlane", cp)
                or spec.get("clusterName") != name or ref.get("kind") != "CloudStackMachine"
                or ref.get("apiGroup") != "infrastructure.cluster.x-k8s.io"):
            raise InvalidRequestError("Qualification Machine ownership mismatch")
        seen.add(meta["uid"])
        capc = get("infrastructure.cluster.x-k8s.io", "v1beta3", "cloudstackmachines", ref.get("name", ""))
        cs = capc.get("spec", {})
        if (capc.get("metadata", {}).get("namespace") != namespace
                or capc.get("metadata", {}).get("deletionTimestamp") or not owned(capc, "Machine", machine)
                or cs.get("offering", {}).get("id") != request["control_plane_service_offering_id"]
                or cs.get("template", {}).get("id") != request["control_plane_image_id"]):
            raise InvalidRequestError("Qualification CAPC ownership/profile mismatch")
        vm_id = cs.get("instanceID")
        if not vm_id:
            continue  # CAPC has not yet established any authoritative allocation.
        if (not isinstance(vm_id, str) or not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", vm_id)
                or vm_id in observed or cs.get("providerID") != "cloudstack:///"+vm_id):
            raise InvalidRequestError("Qualification CAPC instance identity mismatch")
        vm = resolver._exact("listVirtualMachines", "virtualmachine", vm_id, projectid=resolved.project_id)
        if (vm.get("projectid") != resolved.project_id or vm.get("zoneid") != resolved.zone_id
                or vm.get("hostid") != host_id or vm.get("serviceofferingid") != request["control_plane_service_offering_id"]
                or vm.get("templateid") != request["control_plane_image_id"]
                or vm.get("cpunumber") != cores or vm.get("cpuspeed") != speed
                or vm.get("memory") != offering.get("memory")
                or not any(n.get("networkid") == resolved.network_id and n.get("isdefault") is True for n in vm.get("nic", []))):
            raise InvalidRequestError("Qualification native VM scope/profile mismatch")
        if vm.get("state") == "Running":
            observed[vm_id] = {"cpu": cores, "cpu_mhz": cores * speed}
    return observed

DEFERRED = frozenset({
    "CloudStack CCM v1.2.0 is not qualified with Kubernetes 1.36",
    "CloudStack CSI project lifecycle is not qualified",
    "CloudStack CSI resize idempotency is not live-qualified",
    *["E1 evidence gate " + g + " is false" for g in
      ("tupleReconciliation", "endpoint6443", "endpoint9345", "fluxRemoteReconcile")],
})

def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

class FirstClusterQualification:
    def __init__(self, path, release_path, store, *, previous_context=None):
        self.path = Path(path)
        self.release_path = Path(release_path)
        if (not self.path.is_absolute() or self.path.is_symlink() or not self.path.is_file()
                or self.path.stat().st_mode & 0o022):
            raise InvalidRequestError("qualification context must be a protected regular file")
        self.raw = self.path.read_bytes()
        from .components import _unique_object
        self.context = json.loads(self.raw, object_pairs_hook=_unique_object)
        required = {"schemaVersion", "mode", "expiresAt", "releaseSha256", "requestSha256",
                    "idempotencyKey", "hostEvidence", "clusterId", "hostId", "poolId"}
        if (set(self.context) != required or self.context["schemaVersion"] != "1.0"
                or self.context["mode"] != "first-cluster-qualification"):
            raise InvalidRequestError("qualification context fields invalid")
        if any(not isinstance(self.context[k], str) or not re.fullmatch("[0-9a-f]{64}", self.context[k])
               for k in ("releaseSha256", "requestSha256")):
            raise InvalidRequestError("qualification digest invalid")
        self.store = store
        self.check()
        if previous_context is not None:
            old = dict(previous_context); new = dict(self.context)
            old.pop("releaseSha256", None); new.pop("releaseSha256", None)
            if old != new:
                raise InvalidRequestError("qualification revision may only change release identity")
            self.store.revise_qualification_release(fingerprint(previous_context), fingerprint(self.context))
        self.store.bind_qualification(fingerprint(self.context))

    def check(self):
        if self.path.read_bytes() != self.raw:
            raise InvalidRequestError("qualification context changed; restart required")
        expiry = datetime.fromisoformat(self.context["expiresAt"].replace("Z", "+00:00"))
        remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
        if not 0 < remaining <= 7 * 86400:
            raise InvalidRequestError("qualification context expired or exceeds seven days")
        if hashlib.sha256(self.release_path.read_bytes()).hexdigest() != self.context["releaseSha256"]:
            raise InvalidRequestError("qualification release changed")
        contract = load_release_contract(self.release_path)
        if set(contract.readiness.blockers) - DEFERRED:
            raise InvalidRequestError("qualification immutable artifacts are not ready")
        self.manifest = contract.manifest
        return contract

    def validate_request(self, request):
        self.check()
        self.store.bind_qualification(fingerprint(self.context))
        value = asdict(request); value["channel"] = request.channel.value
        lock = qualification_template(self.manifest)
        if (fingerprint(value) != self.context["requestSha256"]
                or request.project_id != lock["projectId"]
                or request.control_plane_image_id != lock["template"]["id"]
                or request.control_plane_replicas != 3 or len(request.node_pools) != 1
                or request.node_pools[0].replicas != 1
                or request.node_pools[0].image_id != request.control_plane_image_id
                or request.cni != "canal" or not request.air_gapped
                or request.channel.value != "preview"
                or any(p.direct_node_disks or p.node_disk_set_id or p.storage_profile_ids or p.gpu for p in request.node_pools)):
            raise ValidationError("request is outside the exact first-cluster qualification")

    def operator_actor(self, client):
        from .auth import CloudStackSessionAuthenticator
        from .model import Actor, AuthenticationError
        self.check()
        capabilities = CloudStackSessionAuthenticator._capabilities(client.call("listApis", {}))
        project = qualification_template(self.manifest)["projectId"]
        rows = client.call("listProjects", {"id": project}).get("project", [])
        if len(rows) != 1 or rows[0].get("id") != project or rows[0].get("state") != "Active":
            raise AuthenticationError("qualification API credential lacks active project access")
        identity = hashlib.sha256(client.config.api_key_file.read_bytes()).hexdigest()
        return Actor(subject="cloudstack-api-qualification:"+identity, account_id="", domain_id="",
                     project_ids=(project,), capabilities=capabilities)

    def admit_capacity(self, resolver, request, *, kubernetes=None):
        from .capacity import plan_cluster, discover_capacity, assess_capacity
        resolved, plan = plan_cluster(resolver, request)
        path = Path(self.context["hostEvidence"])
        if not path.is_absolute() or path.is_symlink() or path.stat().st_mode & 0o022:
            raise InvalidRequestError("qualification host evidence path invalid")
        host = json.loads(path.read_text())
        before = allocated_control_plane_compute(kubernetes, resolver, resolved, request, self.context["hostId"])
        snapshot = discover_capacity(resolver, resolved, self.context["clusterId"],
                                     self.context["hostId"], self.context["poolId"])
        after = allocated_control_plane_compute(kubernetes, resolver, resolved, request, self.context["hostId"])
        if before != after:
            raise InvalidRequestError("Qualification allocation changed during capacity observation")
        compute = {k: sum(v[k] for v in after.values()) for k in ("cpu", "cpu_mhz")}
        result = assess_capacity(snapshot, plan, host, allocated_compute=compute)
        if result["decision"] != "PROVISION_ALLOWED":
            raise InvalidRequestError("fresh qualification capacity admission failed")
        return result
