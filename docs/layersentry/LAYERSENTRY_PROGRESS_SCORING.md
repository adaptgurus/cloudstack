# LayerSentry V1 — Evidence-Weighted Progress Scoring V2

**Rubric version:** `2.0`  
**Effective:** 2026-09-07  
**Historical rubric:** `LAYERSENTRY_PROGRESS_SCORING_V1.md`

## Purpose

This file is the active 100-point progress rubric for the **current LayerSentry V1 production plan**. V2 replaces the narrower original rubric because the product scope now includes two distinct DBaaS/APaaS paths, a LayerSentry-managed CAPI/RKE2 platform, provider-neutral DR orchestration and additional production gates that were not represented in V1.

The percentage is evidence-weighted planning/visibility telemetry. It is not a certification label. The governed statuses and release-blocking gates in `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`, specialist contexts and `AGENTS.md` remain authoritative.

Never use the percentage to override a status. A project at 90% is still not production-ready while any mandatory production gate is `PENDING`, `BLOCKED`, `UNKNOWN` or `NOT_TESTED`.

## Versioning and comparability

- V1 reports remain historically valid against `LAYERSENTRY_PROGRESS_SCORING_V1.md`.
- V2 establishes a **new baseline**. Do not describe the numerical difference between V1 and V2 as engineering progress; distinguish `RUBRIC_REBASE_DELTA` from `EVIDENCE_DELTA`.
- Future material product-scope or weight changes require a new rubric version and preservation of the superseded rubric.
- Do not retroactively rewrite old reports to use V2.

---

## Status credit

For every scored sub-item, credit only the highest status supported by exact evidence:

- `PENDING`, `UNKNOWN`, `NOT_TESTED` -> **0%** of sub-item weight;
- `DESIGN_DEFINED` -> **20%**;
- `SOURCE_COMPLETE` -> **40%**;
- `CI_VERIFIED` -> **60%**;
- `LIVE_VERIFIED` -> **80%**;
- `PRODUCTION_CERTIFIED` -> **100%**;
- `PARTIAL` -> only explicitly proven sub-gates may receive credit; never assign a generic optimistic percentage;
- `BLOCKED` -> retain credit already proven at an earlier gate, but add no credit for the blocked gate.

A status applies only to the exact tested scope. Do not transfer source/CI/live evidence to adjacent providers, products, topology modes, browsers, storage families, Sites or release candidates.

### Source-complete rule

`SOURCE_COMPLETE` is not synonymous with “code exists.” Use it only when the bounded sub-item implementation and its required source-level tests/review are complete according to the applicable workstream. Code explicitly recorded as `source in progress`, tests-authored-but-not-run, or otherwise unfinished remains below `SOURCE_COMPLETE` unless the workstream defines and proves narrower sub-gates.

---

# Production-plan scoring — 100 points

## A. Release, Installer and Supply-Chain Trust — 12 points

1. Reproducible CI build with pinned/controlled toolchains — **2.0**
2. Immutable artifact, digest, detached signature, release manifest, SBOM/provenance and trust negatives — **3.0**
3. Installer fresh/resume/idempotency/staging/atomic activation/rollback-recovery — **3.0**
4. Production source-map policy and no production-side UI compilation — **1.0**
5. Trusted promotion, protected/controlled release refs and auditable release governance — **3.0**

**Production intent:** no runtime target builds product UI/code from moving dependencies; every production payload is immutable, attributable and verified before mutation.

---

## B. KVM IaaS Product / UI / Self-Service — 10 points

1. KVM-only product profile and prerequisite-aware navigation — **2.0**
2. Platform/Department/User/read-only persona experiences — **2.0**
3. Simplified VM provisioning workflow including storage/network/IP semantics — **2.0**
4. Site/Object-Store/core service onboarding using supported CloudStack semantics — **1.5**
5. LayerSentry branding/terminology and wrong-label/hypervisor-leak regression — **1.5**
6. Exact-artifact Chrome/Firefox/responsive/accessibility workflow validation — **1.0**

---

