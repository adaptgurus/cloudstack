# LayerSentry DRaaS — Simple Recovery-Plan Architecture

**Status:** `DESIGN_DEFINED`  
**Baseline:** Apache CloudStack 4.22.1.1 + LayerSentry KVM-first product layer  
**Design goal:** Nutanix-like simplicity for the customer, storage-aware production-grade replication underneath  
**Scope of this document:** target architecture and implementation contract only. It is not runtime or production-certification evidence.

---

## 1. Customer outcome

The customer should not need to understand QEMU dirty bitmaps, NBD, Ceph mirroring, ZFS streams, storage-array replication, fencing state machines or CloudStack internals.

The desired product experience is:

```text
DR
 -> Create Protection Plan
 -> Select VM / Application Group
 -> Select DR Site
 -> Select DR Network / VLAN
 -> Select DR IP policy
 -> Select RPO policy
 -> Enable Protection
```

After protection is enabled:

```text
Healthy
 -> incremental changed data continuously moves to DR
 -> recovery points are created at the configured RPO
 -> LayerSentry continuously verifies DR readiness

DC failure
 -> validate failure
 -> obtain witness/quorum decision
 -> fence/isolate source where required
 -> promote latest safe DR replica
 -> attach DR network/IP mapping
 -> start application tiers in order
 -> validate health
 -> switch traffic
 -> DR ACTIVE

DC returns
 -> reverse-sync
 -> planned failback
 -> validate
 -> production returns to the preferred site
```

The customer-facing operational controls should normally be only:

- **Test Recovery**
- **Planned Failover**
- **Failback**
- **Auto Failover** toggle, available only when witness/fencing/network prerequisites are certified

Do not expose low-level replication choices in normal mode unless support/advanced mode is explicitly requested.

---

## 2. Nutanix design principles to copy — not proprietary implementation

LayerSentry should copy the successful product principles visible in Nutanix DR rather than attempt to clone proprietary Nutanix storage internals:

1. Protection policy and recovery plan are separate concepts.
2. Recovery points are replicated to the remote site.
3. Near-synchronous DR is based on lightweight change tracking rather than repeatedly copying whole VM images.
4. Recovery plans contain boot sequencing and network mapping.
5. IP re-mapping and traffic recovery are part of the recovery plan.
6. Test recovery must not disrupt the protected production VM.
7. Automatic failover requires a third-fault-domain witness/quorum concept for safe site-failure decisions.
8. Multiple replication technologies can serve different RPO classes.

Useful public references used for this design:

- Nutanix DR product: https://www.nutanix.com/products/nutanix-cloud-infrastructure/disaster-recovery
- Nutanix NearSync / lightweight snapshot architecture discussion: https://www.nutanix.com/blog/ensuring-resilient-mission-critical-applications
- Nutanix NCI 7.5 DR enhancements: https://www.nutanix.com/blog/disaster-recovery-dr-enhancements-in-nci-7-5
- QEMU dirty bitmap and incremental backup design: https://www.qemu.org/docs/master/interop/bitmaps.html
- QEMU NBD dirty-bitmap metadata: https://www.qemu.org/docs/master/interop/nbd.html
- libvirt incremental backup internals: https://libvirt.org/kbase/internals/incremental-backup.html
- Ceph RBD mirroring: https://docs.ceph.com/en/latest/rbd/rbd-mirroring/
- OpenZFS send/receive: https://openzfs.github.io/openzfs-docs/Basic%20Concepts/Operations/Send%20and%20Receive.html

---

## 3. Do not use rsync as the primary VM DR engine

`rsync` may remain useful for copying small configuration/evidence files. It must not be the primary VM-disk replication mechanism.

Reasons:

- file-level scanning is the wrong abstraction for multi-hundred-GB/TB VM disks;
- a small guest write can modify blocks inside a very large QCOW2/raw image;
- file-level copying does not by itself establish a VM-consistent multi-disk recovery point;
- repeated scanning does not scale linearly with changed data;
- there is no native VM changed-block lineage, replication epoch or durable recovery-point protocol;
- retry/failover semantics and split-brain handling would have to be reinvented around an unsuitable data plane.

