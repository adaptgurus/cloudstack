# LayerSentry DRaaS — Production-Oriented Recovery-Plan Architecture

**Status:** `DESIGN_DEFINED`  
**Baseline:** Apache CloudStack 4.22.1.1 + LayerSentry KVM-first product layer  
**Design goal:** Nutanix-like customer simplicity with storage-native-first replication and a provider-neutral recovery plane  
**Scope:** target architecture and implementation contract. This is not runtime or production-certification evidence.

The detailed pre-implementation comparison and decision record is:

`docs/layersentry/evidence/dr/2026-09-05-draas-architecture-revalidation.md`

The stable project relationships are indexed in:

`docs/layersentry/LAYERSENTRY_KNOWLEDGE_GRAPH.md`

---

## 1. Customer outcome

The customer workflow must remain simple regardless of whether the underlying storage is NAS, LINSTOR/DRBD, Ceph, enterprise SAN or another certified provider.

```text
DR
 -> Create Protection Plan
 -> Select VM / Application Group
 -> Select DR Site
 -> Select DR Network / VLAN
 -> Select DR IP policy
 -> Select RPO / retention
 -> Enable Protection
```

Normal operations expose only:

- **Test Recovery**
- **Planned Failover**
- **Failback**
- **Recover** from a selected recovery point
- **Auto Failover** only when witness/fencing prerequisites are certified

The normal user must not need to understand QEMU dirty bitmaps, DRBD protocol, RBD mirroring, SAN consistency groups, NBD, multipath or provider-specific promotion commands.

Target lifecycle:

```text
Protect
 -> Protected / measured lag
 -> choose latest or older Recovery Point when needed
 -> Test Recovery without production impact
 -> planned or safe automatic failover
 -> DR Active
 -> reverse replication
 -> Failback
```

---

## 2. Preserve CloudStack as the infrastructure authority

LayerSentry DR is an orchestration extension around CloudStack; it is not a second cloud scheduler.

CloudStack remains authoritative for:

- Site/Zone;
- Pod/Infrastructure Group;
- Compute Cluster/KVM Host;
- VM lifecycle;
- volumes and primary-storage attachment;
- networks and network services;
- account/domain/project/RBAC;
- normal KVM/libvirt orchestration;
- native Backup & Recovery APIs and supported snapshot behavior.

LayerSentry owns only DR-specific product state:

- Site pairing metadata;
- Protection Plans;
- provider capability bindings;
- Recovery Point Catalog;
- Recovery Groups and dependency order;
- DR network/VLAN/IP mappings;
- recovery/failover/failback state machine;
- witness/fencing eligibility;
- traffic-switch adapters;
- DR audit/RPO/RTO evidence.

Do not add DR convenience columns/tables to CloudStack core merely because it is easier. Use a LayerSentry-specific service/state store outside upstream CloudStack tables unless a documented exception is approved.

---

## 3. Reuse existing CloudStack 4.22.1.1 capabilities first

CloudStack already supplies important DR/recovery foundations:

- provider/plugin-based Backup & Recovery framework;
- KVM NAS B&R provider;
- backup offerings, adhoc backup and user scheduling;
- `createBackup`, `listBackups`, `restoreBackup`, volume restore and `createVMFromBackup` APIs;
- VM metadata retained with backups;
- creation of a new VM from a selected older backup;
- since 4.22, creation of a VM from NAS backup in another Zone;
- destination resource/network selection where resources differ;
- native KVM file-backed incremental Volume Snapshot capability when prerequisites are met;
- storage-based and file-based KVM Instance Snapshot capabilities with documented limitations;
- native LINSTOR KVM primary storage;
- CloudStack 4.22.1.x NAS B&R support for VMs on LINSTOR primary storage.

### Native B&R role in LayerSentry

Native CloudStack B&R is the mandatory baseline and safe fallback. It is particularly suitable for:

