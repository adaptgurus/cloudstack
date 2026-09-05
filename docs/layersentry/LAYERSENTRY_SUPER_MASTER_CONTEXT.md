# LayerSentry V1 — Super Master Context

**Context schema:** 3.0  
**Role:** canonical stable product, architecture, safety, validation and production-engineering contract  
**Product baseline:** Apache CloudStack 4.22.1.1 with a LayerSentry KVM-first product layer

This document contains **stable rules and architecture**, not volatile execution state. Current branch HEADs, workflow/job/artifact IDs, live IPs, temporary blockers, current test results and current provider health belong in `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md` and underlying evidence.

The companion relationship/navigation index is `docs/layersentry/LAYERSENTRY_KNOWLEDGE_GRAPH.md`.

---

## 0. Authority model

Use one source of truth for each kind of fact.

| Question | Authoritative source |
| --- | --- |
| What is running/configured/healthy now? | current live-runtime evidence from the intended target |
| What did automation actually execute? | current workflow/job logs + immutable evidence artifacts |
| What source exists now? | current fetched repository branch/commit |
| What is current project status? | `LAYERSENTRY_PROGRESS_LEDGER.md`, corroborated by evidence |
| What are stable product/architecture/security/validation rules? | this Super Master Context |
| How are important components/sources related? | `LAYERSENTRY_KNOWLEDGE_GRAPH.md` |
| What are secure implementation rules? | `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md` |
| What are upgrade/IP/supply-chain rules? | `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md` |
| What differs from upstream CloudStack? | `LAYERSENTRY_UPSTREAM_DIFF.md`, regenerated when required |
| What is the DR target architecture? | `LAYERSENTRY_DRAAS_ARCHITECTURE.md` + current DR decision/evidence records |
| What does CloudStack 4.22.1.x support? | exact source + version-pinned official Apache CloudStack documentation/release notes |
| What does one Codex workstream own? | assigned file under `docs/layersentry/codex/` |

### Conflict rule

Do not average or guess. Resolve conflicts according to the table and gather fresher evidence. Repository/workflow/live evidence overrides historical handoffs.

### Historical-document rule

Historical handoffs/re-audits are audit history after their findings are incorporated into the canonical context. Git history preserves them; they are not normal startup authority.

---

## 1. Mandatory startup and continuity

Before changing source or runtime:

1. read applicable `AGENTS.md`;
2. read this file;
3. read `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. read the assigned workstream file when scoped;
5. use `LAYERSENTRY_KNOWLEDGE_GRAPH.md` when the task crosses components or prior decisions;
6. fetch actual current repository/runner refs and inspect current worktree/state;
7. inspect in-flight workflows/async operations before any potentially conflicting mutation.

Typical source baseline commands:

```bash
git status --short --branch
git remote -v
git branch --show-current
git fetch --all --tags --prune
git rev-parse HEAD
git log -5 --oneline --decorate
```

Never reset to a SHA copied from documentation. Never force-push a shared LayerSentry branch unless explicitly authorized for a known recovery procedure.

---

## 2. Product objectives and boundaries

LayerSentry V1 is a **commercial, production-oriented, on-prem KVM private-cloud product built on Apache CloudStack**, not a new hypervisor and not a replacement cloud scheduler.

Customer outcome:

> A customer receives a simple LayerSentry portal/appliance for VM, Kubernetes, storage, networking, object storage, backup/recovery and validated DR capabilities without needing to operate most CloudStack internals directly.

Architecture:

```text
Customer / Platform Admin / Department Admin / User
                         |
                         v
                 LayerSentry UI
                         |
                         v
       LayerSentry product/automation services
                         |
              supported APIs/contracts
                         |
                         v
              Apache CloudStack 4.22.1.1
                         |
                         v
                    KVM / libvirt
                         |
                         v
        certified storage/network providers