The LayerSentry generic KVM engine should use block-level changed-data tracking.

---

## 4. One LayerSentry DR plan, multiple replication providers

The UI and orchestration layer expose one provider-neutral protection-plan contract.

The controller automatically selects the best certified data-plane provider for the VM's primary storage.

### Provider priority

| Storage type | Preferred replication provider | Purpose |
| --- | --- | --- |
| Ceph RBD | Ceph `rbd-mirror` | native journal/snapshot delta replication |
| ZFS / ZVOL | ZFS send/receive | native incremental block-aware replication |
| QCOW2 on filesystem/NFS/local storage | LayerSentry QEMU CBT provider | QEMU/libvirt dirty-bitmap incremental replication |
| RAW/LVM/SAN | certified array/native replication provider where available | avoid fragile transient-bitmap dependence |
| Unsupported storage provider | native CloudStack B&R / full recovery fallback | truthful reduced-RPO service tier |

The user does **not** select these providers in normal mode. LayerSentry detects storage capability and shows only the DR SLA/RPO tiers that the current source+DR storage topology can actually meet.

This avoids pretending every backend supports the same RPO.

---

## 5. Generic KVM replication engine — QEMU CBT + NBD, not repeated snapshots

For supported QCOW2-backed KVM workloads, the default LayerSentry block-delta engine should use supported QEMU/libvirt primitives.

### Initial enable-protection flow

```text
1. Discover VM disks and source storage.
2. Verify target capacity/network/storage mapping.
3. Establish VM/disk checkpoint lineage.
4. Start full baseline copy while the VM remains online.
5. Track writes that occur during the full seed.
6. Send the catch-up delta.
7. Seal a durable recovery point at DR.
8. Mark the VM Protected only after the destination acknowledges durable state.
```

### Steady-state incremental flow

At each RPO epoch:

```text
Guest writes
   -> QEMU/libvirt dirty-block tracking
   -> lightweight consistency/checkpoint marker
   -> export changed extents only
   -> local replication agent reads changed extents
   -> compress + integrity-frame + encrypt in transit
   -> DR replication receiver
   -> apply delta to DR replica
   -> flush/fsync and seal DR recovery point
   -> DR acknowledges epoch N
   -> source advances checkpoint lineage
```

QEMU documents dirty bitmaps specifically for incremental/differential backup. QEMU can expose dirty-bitmap metadata through NBD; libvirt's QEMU driver uses QEMU dirty bitmaps underneath its incremental-backup checkpoint model.

### Critical correctness rule

Never clear/advance the source changed-block checkpoint merely because transmission started.

Advance only after the destination has durably committed and acknowledged the exact replication epoch.

Use an idempotent tuple such as:

```text
protection_plan_id
vm_id
disk_id
epoch_id
source_checkpoint_id
payload_sequence
```

A retry of an acknowledged or partially transmitted epoch must be safe and deduplicated.

### Bitmap rollover

Use a safe bitmap/checkpoint rollover model so guest writes that occur while epoch N is being transmitted are tracked for epoch N+1. Do not stop dirty tracking during transfer.

If persistent QEMU bitmap state becomes inconsistent or unavailable, fail closed to a new baseline/full resync rather than silently claiming the replica is current.

---

## 6. Replication transport

Do not expose a QEMU NBD server directly to the WAN as the product interface.

Use a local Unix-socket/QMP/NBD interaction between the KVM host and the LayerSentry replication agent. The agent sends only approved changed ranges to the paired DR receiver.

Target transport requirements:

- mutual TLS 1.3;
- short-lived site/agent credentials;
- certificate rotation/revocation;
- no reusable infrastructure secrets in UI/browser/logs;
- bounded parallel streams;
- configurable per-site/per-plan bandwidth limits;
- backpressure;
- resumable epochs;
- per-chunk/extent integrity verification;
- compression such as Zstandard when it provides measured benefit;
- sparse/zero-range awareness;
- explicit timeouts and bounded retries;
- sequence/epoch replay protection at the application protocol level;
- metrics for bytes changed, bytes transmitted, compression ratio, lag and retry count.

The source host must never accept arbitrary remote block-write requests through the DR transport.

---

## 7. Source snapshot policy — keep it simple