- **Backup DR** tiers with hourly-or-greater RPO;
- long-retention recovery points;
- independent full/base recovery points;
- re-seeding when an incremental/storage-native lineage is invalid;
- cross-Zone recovery proof before advanced orchestration is enabled.

CloudStack B&R alone is not the target low-RPO DR controller because native user schedules are HOURLY/DAILY/WEEKLY/MONTHLY and upstream does not provide the complete Recovery Plan/witness/fencing/failback control plane.

---

## 4. Final provider-selection hierarchy

The selected architecture uses the highest-level, most mature supported primitive available for the backend.

```text
Protection Plan
  |
  +-> Does a CloudStack-native capability satisfy the exact SLA/action?
  |      YES -> use supported CloudStack API
  |
  +-> Is a certified storage-native replication provider available?
  |      YES -> use provider-native replication adapter
  |
  +-> Is this a supported QCOW2/file-backed KVM workload?
  |      YES -> use libvirt backup/checkpoint adapter
  |
  +-> otherwise
         -> expose Backup DR/native B&R only
```

### Provider matrix

| Storage | Hot/current replica | PITR/retention | Baseline/fallback |
| --- | --- | --- | --- |
| **LINSTOR/DRBD HCI/SDS** | DRBD/LINSTOR real-time or certified async mode | LINSTOR snapshot + snapshot shipping | CloudStack NAS B&R where supported |
| **Ceph RBD** | `rbd-mirror` journal/snapshot mode according to certified SLA | RBD snapshots/bookmarks + catalog | CloudStack supported recovery path |
| **Enterprise SAN** | certified array-native async/sync consistency-group replication | array snapshot/bookmark/clone | CloudStack VM metadata/lifecycle + backup fallback |
| **NFS/SharedMountPoint/QCOW2** | libvirt domain backup/checkpoint incremental path | sealed DR-side incremental/full points | CloudStack NAS B&R |
| **ZFS/ZVOL where independently managed/certified** | native ZFS replication/send-receive where it is the actual storage contract | ZFS snapshots | CloudStack lifecycle integration as applicable |
| **Unsupported/uncertified** | none beyond supported upstream capability | native backups only | CloudStack B&R |

The user never chooses this low-level provider in normal mode. LayerSentry detects it and exposes only protection tiers the source+DR topology has actually qualified for.

---

## 5. Why storage-native replication is preferred for low-RPO DR

A storage system already knows its own consistency, allocation, replication, promotion and ownership semantics better than a host-side generic copier.

For LINSTOR, Ceph and enterprise SAN, storage-native replication normally gives:

- less data movement through KVM hosts;
- provider-native change tracking;
- better consistency-group support;
- explicit primary/secondary or promote/demote semantics;
- provider telemetry for lag/health;
- more efficient reverse replication;
- lower custom code and better long-term maintainability;
- a clearer fencing/dual-writer model.

LayerSentry standardizes orchestration and evidence without pretending all storage engines behave identically.

Each backend/firmware family remains a separate certification target.

---

## 6. Preferred LayerSentry HCI profile — LINSTOR/DRBD

LINSTOR/DRBD is the preferred LayerSentry-owned HCI/SDS profile because it aligns well with KVM, CloudStack and the DR requirements.

### Local HCI/HA

Use LINSTOR placement and DRBD replication inside the site according to the certified HCI profile.

### Remote DR

Choose the replication mode according to measured WAN latency/bandwidth and target RPO:

1. continuous DRBD replication where topology and workload permit;
2. certified asynchronous/semi-synchronous mode for longer links;
3. optional DRBD Proxy only where licensing and performance requirements justify it;
4. LINSTOR snapshot shipping when WAN characteristics or PITR requirements favor point-in-time delta shipment.

Do not stretch synchronous write acknowledgment across an unsuitable WAN simply to advertise a low RPO.

### PITR

Use LINSTOR snapshots/backup shipping for independently addressable historical points. Real-time replication and point-in-time backup are complementary: corruption/deletion can be replicated immediately, so DRBD replication alone is not a substitute for retained snapshots.