```

LayerSentry value is **simplification, automation, hardening, supportability, validation, evidence and upgrade discipline** around mature upstream capabilities.

### V1 customer scope

- KVM-only normal customer experience;
- role-aware Platform Administrator, Department Administrator and User workflows;
- VM self-service;
- compute/storage profiles;
- supported shared/isolated/VLAN networking and related IP/firewall/LB functions;
- images/templates/ISOs;
- volumes and safe snapshot workflows;
- VM HA/live migration where prerequisites are proven;
- native CloudStack Kubernetes Service (CKS);
- native object-storage bucket workflows;
- Backup & Recovery;
- cross-Zone recovery foundation and LayerSentry DR orchestration as it becomes certified;
- events/alerts/activity/support diagnostics;
- Rocky Linux 9 appliance/bootstrap;
- controlled release/update/rollback model.

### Explicit V1 anti-goals

- DBaaS/APaaS as CloudStack-native LayerSentry V1 services/placeholders;
- a second VM scheduler or provisioning backend;
- a second quota/RBAC/user database;
- replacement Kubernetes/object-storage engines where native CloudStack integration is sufficient;
- deleting non-KVM upstream hypervisor implementations from CloudStack core;
- inventing unsupported API fields to simplify UI;
- claiming impossible-to-reverse-engineer or mathematically immutable appliance properties;
- claiming universal survival of every failure mode.

Future DBaaS belongs above Kubernetes through a separate LayerSentry service/operator model, not inside CloudStack core.

---

## 3. Repositories and project structure

Primary source/product repository:

```text
adaptgurus/cloudstack
  -> CloudStack 4.22.1.1 baseline
  -> LayerSentry UI/product overlay
  -> canonical context/policies/architecture/evidence
```

Integration/live-validation repository:

```text
adaptgurus/cozystack
  -> GitHub runner / Hyper-V / deployment-test automation
  -> durable live validation workflows/artifacts
```

Current branch names/HEADs remain volatile and must be fetched from GitHub and recorded in the progress ledger/evidence rather than frozen into this stable document.

Key documentation:

- `AGENTS.md` — operating rules;
- `LAYERSENTRY_PROGRESS_LEDGER.md` — volatile project checkpoint;
- `LAYERSENTRY_KNOWLEDGE_GRAPH.md` — stable relationship index;
- `LAYERSENTRY_DRAAS_ARCHITECTURE.md` — selected DR architecture;
- `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md` — implementation security;
- `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md` — release/update/IP controls;
- `LAYERSENTRY_DEBUGGING_RUNBOOK.md` — systematic troubleshooting;
- `LAYERSENTRY_UPSTREAM_DIFF.md` — fork/upstream delta record;
- `docs/layersentry/codex/` — scoped workstream contracts.

---

## 4. Development and acceptance environments

### WSL Ubuntu 22.04

Role: development/preliminary tooling environment.  
Current authorized development identity: `opc`.

WSL can validate source/tooling and preliminary automation but does **not** replace final Rocky Linux 9 acceptance.

### Rocky Linux 9

Rocky Linux 9 is the **primary final acceptance environment** for LayerSentry V1 runtime changes and the intended appliance/KVM profile. Apache CloudStack 4.22 supports Rocky Linux 9 for Management Server and KVM profiles.

Current authorized development administration identity for the acceptance VM: `root`.

Final runtime acceptance must cover the applicable application, service, API, dependency, installation, browser, integration, recovery and failure behavior on Rocky Linux 9.

### CloudStack/LayerSentry browser

Current authorized development identity: `admin`.

Browser-facing release acceptance includes actual served UI/UX workflows. CloudStack 4.22 recommends modern Firefox/Chrome/Safari families; LayerSentry acceptance should include current Chrome and Firefox unless the release matrix explicitly documents another scope.

### Credential policy

Temporary development credentials may be supplied by the authorized operator, but **plaintext credential values are never committed to Git, browser code, documentation, logs or evidence artifacts**.

Logical secret references:

```text
LAYERSENTRY_DEV_WSL_PASSWORD
LAYERSENTRY_DEV_ROCKY_ROOT_PASSWORD
LAYERSENTRY_DEV_CLOUDSTACK_ADMIN_PASSWORD
```

Actual values remain in the authorized runtime secret store/operator session. Direct SSH is an approved transport for authorized discovery/deployment/validation, not permission to bypass safety/RBAC/evidence rules.

---

## 5. Research-first architecture decision policy

Before implementing a significant architecture, infrastructure, backend, storage, DR, UI/UX, security, integration, installer, release or automation change:

1. establish the current source/runtime approach;
2. verify version-pinned official documentation/source;
3. research credible alternatives;
4. compare reliability, maintainability, performance, security, scalability, operational simplicity and long-term supportability;
5. keep the established approach unless an alternative provides a defensible improvement;
6. document the decision before implementation.

Do not change an established approach merely for novelty or because it is easier to code.

Every significant decision record includes:

1. existing approach;
2. advantages/disadvantages;
3. alternatives researched;
4. recommended approach;
5. why it is superior;
6. implementation impact;
7. risks/mitigations;
8. testing/validation performed;
9. rollback/recovery procedure;
10. production-readiness status.

---

## 6. Mandatory engineering and testing lifecycle

For every meaningful change:

```text
Research
 -> Design Review
 -> Implementation
 -> Testing
 -> Failure / Edge-Case Validation
 -> Optimization Review
 -> Documentation
 -> Knowledge-Graph Update
 -> Super Master Context / AGENTS.md update when stable rules changed
 -> Git Commit
 -> Final Verification