The user described a model where an incremental snapshot appears and is replicated to DR. The product should present this as a **Recovery Point**, but the source does not need to accumulate a long chain of heavyweight snapshots.

Preferred implementation:

- one baseline seed;
- lightweight changed-block/checkpoint tracking at source;
- changed blocks replicated forever-incrementally;
- recovery-point history sealed primarily on DR storage;
- short source checkpoint metadata retained only as required for safe delta lineage;
- configurable immutable/retained recovery points at DR or an external backup repository.

This reduces source capacity consumption and avoids snapshot-chain operational debt.

---

## 8. Application consistency

Default protection level: **crash consistent**.

Optional higher consistency:

1. QEMU Guest Agent filesystem freeze/thaw for supported Linux guests.
2. Windows VSS integration through supported guest-agent mechanisms.
3. application/database pre-freeze and post-thaw hooks for workloads that require transactional consistency.
4. Recovery Groups for coordinated application tiers.

Freeze only long enough to establish the consistency marker/checkpoint; do not hold the application frozen for WAN replication.

A filesystem-consistent snapshot must never be labelled application-consistent unless the relevant application integration has actually succeeded.

---

## 9. DR Site pairing and cluster sync

The user should configure the DR cluster once.

### Pair Site

```text
Administration -> DR Sites -> Pair Site
```

Pairing establishes mutual trust and continuously synchronizes **metadata only** that is required to build recovery plans:

- Site/Zone identity;
- Compute Clusters and available capacity;
- Storage pools and DR capability labels;
- VM Networks;
- VLAN IDs;
- CIDR/subnet;
- gateway;
- DNS/NTP metadata where required;
- available DR IP pools;
- traffic-switch integrations;
- provider capabilities;
- health and last-sync timestamp.

Do not copy long-lived CloudStack administrator secrets between sites. Each site's agent/controller keeps its local credentials within that site's trust boundary.

The LayerSentry controller must not build a second independent VM scheduler/inventory. CloudStack remains authoritative for VM, network, account, Zone and storage lifecycle; LayerSentry stores only DR-plan, mapping, replication and recovery state.

---

## 10. Simplest DR plan UI

### Step 1 — Workloads

- VM
- multiple VMs
- Application Group / Recovery Group

### Step 2 — DR Site

Destination Site list comes from paired-site sync.

Show only sites that currently satisfy minimum compute/storage/network requirements.

### Step 3 — Network

For every source VM network, auto-suggest a destination mapping using paired-site metadata.

Normal UI:

```text
Source Network     DR Network          IP Mode
VLAN 120 / WEB ->  VLAN 520 / DR-WEB   Use DR IP Pool
VLAN 121 / APP ->  VLAN 521 / DR-APP   Use DR IP Pool
VLAN 122 / DB  ->  VLAN 522 / DR-DB    Use DR IP Pool
```

Supported IP modes:

1. **Keep IP** — only when validated stretched L2/routing semantics make it safe.
2. **Use DR IP Pool** — recommended default; LayerSentry deterministically allocates and persists a DR IP per NIC.
3. **Static Mapping** — operator supplies exact destination IP when required.
4. **DHCP** — only where the DR network is intentionally DHCP-driven.

The customer should normally choose a DR VLAN/network and an IP pool, not manually type every VM's address.

Advanced mode may show per-VM/per-NIC override.

### Step 4 — Protection level

Expose only policies the current provider can support:

- **Backup DR** — 1 hour or greater, manual recovery
- **Standard DR** — target <= 5 minutes, automated recovery eligible
- **Advanced DR** — target <= 1 minute, automated recovery eligible
- **Metro DR** — near-zero/zero RPO only when synchronous storage, latency, witness and application prerequisites are certified

Do not advertise a 1-minute/5-minute tier merely because the UI has a selector.

### Step 5 — Review

Show:

- source Site;
- DR Site;
- protected VMs;
- destination storage;
- source -> destination network mapping;
- DR IP mapping/pool;
- target RPO;
- detected replication provider;
- initial seed size;
- estimated bandwidth requirement as an estimate, not an SLA;
- auto-failover eligibility and missing prerequisites.

Button: **Enable Protection**.