### Product positioning

Customers choosing LayerSentry HCI can receive the most integrated low-RPO path. Customers with NAS/SAN are not forced to migrate to LINSTOR.

---

## 7. Enterprise SAN adapter contract

Do not create a host-level block copier for arrays that already provide certified replication.

A SAN adapter must be able to implement, when the array supports it:

```text
discoverCapabilities()
resolveCloudStackVolumeToArrayObject()
createConsistencyPoint()
startProtection()
getReplicationState()
getReplicationLag()
listRecoveryPoints()
verifyRecoveryPoint()
promote()
demote()
reverseReplication()
createTestClone()
mapToDRHosts()
verifyHostAccess()
fenceWriteOwnership()
deleteRecoveryPoint()
```

Required correctness checks include:

- exact source/destination array identity;
- LUN/volume mapping;
- consistency group membership;
- host group/initiator mapping;
- WWID identity;
- multipath health;
- no dual-writable source/DR presentation during failover;
- safe promote/demote/reprotect sequence;
- exact firmware/API version certification.

If the adapter cannot establish safe write ownership, automatic failover is ineligible.

---

## 8. Ceph RBD provider

Use native `rbd-mirror` rather than pulling RBD blocks through a generic LayerSentry copier.

Ceph supports asynchronous mirroring in journal-based and snapshot-based modes. The exact mode is a provider-policy decision:

- journal mode gives fine-grained ordered replication but adds write overhead;
- snapshot mode transfers changed deltas and may provide a better write-performance tradeoff for some workloads;
- both require enough WAN capacity and correct primary/non-primary management.

LayerSentry is responsible for:

- mapping the CloudStack VM/disk to the exact RBD image;
- checking mirror state/lag;
- coordinating multi-disk application epochs where required;
- safe promotion/demotion;
- Recovery Point Catalog metadata;
- network/application recovery;
- witness/fencing/failback orchestration.

Forced promotion without safely excluding the prior primary is an emergency exception, not the normal automatic path.

---

## 9. Generic NAS/file-backed fallback — libvirt, not a custom raw QMP protocol

For supported QCOW2/file-backed KVM workloads where no better storage-native replication exists, use libvirt's backup/checkpoint API as the product boundary.

### Why

`virDomainBackupBegin()` supports full/incremental backups and domain checkpoints. Libvirt uses QEMU dirty bitmaps underneath, so LayerSentry gets changed-block efficiency without making raw QMP commands its external contract.

Benefits:

- lower QEMU version coupling;
- domain-level semantics;
- fewer custom low-level failure paths;
- supported push/pull backup abstraction;
- easier future libvirt/QEMU validation.

### Initial protection

```text
Discover VM + disks
 -> verify destination capacity/mapping
 -> create full baseline + checkpoint
 -> copy/ship baseline to DR
 -> track writes during seed
 -> transfer catch-up delta
 -> seal destination recovery point
 -> mark Protected only after durable destination acknowledgement
```

### Incremental epoch

```text
libvirt checkpoint N
 -> changed extents since prior checkpoint
 -> bounded transfer/receiver
 -> destination durable write + integrity validation
 -> seal Recovery Point N
 -> source lineage advances only after successful destination commit
```

### QEMU bitmap correctness remains relevant

- persistent dirty bitmaps are QCOW2-specific;
- raw-image transient bitmaps do not survive QEMU exit;
- an inconsistent bitmap after unclean shutdown cannot be trusted;
- chain loss triggers a safe new baseline/reseed;
- never display `Protected` when lineage is inconsistent.

Do not expose an unauthenticated NBD endpoint over the DR WAN. If pull mode is used internally, constrain it to the local trusted host/agent boundary and move data through the authenticated LayerSentry replication transport.

---

## 10. `rsync` policy

`rsync` is explicitly **not** the generic running-VM replication engine.

It may be used for:

- small configuration/evidence files;
- a zone-local CloudStack backup-repository synchronization design where the repository content is already immutable/consistent and the exact workflow has been tested;
- operational transfers that do not pretend to provide changed-block VM consistency.

Repository synchronization still needs:

- atomic publication/manifest;
- integrity checks;
- partial-transfer handling;
- retention coordination;
- sufficient WAN bandwidth;
- proof that CloudStack sees a complete backup before recovery is allowed.

---

## 11. Hot replica and point-in-time recovery are separate

The DR site maintains both:

```text
HOT REPLICA
  -> newest safely promotable state
  -> used for planned/emergency failover

RECOVERY POINT CATALOG
  -> RP-N
  -> RP-N-1
  -> older hourly/daily/weekly points
  -> application-consistent points where actually proven
```

A user can choose **Recover** or **Test Recovery** and select an older point.

### Recovery Point minimum record

- plan/application/VM ID;
- source and DR Site IDs;
- consistency epoch ID;
- timestamp/source clock reference;
- consistency class;
- every disk/provider checkpoint ID;
- baseline/parent dependencies;
- destination object/storage IDs;
- integrity/checksum state where supported;
- retention class/expiry;
- measured lag/RPO;
- validation state;
- last successful Test Recovery reference.

A point is usable only when its entire data/dependency chain exists.

### Multi-disk atomicity

One VM/application recovery point may contain multiple provider checkpoints. Seal the logical point only after all required disks are durable. Partial disk success must not be presented as a complete VM/application recovery point.

---

## 12. Snapshot safety policy

CloudStack 4.22 documents KVM limitations between VM/Instance snapshots and Volume snapshots. LayerSentry must not combine them indiscriminately.

For each storage profile, certify one supported protection strategy and guard conflicting actions.

Principles:

- do not maintain unbounded VM snapshot chains;
- do not rely on a long qcow2 parent/child chain as the only DR copy;
- create periodic durable baselines/full points;
- keep DR recovery history independent of the source's ordinary user snapshot lifecycle where possible;
- detect incompatible existing VM/Volume snapshot state before protection or restore;
- regression-test snapshot/create/delete/revert/restore interactions for the exact release.

---

## 13. Application consistency

Default: **crash-consistent**.

Filesystem consistency may use QEMU Guest Agent freeze/thaw where supported. Freeze only for the short checkpoint/consistency-marker window, never for WAN transfer duration.

Application consistency requires application-aware integration such as:

- Windows VSS where properly integrated;
- database-native pre/post hooks;
- transactional application hooks;
- application-group coordination.

Never label a filesystem-frozen point `Application Consistent` without successful application-specific evidence.

---

## 14. Site pairing and metadata sync

The user pairs the DR Site once:

```text
Administration -> DR Sites -> Pair Site
```

Pairing synchronizes only the metadata/capabilities needed for plans:

- Site/Zone identity;
- compute clusters/capacity;
- storage pools/provider capabilities;
- VM networks/VLAN IDs;
- CIDR/subnet/gateway;
- DR IP pools;
- traffic-switch capability;
- provider health/last sync.

Do **not** copy a long-lived CloudStack administrator password or storage-array credential to the peer site. Each site keeps local provider credentials in its own secret boundary.

---

## 15. Simplified Protection Plan UI

### Step 1 — Workloads

- one VM;
- multiple VMs;
- application/Recovery Group.

### Step 2 — DR Site

Show only paired Sites that satisfy minimum compute/storage/network prerequisites.

### Step 3 — Network mapping

Auto-suggest destination networks from synchronized metadata.

```text
Source                     DR
WEB / VLAN 120       ->    DR-WEB / VLAN 520
APP / VLAN 121       ->    DR-APP / VLAN 521
DB  / VLAN 122       ->    DR-DB  / VLAN 522
```

IP modes:

1. **Use DR IP Pool** — preferred general default;
2. **Static Mapping** — deterministic operator mapping;
3. **Keep IP** — only when stretched-L2/routing semantics are validated;
4. **DHCP** — only for intentionally DHCP-driven DR networks.

