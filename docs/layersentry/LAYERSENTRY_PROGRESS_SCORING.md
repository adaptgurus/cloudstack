# LayerSentry V1 — Evidence-Weighted Progress Scoring

## Purpose

This file defines one stable 100-point rubric for periodic LayerSentry progress reporting. It exists to prevent AI/human reports from moving the percentage arbitrarily or treating documentation/design as equivalent to verified product behavior.

This percentage is **planning/visibility telemetry**, not a certification label. The governed statuses and production gates in `LAYERSENTRY_SUPER_MASTER_CONTEXT.md` remain authoritative.

Never use the percentage to override a status. A project at 90% is still not production-ready if a required release-blocking gate remains `PENDING`, `BLOCKED`, `UNKNOWN` or `NOT_TESTED`.

---

## Status credit

For each scored sub-item, credit only the highest evidence-backed status:

- `PENDING`, `UNKNOWN`, `NOT_TESTED` -> 0% of sub-item weight;
- `DESIGN_DEFINED` -> 20%;
- `SOURCE_COMPLETE` -> 40%;
- `CI_VERIFIED` -> 60%;
- `LIVE_VERIFIED` -> 80%;
- `PRODUCTION_CERTIFIED` -> 100%;
- `PARTIAL` -> credit only explicitly proven sub-gates, never a default optimistic percentage;
- `BLOCKED` -> retain credit for already-proven sub-gates but add no credit for the blocked gate.

A `LIVE_VERIFIED` status applies only to the exact tested scope. Do not transfer it to adjacent functionality.

---

## A. Release / Installer / Build — 20 points

1. CI UI build with pinned/controlled toolchain — **4**
2. Immutable artifact + digest/signature + release manifest + SBOM/provenance — **5**
3. Production source-map policy and no production-side UI compilation — **2**
4. Installer fresh/resume/idempotency/atomic deployment/rollback-recovery behavior — **5**
5. Trusted release promotion/source-governance controls — **4**

---

## B. KVM Product Profile / UI / Self-Service — 20 points

1. KVM-only customer product profile and prerequisite-aware navigation — **4**
2. Platform Administrator dashboard/experience — **3**
3. Department Administrator dashboard/experience — **3**
4. Normal User/read-only experience — **2**
5. Simplified VM workflow/wizard — **3**
6. Simplified CKS/Bucket/Site onboarding UX using supported semantics — **3**
7. Branding/terminology/DBaaS-APaaS V1 cleanup and wrong-label regression — **2**

---

## C. Security / Appliance / Negative Validation — 15 points

1. SELinux-enforcing policy and live validation — **3**
2. Firewall policy and required traffic-path validation — **3**
3. Package/repository lockdown and controlled-update enforcement — **2**
4. RBAC/direct-URL/direct-API negative test matrix — **3**
5. Support-bundle/redaction/TLS/session/browser-security/diagnostic controls — **2**
6. KVM snapshot-safety + CKS metadata-isolation security guards — **2**

---

## D. CKS / Object Storage / Backup Core Integrations — 10 points

1. Native CKS lifecycle on the LayerSentry target — **3**
2. CKS CSI/CNI/metadata-isolation validation — **2**
3. Object Store/Bucket provider and user workflow validation — **2**
4. Native Backup & Recovery backup/restore validation — **3**

---

## E. DR / HA — 15 points

1. Repeated two-Zone native recovery + negative tests + RPO/RTO/throughput evidence — **5**
2. Management/LB HA failure/reboot validation — **4**
3. Exact DB HA/failover topology validation — **3**
4. KVM Host HA/OOBM/fencing validation for the certified hardware scope — **3**

A same-host nested lab can score the functional DR sub-gates it actually verifies, but cannot score physical site independence or physical OOBM/fencing.

---

## F. Upgrade / Rollback / Recovery — 10 points

1. Versioned compatibility/upgrade matrix and preflight — **2**
2. Supported N-1 -> N upgrade validation — **4**
3. Interrupted upgrade/resume validation — **2**
4. Tested rollback/recovery classes including schema-aware recovery — **2**

---

## G. Production Validation / Release Governance — 10 points

1. Protected/controlled release refs, required checks/review and auditable promotion — **2**
2. Clean fresh-install production-candidate certification run — **2**
3. Integrated security/regression/negative-test release gate — **2**
4. Reliability/failure/concurrency/capacity/soak evidence for release-defined thresholds — **2**
5. Exact-release support/operations/known-limitations/security/upgrade documentation — **2**

---

## Reporting format

Every periodic report should show:

```text
TIME=
CLOUDSTACK_HEAD=
RUNNER_HEAD=
A_RELEASE_INSTALLER=x/20
B_UI_SELF_SERVICE=x/20
C_SECURITY_APPLIANCE=x/15
D_INTEGRATIONS=x/10
E_DR_HA=x/15
F_UPGRADE_ROLLBACK=x/10
G_PRODUCTION_VALIDATION=x/10
OVERALL=x/100
DELTA_SINCE_PRIOR=
NEW_EVIDENCE=
BLOCKERS=
NEXT_GATE=
```

If a category/sub-item cannot be established from current evidence, do not guess; keep the previous evidence-backed credit or mark the state `UNKNOWN` and explain.

## No-false-pass rule

Do not report `PASS`, `complete`, `fixed`, `healthy`, `HA ready`, `DR ready`, `production ready` or equivalent from the percentage. Those claims require their exact governed evidence/status gates.