---

## 11. Recovery Group

A Recovery Group is the application-level failover unit.

Example:

```text
Stage 0: network / firewall / required virtual appliances
Stage 1: database
Stage 2: cache / message queue
Stage 3: application servers
Stage 4: web servers
Stage 5: load balancer / traffic endpoint
```

Each stage may define:

- start order;
- parallelism;
- startup timeout;
- TCP/HTTP/application health gate;
- pre/post recovery hook;
- failure behavior: stop, continue, or manual approval.

Traffic must not be switched to DR until required application health gates pass.

---

## 12. Automatic failover — witness and fencing are mandatory

Never implement:

```text
ping failed -> boot DR VMs
```

That is not production DR and creates split-brain risk.

### Required failure decision

A site may be declared failed only after multiple independent signals are evaluated, such as:

- source LayerSentry controller heartbeat;
- source CloudStack management/API health;
- KVM/agent/site heartbeat;
- protected application probes;
- network reachability from DR;
- independent Witness result.

### Witness

Deploy a small independent Witness/Quorum service in a third fault domain outside both source and DR sites.

The witness participates in an exclusive recovery lease/fencing decision.

### Fencing

The exact fence mechanism depends on topology and may include:

- BMC/OOBM power fencing;
- storage primary/demotion fencing;
- SDN/network isolation;
- external ADC/BGP route withdrawal;
- hypervisor/cluster fencing;
- provider-native promotion/demotion.

If LayerSentry cannot establish a safe exclusivity/fencing condition for a topology, automatic failover must be disabled or require explicit operator override with a strong split-brain warning.

Ceph documentation explicitly warns that forced RBD promotion when the old primary cannot be demoted creates a split-brain condition; LayerSentry orchestration must treat that as a last-resort emergency action, not the normal path.

---

## 13. Failover state machine

Use a durable, resumable state machine:

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

Every phase must be:

- idempotent;
- persisted;
- restartable after controller failure;
- auditable;
- bounded by explicit timeout;
- safe to query without mutation;
- capable of returning a clear partial/failed state.

Never rerun an unknown in-flight failover operation blindly.

---

## 14. Test Recovery

Test Recovery is a first-class product function, not a support script.

```text
Production VM keeps running
        |
        +-> latest replicated recovery point
             -> isolated DR test network
             -> temporary recovered VM/group
             -> health checks
             -> evidence/report
             -> cleanup
```

Requirements:

- isolated bubble network by default;
- no accidental production IP/BGP/DNS advertisement;
- configurable test-IP mapping;
- test boot and application validation;
- automatic cleanup with explicit orphan detection;
- report actual boot/application timings;
- no promotion of the production replica state by a test.

---

## 15. Failback

Failback is part of DR, not a future manual procedure.

```text
DR_ACTIVE
 -> verify source Site repaired
 -> rebuild/re-seed or reverse incremental replication
 -> catch source up from DR primary
 -> validate source readiness
 -> acquire cutback lease
 -> quiesce/final delta
 -> fence DR write side as required
 -> promote preferred/source Site
 -> recover workloads in dependency order
 -> validate
 -> switch traffic
 -> resume normal forward protection
```

Failback must use the same idempotency, fencing, health-gate and evidence rules as failover.

---

## 16. Network and traffic recovery

A VM being powered on is not a completed DR event.

LayerSentry needs a provider-neutral Traffic Switch adapter layer.

Supported adapters may include:

- DNS/GSLB update;
- external ADC/LB pool activation;
- BGP route advertisement/withdrawal;
- firewall/NAT mapping;
- SDN integration;
- stretched-L2 no-change mode where validated.

Traffic switch occurs only after application health validation.

For DNS-based recovery, show configured TTL and warn that end-to-end convergence can exceed VM boot time.

---

## 17. Storage-native providers

### Ceph RBD

Prefer native `rbd-mirror` for Ceph-backed VM disks.

Advantages:

- journal or snapshot-based asynchronous mirroring;
- changed-data replication handled by the storage platform;
- primary/non-primary semantics;
- provider health/status APIs.

LayerSentry remains responsible for recovery-plan ordering, CloudStack VM lifecycle, networking, traffic switching, witness/fencing and failback orchestration.

