# LayerSentry V1 — Super Master Context

**Context schema:** 4.1  
**Role:** concise canonical product/architecture contract  
**Product baseline:** Apache CloudStack 4.22.1.1 + LayerSentry KVM-first product layer  
**Execution policy:** `LAYERSENTRY_EXECUTION_CONTRACT.md`

This file contains stable product/architecture rules only. Current branch heads, workflow IDs, live target observations and temporary blockers belong in `LAYERSENTRY_PROGRESS_LEDGER.md` and evidence.

The objective is the smallest supportable LayerSentry overlay that reuses CloudStack and mature upstream controllers/products, then proves complete customer-operable vertical slices.

---

## 0. Authority model

| Question | Authority |
| --- | --- |
| What source exists now? | actual fetched repository branch/commit |
| What is running now? | current live evidence from the intended target |
| What did automation execute? | workflow/job logs and immutable artifacts |
| Current project status | `LAYERSENTRY_PROGRESS_LEDGER.md` + evidence |
| Execution/model routing | `LAYERSENTRY_EXECUTION_CONTRACT.md` |
| Stable product architecture | this file |
| Kubernetes/RKE2 details | `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` + current Workstream E |
| VM-native details | `LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` |
| DR details | `LAYERSENTRY_DRAAS_ARCHITECTURE.md` |
| Security details | `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md` |

Repository/workflow/live evidence overrides stale documentation. Historical handoffs are not normal startup context after their durable findings are incorporated.

---

## 1. Minimal startup

Every engineering session starts with:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. one relevant specialist workstream/context;
5. actual repository/workflow/live discovery.

Do not reread every architecture document by default.

---

## 2. Product objective

LayerSentry V1 is a commercial, production-oriented, on-prem KVM private-cloud product built on Apache CloudStack rather than a replacement cloud scheduler.

Customer outcome:

```text
LayerSentry Portal
  -> VM/storage/network/image/backup
  -> LayerSentry-managed RKE2/Kubernetes
  -> Kubernetes DBaaS/APaaS/Streaming
  -> VM-native Single-OS DBaaS/APaaS
  -> Backup/Recovery/DR
  -> support/operations/evidence
```

Normal customers should not need CloudStack internals, raw Kubernetes YAML, kubectl, RKE2 join tokens, provider-specific replication commands or guest installation scripts.

---

## 3. CloudStack is the IaaS authority

CloudStack 4.22.1.1 remains authoritative for:

- KVM VM lifecycle;
- Site/Zone, Pod/Infrastructure Group, Cluster and Host;
- VM networks/VPCs, IPs, firewall/ACL and native load-balancing resources;
- storage integrations, volumes, templates, ISOs and supported snapshots;
- native Backup & Recovery;
- account/domain/project/RBAC/quota;
- async jobs and native resource state.

LayerSentry must not create a second VM scheduler, tenancy/RBAC authority, quota authority or conflicting inventory of CloudStack-owned state.

Default implementation order:

```text
CloudStack native API
 -> supported provider/plugin/configuration
 -> Kubernetes ecosystem controller where Kubernetes owns lifecycle
 -> thin LayerSentry orchestration/policy/evidence
 -> narrow CloudStack core change only by explicit exception
```

---

## 4. Current execution strategy

### 4.1 Codex

Codex owns two bounded scopes:

- **UI finishing/optimization/integration** — no broad redesign;
- **RKE2/Kubernetes E2E** — the primary technical stream, including exact K8s artifact integration and upstream service package qualification.

### 4.2 ChatGPT

ChatGPT remains the default for:

- VM-native Single-OS Go + Ansible;
- hypervisor/bootstrap/control-plane HA;
- native CloudStack DC/DR troubleshooting/integration;
- context/document maintenance;
- thin native API orchestration outside Kubernetes.

### 4.3 UI state

The broad LayerSentry UI is feature-frozen. Codex should finish defects, API/BFF wiring, RBAC/status/error handling, KVM-only presentation, responsive/accessibility/security and exact-artifact browser acceptance.

Do not start a second product redesign.

---

## 5. VM-native Single-OS architecture

This path is separate from Kubernetes services.

```text
LayerSentry UI/API
 -> Go orchestration/control
 -> Ansible Runner / ansible-core
 -> versioned roles/playbooks
 -> Rocky Linux 9 VM
```

Go owns authorization, schema validation, immutable plan/confirmation, operation UUID/idempotency, locking, durable state/journal, secret references, Ansible invocation/results, evidence and recovery state.