```

A source commit/build does not mean a capability is complete.

Test coverage is proportional to the affected surface and includes where applicable:

- functional/regression testing;
- GUI/UI/UX/browser validation;
- backend/API validation;
- authentication/authorization/direct-API negative testing;
- install/deploy/idempotent rerun/resume;
- service start/stop/restart/recovery;
- error/edge cases;
- performance/resource efficiency;
- security configuration/trust-boundary testing;
- upgrade/rollback/recovery;
- backup/restore/DR;
- cross-component integration;
- affected existing-functionality regression;
- Rocky Linux 9 final compatibility.

Documentation-only design changes do not require meaningless VM mutation. The runtime capability they describe remains `PENDING`/`NOT_TESTED` until implemented and exercised.

---

## 7. CloudStack-core preservation

Default decision: **do not rewrite CloudStack core**.

Do not change without a documented exception:

- backend API contracts/names;
- CloudStack DB schema for LayerSentry convenience;
- async-job semantics;
- VM lifecycle semantics;
- KVM agent/core orchestration;
- server-side RBAC semantics;
- Zone/Pod/Cluster/Host model;
- storage/network orchestration semantics;
- plugin contracts;
- upstream hypervisor implementations;
- upstream upgrade model.

Prefer in order:

1. LayerSentry UI/product-profile behavior;
2. configuration;
3. supported CloudStack APIs;
4. LayerSentry-specific controller/service;
5. installer/bootstrap automation;
6. narrow upstream patch only when alternatives cannot satisfy the requirement.

Any core-change exception requires exact need, evidence supported interfaces are insufficient, affected subsystem/files, compatibility/security consequences, upgrade/rebase risk, regression tests, rollback/removal strategy and upstream-delta update.

---

## 8. Version and upstream-documentation discipline

LayerSentry V1 targets **Apache CloudStack 4.22.1.1**.

For capability claims:

1. prefer exact current source;
2. use 4.22.1.1 release notes for patch-specific fixes;
3. use version-pinned 4.22.1.x documentation;
4. where exact 4.22.1.1 docs are unavailable, use closest 4.22.1.x page and cross-check source/release notes;
5. never use moving `/latest/` documentation as sole authority.

Stable product profile:

- Rocky Linux 9.x;
- Java 17 for the 4.22 baseline;
- selected validated MySQL-compatible topology/version according to the exact release/profile;
- KVM/libvirt following secure CloudStack KVM guidance.

Do not delete upstream support just because LayerSentry narrows its certified customer profile.

---

## 9. KVM, network and host-security contract

- Compute Clusters must be sufficiently homogeneous for supported scheduling/live migration.
- Do not use insecure unauthenticated libvirt TCP as a production default.
- Validate CloudStack/libvirt security and migration behavior on Rocky Linux 9.
- Nested Hyper-V is a functional POC environment, not proof of physical site independence or BMC fencing.
- Physical OOBM/BMC/IPMI/Redfish fencing must be tested on intended hardware before certification.

### Firewalld

Production target keeps a tested firewall policy. Validate management-agent, migration, console, bridge/VLAN forwarding, System VM, storage, B&R, CKS/CSI and reboot-persistence paths. Do not broadly expose management/libvirt ports.

### SELinux

Production target is `SELinux=enforcing` with reviewed minimal policy. Collect representative AVC denials, avoid blind broad `audit2allow`, and validate management, agent, libvirt, storage, System VM, console, migration, backup, CKS and upgrade paths.

### Networking information

Stable topology/terminology belongs here; current IP/VLAN/gateway values belong in the progress ledger/evidence. Never invent live networking values from an old handoff.

---

## 10. Identity, tenancy and RBAC

CloudStack server-side RBAC remains the security boundary. UI hiding is UX only.

Recommended enterprise model:

- Department -> Domain;
- Department Administrator -> Domain Administrator/custom role;
- team/application isolation -> Account/Project;
- individual identity -> User inside Account.

Users in the same CloudStack Account are not isolated owners of resources. Use separate Accounts/Projects where isolation is required.

Every role test includes presentation plus direct URL/direct API authorization checks and object-ID tampering negatives.

LayerSentry privileged controllers separately authorize any additional DR/support/update action they introduce and use least-privilege service identities.

---

## 11. Feature availability and UI/UX contract

A route/menu is not proof a feature is available.

Expose an optional feature only when applicable gates pass:

1. RBAC/API permission;
2. LayerSentry feature policy;
3. global/Zone configuration;
4. required provider/backend;
5. offerings/templates/networks/storage prerequisites;
6. reliable service/provider health signal when available.

Never display `Healthy`, `Protected`, `Replicated`, `HA`, `Encrypted`, `Backed up` or `DR Ready` without evidence.

### Normal customer navigation

Platform Admin areas may include Dashboard, Compute, Storage, Network, Images, Infrastructure, Backup & DR, Activity and Administration.

Department/User views expose only owned/delegated functions. Physical infrastructure internals remain hidden unless role/support scope requires them.

### Customer terminology

Presentation mappings may include:

- Zone -> Site;
- Pod -> Infrastructure Group;
- Cluster -> Compute Cluster;
- Host -> KVM/Compute Host;
- Service Offering -> Compute Profile;
- Disk Offering -> Storage Profile;
- Template -> OS Image;
- Guest Network -> VM/Workload Network;
- Physical Network -> Datacenter Network.

Mappings are presentation only; backend APIs/fields remain unchanged. Avoid global substitutions that create semantic errors.

---

## 12. VM, CKS and object-storage contracts

### VM workflow

Reuse CloudStack deployment APIs/scheduler. A simple LayerSentry VM wizard may ask Name, OS Image, Compute Profile, Storage Profile/size, VM Network, HA and optional protection, but it must preserve backend semantics.

`Backup Policy` is not a native `deployVirtualMachine` field. Protection selected during VM creation is a separate post-deploy operation: deploy -> wait async result -> assign B&R/DR policy -> verify -> report partial failure honestly.

### CKS

Use native CloudStack Kubernetes Service where it meets requirements. Do not build a second Kubernetes lifecycle engine without a proven limitation.

CSI maps CloudStack Disk Offerings to Kubernetes Storage Classes; do not invent a native CKS `storage profile` field.

Production CKS requires metadata isolation tests so pods cannot access CloudStack VM metadata/user-data unless explicitly required.

NAS VM-level B&R is not the primary protection mechanism for CKS nodes.

Full air-gap CKS remains `PENDING` until an internal-registry/bootstrap path is implemented and live-tested; a binaries ISO alone does not prove complete offline provisioning.

### Object storage

Use native CloudStack Object Storage APIs/provider integration. Show Bucket functionality only when a usable provider is configured. Provider credentials/internal endpoints should not be exposed to ordinary users unless required.

---

## 13. Snapshot-safety contract

CloudStack 4.22 documents KVM safety/compatibility limitations between Instance/VM snapshots and Volume snapshots. LayerSentry must not hide them.

Required behavior:

- detect/guard conflicting snapshot states/policies;
- certify a supported snapshot/protection strategy per storage profile;
- regression-test create/revert/delete/restore combinations;
- avoid unbounded VM snapshot chains;
- never claim both snapshot mechanisms are independently safe without release-specific evidence.

For generic file-backed DR, prefer libvirt backup/checkpoint APIs rather than using long VM snapshot chains as the DR catalog.

---

## 14. Backup & Recovery and DR contract

### CloudStack native foundation

CloudStack B&R is the mandatory first proof and fallback. CloudStack 4.22 can create a VM from a NAS backup in another Zone when repository/destination prerequisites are met. Destination-unique resources such as networks may require mapping. Destination hosts must reach/mount the repository; restore throughput affects RTO.

Backup metadata/source records required by recovery must not be purged while points are intended to remain usable.

Native user backup schedule intervals are HOURLY/DAILY/WEEKLY/MONTHLY; `backup.framework.sync.interval` is an internal reconciliation/scheduling interval, not a 5-minute backup policy.

Native B&R therefore supports a strong **Backup DR** foundation but is not by itself the complete low-RPO automatic DR product.

### Selected LayerSentry DR architecture

Detailed contract: `LAYERSENTRY_DRAAS_ARCHITECTURE.md`.

Selected principles:

1. one provider-neutral Protection Plan/Recovery Point customer experience;
2. CloudStack stays authoritative for normal VM/network/storage/account/Site lifecycle;
3. use CloudStack-native operations when they satisfy the exact action/SLA;
4. prefer certified **storage-native replication** for low-RPO DR;
5. preferred LayerSentry HCI profile is LINSTOR/DRBD, but existing SAN/NAS customers are not forced to migrate;
6. Ceph uses native RBD mirroring when certified;
7. enterprise SAN uses certified array-native consistency-group replication/promotion/reverse replication;
8. generic QCOW2/file-backed NAS fallback uses **libvirt backup/checkpoint APIs**, not a LayerSentry-owned raw QMP/NBD product protocol;
9. CloudStack NAS B&R remains baseline/fallback/long-retention/reseed path;
10. `rsync` is not the primary running-VM replication engine; it may synchronize a validated immutable backup repository or small config/evidence data;
11. Hot Replica and historical Recovery Point Catalog are separate;
12. latest and older retained recovery points must be independently recoverable;
13. multi-disk points are sealed only after every required disk in the consistency epoch is durable;
14. default consistency is crash-consistent; filesystem/application labels require real guest/application evidence;
15. Planned Failover/Failback are certified before emergency Auto Failover;
16. automatic failover requires independent witness/quorum, exclusive recovery lease and safe fencing/no dual writers;
17. traffic switches only after application health validation;
18. UI exposes only RPO/failover tiers that the exact provider/topology has measured and certified.

### DR provider examples

- LINSTOR/DRBD: continuous/certified async hot replica + LINSTOR snapshot shipping for PITR;
- Ceph RBD: `rbd-mirror` + RBD snapshot lineage;
- enterprise SAN: array-native replication + consistency-group snapshots/bookmarks;
- NFS/SharedMountPoint/QCOW2: libvirt incremental backup/checkpoint + CloudStack NAS B&R baseline;
- unsupported backend: native Backup DR only.

### DR readiness truth

A high architecture score is not implementation readiness. Advanced multi-backend DR remains at the evidence status actually achieved; do not transfer a design score to runtime status.

---

## 15. HA/control-plane contract

Target production management profile:

- two load-balancer nodes or enterprise ADC;
- three CloudStack/LayerSentry Management Servers;
- three database nodes in the selected certified topology;
- KVM compute capacity designed for N+1/failure domains.

This becomes HA only when failure-domain placement, quorum, redundant network/storage, capacity and recovery are tested.

CloudStack management-node reboot/failure and DB/schema upgrade availability are different cases. Do not promise zero management-plane downtime for upgrade paths whose upstream procedure requires management services to stop.

If LayerSentry control-plane VMs live on the estate they manage, provide an out-of-band/rescue recovery path that does not depend on a healthy CloudStack API.

---

## 16. Support identity and proprietary Support Cluster UUID

LayerSentry requires one durable proprietary Support Cluster UUID per installed product cluster/environment.

Contract:

```text
Installation
 -> generate Support Cluster UUID once
 -> store in durable local product state
 -> expose read-only in Support/About diagnostics
 -> include in sanitized support bundle
 -> preserve across normal reboot/update