### Step 4 — Protection policy

The UI shows only provider-qualified policies. Example product categories:

- **Backup DR** — >= 60 min target, manual/planned recovery;
- **Standard DR** — <= 5 min target, only for measured/certified providers;
- **Advanced DR** — <= 1 min target, only for measured/certified providers;
- **Metro DR** — near-zero/zero target only with certified synchronous storage, latency, quorum/fencing and application topology.

These are policy targets, not universal promises.

### Step 5 — Review

Display:

- protected workloads;
- source/DR Site;
- source -> destination network/IP mapping;
- detected provider;
- target RPO/retention;
- initial seed size;
- current eligibility/missing prerequisites;
- auto-failover eligibility.

Button: **Enable Protection**.

---

## 16. Recovery Groups

A Recovery Group is the application failover unit.

```text
Stage 0: required network/security virtual appliances
Stage 1: database
Stage 2: cache / queue
Stage 3: application
Stage 4: web
Stage 5: load balancer / traffic endpoint
```

Each stage can define:

- parallelism;
- startup timeout;
- TCP/HTTP/application health gate;
- pre/post recovery hook;
- stop/continue/manual-approval behavior.

Do not switch production traffic until all required health gates pass.

---

## 17. Test Recovery

Test Recovery is first-class and must not modify the production replica lineage.

```text
selected Recovery Point
 -> isolated DR test network
 -> temporary VM/group
 -> apply test IP mappings
 -> boot dependency stages
 -> application/guest validation
 -> timing/evidence report
 -> cleanup + orphan check
```

Default isolation must prevent accidental production DNS/BGP/IP advertisements.

Users should be able to Test Recovery from the latest point **or an older retained point**.

---

## 18. Planned failover before emergency automation

Certify Planned Failover and Failback before enabling automatic disaster declaration.

Planned sequence:

```text
preflight source + DR
 -> stop/quiesce application according to policy
 -> final replication epoch
 -> verify DR caught up
 -> fence/demote source write side
 -> promote DR storage
 -> recover VM definitions through CloudStack
 -> apply network/IP mapping
 -> start dependency stages
 -> validate application
 -> switch traffic
 -> DR_ACTIVE
```

Every operation is persisted, idempotent or explicitly recovery-controlled.

---

## 19. Automatic failover — witness and fencing are mandatory

Never implement:

```text
ping fails -> start DR
```

Automatic site recovery requires:

- multiple independent source health signals;
- third-fault-domain witness/quorum;
- exclusive recovery lease;
- proven source fence;
- no dual-writer storage condition;
- provider-safe promotion;
- durable state machine;
- application validation;
- traffic switching only after validation.

Possible fencing mechanisms depend on the deployment:

- BMC/OOBM;
- provider-native storage demotion/fence;
- SAN presentation removal;
- SDN/firewall isolation;
- BGP/route withdrawal;
- hypervisor/cluster fence.

If exclusivity cannot be established, automatic failover is disabled or requires explicit high-risk operator override.

---

## 20. Durable failover state machine

```text
NORMAL
 -> SUSPECT
 -> VALIDATE_FAILURE
 -> ACQUIRE_RECOVERY_LEASE
 -> FENCE_SOURCE
 -> SELECT_RECOVERY_POINT
 -> PROMOTE_STORAGE
 -> CREATE_OR_RECOVER_VM_DEFINITIONS
 -> APPLY_NETWORK_MAPPING
 -> APPLY_IP_MAPPING
 -> START_RECOVERY_STAGES
 -> VALIDATE_APPLICATION
 -> SWITCH_TRAFFIC
 -> DR_ACTIVE
```

Each phase must be:

- durable/persisted;
- bounded by timeout;
- idempotent or deduplicated;
- restartable after controller failure;
- auditable;
- queryable without mutation;
- explicit about partial/failure state.

A lost session/timeout never authorizes blindly rerunning the phase.

---

## 21. Failback

