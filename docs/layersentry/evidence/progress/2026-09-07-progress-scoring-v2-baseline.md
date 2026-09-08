# LayerSentry Progress Scoring V2 — Baseline

**Rubric:** `LAYERSENTRY_PROGRESS_SCORING.md` version `2.0`  
**Baseline date:** 2026-09-07  
**V1 last reported score:** `24.2/100` (informational only; not directly comparable as engineering delta)  
**V2 baseline score:** `25.36/100`

## Scoring discipline

This baseline applies only evidence statuses already supported by repository/workflow/live evidence. It does not convert source existence into runtime proof, and it does not treat the V1-to-V2 numerical change as engineering progress.

`SOURCE_COMPLETE` is used only where the applicable workstream/ledger records the bounded implementation at that status. Code explicitly recorded as source-in-progress or tests-authored-but-not-run remains below `SOURCE_COMPLETE`.

## Category score

| Category | Points |
| --- | ---: |
| A. Release, Installer and Supply-Chain Trust | **3.20 / 12** |
| B. KVM IaaS Product / UI / Self-Service | **3.70 / 10** |
| C. Security, Appliance Hardening and Negative Validation | **2.70 / 10** |
| D. LayerSentry Kubernetes Platform | **4.30 / 12** |
| E. Kubernetes Networking, Storage and Package Plane | **2.70 / 8** |
| F. Kubernetes DBaaS, APaaS and Streaming | **2.00 / 10** |
| G. VM-Native Single-OS DBaaS/APaaS | **2.00 / 10** |
| H. Backup, Recovery and DC↔DR Orchestration | **2.00 / 10** |
| I. Control-Plane / Database / Host HA | **0.60 / 6** |
| J. Upgrade, Rollback and Recovery | **1.20 / 6** |
| K. Integrated Production Validation and Operations | **0.96 / 6** |
| **Overall** | **25.36 / 100** |

## Item status basis

### A — 3.20 / 12

- A1 reproducible/pinned CI build — `CI_VERIFIED` -> 1.20/2.00.
- A2 signed immutable artifact/trust chain — `DESIGN_DEFINED` -> 0.60/3.00; unsigned candidate/source contract evidence does not satisfy detached-signature/trust negatives.
- A3 installer atomic activation/rollback-recovery — `DESIGN_DEFINED` -> 0.60/3.00; substantial installer source exists but the full product-wide immutable-artifact consumption/atomic recovery gate is not proven.
- A4 source-map/no target-side UI compilation policy — `DESIGN_DEFINED` -> 0.20/1.00.
- A5 trusted promotion/protected release governance — `DESIGN_DEFINED` -> 0.60/3.00; active LayerSentry branch remains development governance rather than the certified promotion path.

### B — 3.70 / 10

- B1 KVM-only profile/navigation — `CI_VERIFIED` -> 1.20/2.00.
- B2 persona experiences — `SOURCE_COMPLETE` -> 0.80/2.00.
- B3 simplified VM provisioning — `SOURCE_COMPLETE` -> 0.80/2.00.
- B4 Site/Object/core-service onboarding — `DESIGN_DEFINED` -> 0.30/1.50.
- B5 branding/terminology regression — `SOURCE_COMPLETE` -> 0.60/1.50.
- B6 exact-artifact browser/responsive acceptance — `NOT_TESTED` -> 0/1.00.

### C — 2.70 / 10

- C1 SELinux policy/live matrix — `DESIGN_DEFINED` -> 0.40/2.00.
- C2 firewall/default-deny traffic matrix — `DESIGN_DEFINED` -> 0.40/2.00.
- C3 repository/update lockdown — `DESIGN_DEFINED` -> 0.30/1.50.
- C4 RBAC/direct-route/API/foreign-object negatives — `SOURCE_COMPLETE` -> 0.80/2.00.
- C5 auth/session/TLS/redaction/diagnostics — `SOURCE_COMPLETE` for bounded source controls -> 0.60/1.50.
- C6 snapshot/metadata/storage-destructive safety — `DESIGN_DEFINED` -> 0.20/1.00.

### D — 4.30 / 12

- D1 BFF/controller/saga/journal/reconciliation — `SOURCE_COMPLETE` -> 1.00/2.50; ledger records 32 local tests passed.
- D2 CAPI/CAPC/CAPRKE2 + create/status/scale/delete — `SOURCE_COMPLETE` -> 1.20/3.00; lifecycle executor and provider-resource contracts are source-complete with local tests.
- D3 RKE2 bootstrap/readiness/node replacement/upgrade — `DESIGN_DEFINED` -> 0.50/2.50; provider objects exist but real cluster readiness/automatic join/upgrade is not exercised.
- D4 CloudStack-session-backed K8s auth/RBAC/project ownership — `SOURCE_COMPLETE` -> 0.80/2.00; ledger records 62 local tests.
- D5 controller packaging/service wiring/Rocky deployment — `SOURCE_COMPLETE` / blocked at deployment -> retain source credit 0.80/2.00; runtime remains blocked/unverified.