### ZFS

Prefer ZFS snapshot + incremental `zfs send`/`zfs receive` for ZFS-backed volumes.

OpenZFS computes incremental streams from its own block-level snapshot bookkeeping, so replication cost is proportional to changed data rather than directory/file-tree scanning.

### Enterprise SAN

Where the primary storage array has certified replication APIs, use a LayerSentry storage-replication adapter rather than reading/writing every block through a host-side generic path.

Required adapter contract:

- capability discovery;
- establish protection;
- get replication lag/state;
- create consistency point;
- promote/demote;
- resync/reverse;
- test clone where supported;
- fence state;
- capacity/error reporting.

Unsupported arrays fall back to a truthful lower service tier rather than an unverified near-sync claim.

---

## 18. Scale architecture

Production design targets many plans/VMs without a single giant replication worker.

### Data plane

- one lightweight replication agent per KVM host or storage-access domain;
- bounded worker pool;
- per-disk parallelism limits;
- WAN bandwidth scheduler;
- priority queues by protection tier;
- site-level admission control;
- destination backpressure;
- staggered recovery-point epochs to avoid snapshot storms;
- multi-stream transfer only after measuring provider/network behavior.

### Control plane

- stateless/restartable DR controller replicas where practical;
- durable protection-plan and state-machine storage separate from CloudStack core tables;
- third-site witness/quorum for automatic failover;
- no customer VM data through the management UI process;
- replication data plane separate from CloudStack management/API traffic.

### Capacity signals

Continuously measure:

- change rate MB/s per VM/disk;
- replication throughput;
- replication lag seconds;
- queue depth;
- source/destination storage latency;
- WAN utilization/loss;
- estimated time to RPO breach;
- DR compute/storage headroom.

A plan becomes **At Risk** before it exceeds RPO when current throughput predicts that the RPO cannot be met.

---

## 19. Security and tenant isolation

The DR service is privileged and must follow `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`.

Minimum contract:

- CloudStack RBAC remains authoritative for source workload ownership/actions;
- LayerSentry separately authorizes DR-plan/failover/fencing operations;
- per-tenant plan/resource authorization;
- mutual TLS between trusted site components;
- certificate rotation/revocation;
- least-privilege local CloudStack credentials;
- no arbitrary URL/host replication target supplied directly by an untrusted tenant;
- allowlisted paired sites only;
- no shell-string construction from VM/network names;
- bounded payloads/concurrency/timeouts;
- audit every protection, test, failover, failback and override action;
- secrets redacted from logs/artifacts;
- encrypt data in transit;
- encryption-at-rest status is reported only according to the actual storage provider mechanism;
- explicit tenant isolation tests for plan/object-ID tampering.

---

## 20. Truthful dashboard

Main DR dashboard should show only decision-useful state:

| Field | Meaning |
| --- | --- |
| Status | Protected / Syncing / At Risk / Failed / DR Active |
| Source | source Site |
| DR Site | paired recovery Site |
| Target RPO | configured policy objective |
| Current Lag | measured replication lag |
| Last Safe Recovery Point | destination-acknowledged durable point |
| Recovery Readiness | compute + storage + network + provider preflight |
| Last Test | last successful isolated Test Recovery |
| Auto Failover | Enabled / Disabled / Blocked with reason |
| Failback Ready | measured readiness, not a static label |

Never show `Protected`, `Replicated`, `DR Ready` or `Healthy` without current supporting evidence.

---

## 21. Suggested product SLA tiers

These are product targets, not current claims.

| Tier | Target RPO | Recovery mode | Eligible provider examples |
| --- | ---: | --- | --- |
| Backup DR | >= 60 min | manual/planned | CloudStack B&R |
| Standard DR | <= 5 min | planned + automatic when fenced | QEMU CBT, Ceph snapshot mirror, ZFS incremental, array-native |
| Advanced DR | <= 1 min | planned + automatic when fenced | measured high-rate CBT, Ceph journal/native, certified array-native |
| Metro DR | ~0 | automatic | certified synchronous storage + witness/fencing + latency/app qualification |

