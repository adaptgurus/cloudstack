# LayerSentry DRaaS — Architecture Revalidation Before Implementation

**Date:** 2026-09-05  
**Status:** `DESIGN_DEFINED`  
**Baseline:** Apache CloudStack 4.22.1.1, LayerSentry KVM-first profile  
**Purpose:** mandatory research/design-review gate before runtime DR implementation

This document revalidates the existing LayerSentry DR strategy before implementation. It is an architecture decision record and source/documentation research artifact only. It does **not** claim that advanced DR is implemented, `LIVE_VERIFIED`, or `PRODUCTION_CERTIFIED`.

## 1. Current requirement

The desired customer experience remains intentionally simple:

```text
DR
 -> Create Protection Plan
 -> Select VM / Application Group
 -> Select DR Site
 -> Select DR VLAN / Network
 -> Select DR IP policy
 -> Select RPO / retention
 -> Enable Protection
```

The product must support heterogeneous KVM storage, including NAS/file-backed storage, LINSTOR/DRBD SDS/HCI, Ceph RBD where selected, and certified enterprise SAN arrays. The user must be able to recover the latest safe point or an older retained recovery point. Planned failover, Test Recovery and failback are product requirements; automatic emergency failover is available only when the exact topology has safe witness/quorum and fencing.

## 2. Existing CloudStack 4.22.1.1 foundation

The design must reuse these upstream capabilities rather than replace them:

- CloudStack Backup & Recovery provider/plugin abstraction;
- KVM NAS B&R provider;
- backup offerings, adhoc backups and user backup schedules;
- `createBackup`, `listBackups`, `restoreBackup`, volume-restore and `createVMFromBackup` APIs;
- backup metadata sufficient to recreate a VM and its disks/configuration;
- create a VM from an older selected backup;
- since 4.22, create a VM from NAS backup in another Zone;
- destination Zone/resource selection and network remapping where resources differ;
- native KVM file-based incremental Volume Snapshots where prerequisites are met;
- KVM Instance Snapshot mechanisms, including storage-based snapshots for supported block storage and incremental disk-only Instance Snapshots on file storage;
- native LINSTOR KVM primary-storage integration;
- CloudStack 4.22.1.x NAS B&R support for VMs on LINSTOR primary storage;
- CloudStack remains authoritative for VM, volume, Zone, network, account, RBAC and KVM lifecycle.

Important upstream limits that prevent native CloudStack B&R alone from being the full target DR product:

- VM backup schedule intervals are HOURLY, DAILY, WEEKLY and MONTHLY, not a generic sub-hour continuous-replication scheduler;
- cross-Zone create-from-backup in 4.22 is currently NAS-B&R-specific;
- NAS B&R is recovery-oriented rather than a generic storage-replication control plane;
- no complete Recovery Plan/Recovery Group object with application ordering and health gates;
- no independent witness/quorum plus generic fencing state machine for automatic site failover;
- no generic enterprise-array replication abstraction;
- no unified provider-neutral recovery-point catalog across NAS, LINSTOR, Ceph and SAN;
- no end-to-end traffic cutover and reverse-replication/failback controller.

CloudStack 4.22 also documents an important KVM snapshot safety limitation: VM/Instance snapshots and Volume snapshots cannot be treated as freely composable mechanisms. A LayerSentry DR design must therefore choose a validated protection strategy per backend rather than layering every upstream snapshot mechanism together.

## 3. Options researched

### Option A — CloudStack native B&R only

**Advantages**

- lowest custom-code and maintenance burden;
- upstream API/RBAC/VM metadata integration;
- straightforward restore and cross-Zone recovery baseline;
- good foundation for hourly-or-greater Backup DR.

**Disadvantages**

- does not provide the target 5-minute/1-minute low-RPO service on its own;
- full restore/copy path can produce longer RTO;
- no complete Test Recovery/Recovery Group/fencing/failback orchestration.

**Decision:** keep as mandatory baseline and fallback, not the only advanced DR data plane.

### Option B — `rsync` as the main VM replication engine