```

The Support Cluster UUID is an identifier, **not an authentication secret**. It must not be used as a password/token.

Do not fabricate it from a CloudStack/KVM/VM UUID. If the current lab value has not been implemented/discovered from live evidence, report `UNKNOWN / PENDING`.

Current volatile UUID value belongs in the progress ledger/evidence after live verification, not in this stable contract.

---

## 17. Appliance and secret-management contract

Production target is appliance-locked, not falsely described as mathematically immutable.

Desired controls:

- SELinux enforcing with reviewed policy;
- tested firewall policy;
- audit logging;
- routine password SSH disabled;
- no routine customer root shell;
- package/repository lockdown for normal admins;
- preinstalled support diagnostics;
- updates only through controlled LayerSentry update mechanism;
- least-privilege service identities;
- secure filesystem/temp handling.

Never commit/print/embed:

- passwords;
- API/session tokens;
- DB/customer credentials;
- reusable SSH private keys;
- signing/license private keys;
- support backdoors.

Secrets use approved runtime/CI stores, rotation, revocation and short-lived credentials where practical.

---

## 18. Secure engineering contract

Follow `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md` for privileged changes.

Minimum principles:

- threat-model new privileged trust boundaries;
- server-side authorization and confused-deputy prevention;
- validate untrusted inputs/types/lengths/state;
- parameterized SQL/ORM binding;
- argv/subprocess execution instead of shell interpolation;
- path/archive/symlink/temp safety;
- SSRF/URL/redirect/egress controls;
- TLS verification by default;
- established cryptographic libraries/formats;
- bounded timeouts/retries/concurrency/resource use;
- secret redaction;
- CI signing-secret isolation;
- security negatives proportional to the boundary.

Do not claim compliance/security controls without measured evidence.

---

## 19. Release and software-supply-chain contract

Production management nodes do not compile the Vue UI.

Target flow:

```text
exact source commit
 -> pinned CI builder/toolchain
 -> lint/static/unit/security checks
 -> production build
 -> policy/terminology/source-map gates
 -> immutable artifact
 -> SBOM + provenance + digest + signature
 -> release manifest
 -> staging/canary
 -> production promotion