Ansible owns repositories/packages, service configuration, SELinux, firewalld, LVM/filesystems/mounts, VIP/network configuration and provider-specific DB/application configuration.

Bash/sh is not the product installation/configuration engine. Existing runtime shell lifecycle assets are deprecated and must not be extended.

---

## 6. One LayerSentry RKE2 lifecycle

User Kubernetes, Data Services, APaaS and Streaming use the same underlying cluster lifecycle.

```text
LayerSentry UI/BFF
      |
      v
     CAPI
   /      \
 CAPC    CAPRKE2
  |        |
CloudStack RKE2
      |
      v
  CNI / CCM / CSI
      |
      v
 central Flux
      |
      +-> user-selected packages/operators
```

Ownership:

- CloudStack owns IaaS;
- CAPI owns cluster/machine desired state;
- CAPC owns CloudStack resources created for CAPI Machines;
- CAPRKE2 owns RKE2 bootstrap/control-plane lifecycle;
- CCM owns selected Kubernetes L4 LoadBalancer reconciliation;
- CSI owns workload-volume lifecycle on its certified path;
- Flux owns internal package reconciliation;
- upstream operators own application/database lifecycle;
- LayerSentry owns UI/BFF, profiles, compatibility, release channels, policy, audit and composite workflow state.

Do not create separate cluster provisioners for DBaaS/APaaS/Streaming and do not create two active controllers for the same VM/VIP/volume/node/application lifecycle.

### 6.1 Current RKE2 execution priority

The existing E0/E1 source must become a real vertical slice before more broad source is added.

```text
immutable artifacts
 -> controller deployment
 -> GUI/API create
 -> CloudStack VM/resource reconciliation
 -> CAPRKE2 automatic join
 -> 6443 + 9345
 -> primary CNI Ready
 -> CCM/L4
 -> one safe CSI path
 -> Flux remote reconciliation
 -> status/scale
 -> replacement + PVC/data safety
 -> delete/cleanup
 -> restart/UNKNOWN reconciliation
 -> supported upgrade
 -> air-gap proof where claimed
```

For every observed failure, fix the smallest correct owner and rerun the same step.

### 6.2 CAPC stop-loss

CAPI/CAPC/CAPRKE2 is preferred because significant source already exists, but LayerSentry must not maintain a disproportionate provider fork merely to preserve sunk cost.

If a focused qualification campaign cannot produce CloudStack VM creation + automatic RKE2 join + 6443/9345 + cluster `Ready`, and evidence shows continued downstream maintenance is disproportionate, select the approved release fallback:

```text
LayerSentry durable workflow
 -> native CloudStack APIs
 -> hardened QCOW2/cloud-init
 -> Ansible Runner
 -> RKE2
 -> Flux
```

One release selects one cluster lifecycle owner.

---

## 7. Kubernetes DBaaS/APaaS/Streaming — upstream-first

These are valid LayerSentry modules **above the same RKE2/Flux substrate**.

For current V1, use mature upstream products rather than writing replacements:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB lifecycle;
- OpenBao through pinned supported Helm/OCI content;
- Harbor through pinned supported Helm/OCI content;
- Strimzi for Kafka lifecycle.

LayerSentry supplies:

- service catalog/entry point;
- project/namespace/RBAC policy;
- certified StorageClass/storage profile;
- network/VIP/exposure policy;
- compatibility/release selection;
- local/offline artifact references;
- health/status/audit integration;
- E2E qualification.

Do not build replacement DB operators, backup/PITR engines, DB failover engines, Kafka operators, Harbor controllers or OpenBao controllers.

For current V1, upstream application UI rebranding is not required unless the owner explicitly adds that task. Required legal attribution remains intact.

Application-specific certification still proves the lifecycle actually relied on: for example DB create/read-write/HA/backup/PITR/upgrade/data integrity, OpenBao HA/snapshot/recovery, Harbor persistence/upgrade, and Kafka listener/storage/failure behavior. These are integration tests, not a reason to rewrite upstream features.

---

## 8. One V1 platform release carrier

Current V1 execution uses one logical signed carrier:

```text
layersentry-platform-<release>.iso
```

It may include:

- QCOW2 node images;
- RKE2/CAPI/CAPC/CAPRKE2;
- CNI/CCM/CSI;
- Flux;
- OpenEverest/database operators/images;
- OpenBao;
- Harbor;
- Strimzi/Kafka;
- approved security/observability/backup packages;
- local registry/RPM/DEB content;
- compatibility metadata, checksums, signatures, SBOM and provenance.