### E — 2.70 / 8

- E1 CSI project/snapshot/expand/PVC-safety implementation — `SOURCE_COMPLETE` -> 1.00/2.50; exact patched source/local tests exist, live qualification does not.
- E2 CCM/L4 endpoint lifecycle — `SOURCE_COMPLETE` -> 0.60/1.50; Kubernetes 1.36 source overlay builds/tests, live LB lifecycle does not.
- E3 primary CNI lifecycle — `DESIGN_DEFINED` -> 0.20/1.00.
- E4 central Flux package plane — `DESIGN_DEFINED` -> 0.30/1.50; reconciliation foundations exist but immutable catalog/late-package/recovery scope is not source-complete as a whole.
- E5 NodeDiskSet/CAPC volume ownership safety — `SOURCE_COMPLETE` -> 0.60/1.50.

### F — 2.00 / 10

All five Kubernetes DBaaS/APaaS/Streaming scored items remain `DESIGN_DEFINED` at the whole-item level. The Kubernetes substrate is materially implemented, but the release-defined DBaaS controller/provider matrix, DB backup/PITR lifecycle, OpenBao/Harbor lifecycle and Kafka/Strimzi lifecycle do not yet have bounded `SOURCE_COMPLETE` evidence as whole product items.

### G — 2.00 / 10

All six Single-OS sub-items receive `DESIGN_DEFINED` credit only in this baseline. This is deliberately conservative despite substantial code being present: the current Single-OS implementation handoff records source-in-progress and tests written but not executed. Workstream F states `SOURCE_COMPLETE` requires completed source plus source tests. New provider commits after the handoff do not by themselves promote the whole scored sub-items without the required source-test gate.

This category is the main place where V2 now makes the previously invisible Single-OS work explicit; future execution of its authored tests can promote large portions of this category without changing rubric weights.

### H — 2.00 / 10

All five DR/recovery sub-items remain at `DESIGN_DEFINED` at the whole-item level. Evidence includes a bounded native recovery adapter recorded `SOURCE_COMPLETE` for metadata/clone/journal scope and a provider-neutral DR state-machine source foundation, but native two-Zone E2E recovery has not passed, native-provider binding is incomplete, replication-provider implementations remain incomplete, and planned failover/failback plus measured RPO/RTO/data-integrity gates remain unverified.

### I — 0.60 / 6

- I1 Management/LB HA — `DESIGN_DEFINED` -> 0.40/2.00.
- I2 exact control-plane DB HA — `NOT_TESTED`/unselected exact topology -> 0/1.50.
- I3 physical host HA/OOBM/fencing — `NOT_TESTED` -> 0/1.50.
- I4 witness/quorum/auto-failover safety — `DESIGN_DEFINED` -> 0.20/1.00; source safety contracts exist but witness/fencing executors are not implemented/live.

### J — 1.20 / 6

All four upgrade/rollback/recovery items remain `DESIGN_DEFINED` -> 20% of category weight. Release-specific N-1->N, interruption/resume and schema-aware recovery execution remain unverified.

### K — 0.96 / 6

- K1 controlled release ref/promotion — `DESIGN_DEFINED` -> 0.24/1.20.
- K2 clean fresh-install candidate — `DESIGN_DEFINED` -> 0.24/1.20.
- K3 integrated security/regression gate — `DESIGN_DEFINED` -> 0.24/1.20.
- K4 reliability/capacity/soak — `NOT_TESTED` -> 0/1.20.
- K5 exact-release operations documentation — `DESIGN_DEFINED` -> 0.24/1.20.

## Interpretation

The V2 score is intentionally not dramatically higher than the last V1 score even though much more code exists. V2 adds previously invisible production scope to the denominator as well as recognizing its evidence. The important change is that future progress in CAPI/RKE2, Kubernetes DBaaS/APaaS, Single-OS providers and advanced DR can now move the canonical project score instead of being invisible.

`25.36 - 24.20 = +1.16` is the **rubric rebase difference**, not an evidence-backed engineering delta.

## Highest-leverage next score gates

1. Execute and record the Single-OS source test/build/vet/RPM gates so bounded G sub-items can move to `SOURCE_COMPLETE`/`CI_VERIFIED` where evidence supports it.
2. Publish immutable signed CCM/CSI/Flux artifacts and execute the E0/E1 live CAPI/RKE2 lifecycle so D/E can move from source to CI/live evidence.
3. Implement/execute Kubernetes DBaaS provider lifecycle rather than counting substrate code as DBaaS completion.
4. Bind and execute native DR recovery end-to-end before advanced replication/failback promotion.
5. Close A2 signed release trust; it remains a cross-cutting release blocker.
