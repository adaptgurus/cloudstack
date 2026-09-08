# LayerSentry K8s / DBaaS / APaaS — Production Integration Addendum

**Status:** `DESIGN_DEFINED`  
**Role:** exact integration constraints that supplement the compact Kubernetes specialist master  
**Baseline:** Apache CloudStack 4.22.1.1 + KVM

The prior expanded validation narrative remains available in Git history. This file intentionally keeps only constraints that materially prevent unsafe implementation or false production claims. Exact current versions/status live in `tools/layersentry/k8s/release-candidate-lane-b.json` and focused evidence.

## 1. Release tuple is atomic

CAPI, CAPC, CAPRKE2, RKE2, OS/QCOW2, CNI, CCM and CSI are not selected independently. LayerSentry promotes one tested tuple.

Do not infer production compatibility from individual upstream releases. Actual CloudStack reconciliation, automatic RKE2 join, lifecycle operations and data safety must pass for the exact tuple.

If the current CAPC lane cannot pass the bounded qualification criteria and maintenance becomes disproportionate, use the formally approved fallback from the Execution Contract. Do not run both lifecycle owners in the same release.

## 2. RKE2 endpoint requires 6443 and 9345

The selected LayerSentry endpoint authority must provide stable reachability for the Kubernetes API (`6443`) and RKE2 supervisor/registration (`9345`) required by the exact CAPRKE2/RKE2 release.

One owner must reconcile the VIP and both required rules. Do not split ownership across unrelated controllers without an explicit reconciliation contract.

A green Kubernetes API alone does not prove automatic RKE2 join.

## 3. CAPC Machine deletion must be workload-volume safe

A CAPI Machine/CloudStack VM can have:

- CAPC-owned deploy-time/node resources;
- later-attached CSI workload volumes;
- explicitly LayerSentry-owned node disks.

CAPC deletion must destroy only resources proven to belong to the Machine lifecycle. An attached CSI/unowned workload volume must not be deleted merely because it is present at VM deletion time.

Required destructive evidence before stateful remediation/scale-down/rollout is certified:

1. create PVC and write identifiable data;
2. attach/mount on a worker;
3. replace/delete the Machine;
4. prove backend volume/PVC survives;
5. attach to replacement node and verify identical data;
6. repeat for any upgrade/scale-down/remediation behavior the release advertises.

Until this passes, automatic stateful remediation and unsafe DB-worker scale-down remain disabled.

## 4. NodeDiskSet is separate from PVC storage

Additional node-attached CloudStack disks require explicit ownership metadata and lifecycle intent, including at least owner, CloudStack volume ID, disk offering/tier, purpose, retain/delete policy, resize policy and replacement behavior.

Durable DB/application data uses certified CSI/PVC storage. Direct node disks are initially limited to approved scratch/cache/container-host purposes after qualification.

No node disk is deleted solely because it was attached to a Machine.

## 5. CloudStack CSI project/resize qualification remains mandatory

A newer driver implementation or source fix does not close the live gate.

For the exact selected CSI build on CloudStack 4.22.1.1, test the applicable project-scoped lifecycle:

- provision;
- attach/mount;
- detach;
- snapshot/restore if offered;
- repeated resize/expansion if offered;
- delete;
- restart/reconcile after ambiguous result.

Automatic PVC growth remains disabled until repeated/idempotent expansion is live-qualified.

## 6. Stateful safety is not RKE2 DR

The current Kubernetes/Data Services scope requires CSI/PVC persistence, stateful Machine replacement safety and DB backup/restore/PITR where advertised.

It does **not** currently include:

- cross-site RKE2 application DR;
- database DC->DR replication/promotion/failback;
- APaaS DR;
- RKE2 RPO/RTO or cross-site DNS/VIP switching;
- RKE2 DR UI.

Do not convert those excluded items into Workstream-E blockers. The independent LayerSentry DR workstream remains separate.

## 7. Upstream services are integration targets

Use pinned/qualified upstream lifecycle implementations:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB;
- OpenBao supported Helm/OCI;
- Harbor supported Helm/OCI;
- Strimzi for Kafka.

LayerSentry adds policy, package reconciliation, storage/network choices, local/offline artifacts, status/audit and customer-facing integration.

Do not write replacement database/Kafka/application operators, DB backup/PITR engines or replacement upstream UIs.

Upstream air-gap/support claims must be revalidated for the exact release. LayerSentry offline support requires LayerSentry's own immutable artifact closure and deny-all-egress proof.

## 8. UI/API completion is vertical, not screen-based

For each advertised Kubernetes/DBaaS/APaaS action, production audit must trace:

`UI -> API -> AUTHORIZATION -> BACKEND -> RECONCILER/OPERATOR -> K8S/STORAGE -> PERSISTENCE -> FAILURE PATH -> TEST -> LIVE EVIDENCE`

A UI screen, API route, CRD or installed operator is not a complete feature.

No overall UI percentage may be used as production proof without the underlying per-capability traceability.

## 9. Completion rule

The specialist architecture suite is current when these are mutually consistent:

1. `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` — stable scope/architecture/production contract;
2. this addendum — exact integration safety constraints;
3. `codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md` — implementation ownership/order;
4. `tools/layersentry/k8s/release-candidate-lane-b.json` — current machine-readable release/gates;
5. focused current evidence for exact artifacts/live results.

None of these documents by themselves make the module `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED`.