**Advantages**

- simple and widely available;
- useful for small configuration files or a carefully controlled repository-copy workflow.

**Disadvantages**

- wrong abstraction for continuously changing VM block images;
- file scanning/copy behavior does not provide VM-wide consistency epochs;
- poor fit for SAN/LINSTOR/Ceph;
- retry, checkpoint lineage and split-brain semantics would need to be invented around it.

**Decision:** rejected as primary VM replication. May be used only for a specifically validated backup-repository synchronization path or small non-VM files.

### Option C — custom QEMU/QMP/NBD CBT engine for every backend

**Advantages**

- fine-grained changed-block control;
- can support efficient incremental transfers on appropriate QCOW2/file-backed workloads.

**Disadvantages**

- unnecessary hypervisor coupling when storage-native replication exists;
- persistent dirty bitmaps exist only for QCOW2; transient raw-image bitmaps are lost on QEMU exit;
- bitmap inconsistency after abnormal QEMU shutdown requires safe chain recovery/rebaseline;
- LayerSentry would own more QEMU version behavior, multi-disk transaction logic and protocol security;
- duplicates higher-level libvirt backup/checkpoint APIs.

**Decision:** do not make raw QMP/NBD the product contract. Use libvirt's supported backup/checkpoint abstraction for the generic file-backed fallback; direct QMP/NBD is an internal implementation detail only if a proven libvirt gap requires it.

### Option D — standardize all customers on LINSTOR/DRBD

**Advantages**

- strong HCI/SDS story;
- real-time DRBD replication;
- LINSTOR snapshots and incremental snapshot shipping to a remote LINSTOR cluster or S3-compatible storage;
- good integration fit with KVM and CloudStack's existing LINSTOR primary-storage support.

**Disadvantages**

- forces customers with existing enterprise SAN/NAS investments to migrate storage;
- WAN/latency design determines whether continuous DRBD, asynchronous modes, DRBD Proxy or snapshot shipping is appropriate;
- DRBD Proxy is proprietary and therefore cannot be assumed as the zero-cost default.

**Decision:** adopt as the preferred LayerSentry HCI/SDS profile, but not as a universal mandatory backend.

### Option E — storage-native adapters + LayerSentry DR orchestration + CloudStack native baseline/fallback

**Advantages**

- exploits the most mature replication primitive available for each storage system;
- best performance and lowest host-side data movement for SAN/LINSTOR/Ceph;
- minimizes custom low-level block replication code;
- keeps CloudStack authoritative for VM/network/storage lifecycle;
- supports heterogeneous customer storage without forcing migration;
- enables a uniform UI while preserving provider-specific reliability semantics;
- cleanly separates hot replication from retained point-in-time recovery.

**Disadvantages**

- each storage family/firmware line needs capability and certification work;
- controller and provider contracts must handle different promotion/reverse/snapshot semantics;
- a generic file-backed fallback is still needed.

**Decision:** **RECOMMENDED**.

### Option F — rely on a commercial DR product as LayerSentry's core

Examples may include vendor backup/DR products where CloudStack/KVM integration exists.

**Advantages**

- potentially mature operational workflows and vendor support.

**Disadvantages**

- licensing/lock-in;
- inconsistent KVM/CloudStack feature coverage;
- weak fit with a storage-neutral LayerSentry appliance unless treated as optional integration;
- would make core LayerSentry DR capability dependent on third-party commercial lifecycle and licensing.

**Decision:** allow optional certified integrations, but do not make one proprietary product the LayerSentry DR core.

## 4. Weighted design comparison

The score is an architecture-review aid, not production evidence. Weighting reflects the current product priorities.