Bundled means `AVAILABLE`, not installed. Flux installs only selected packages. Users do not reinstall the ISO or cluster to add an already-bundled package unless host/kernel capability actually changes.

This current V1 packaging decision supersedes the earlier conceptual K8s/Data Services two-ISO split for execution. Logical sections may remain distinct inside one signed carrier.

---

## 9. DC/DR/DRaaS

The V1 critical path is native CloudStack recovery first.

```text
healthy DC/DR infrastructure
 -> working storage/templates/KVM
 -> supported B&R enabled/configured
 -> Recovery Point OLD
 -> mutate data
 -> Recovery Point NEW
 -> isolated createVMFromBackup recovery of OLD and NEW
 -> exact root/data-disk validation
 -> negative/retry/RBAC tests
 -> thin LayerSentry recovery UI/orchestration
```

After native recovery passes, add one provider-native low-RPO path for the selected profile, then planned failover/failback, then witness/fencing/automatic failover last.

Prefer LINSTOR/DRBD, Ceph RBD or certified SAN-native replication when selected. Do not build a generic host block copier where a mature provider primitive exists.

---

## 10. Bootstrap/control-plane HA

LayerSentry may use one temporary bootstrap server for initial site creation or catastrophic reseed. Production must not depend on it after commissioning.

The target virtualized control-plane profile uses 3 Management VMs, 3 DB VMs and redundant LB/VIP nodes or a certified external ADC, distributed across independent failure domains and tested with the bootstrap server off.

Normal upgrades use the persistent LayerSentry management plane, not the one-time bootstrap server.

---

## 11. Release/supply-chain baseline

Release engineering must converge on immutable artifacts:

- pinned source/version inputs;
- exact digests;
- SBOM/provenance;
- signature verification;
- no unintended production source maps;
- atomic activation/rollback;
- safe upgrade/resume/recovery;
- offline artifact provenance.

Kubernetes stable candidates must not depend on moving image/package inputs.

---

## 12. Security invariants

Minimum:

- server-side authorization;
- strict validation;
- safe argv/typed API/module invocation;
- no untrusted shell interpolation/eval;
- parameterized SQL;
- path/archive/symlink safety;
- TLS verification by default;
- SSRF controls;
- finite timeouts/retries/concurrency;
- idempotency for mutations;
- secrets never committed or emitted to browser/log/evidence;
- SELinux Enforcing on production Rocky profiles;
- firewalld active with explicit required rules.

Do not disable security controls to make tests pass.

---

## 13. Evidence model

Valid statuses:

- `DESIGN_DEFINED`
- `SOURCE_COMPLETE`
- `CI_VERIFIED`
- `LIVE_VERIFIED`
- `PRODUCTION_CERTIFIED`
- `PARTIAL`
- `PENDING`
- `BLOCKED`
- `UNKNOWN`
- `NOT_TESTED`

Source presence != runtime proof. Passing unit tests != E2E proof. Build artifact != deployed artifact proof. HTTP 200 != whole-service health. Documentation support != exact combination qualification.

---

## 14. Progress model

Progress is measured by customer-operable vertical slices.

Priority proofs:

### A. RKE2

```text
UI/API
 -> create
 -> Ready
 -> CNI/CCM/CSI/Flux
 -> scale
 -> replacement/data safety
 -> delete
 -> upgrade/air-gap as claimed
```

### B. UI

```text
existing LayerSentry UI
 -> optimize/wire
 -> role/RBAC correctness
 -> KVM-only behavior
 -> exact backend integration
 -> browser acceptance
```

### C. Kubernetes services

```text
same RKE2/Flux substrate
 -> OpenEverest/OpenBao/Harbor/Strimzi package install
 -> exact upstream lifecycle qualification
```

### D. VM-native

```text
UI/API
 -> CloudStack VM/storage/network
 -> Go plan
 -> Ansible
 -> provider health/restart/backup/repair/uninstall
```

### E. Native DR

Two distinct recovery points recovered into isolated DR networking with exact guest-data verification.

File count, line count and commit count do not define completion.

---

## 15. Architecture-change rule and continuity

Do not repeatedly reopen frozen architecture.

Research/decision work is required only when an exact version/provider changes, a hard blocker appears, security/data-safety invalidates the design, a materially simpler supported native mechanism is found, or the owner changes scope.

Before mutations fetch actual refs, inspect concurrent commits and in-flight operations, and resume from the first unmet evidence gate. After meaningful vertical milestones update durable evidence concisely rather than creating repetitive handoffs.