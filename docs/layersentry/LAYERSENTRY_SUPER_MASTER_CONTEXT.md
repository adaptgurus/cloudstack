# LayerSentry V1 — Super Master Context

**Context schema:** 4.0  
**Role:** concise canonical product/architecture contract  
**Product baseline:** Apache CloudStack 4.22.1.1 + LayerSentry KVM-first product layer  
**Execution policy:** `LAYERSENTRY_EXECUTION_CONTRACT.md`

This file contains stable product and architecture rules only. Current branch heads, workflow IDs, lab observations, temporary blockers and evidence status belong in `LAYERSENTRY_PROGRESS_LEDGER.md` and dated evidence.

The goal of schema 4.0 is to reduce repeated context loading and prevent architecture/documentation work from outrunning working product capability.

---

## 0. Authority model

Use one source of truth for each fact.

| Question | Authority |
| --- | --- |
| What source exists now? | actual fetched repository branch/commit |
| What is running/healthy now? | current live evidence from the intended target |
| What did automation execute? | current workflow/job logs and immutable artifacts |
| What is current project status? | `LAYERSENTRY_PROGRESS_LEDGER.md` + evidence |
| How work is routed/executed now? | `LAYERSENTRY_EXECUTION_CONTRACT.md` |
| Stable product/architecture rules | this file |
| Kubernetes/RKE2/Data Services details | `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` |
| VM-native Single-OS details | `LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` |
| DR provider/recovery architecture details | `LAYERSENTRY_DRAAS_ARCHITECTURE.md` |
| Security implementation details | `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md` |

Repository/workflow/live evidence overrides stale documentation. Historical re-audits/handoffs are not normal startup context once their durable findings are incorporated.

---

## 1. Minimal startup

Every AI engineering session starts with:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. one relevant specialist context/workstream;
5. actual repository/workflow/live discovery.

Do not reread every architecture document by default.

---

## 2. Product objective

LayerSentry V1 is a commercial, production-oriented, on-prem KVM private-cloud platform built on Apache CloudStack rather than a replacement hypervisor/cloud scheduler.

Customer outcome:

```text
LayerSentry Portal
  -> VM / storage / network / image / backup
  -> LayerSentry-managed RKE2/Kubernetes
  -> Kubernetes DBaaS/APaaS/Streaming
  -> VM-native Single-OS DBaaS/APaaS
  -> Backup/Recovery/DR
  -> support/operations/evidence
```

The normal customer should not need to understand CloudStack internals, raw Kubernetes YAML, RKE2 join tokens, provider-specific DR replication commands or guest installation scripts.

---

## 3. CloudStack is the IaaS authority

CloudStack 4.22.1.1 remains authoritative for:

- KVM VM lifecycle;
- Site/Zone, Pod/Infrastructure Group, Cluster and Host lifecycle;
- VM networks/VPCs where supported, IPs, firewall/ACL and native load-balancing resources;
- primary/secondary/object-storage integrations exposed by CloudStack;
- volumes, templates, ISOs and supported snapshot operations;
- native Backup & Recovery;
- account/domain/project/RBAC/quota;
- async jobs and native resource state.

LayerSentry must not create:

- a second VM scheduler;
- a second account/project/RBAC authority;
- a second quota authority;
- a conflicting inventory of CloudStack-owned infrastructure state.

Default implementation order:

```text
CloudStack native API
 -> supported CloudStack plugin/provider/configuration
 -> Kubernetes ecosystem controller where Kubernetes owns lifecycle
 -> thin LayerSentry orchestration for composite workflows/policy/evidence
 -> narrow core change only by explicit exception
```

Do not modify CloudStack Java/API/schema/KVM-agent/core orchestration merely to make LayerSentry easier to code.

---

## 4. Current execution strategy

### 4.1 Codex scope

Codex is primarily reserved for:

- LayerSentry-managed RKE2/Kubernetes;
- CAPI/CAPC/CAPRKE2 integration;
- Kubernetes CNI/CCM/CSI/Flux integration;
- Kubernetes DBaaS/APaaS/Streaming;
- end-to-end Kubernetes qualification.

### 4.2 ChatGPT scope

ChatGPT is the default implementation/troubleshooting path for:

- VM-native Single-OS DBaaS/APaaS;
- Go + Ansible migration and provider work;
- DC/DR native CloudStack API troubleshooting/integration;
- UI defect/integration work;
- context/document maintenance;
- thin native API orchestration outside the Kubernetes workstream.

### 4.3 UI state

Broad LayerSentry UI development is feature-frozen for this phase. Continue only defects, integration, RBAC/status/error wiring, browser E2E, responsive/accessibility/security corrections and feature wiring required by a working vertical slice.

UI source completeness is not the same as live/browser production certification.

---

## 5. VM-native Single-OS DBaaS/APaaS architecture

This is separate from Kubernetes DBaaS/APaaS.

Selected architecture:

```text
LayerSentry UI/API
      |
      v
Go orchestration/control service
  - auth/project binding
  - schema validation
  - immutable plan/confirmation
  - operation UUID/idempotency
  - lock
  - durable state/journal
  - secret references
  - evidence/status
      |
      v
Ansible Runner / ansible-core
      |
      v
versioned LayerSentry roles/playbooks
      |
      v
Rocky Linux 9 VM
```

### Go boundary

Go owns orchestration and safety state, not every imperative OS/package action.

Retain the existing Go investment for:

- API/auth;
- plan/model/provider metadata;
- state/journal;
- lifecycle lock/idempotency;
- secret references;
- execution policy;
- Ansible invocation/result handling;
- health/evidence;
- rollback/recovery state.

### Ansible boundary

Ansible owns guest configuration:

- OS hardening application;
- repositories/packages;
- services/users/files/directories;
- SELinux;
- firewalld;
- LVM/filesystems/mounts;
- NetworkManager/VIP configuration;
- PostgreSQL/MySQL/MariaDB/Redis/Valkey;
- Nginx/Apache/Tomcat;
- Node.js/Python/Podman;
- provider-specific cluster/bootstrap/upgrade/repair/uninstall where appropriate.

### No shell-script installation

Bash/sh is not the product installation/configuration engine.

Existing shell-based installation/configuration paths are deprecated and must not be extended. Migrate runtime/product behavior to Ansible roles/playbooks.

Small developer/build/packaging wrappers may remain temporarily when they are not the customer/runtime installation boundary.

Normal Ansible implementation uses dedicated modules. `shell`/`raw` are exceptions, not provider design.

### Product workflow

```text
customer selects product/version/topology/storage/network
 -> CloudStack provisions VM/network/volumes
 -> LayerSentry generates immutable plan
 -> customer confirms
 -> Go coordinator invokes approved Ansible content
 -> health/security assertions
 -> evidence/state commit
```

Secrets are runtime references, never durable plaintext.

---

## 6. LayerSentry-managed RKE2/Kubernetes architecture

Preferred architecture remains:

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
  workload clusters
      |
      +-> CNI
      +-> CloudStack CCM
      +-> safe CSI/storage
      +-> Flux
      +-> DBaaS/APaaS/Streaming operators
```

Ownership:

- CloudStack owns IaaS;
- CAPI owns cluster/machine desired state;
- CAPC owns CloudStack infrastructure created for CAPI Machines;
- CAPRKE2 owns RKE2 bootstrap/control-plane lifecycle;
- Flux owns internal package reconciliation;
- DB/application operators own application-specific lifecycle;
- LayerSentry owns GUI, policy, compatibility, release channels, audit and orchestration state.

Do not create two active controllers for the same VM, VIP, volume, node or application lifecycle.

### Current K8s execution priority

The existing E0/E1 source must become a real vertical slice before more broad provider/catalog code is added.

Required base proof:

1. immutable artifacts available;
2. management controller services deployed;
3. GUI/API create;
4. CloudStack infrastructure reconciled by the selected ownership path;
5. automatic RKE2 join;
6. 6443 + 9345 endpoint proof;
7. primary CNI Ready;
8. CCM/L4 lifecycle;
9. one safe CSI/storage path;
10. central Flux reconciliation;
11. status/scale;
12. node replacement/data-safety where applicable;
13. delete/cleanup;
14. restart/reconciliation negatives;
15. Rocky Linux 9 evidence.

Kubernetes DBaaS/APaaS/Streaming expands only after the base cluster lifecycle passes the release-defined gates.

PostgreSQL is the first Kubernetes DBaaS vertical slice.

### Approved fallback

If exact qualification proves the CAPI/CAPC/CAPRKE2 path unsuitable for a required V1 gate without disproportionate downstream maintenance, the approved release fallback is:

```text
LayerSentry durable workflow
 -> native CloudStack APIs
 -> hardened QCOW2/cloud-init
 -> Ansible Runner
 -> RKE2
 -> Flux
```

A release selects one owner path. Do not operate CAPI and fallback concurrently for the same lifecycle.

---

## 7. Kubernetes DBaaS/APaaS/Streaming

These remain valid LayerSentry modules above Kubernetes rather than CloudStack-core features.

Sequence:

```text
base RKE2 vertical slice
 -> PostgreSQL DBaaS
 -> backup/PITR/restore/maintenance
 -> additional DB engines
 -> one APaaS vertical slice
 -> Harbor/OpenBao expansion
 -> Strimzi/Kafka
 -> GPU/advanced storage only after base reliability
```

Do not count substrate/controller code as completion of a DBaaS/APaaS/Streaming product lifecycle.

Normal users operate through LayerSentry GUI/API, not YAML/kubectl/SSH.

---

## 8. DC/DR/DRaaS architecture

The V1 critical path is native CloudStack recovery first, not a large custom DR controller.

### Native baseline

Use supported CloudStack 4.22.1.1 Backup & Recovery and cross-Zone recovery capabilities first.

Execution order:

```text
healthy DC/DR infrastructure
 -> working storage/templates/KVM hosts
 -> supported B&R enabled/configured
 -> disposable workload
 -> Recovery Point OLD
 -> mutate data
 -> Recovery Point NEW
 -> isolated cross-Zone recovery of OLD and NEW
 -> exact guest root/data-disk verification
 -> negative/retry/RBAC tests
 -> thin LayerSentry recovery UI/orchestration
