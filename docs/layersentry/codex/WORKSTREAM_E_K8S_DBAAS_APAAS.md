# Codex Workstream E — LayerSentry RKE2 / Kubernetes / Data Services

**Execution owner:** Codex  
**Primary objective:** finish one reusable LayerSentry RKE2 lifecycle end to end, then qualify upstream services through the same Flux package plane  
**Cloud baseline:** Apache CloudStack 4.22.1.1 + KVM  
**Customer distribution:** RKE2

This is the primary technical Codex stream.

## 1. Minimal startup

Read only:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_CURRENT_STATUS.md`;
4. this file;
5. current `tools/layersentry/k8s/release-candidate-lane-b.json` plus actual branch/workflow/live state.

Open `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`, the compact architecture addendum or historical evidence only when the current gate needs detailed storage/network/VIP/provider/version semantics or an architecture conflict must be resolved. Do not load historical expanded masters/ledger by default.

When working from a normal Git worktree, initialize/check the K8s writer guard from `tools/layersentry/governance/module-writer-guard.sh` before meaningful batches. After staging a K8s source batch and before committing, run `tools/layersentry/governance/module-writer-guard.sh precommit k8s`. `FOREIGN_MODULE_EDIT` is a hard stop: unstage the foreign path and hand it to its owning module; never work around the guard.

Every K8s source batch must pass the module-specific **LayerSentry K8s Source Validation** workflow. This is the cheap pre-live gate for Python syntax/unit tests, JSON/release-manifest integrity, downstream patch digests, systemd source checks and the commit-aware K8s path fence. A green source-validation workflow is `CI_VERIFIED` only for those checks; it does not promote E0/E1 runtime gates.

## 2. Hard file fence

Writable by the primary K8s writer:

- `tools/layersentry/k8s/**`;
- K8s-specific tests/evidence;
- `.github/workflows/layersentry-k8s-*` when a module-specific workflow directly closes the failing K8s gate.

Do not edit:

- `ui/**`;
- `tools/layersentry/single-os/**`;
- `tools/layersentry/ansible/**` unless the approved CAPI fallback has been formally selected and separately assigned;
- `tools/layersentry/dr*`;
- generic release/security workflows/tooling;
- global authority files.

If a generic release/signing workflow blocks an immutable K8s artifact, hand the exact requirement to the milestone release owner instead of expanding this workstream.

Only **one K8s source writer** is allowed at a time.

## 3. One lifecycle

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> central Flux
 -> selected packages/operators
```

The same lifecycle serves user Kubernetes, Kubernetes-backed DBaaS, APaaS and Streaming profiles. Profiles differ by worker pools, placement, storage, networking, security and package selection.

Ownership remains CloudStack -> IaaS, CAPI/CAPC -> Machines, CAPRKE2 -> RKE2 bootstrap/control plane, CCM -> L4 LB, CSI -> workload storage, Flux -> packages, upstream operators -> application/database lifecycle, LayerSentry -> UI/BFF/policy/audit/composite state.

### Current scope exclusions

This workstream does **not** implement or audit:

- VM-native Single-OS DBaaS/APaaS;
- cross-site RKE2 application DR;
- Kubernetes-backed DBaaS DC->DR replication/promotion/failback;
- APaaS cross-site DR;
- RKE2 RPO/RTO, cross-site DNS/VIP switching or RKE2 DR UI.

Do not turn those items into Workstream-E blockers unless the owner explicitly reopens scope. Independent DC/DR remains owned by Workstream D.

CSI/PVC project isolation, resize, stateful Machine replacement/PVC survival and DB backup/restore/PITR where advertised remain in scope because they are normal stateful-Kubernetes/DBaaS lifecycle capabilities, not cross-site DR.

## 4. Existing source must be reused

Current source already includes substantial:

- BFF/auth/RBAC;
- saga/journal/reconciliation;
- CloudStack client/preflight;
- CAPI/CAPC/CAPRKE2 resources;
- create/status/scale/delete executor;
- CAPC dual 6443/9345 endpoint and volume-ownership work;
- CCM Kubernetes 1.36 downstream work;
- CloudStack CSI project/idempotency work;
- NodeDiskSet;
- Flux resources;
- runtime/systemd wiring.

Do not rebuild these foundations or create adjacent frameworks.

## 5. First failing gate only

Close E0/E1 in this order:

```text
immutable artifacts
 -> deploy controller/BFF/reconciler
 -> create one real cluster
 -> CAPC creates CloudStack resources
 -> CAPRKE2 automatic join
 -> 6443
 -> 9345
 -> cluster Ready
 -> one primary CNI
 -> CCM/L4 lifecycle
 -> one safe CSI path
 -> Flux remote reconciliation
 -> status/scale
 -> worker replacement + PVC/data survival
 -> delete/cleanup
 -> restart/UNKNOWN reconciliation
 -> exact supported upgrade
 -> air-gap proof where claimed
```

Do not work on the next item while the current gate fails.

For each failure: capture exact evidence, classify the owning layer, fix the smallest correct owner inside this file fence, add regression coverage, rebuild/redeploy the affected immutable artifact and rerun the same step.

## 6. CAPC/CAPRKE2 stop-loss

CAPI/CAPC/CAPRKE2 remains preferred because substantial source already exists.

If a bounded qualification campaign repeatedly cannot achieve:

1. CloudStack VM/resource creation;
2. automatic RKE2 join;
3. reachable/owned 6443 and 9345;
4. cluster `Ready`;

and evidence shows continued provider maintenance is disproportionate, record a release decision and activate the approved fallback:

```text
native CloudStack APIs -> hardened QCOW2/cloud-init -> Ansible Runner -> RKE2 -> Flux
```

The fallback becomes a separately assigned implementation scope. Do not quietly start editing the shared Ansible tree before that decision.

## 7. Existing healthy RKE2 cluster — package qualification lane

The owner may provide a second already-working RKE2 cluster.

Use it to test, in parallel with primary lifecycle work:

- Flux remote/package reconciliation;
- OpenEverest install and supported DB lifecycle;
- OpenBao;
- Harbor;
- Strimzi/Kafka;
- package upgrade/remove/recovery;
- DB backup/restore where available/claimed;
- local-registry/offline package behavior.

This lane is test-only/read-mostly. It must not commit lifecycle source or create a second CAPI/CAPC/CAPRKE2 implementation.

Evidence from this cluster proves only scoped package/application behavior on that target. It does not by itself promote the complete LayerSentry K8s/DBaaS stack to `LIVE_VERIFIED`; the same pinned package must later pass on the LayerSentry-owned cluster path with certified CloudStack project/storage/network boundaries.

## 8. Upstream services — no rewrites

After base RKE2/CSI/CCM/Flux is live-proven, integration work is pinned manifests/Helm/Flux + policy + E2E.

Use:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB lifecycle;
- OpenBao supported Helm/OCI;
- Harbor supported Helm/OCI;
- Strimzi for Kafka.

Do not implement replacement DB operators, backup/PITR engines, DB failover engines, engine-upgrade controllers, Kafka operators, OpenBao/Harbor controllers or replacement upstream UIs.

LayerSentry integration is limited to Flux source/HelmRelease, namespace/RBAC/project policy, certified StorageClass, network/VIP/exposure policy, local/offline artifacts, health/status/audit and E2E qualification.

## 9. UI/backend traceability contract

Workstream E does not edit Vue/browser source. It must expose stable backend contracts and evidence that Workstream A can consume.

For every advertised K8s/DBaaS/APaaS action, the final audit should be able to trace, where applicable:

`UI -> API -> AUTHORIZATION -> BACKEND -> RECONCILER/OPERATOR -> K8S/STORAGE -> PERSISTENCE -> FAILURE PATH -> TEST -> LIVE EVIDENCE`

Do not report an overall UI/service percentage as production proof when individual actions have different evidence ceilings.

## 10. One platform carrier

Current V1 uses `layersentry-platform-<release>.iso` as one logical signed carrier. Bundled packages are `AVAILABLE`, not installed; Flux installs only selected packages.

## 11. Status and handoff

At a meaningful evidence milestone, update the K8s release candidate/module evidence. Do not append long history to the Progress Ledger. An integration/status reconciliation pass refreshes `LAYERSENTRY_CURRENT_STATUS.md` when the global summary materially changes.

Report only:

- exact branch/base/final commit;
- exact release/artifact digests;
- first/last vertical gate reached;
- tests/live actions actually executed;
- exact observed failure/root cause;
- storage/data-safety result;
- fallback decision if any;
- exact next gate.

Do not generate broad architecture documents from normal E2E work.