## C. Security, Appliance Hardening and Negative Validation — 10 points

1. SELinux-enforcing policy plus required AVC/denial/live validation — **2.0**
2. Firewall/default-deny policy plus required traffic-path validation — **2.0**
3. Package/repository/update lockdown and supply-chain enforcement — **1.5**
4. RBAC/direct-URL/direct-API/foreign-object negative matrix — **2.0**
5. Authentication/session/TLS/redaction/support/diagnostic security controls — **1.5**
6. Snapshot/metadata/storage-destructive safety guards — **1.0**

---

## D. LayerSentry Kubernetes Platform — 12 points

1. BFF/controller, durable saga/journal, idempotency and ambiguous-mutation reconciliation — **2.5**
2. Exact CAPI/CAPC/CAPRKE2 resource contracts and create/status/scale/delete lifecycle — **3.0**
3. RKE2 cluster bootstrap/readiness/automatic join/node replacement and supported upgrade lifecycle — **2.5**
4. CloudStack-session-backed authentication/RBAC/project ownership for Kubernetes operations — **2.0**
5. Management-cluster/controller packaging, service wiring, restart/recovery and Rocky Linux 9 deployment — **2.0**

**Architecture rule:** this category scores the LayerSentry-managed CAPI/RKE2 path; it does not borrow credit from legacy native CKS semantics.

---

## E. Kubernetes Networking, Storage and Package Plane — 8 points

1. CloudStack CSI project isolation, attach/detach, snapshot/restore, expansion/idempotency and PVC survival — **2.5**
2. CloudStack CCM/L4 endpoint lifecycle including required control-plane/LB paths — **1.5**
3. Certified primary CNI lifecycle and metadata/network-policy behavior — **1.0**
4. Central Flux immutable catalog/reconciliation, late package install and recovery — **1.5**
5. NodeDiskSet/CAPC volume ownership, retain/delete/replace/resize safety — **1.5**

---

## F. Kubernetes DBaaS, APaaS and Streaming — 10 points

1. DBaaS API/controller/catalog/GUI lifecycle on the LayerSentry Data Services RKE2 platform — **3.0**
2. Certified DB provider/operator matrix (PostgreSQL, MySQL/PXC, MongoDB, Redis/Valkey and release-defined engines) — **2.5**
3. DB backup/restore/PITR/maintenance/engine-operator upgrade/data-integrity workflows — **1.5**
4. APaaS service lifecycle for the release-defined OpenBao/Harbor set — **1.5**
5. Streaming/Kafka/Strimzi lifecycle, exposure and upgrade/recovery behavior — **1.5**

Do not credit the Kubernetes substrate alone as DBaaS/APaaS provider completion.

---

## G. VM-Native Single-OS DBaaS/APaaS — 10 points

1. `layersentryd` lifecycle/journal/secrets/auth/privilege-separation/security foundation — **2.0**
2. Release-defined database provider matrix and exact package/version lifecycle — **2.0**
3. Release-defined application provider matrix and exact package/version lifecycle — **1.5**
4. Storage/mount/network/firewall lifecycle and destructive safety — **1.5**
5. Embedded HTTPS API/GUI, maintenance, backup/restore and evidence lifecycle — **1.5**
6. RPM/image/firstboot/seal plus supported cluster planning/enrollment boundary — **1.5**

The Single-OS path remains architecturally separate from Kubernetes DBaaS/APaaS. One path cannot receive runtime credit from the other.

---

## H. Backup, Recovery and DC↔DR Orchestration — 10 points

1. Native CloudStack B&R and repeated two-Zone recovery of root/data/network state — **3.0**
2. Provider-neutral Site Pair/Protection Plan/Recovery Point/Recovery Group state machine plus native-provider binding — **2.0**
3. Release-defined replication providers (for example LINSTOR/DRBD, Ceph RBD, SAN-array or certified fallback paths) — **2.0**
4. Test Recovery, Planned Failover, reverse replication and Failback execution — **1.5**
5. Negative/retry/RBAC/data-integrity plus measured RPO/RTO/throughput evidence — **1.5**

