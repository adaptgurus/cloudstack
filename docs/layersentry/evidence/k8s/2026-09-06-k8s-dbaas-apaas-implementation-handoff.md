# LayerSentry K8s / DBaaS / APaaS — implementation handoff

**Date:** 2026-09-06  
**Repository:** `adaptgurus/cloudstack`  
**Branch:** `layersentry/4.22.1.1-ui`  
**Base before this Workstream E implementation slice:** `8b8937757c89a062a9ea524994f38e83c7dbfc32`  
**Implementation head before this handoff document:** `44cdfc41a8be1f87425dc4dd975d81f678ee4dec`  
**Module:** Kubernetes / DBaaS / APaaS / Streaming only  
**CloudStack-core impact:** **NO**  
**Runtime mutation:** **NONE**  
**Status:** `SOURCE_COMPLETE` for policy/UI foundation; **E0 NOT COMPLETE**; DBaaS production remains `BLOCKED`

## 1. Governing instructions read

The implementation was resumed only after reading the current branch copies of:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`
5. `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_ARCHITECTURE_ADDENDUM.md`
6. `docs/layersentry/evidence/k8s/2026-09-06-k8s-master-context-full-validation.md`
7. `docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`

The root policy file is `AGENTS.md` (plural), not `AGENT.md`.

## 2. Architecture/version tuple retained

No release-tuple architecture change was made. The current Lane B qualification candidate remains:

```text
CloudStack  4.22.1.1
CAPI        1.13.5
CAPC        0.6.1
CAPRKE2     0.25.2
RKE2        1.36.4+rke2r1
Kubernetes  1.36.x
CloudStack CSI 3.0.2 (qualification candidate)
```

This tuple remains `PENDING`, not production certified.

Controller ownership remains:

```text
CloudStack     -> IaaS authority
CAPI/CAPC      -> Cluster/Machine infrastructure lifecycle
CAPRKE2        -> RKE2 bootstrap/join/control-plane lifecycle
endpoint owner -> one lifecycle for 6443 + 9345
CloudStack CCM -> selected Kubernetes L4 cloud-provider lifecycle
Flux           -> selected package lifecycle
DB/app operator-> application/database lifecycle
LayerSentry    -> GUI, policy, profiles, compatibility, audit/evidence
```

No second VM scheduler, storage controller, Kubernetes lifecycle controller or database lifecycle controller was introduced.

## 3. Files added/changed by this slice

### Added

- `tools/layersentry/k8s/layersentry_k8s_policy.py`
- `tools/layersentry/k8s/test_layersentry_k8s_policy.py`
- `tools/layersentry/k8s/release-candidate-lane-b.json`
- `ui/src/views/layersentry/k8sDataServices.js`
- `ui/src/views/layersentry/KubernetesDataServices.vue`
- `ui/tests/unit/layersentry/k8sDataServices.spec.js`

### Changed

- `ui/src/config/router.js`
  - adds `/kubernetes-data-services`
  - visible only in the LayerSentry KVM profile unless explicitly disabled by `layersentry.features.kubernetesDataServices.enabled=false`

### Concurrent file not owned by this workstream

Between the recorded base and this slice, another commit/session also modified:

- `ui/src/views/layersentry/quickProvision.js`

This K8s/Data Services work did **not** edit or overwrite that file. Treat it as concurrent Workstream A/VM self-service work, not part of this Workstream E implementation.

## 4. What the new source implements

### Policy/controller contract

`tools/layersentry/k8s/layersentry_k8s_policy.py` now provides:

- typed service kinds for Kubernetes, DBaaS, APaaS and Streaming;
- release-channel and release-gate models;
- StorageProfile contract with RWO/RWX, database/NVMe and direct-node-disk distinctions;
- ClusterRequest/NodePoolRequest models;
- DatabaseRequest model;
- ApplicationRequest model for OpenBao/Harbor/Strimzi Kafka;
- fail-closed cluster validation;
- fail-closed DBaaS validation;
- fail-closed APaaS/Streaming validation;
- controller-owned, idempotency-keyed workflow plans;
- readiness projection suitable for a future BFF/API.

The policy explicitly rejects:

- a managed cluster if the RKE2 `9345` endpoint gate is not passed;
- arbitrary direct node disks before NodeDiskSet ownership is implemented/certified;
- stateful DBaaS while CAPC volume ownership/data-survival is unresolved;
- non-NVMe production DB storage under the current DBaaS profile;
- durable data on direct node disks;
- PITR before retained recovery-point restore evidence passes;
- external APaaS exposure without a LayerSentry Frontend/VIP lifecycle object.

### UI product surface

`KubernetesDataServices.vue` adds one LayerSentry customer surface for:

- K8s clusters;
- DBaaS;
- APaaS;
- Streaming.

It displays:

- the exact Lane B release candidate;
- mandatory release gates and their current pass/block state;
- Kubernetes cluster request fields;
- controller ownership preview;
- DBaaS target topology/storage/provider contract;
- OpenBao and Harbor APaaS entries;
- Kafka/Strimzi streaming entry.

The page intentionally fails closed. With no validated runtime gate state configured, mutation buttons remain blocked.

## 5. Tests/source checks added

Python unit-test source covers:

- mandatory `9345` gate;
- controller ownership for cluster plans;
- direct-node-disk fail-closed behavior;
- CAPC volume-ownership DBaaS blocker;
- NVMe DB storage rule;
- PITR evidence gate;
- OpenEverest delegation for PostgreSQL;
- APaaS base-gate and Frontend requirements;
- readiness blocker reporting.

Vue/Jest source covers:

- default fail-closed gates;
- `9345` requirement;
- CAPC DBaaS safety gate;
- NodeDiskSet blocker;
- NVMe database storage validation;
- external Frontend requirement;
- controller ownership.

### Checks actually run

No repository CI check or live runtime test completed in this chat session.

GitHub combined status for implementation head `44cdfc41a8be1f87425dc4dd975d81f678ee4dec` returned no status checks.

The existing branch already records an npm/package-lock mismatch in the global progress ledger, so this handoff does **not** claim `CI_VERIFIED`.

No Rocky Linux 9 / `adaptgurus/cozystack` runner mutation was performed, so this handoff does **not** claim `LIVE_VERIFIED`.

## 6. Hard blockers that remain

### E0 blocker 1 — CAPC RKE2 endpoint ownership

The selected provider path must own and reconcile one HA control-plane frontend with at least:

```text
VIP/FQDN:6443 -> RKE2 server nodes:6443
VIP/FQDN:9345 -> RKE2 server nodes:9345
```

The current repository policy/UI models this requirement, but no CAPC/provider runtime patch has been added here because CAPC is an external provider source, not CloudStack Java core.

### E0 blocker 2 — CAPC DATADISK deletion/data loss

Current validated upstream CAPC behavior can include every attached `DATADISK` volume ID during VM destruction. Stateful production remains blocked until the provider implementation deletes only Machine-owned disks and proves CSI/unowned volumes survive delete/rollout/repair/scale-down.

This is the **first stateful production blocker**. Do not bypass it in the UI/BFF.

### E0 blocker 3 — NodeDiskSet

Multiple direct worker disks are still `PENDING`. Implement an ownership/tag/retain/delete/resize/replacement contract before enabling this field.

### E0 blocker 4 — CloudStack CSI qualification

CloudStack CSI `3.0.2` still requires CloudStack `4.22.1.1` project-scoped create/attach/detach/snapshot/restore/resize/idempotency qualification before project PVC auto-grow is enabled.

### E0 blocker 5 — air gap and lifecycle evidence

Deny-all-egress create/scale/repair/replace/package/backup/restore/upgrade is still `NOT_TESTED` for the exact tuple.

## 7. DBaaS/APaaS status after this slice

```text
Base K8s policy/UI foundation        SOURCE_COMPLETE
Lane B runtime reconciliation        PENDING
6443 + 9345 endpoint runtime         BLOCKED/PENDING
CAPC volume ownership fix            BLOCKED/PENDING
NodeDiskSet                           PENDING
CloudStack CSI qualification          PENDING
Flux remote package lifecycle         PENDING runtime proof
PostgreSQL DBaaS mutation              BLOCKED by E0
MySQL/MongoDB DBaaS mutation           BLOCKED by E0/PostgreSQL-first rule
Redis/Valkey mutation                  BLOCKED by stateful E0 where persistent
OpenBao/Harbor mutation                BLOCKED until base/runtime gates pass
Kafka/Strimzi mutation                 BLOCKED until base/runtime gates pass
Air-gap certification                  NOT_TESTED
Production certification               NOT established
```

## 8. Exact next-chat continuation instruction

The next chat must **not restart architecture research or rewrite this foundation** unless new evidence requires it.

Resume in this exact order:

1. Fetch `layersentry/4.22.1.1-ui` and verify branch head is this handoff commit or a descendant.
2. Read this handoff and `WORKSTREAM_E_K8S_DBAAS_APAAS.md`.
3. Preserve any concurrent `quickProvision.js`/Workstream A changes.
4. Continue **E0**, not PostgreSQL UI wiring first.
5. Implement/package the CAPC-owned `6443 + 9345` endpoint change in the correct external-provider/downstream integration location; do not patch CloudStack Java core for it.
6. Implement/package the CAPC Machine-volume ownership fix so only Machine-owned disks are destroyed; CSI/unowned volumes must be preserved.
7. Add exact tests for both fixes, including destructive PVC survival cases.
8. Only after those source gates are complete, wire a LayerSentry BFF/controller endpoint that consumes the policy contract and CAPI/Kubernetes APIs.
9. Then complete E1 cluster create/status/delete/scale and central Flux reconciliation.
10. Only after E0/E1 runtime evidence passes, enable PostgreSQL DBaaS mutations; follow with MySQL/MongoDB, Redis/Valkey, OpenBao, Harbor and Strimzi in the Workstream E order.
11. Keep every unverified runtime claim below `LIVE_VERIFIED`.
12. Append a new dated evidence/handoff with exact final commit, tests and remaining gates.

## 9. Recovery / rollback

This slice does not mutate runtime resources or CloudStack schema.

Source rollback is bounded to the Workstream E commits/files listed above. The code intentionally defaults all release gates to false, so an incomplete runtime integration fails closed instead of dispatching provisioning actions.

Do not roll back the concurrent `quickProvision.js` change when reverting this K8s/Data Services slice unless that other workstream explicitly requests it.