Failback is part of the product.

```text
DR_ACTIVE
 -> validate preferred/source Site repaired
 -> reverse replication or rebuild/reseed
 -> catch source up
 -> source readiness preflight
 -> acquire cutback lease
 -> final application consistency epoch
 -> fence/demote DR write side
 -> promote source storage
 -> recover/start workload stages
 -> validate
 -> switch traffic back
 -> resume normal source -> DR protection
```

Use the same fencing, idempotency, health and evidence rules as failover.

---

## 22. Traffic-switch adapter

A powered-on DR VM is not a completed disaster recovery event.

Provider-neutral traffic integrations may include:

- DNS/GSLB;
- ADC/LB pool activation;
- BGP route advertisement/withdrawal;
- firewall/NAT mapping;
- SDN;
- certified stretched-L2 mode.

Traffic moves only after application health gates pass.

For DNS, show configured TTL and do not equate VM boot time with user traffic convergence.

---

## 23. Scale and performance architecture

Do not create one giant single-threaded replication worker.

### Data plane

- distributed agent per KVM host/storage-access domain where generic host-side transfer is needed;
- storage-native provider workers where the storage owns replication;
- bounded worker/concurrency pools;
- WAN bandwidth scheduling;
- priority by protection policy;
- destination backpressure;
- staggered checkpoint creation to avoid snapshot storms;
- resumable transfer where the provider supports it.

### Control plane

- restartable controller replicas where practical;
- durable plan/state-machine store;
- no guest data through the web UI process;
- DR data path separated from ordinary CloudStack management traffic;
- witness outside source/DR failure domains.

### Measure continuously

- VM/disk change rate;
- provider replication throughput;
- lag seconds;
- queue depth;
- WAN utilization/loss;
- storage latency;
- expected time to RPO breach;
- destination capacity/headroom;
- recovery-point creation/validation time.

Mark a plan `At Risk` before the configured RPO is actually exceeded when measured throughput predicts an imminent breach.

---

## 24. Security and tenant isolation

The DR service is privileged.

Minimum requirements:

- CloudStack server-side RBAC remains authoritative for CloudStack resources;
- LayerSentry authorizes the exact DR operation/resource/tenant;
- no cross-tenant object-ID substitution;
- least-privilege service identities;
- mTLS between paired-site components;
- short-lived/rotatable credentials;
- provider credentials remain local to the required site;
- no arbitrary untrusted replication target/URL;
- explicit allowlisted Site pairing;
- secrets never in browser bundles/Git/logs/artifacts;
- bounded payloads/timeouts/retries/concurrency;
- audit every protect/test/recover/failover/fence/failback/delete/override action;
- data-in-transit encryption;
- at-rest encryption status only from the real provider;
- direct API/RBAC and cross-tenant negative tests.

Follow `docs/layersentry/LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`.

---

## 25. Truthful dashboard

| Field | Meaning |
| --- | --- |
| Status | Protected / Syncing / At Risk / Failed / DR Active |
| Source | source Site |
| DR Site | paired recovery Site |
| Target RPO | configured objective |
| Current Lag | measured provider lag |
| Last Safe Recovery Point | destination-validated point |
| Recovery Readiness | compute + storage + network + provider preflight |
| Last Test | successful isolated Test Recovery |
| Auto Failover | Enabled / Disabled / Blocked with reason |
| Failback Ready | measured state, not static text |

Never show `Protected`, `Healthy`, `Replicated` or `DR Ready` without current evidence.

---

## 26. Mandatory implementation/evidence gates

### Gate A — native CloudStack two-Zone recovery

- supported B&R provider/repository;
- cross-Zone create-from-backup;
- destination network mapping;
- repeated recoveries;
- older backup recovery;
- RPO/RTO timing;
- negative cases.

### Gate B — Site Pairing

- mutual trust;
- metadata/capability sync;
- network/VLAN/IP pool sync;
- provider/capacity discovery;
- no secret leakage.