A same-host nested lab can earn only the exact functional evidence it proves; it cannot establish independent-site resilience.

---

## I. Control-Plane / Database / Host HA — 6 points

1. Management and LB HA failure/reboot/recovery validation — **2.0**
2. Exact control-plane database HA topology and failover/rejoin validation — **1.5**
3. KVM Host HA/OOBM/fencing for the certified physical hardware scope — **1.5**
4. Witness/quorum/exclusivity and automatic-failover safety where the release enables automatic failover — **1.0**

---

## J. Upgrade, Rollback and Recovery — 6 points

1. Versioned compatibility/upgrade matrix and fail-closed preflight — **1.0**
2. Supported N-1 -> N platform upgrade validation — **2.0**
3. Interrupted upgrade/resume/reconcile validation — **1.5**
4. Tested rollback/recovery classes including schema-aware recovery — **1.5**

Upgrade certification must cover the actual release-defined platform boundaries; do not collapse Kubernetes, DB-engine, CSI/operator and CloudStack upgrade lifecycles into one blind transaction.

---

## K. Integrated Production Validation and Operations — 6 points

1. Controlled release candidate/ref, required review/checks and auditable promotion — **1.2**
2. Clean fresh-install production-candidate certification run — **1.2**
3. Integrated functional/security/regression/negative release gate — **1.2**
4. Reliability/failure/concurrency/capacity/performance/soak evidence against release-defined thresholds — **1.2**
5. Exact-release support, operations, known-limitations, security, backup/DR and upgrade documentation — **1.2**

---

## Production readiness rule

The overall percentage alone never means production readiness.

A release may be described as production-ready / production-certified only when all release-blocking sub-items required by the release profile have reached the governed production gate and there are no unresolved mandatory `BLOCKED`, `UNKNOWN`, `PENDING` or `NOT_TESTED` gates.

At minimum the release must have:

- signed immutable artifacts and trusted promotion;
- exact-artifact Rocky Linux 9 deployment;
- required browser/persona workflows;
- integrated security/negative validation;
- release-defined KVM/Kubernetes/DBaaS/APaaS/Single-OS capability gates;
- release-defined backup/DR and HA gates;
- upgrade/rollback/recovery evidence;
- reliability/capacity/soak evidence;
- exact-release operations/security/upgrade/DR documentation.

A module excluded from a specific SKU/release must be explicitly declared out of scope in the release manifest/profile; its weight is **not silently redistributed**. Product-wide V1 progress continues to score the full V1 scope above.

---

## Reporting format

Every V2 periodic report should show:

```text
TIME=
SCORING_RUBRIC=2.0
CLOUDSTACK_HEAD=
RUNNER_HEAD=
A_RELEASE_INSTALLER=x/12
B_KVM_UI_SELF_SERVICE=x/10
C_SECURITY=x/10
D_K8S_PLATFORM=x/12
E_K8S_NETWORK_STORAGE_PACKAGES=x/8
F_K8S_DBAAS_APAAS_STREAMING=x/10
G_SINGLE_OS_DBAAS_APAAS=x/10
H_BACKUP_DR=x/10
I_HA=x/6
J_UPGRADE_ROLLBACK=x/6
K_PRODUCTION_VALIDATION=x/6
OVERALL=x/100
PRIOR_V2=
EVIDENCE_DELTA=
V1_LAST_REPORTED=            # informational only
RUBRIC_REBASE_DELTA=         # V2 baseline minus last V1 score; not engineering progress
NEW_EVIDENCE=
BLOCKERS=
NEXT_GATE=
```

If a category/sub-item cannot be established from exact current evidence, do not guess. Keep previous evidence-backed credit only when the scope is identical; otherwise use `UNKNOWN`/0 until established.

## No-false-pass rule

Never report `PASS`, `complete`, `fixed`, `healthy`, `HA ready`, `DR ready`, `production ready`, `production certified` or equivalent from this percentage. Those claims require the exact governed evidence gate.