```

Resolve environment defects before advanced coding. Current types of blockers include B&R configuration, storage/image-store/template readiness, API/RBAC/async-job behavior, KVM/libvirt readiness and destination Zone/network compatibility.

### Advanced DR

After native recovery passes:

1. add one provider-native low-RPO adapter for the selected LayerSentry profile;
2. prove Test Recovery;
3. prove Planned Failover;
4. prove reverse replication and Failback;
5. only then implement/certify witness, fencing and automatic failover.

Prefer provider-native replication such as LINSTOR/DRBD, Ceph RBD or certified SAN replication when selected. Do not build a generic host-level block copier where a mature provider primitive exists.

CloudStack remains VM/network/storage authority throughout DR recovery.

The existing provider-neutral DR state-machine code may be retained as source foundation but is not the current implementation priority until native recovery works.

---

## 9. Release/build/supply-chain baseline

Release engineering must converge on immutable, reproducible artifacts.

Requirements include as applicable:

- pinned source/version inputs;
- deterministic/reproducible build where feasible;
- exact digest manifest;
- SBOM/provenance;
- trusted signature verification before production promotion;
- no production source maps unless explicitly intended;
- no target-side production UI compilation;
- atomic deploy/activation/rollback;
- safe upgrade/resume/recovery;
- offline bundle provenance and digest verification.

Kubernetes components must not be deployed from unresolved/moving image/package inputs.

---

## 10. Security invariants

Minimum:

- server-side authorization; UI hiding is not security;
- strict schema/input validation;
- safe argv/typed API/module invocation;
- no untrusted shell interpolation/eval;
- parameterized SQL;
- path/archive/symlink safety;
- TLS verification by default;
- SSRF controls for external fetch/integration;
- finite timeouts/retries/concurrency;
- idempotency for mutations;
- secrets never committed, embedded in browser code or written to normal logs/evidence;
- SELinux Enforcing on production Rocky profiles;
- firewalld active/default-deny with explicit required rules;
- no disabling security controls to make tests pass.

Read `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md` for detailed implementation rules when crossing a trust boundary.

---

## 11. Evidence model

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

Rules:

- source presence != runtime proof;
- passing unit tests != E2E proof;
- build artifact != deployed artifact proof;
- HTTP 200 != application/cluster health;
- documentation support != exact combination qualification;
- same-host nested DR != independent-site DR certification.

Live claims require exact source/artifact, target, assertions and durable evidence.

---

## 12. Rocky Linux 9 acceptance

Rocky Linux 9 remains the primary V1 runtime acceptance environment for appliance/KVM-related LayerSentry behavior.

WSL/other development environments may validate source and tooling but cannot alone promote runtime behavior to `LIVE_VERIFIED`.

Current lab sizes/topologies/IPs/credentials are volatile and belong in the progress ledger/evidence, not this stable context.

---

## 13. Progress model

Progress is measured by complete customer-operable vertical slices.

Priority vertical proofs:

### A. VM-native PostgreSQL

```text
UI/API
 -> CloudStack VM/storage/network
 -> Go plan
 -> Ansible install/configure
 -> health
 -> restart/reboot
 -> backup/restore
 -> patch/repair
 -> uninstall/residue/security validation
```

### B. RKE2 cluster

```text
UI/API
 -> create
 -> Ready
 -> CNI/CCM/CSI/Flux
 -> scale
 -> replacement/data safety
 -> delete
```

### C. Kubernetes PostgreSQL DBaaS

```text
provision
 -> storage
 -> HA as selected
 -> backup/PITR
 -> restore
 -> maintenance/upgrade
 -> failure recovery
```

### D. APaaS

Complete one OpenBao or Harbor lifecycle before expanding catalog breadth.

### E. Native DR

Two distinct recovery points recovered into isolated DR networking with exact guest data verification.

File count, line count and commit count do not define completion.

---

## 14. Architecture-change rule

Do not repeatedly reopen frozen architecture.

Research/decision work is required when:

- an exact version/provider combination changes;
- a hard blocker is discovered;
- a security/data-safety issue invalidates the current design;
- a materially simpler supported native mechanism is found;
- the owner changes product scope.

Otherwise execute the selected architecture and spend effort on integration/testing.

---

## 15. Continuity

Before mutations:

- fetch actual current refs;
- inspect current worktree and concurrent commits;
- inspect in-flight workflows/async operations where duplicate mutation matters;
- resume from the first unmet evidence gate.

After meaningful vertical milestones, update durable evidence/status concisely. Do not create repetitive large handoffs for every small change.