| Criterion | Weight | Native B&R only | rsync primary | Generic CBT everywhere | LINSTOR-only | Storage-native adapters + orchestration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Reliability/correctness | 25% | 8.0 | 4.0 | 7.5 | 9.0 | 9.5 |
| Maintainability | 15% | 9.5 | 7.0 | 6.0 | 8.0 | 8.5 |
| Performance | 15% | 6.0 | 4.0 | 8.0 | 9.0 | 9.5 |
| Security | 15% | 8.5 | 5.0 | 7.0 | 8.5 | 9.0 |
| Scalability | 10% | 6.5 | 4.0 | 7.5 | 9.0 | 9.5 |
| Operational simplicity | 10% | 9.0 | 6.0 | 6.0 | 8.5 | 9.0 |
| Long-term supportability | 10% | 9.0 | 5.0 | 6.5 | 8.0 | 9.0 |
| **Weighted result** | **100%** | **8.0** | **4.9** | **7.0** | **8.6** | **9.3/10** |

The selected architecture is therefore **storage-native adapters + a LayerSentry DR orchestration plane + CloudStack-native B&R/snapshot fallback**.

## 5. Refined provider selection hierarchy

The previous architecture correctly chose a provider-neutral DR plan, but its generic QEMU CBT path was too prominent. The refined priority is:

1. **CloudStack-native operation** when it directly satisfies the protection/recovery requirement and SLA.
2. **Storage-native replication adapter** for low-RPO/current-replica protection when available and certified.
3. **libvirt incremental backup/checkpoint adapter** for supported QCOW2/file-backed KVM workloads when no storage-native replication exists.
4. **CloudStack NAS B&R + zone-local repository replication** for Backup DR, long-retention recovery and safe fallback/reseed.
5. `rsync` only for a separately validated repository-sync use case, never the generic running-VM replication engine.

Examples:

| Backend | Current hot-replica path | PITR/retention path | Baseline/fallback |
| --- | --- | --- | --- |
| LINSTOR/DRBD HCI | DRBD/LINSTOR continuous or certified async mode | LINSTOR snapshot/snapshot shipping | CloudStack NAS B&R where supported |
| Ceph RBD | `rbd-mirror` journal or snapshot mode according to SLA | RBD snapshots plus catalog | CloudStack recovery path where supported |
| Enterprise SAN | certified array consistency-group async/sync replication | array snapshots/bookmarks/clones | CloudStack VM metadata/lifecycle + backup fallback |
| NFS/SharedMountPoint/QCOW2 | libvirt checkpoint/incremental backup adapter | sealed DR-side recovery chain + periodic full | CloudStack NAS B&R |
| Unsupported backend | none beyond certified upstream capability | native backups only | CloudStack B&R |

## 6. Why libvirt is the preferred generic KVM boundary

libvirt exposes full and incremental VM disk backup through `virDomainBackupBegin()` and checkpoint objects. It can run push or pull backup modes and uses QEMU dirty bitmaps underneath. This is preferable to making LayerSentry own a raw QMP protocol because:

- it is the supported virtualization management abstraction CloudStack/KVM already relies on;
- it centralizes QEMU version-specific behavior;
- it provides domain-level checkpoint semantics;
- it reduces direct QMP attack surface and custom protocol code;
- it makes future QEMU/libvirt upgrades easier to validate.

QEMU dirty bitmap behavior still matters for correctness. In particular, persistent bitmaps are QCOW2-only and can become inconsistent after unclean shutdown. The LayerSentry provider must detect that state and rebaseline rather than advertising a current replica.

## 7. Recovery Point Catalog and old-checkpoint recovery

A hot DR replica and historical recovery points are separate product objects.

```text
Hot Replica
  -> latest promotable state for planned/emergency failover

Recovery Point Catalog
  -> RP-000123 latest safe
  -> RP-000122
  -> RP-000121 application-consistent
  -> hourly/daily/weekly retained points
```

Each Recovery Point must identify:

- protection plan / application / VM;
- consistency epoch and timestamp;
- consistency class: crash, filesystem or application;
- every participating disk and provider checkpoint ID;
- parent/baseline dependencies;
- destination storage/object identifiers;
- integrity state/checksum where the provider supports it;
- retention/expiry class;
- measured replication lag/RPO at creation;
- validation/test state.

A point is not displayed as usable merely because metadata exists. All dependent provider data must be present and the chain must pass validation.