Do not guarantee an RPO tier until the provider/topology has passed sustained change-rate, restart, WAN-loss and recovery testing at the intended scale.

---

## 22. Architecture score

### Target design score after this architecture

| Area | Target design score |
| --- | ---: |
| Customer simplicity | 9.8/10 |
| Replication architecture | 9.6/10 |
| Storage portability | 9.7/10 |
| Recovery orchestration | 9.7/10 |
| Network/IP recovery | 9.4/10 |
| Split-brain prevention | 9.8/10 when witness + fencing is certified |
| Test Recovery | 9.7/10 |
| Failback | 9.6/10 |
| Security/audit model | 9.6/10 |
| Scale/operability | 9.5/10 |
| Overall target architecture | **9.6/10** |

This score applies to the **design**, not the current implementation.

Current production readiness remains governed by live evidence. A design cannot become `PRODUCTION_CERTIFIED` by documentation or code review alone.

A practical maximum claim after implementation should remain approximately 9-9.5/10 until repeated independent-site failure tests, security testing, scale tests and real failback evidence exist. A literal 10/10 resilience claim is not credible for a production infrastructure product.

---

## 23. Required implementation gates

The existing LayerSentry rule remains in force: first prove the native CloudStack 4.22.1.1 two-Zone recovery baseline, then build/enable advanced orchestration.

### Gate A — native recovery baseline

- two Zones/Sites;
- supported B&R provider/repository;
- cross-Zone create-from-backup;
- network mapping;
- repeat recovery;
- measured RPO/RTO;
- negative tests.

### Gate B — Site Pairing + DR inventory sync

- paired-site mutual trust;
- DR network/VLAN/IP pool discovery;
- capacity/storage capability discovery;
- no long-lived credential leakage.

### Gate C — Protection Plan API/model

- VM/Recovery Group;
- destination Site;
- storage/provider binding;
- network/IP mapping;
- RPO/retention;
- RBAC;
- idempotency.

### Gate D — generic QEMU CBT replication

- full seed;
- persistent changed-block tracking on supported QCOW2 path;
- incremental transfer;
- disconnect/resume;
- controller/agent restart;
- corrupt/inconsistent bitmap -> safe resync;
- multi-disk recovery point;
- measured source overhead.

### Gate E — storage-native providers

At minimum certify selected production backends, starting with the storage profiles LayerSentry actually sells/supports.

### Gate F — Test Recovery

- isolated network;
- no production traffic collision;
- automated validation/cleanup.

### Gate G — planned failover/failback

- reverse replication;
- dependency order;
- network/IP mapping;
- traffic switch;
- repeatability.

### Gate H — automatic failover

- independent witness;
- fencing;
- source/DR partition tests;
- witness-loss tests;
- controller restart during failover;
- no double promotion.

### Gate I — production certification

Minimum destructive/chaos matrix:

- DC hard power loss;
- WAN/site partition;
- source management loss with workloads healthy;
- DR management restart;
- witness loss;
- storage provider unavailable;
- stale replica;
- corrupt recovery point;
- missing network mapping;
- DR capacity exhaustion;
- replication backlog/RPO breach;
- application stage failure;
- controller restart in every failover phase;
- duplicate/replayed recovery request;
- source returns unexpectedly during DR operation;
- successful failback after each supported disaster class;
- security/RBAC/tenant isolation negative tests;
- sustained scale/performance test at the advertised VM/change-rate envelope.

Only successful, repeatable independent-site evidence can promote the implementation to `PRODUCTION_CERTIFIED`.

---

## 24. Non-negotiable architectural boundaries

1. CloudStack remains authoritative for VM/network/storage/account/Zone lifecycle.
2. LayerSentry DR orchestration remains outside CloudStack core unless a documented exception is approved.
3. No `rsync`-based primary VM replication engine.
4. No `ping failed -> boot DR` automation.
5. No automatic failover without safe witness/fencing eligibility.
6. No source checkpoint advance before durable DR acknowledgement.
7. No `Protected` status before the initial seed and catch-up are complete.
8. No advertised RPO that the selected provider/topology has not measured and certified.
9. No traffic switch before required application health gates pass.
10. Failback and Test Recovery are part of the product definition, not optional support procedures.