```

Required principles:

- pinned dependencies/toolchains;
- production source maps off by default;
- signing keys outside source/customer artifacts;
- machine-readable SBOM;
- source/build/dependency/artifact provenance;
- dependency/vulnerability/secret scanning;
- immutable artifact IDs;
- installer verifies manifest/signature/digest/compatibility;
- fail closed on integrity failure;
- atomic/equivalent deployment with deterministic rollback;
- prior known-good artifact retained where policy permits.

Do not claim a SLSA level unless actually implemented/evidenced.

Release manifest records at least release version, upstream reference, source commit, package versions, OS/runtime compatibility, artifact digests/signatures, SBOM reference, configuration/policy versions, certified provider versions and supported upgrade-from versions.

---

## 20. Installer/deployment contract

Customer experience may be one command, but implementation is modular/stateful/idempotent.

Preferred structure:

- thin entrypoint;
- structured controller + declarative automation where useful;
- versioned inventory/config schema;
- immutable verified artifacts;
- supported CloudStack API client rather than undocumented DB writes;
- explicit state/resume markers;
- health checks/evidence report;
- rollback/recovery classification.

Every mutation is idempotent, deduplicated/state-checked or explicitly marked non-idempotent with recovery procedure.

For CloudStack async jobs, record job IDs and inspect terminal state. Timeout/lost connection is `UNKNOWN` until the exact operation is checked.

The bootstrap controller must not become a runtime single point of failure after successful install.

---

## 21. Upgrade and rollback contract

```text
new upstream release
 -> compatibility audit
 -> upstream-delta review
 -> minimum LayerSentry overlay reapplication
 -> automated build/regression
 -> fresh-install + supported N-1 -> N tests
 -> provider/storage/B&R/DR regression
 -> staging/canary
 -> production