### Gate C — Protection Plan + Recovery Point Catalog

- provider-neutral plan;
- RBAC;
- network/IP mapping;
- retention;
- full disk/epoch membership;
- provider capability gating.

### Gate D — first production provider

Prefer the actual storage profile intended for LayerSentry production. If LayerSentry HCI is first, certify LINSTOR/DRBD. If current customer storage is NAS/SAN, certify that backend first.

For every provider:

- baseline/seed;
- >=2 incremental/replication epochs where applicable;
- restart/resume;
- provider loss/recovery;
- latest-point restore;
- older-point restore;
- data validation;
- measured overhead/lag.

### Gate E — Test Recovery

- isolated network;
- no production collision;
- selected old/latest point;
- automated validation/cleanup.

### Gate F — planned failover/failback

- final delta;
- provider demote/promote;
- Recovery Group order;
- network/IP mapping;
- traffic switch;
- reverse replication;
- repeatability.

### Gate G — automatic failover

- independent witness;
- fence/exclusive lease;
- WAN partition tests;
- witness loss;
- source return;
- controller restart during every phase;
- no double promotion.

### Gate H — production certification

- independent physical/site failure domains;
- hard source power/network loss;
- storage/provider failure;
- stale/corrupt recovery point;
- capacity exhaustion;
- RPO backlog;
- missing mapping;
- application-stage failure;
- duplicate/replayed requests;
- successful failback;
- RBAC/security negative testing;
- performance/scale/soak;
- supported upgrade/rollback regression.

---

## 27. Rocky Linux 9 acceptance

Rocky Linux 9 is the primary LayerSentry acceptance environment.

Runtime-affecting DR changes require final validation on the authorized Rocky Linux 9 environment using the `adaptgurus/cozystack` GitHub runner/integration path or another explicitly approved durable path.

Development/preliminary validation on WSL or another OS does not replace Rocky Linux 9 acceptance.

Evidence must include exact source/artifact, target, provider, workflow/job/artifact IDs where runner automation is used, mutations, assertions, negative cases, rollback state and remaining limitations.

Documentation/design changes do not require a meaningless VM mutation; their described runtime capability remains `PENDING`/`NOT_TESTED` until implemented and live-tested.

---

## 28. Architecture score and status

Weighted pre-implementation review selected this architecture at approximately **9.3/10 as a design direction** because it provides the best balance of reliability, maintainability, performance, security, scalability, operational simplicity and long-term supportability.

That score is **not** implementation readiness.

Current state:

- architecture: `DESIGN_DEFINED`;
- advanced multi-backend DR implementation: `PENDING`;
- independent-site automatic failover/failback: `NOT_TESTED`;
- production certification: `PENDING`.

A literal 10/10 production resilience claim is not credible. After implementation, the practical target is roughly 9–9.5/10 with repeated independent-site failure, security, upgrade, scale and failback evidence.

---

## 29. Non-negotiable boundaries

1. CloudStack remains authoritative for normal VM/network/storage/account/Zone lifecycle.
2. Advanced DR orchestration stays outside CloudStack core unless a documented exception passes review.
3. Prefer storage-native replication for low-RPO DR when certified.
4. Prefer libvirt backup/checkpoint APIs over a LayerSentry-owned raw QMP/NBD protocol for the generic file-backed fallback.
5. No `rsync` primary running-VM replication engine.
6. No unbounded VM snapshot chain as the only DR copy.
7. No incompatible VM/Volume snapshot combination hidden behind the UI.
8. No `ping failed -> boot DR` automatic recovery.
9. No automatic failover without witness/quorum and safe fencing/exclusivity.
10. No source lineage advancement or `Protected` state before the destination has durably committed the required point.
11. No advertised RPO/failover tier without provider/topology certification.
12. No traffic switch before required application health gates pass.
13. Test Recovery, older-point recovery and Failback are part of the product definition.
14. Every runtime claim requires Rocky Linux 9 evidence at the applicable status gate.