For multi-disk VMs/application groups, a Recovery Point is sealed only when all required disks in the consistency epoch are durably committed. Partial provider success must never be promoted as an application recovery point.

## 8. CloudStack snapshot use policy

CloudStack's KVM snapshot mechanisms are useful but are not a universal long-term DR catalog.

Rules:

- select either the certified Volume Snapshot or Instance Snapshot strategy for a workload/profile; do not combine incompatible paths;
- do not accumulate unbounded file-backed VM snapshot chains;
- use CloudStack Instance Snapshots primarily for supported local/storage-provider checkpoint workflows when they fit the backend;
- use libvirt backup/checkpoint or storage-native replication for provider-neutral DR lineage as defined above;
- keep a periodic durable baseline/full recovery point so incremental chains remain bounded and recoverable;
- failure of a delta/bitmap/checkpoint chain must trigger safe rebaseline, never a false `Protected` state.

## 9. Failover and split-brain strategy

Planned Failover is simpler than emergency automatic failover and should be implemented/certified first.

Automatic failover requires all of the following for the exact topology:

- multiple independent source-failure signals;
- independent witness/quorum outside both failure domains;
- exclusive recovery lease;
- a proven source fence: storage, network, hypervisor/BMC or provider-native equivalent;
- storage promotion with no dual-writer condition;
- durable resumable state machine;
- application health gates;
- traffic switch only after recovery validation.

Never implement `ping failed -> boot DR`.

## 10. Network/IP strategy

Site pairing synchronizes metadata/capabilities, not administrator secrets.

A protection plan persists:

- source Site -> DR Site;
- source network/VLAN -> DR network/VLAN;
- IP mode: keep IP only when network design proves it safe, DR pool, static mapping or intentional DHCP;
- traffic-switch adapter: DNS/GSLB, BGP, ADC/LB, NAT/firewall or certified stretched-L2 mode.

CloudStack remains responsible for creating/starting the destination VM and network-facing resources; LayerSentry owns only the DR mappings and orchestration state.

## 11. Security architecture

- mTLS between LayerSentry site components;
- short-lived/rotatable site credentials;
- provider credentials remain local to the site that needs them;
- least-privilege CloudStack/provider service accounts;
- no customer-supplied arbitrary replication endpoint without allowlist/policy;
- no passwords/private keys in Git, UI bundle, logs or evidence artifacts;
- authorization on exact plan/resource/tenant, not UI visibility;
- immutable/auditable operation IDs for protection, snapshot, promote, fence, failback and delete actions;
- provider-native encryption-at-rest claims only when actually configured and tested;
- explicit RBAC/object-ID tampering tests.

## 12. Rocky Linux 9 acceptance rule

Rocky Linux 9 is the primary LayerSentry acceptance environment. Apache CloudStack 4.22 supports Rocky Linux 9 for both Management Server and KVM profiles.

Development or preliminary tests may use WSL Ubuntu 22.04, but a runtime-affecting change cannot become `LIVE_VERIFIED` until the exact artifact/configuration is tested on the authorized Rocky Linux 9 LayerSentry environment through the `adaptgurus/cozystack` runner/integration path or another explicitly approved durable path.

Browser acceptance must include the served CloudStack/LayerSentry UI and the supported browser family used for the release, with at least current Chrome and Firefox in the LayerSentry acceptance matrix unless an explicit release exception is documented.

## 13. Required engineering lifecycle

For every meaningful technical change:

```text
Research
 -> Design Review
 -> Implementation
 -> Functional/Regression Testing
 -> Failure/Edge-Case Validation
 -> Optimization Review
 -> Documentation
 -> Knowledge-Graph Update
 -> Super Master Context / AGENTS.md update when stable policy changed
 -> Git Commit
 -> Final Verification
```

Do not change an established design merely to produce a different implementation. A change must have a defensible improvement in reliability, performance, maintainability, scalability, security, operational simplicity, supportability or recovery capability.

## 14. Significant-decision record template

Every significant architecture/infrastructure/backend/UI/integration decision must record:

1. existing approach;
2. advantages and disadvantages;
3. alternatives researched;
4. recommended approach;
5. why it is superior;
6. implementation impact;
7. risks and mitigations;
8. testing/validation performed;
9. rollback/recovery procedure;
10. final production-readiness status.

## 15. Testing/certification gate for advanced DR

Per backend claimed, the minimum live evidence includes:

- source/DR provider inventory and version;
- initial seed/baseline;
- at least two incremental/replication epochs where supported;
- provider restart/controller restart recovery;
- latest-point recovery;
- at least one older retained recovery-point recovery;
- data validation inside the recovered guest;
- DR VLAN/IP mapping verification;
- isolated Test Recovery;
- planned failover and failback before emergency automation;
- disconnect/retry/idempotency negative case;
- corruption/stale point handling;
- RPO lag and RTO timing measured for the exact workload;
- source/DR capacity and performance overhead;
- RBAC/security negative tests;
- upgrade/rollback regression for the exact release/provider combination.

Automatic failover adds WAN partition, witness loss, source return, double-promotion prevention and fencing tests. Those are R4 and require independent failure domains before production certification.

## 16. Current production-readiness status

- architecture: `DESIGN_DEFINED`;
- CloudStack native DR foundation: source/documentation support exists, full current two-site LayerSentry live proof remains pending;
- advanced multi-backend DR controller: `PENDING`;
- provider adapters: `PENDING`;
- Recovery Point Catalog/PITR orchestration: `PENDING`;
- Test Recovery: `PENDING`;
- planned failover/failback: `PENDING`;
- automatic failover/witness/fencing: `PENDING`;
- independent-site production certification: `NOT_TESTED`.

The current architecture is assessed at approximately **9.3/10 as a design direction** using the weighted rubric above. Current advanced-DR implementation readiness remains far lower and must not inherit the architecture score.

## 17. Implementation impact and effort

The previous small `+5–7 man-day` advanced-DR placeholder is not a valid estimate for the expanded requirement. Multi-backend storage, PITR, failover/failback and production failure testing materially increase the scope.

A current planning range after native two-Zone recovery proof is approximately **36–57 engineering man-days** for NAS/file-backed DR, LINSTOR/DRBD, a first enterprise-SAN family, PITR catalog, Test Recovery, recovery groups, witness/fencing, failback, security and scale/failure testing. Additional storage families require separate adapter/certification effort.

This is engineering effort, not calendar-duration or delivery promise.

## 18. Rollback/recovery for the design change

This revalidation changes documentation/design policy only and performs no runtime mutation. Rollback is a Git revert of the documentation commits. Runtime implementation must retain separate rollback/recovery plans per provider and risk class.

## 19. Authoritative public references reviewed

- Apache CloudStack 4.22 Backup and Recovery documentation: `https://docs.cloudstack.apache.org/en/latest/adminguide/backup_and_recovery.html` (cross-checked against 4.22.1.x source/release notes).
- Apache CloudStack 4.22.1.1 changes: `https://docs.cloudstack.apache.org/en/4.22.1.1/releasenotes/changes.html`.
- Apache CloudStack 4.22 API reference: `https://cloudstack.apache.org/api/apidocs-4.22/`.
- Apache CloudStack 4.22 KVM Instance Snapshot documentation.
- libvirt Backup XML: `https://libvirt.org/formatbackup.html`.
- libvirt QEMU incremental-backup internals: `https://libvirt.org/kbase/internals/incremental-backup.html`.
- QEMU dirty bitmap/incremental backup documentation: `https://www.qemu.org/docs/master/interop/bitmaps.html`.
- Ceph RBD mirroring documentation: `https://docs.ceph.com/en/latest/rbd/rbd-mirroring/`.
- LINBIT LINSTOR snapshot-shipping and DRBD DR material.
- Nutanix DR public architecture/product material for protection-policy/recovery-plan/Test Recovery UX principles.

Revalidate all version/provider assumptions against the exact release and deployed provider before implementation or certification.