```

Never overwrite a new upstream release with old modified upstream files wholesale.

Before upgrade: verify supported path; validate artifacts; back up DB/config/release manifest; record known-good state; inspect async jobs/provider health; respect schema sequencing; test interruption/resume.

Rollback classification must be honest:

- UI artifact rollback may be an atomic switch;
- service/config rollback requires compatibility;
- package rollback without DB change requires validation;
- schema rollback may require restoring matching pre-upgrade DB/config/software state.

Never promise simple package downgrade after an irreversible/unvalidated DB migration.

---

## 22. Observability, troubleshooting and supportability

LayerSentry must be diagnosable without installing arbitrary packages during incidents.

Sanitized support/evidence tooling should collect as applicable:

- release manifest/package inventory;
- service states;
- management/agent logs/journal;
- KVM/libvirt state;
- network/bridge/VLAN/route state;
- storage/mount/multipath/Ceph/LINSTOR state;
- SELinux AVC summary;
- firewall state;
- DB connectivity/replication summary;
- CKS/CSI/CNI state;
- object store/B&R/DR provider state;
- recent async-job failures;
- sanitized configuration;
- Support Cluster UUID.

No support bundle contains plaintext secrets by default.

Health must distinguish configured, reachable, functionally tested, degraded and unknown.

For non-trivial failures follow `LAYERSENTRY_DEBUGGING_RUNBOOK.md`: baseline evidence -> precise expected/observed -> layer classification -> ranked hypotheses -> discriminating checks -> one causal change -> regression test -> live revalidation. Do not fabricate root cause.

Reusable troubleshooting knowledge connects into `LAYERSENTRY_KNOWLEDGE_GRAPH.md`.

---

## 23. Evidence, status and anti-hallucination protocol

Evidence precedence:

1. current live runtime;
2. workflow/job logs + immutable artifacts;
3. current source;
4. version-pinned official source/docs;
5. stable project contracts;
6. historical handoffs;
7. model inference only as labeled hypothesis.

Never invent:

- HEADs/run/artifact IDs;
- IP/VLAN/gateway/DNS/credentials;
- CloudStack inventory/provider health;
- backup/restore/DR results;
- RPO/RTO;
- DB/LB/HA state;
- permissions;
- test results;
- Support Cluster UUID;
- release certification.

Use only material statuses:

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

A commit is source history, a build is build evidence, HTTP 200 is one endpoint result, and documentation capability is not configured-runtime proof.

---

## 24. Mandatory live-validation contract

Every LayerSentry source/config/installer/workflow/automation change that can affect runtime behavior must be exercised on the authorized **Rocky Linux 9** acceptance environment before `LIVE_VERIFIED`.

Default durable path: `adaptgurus/cozystack` GitHub runner/integration automation.

Before live mutation:

- fetch actual runner branch;
- inspect in-flight/conflicting workflows;
- verify exact target/resource IDs;
- classify R0–R4 risk;
- establish checkpoint/rollback/recovery;
- serialize conflicting operations.

Controlled SSH may be used from the authorized runner/operator path for discovery/deployment/diagnostics/validation. Credentials are runtime-injected and never committed/logged/artifacted.

Live evidence records exact source/artifact, workflow/job/artifact IDs where used, target scope, mutations, assertions, negatives/retries, cleanup/rollback and limitations.

If live validation is unavailable, retain a truthful lower status.

For Backup/DR/storage: test the exact backend; latest and older retained points; guest data; network/IP mapping; retry/idempotency; provider restart where applicable; RPO/RTO/overhead. Automatic failover/fencing/failback is R4.

---

## 25. Change-risk classification

Use the highest applicable class.

- **R0** — read-only discovery/documentation; no runtime mutation.
- **R1** — source-only reversible change.
- **R2** — controlled reversible deployment with known rollback.
- **R3** — infrastructure-affecting network/storage/package/DB/firewall/reboot/topology mutation.
- **R4** — destructive/high-consequence operation such as DR failover/failback/fencing, destructive storage test, DB/schema restore/upgrade or broad network change.

R3/R4 require current-state inspection, exact target, durable checkpoint, rollback/recovery, idempotency/deduplication, explicit task authorization and serialized execution.

Never repeat an R2–R4 action after timeout/session loss until the exact prior operation has been checked.

---

## 26. Multi-agent governance

Use isolated worktrees/branches. Never let two writing agents share one worktree.

Default ownership:

- A — UI/Self-service;
- B — Release/Installer/Build;
- C — Security/Validation;
- D — DR/HA/Upgrade and runner automation.

Agents do not self-merge into the shared integration branch unless explicitly assigned integration authority. Serialize heavy builds and conflicting live lab mutations.

Every handoff records repository/branch/base/final commit, files changed, core impact, design decision, tests/evidence, runtime mutations, limitations, rollback state, knowledge/context updates and next gate.

---

## 27. Production certification gates

`PRODUCTION_CERTIFIED` applies to an exact release/artifact/profile, never to the project in general.

Applicable gates include:

### Release/supply chain

- exact release manifest/source;
- signed immutable artifact/digest;
- SBOM/provenance;
- dependency/security/secret checks;
- promotion/rollback path.

### Installation/recovery

- clean Rocky Linux 9 install;
- idempotent rerun/resume;
- interruption recovery;
- fail-closed integrity behavior;
- deterministic rollback/recovery.

### UI/RBAC

- branding/terminology;
- KVM-only customer profile;
- no V1 DBaaS/APaaS placeholders;
- feature prerequisite gating;
- Platform/Department/User/read-only roles;
- direct URL/API negatives;
- loading/empty/error states;
- browser acceptance/accessibility/contrast review.

### Security/appliance

- SELinux enforcing;
- firewall policy;
- routine root/password access disabled in production profile;
- repository/package lockdown;
- signed update path;
- support-bundle secret redaction;
- no unresolved release-blocking security issue without explicit acceptance.

### Core function

Representative VM lifecycle, storage, network, console, HA/live migration, restart/failure behavior.

### Optional integrations

Only enabled/certified integrations need their positive gate; disabled/uncertified integrations must be hidden/clearly unavailable.

### B&R/DR

- native backup/restore;
- cross-Zone recovery/mapping;
- source-record retention guard;
- exact provider replication path;
- latest + old checkpoint restore;
- Test Recovery;
- planned failover/failback;
- measured RPO/RTO/throughput/overhead;
- witness/fencing/automatic failover only for independent certified failure domains.

### HA

- management/LB fail/reboot;
- KVM agent management connectivity;
- DB failure behavior for exact topology;
- physical fencing only on supported tested hardware.

### Upgrade

- fresh target install;
- supported N-1 -> N;
- interruption/resume;
- schema-aware sequencing;
- post-upgrade functional/security/provider regression;
- rollback/recovery class.

### Reliability/performance

Release-specific acceptance thresholds for concurrency, capacity, error paths, disk exhaustion, service restart, DB/network/storage interruption, DR backlog and meaningful soak/stability duration. Do not invent universal performance numbers.

---

## 28. Durable evidence and knowledge graph

Chat history is not the persistence layer.

Durable project state is:

- Git commits;
- progress ledger;
- workflow/job logs;
- immutable evidence artifacts;
- verified live state;
- architecture/policy decisions;
- knowledge graph.

After meaningful work persist enough to resume from the first unmet gate.

`LAYERSENTRY_KNOWLEDGE_GRAPH.md` stores durable relationships, not volatile values. Update it when component relationships, dependencies, environment roles, architecture decisions, validation flows, support flows or reusable troubleshooting knowledge changes.

Current HEADs, workflow IDs, passwords, live IPs and temporary blockers do not belong in the knowledge graph or this Super Master Context.

---

## 29. Effort-planning model

Effort ranges are planning aids, not promises.

Historical base V1 ranges while aggressively reusing CloudStack capabilities were approximately:

- GUI/self-service: **6–9 engineering man-days**;
- automated HA installer/Rocky appliance/K8s/buckets: **9–12**;
- native cross-Zone recovery + simplified DR UX baseline: **2–3**;
- deep base production validation: **3–5**.

The prior `+5–7 man-day` advanced-DR placeholder is **superseded and must not be used** for the expanded requirement.

Current advanced multi-backend DR planning after native two-Zone proof is approximately **36–57 engineering man-days** for NAS/file-backed DR, LINSTOR/DRBD, a first enterprise-SAN family, PITR catalog, Test Recovery, recovery groups, planned/automatic failover, witness/fencing, failback, security and scale/failure testing. Additional storage families/providers add separate adapter/certification effort.

Calendar duration can be shorter with safe parallelism, but production certification is constrained by integration, physical lab/failure-domain availability, destructive tests, performance/soak and evidence.

Re-estimate from current evidence at major milestones.

---

## 30. Context-maintenance and continuation rules

This Super Master Context changes only when a **stable** product, architecture, security, acceptance, support or engineering rule changes. Volatile progress belongs in the ledger/evidence.

Do not duplicate the same rule across many files when a reference is sufficient. Keep detailed specialist content in specialist docs and use the knowledge graph for navigation.

When CloudStack target version changes, repeat source/document compatibility research and provider validation before carrying forward capability claims.

### Continuation instruction

For a new ChatGPT/Codex session:

> Continue LayerSentry from repository/workflow/live evidence, not memory. Read `AGENTS.md`, the Super Master Context, the Progress Ledger and assigned workstream. Use the Knowledge Graph to locate related decisions. Fetch actual CloudStack and cozystack refs before editing. Research significant alternatives before implementation, preserve CloudStack core, validate runtime-affecting work on Rocky Linux 9, never persist plaintext credentials, and never promote status beyond its evidence gate.

---

## 31. Definition of success

The engineering principle is:

> **Preserve CloudStack's mature engine. Make LayerSentry simple, secure, storage-aware, supportable, evidence-driven and inexpensive to carry forward to future releases.**

The best change is the smallest supportable change that satisfies the requirement, improves a defensible engineering dimension, fails safely, can be diagnosed/upgraded/recovered, has explicit test evidence, updates durable project knowledge, and leaves the next engineering session with no need to guess what happened.
