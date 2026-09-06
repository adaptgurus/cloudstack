# LayerSentry DRaaS — Storage Backend and Point-in-Time Recovery Research

**Date:** 2026-09-05  
**Status:** `DESIGN_DEFINED` / source-and-documentation research only  
**Baseline:** Apache CloudStack 4.22.1.1, LayerSentry KVM-first profile

This record captures the upstream capability audit and the target storage-aware DR approach for NAS/file storage, LINSTOR/DRBD SDS/HCI, Ceph RBD where present, and enterprise SAN. It is not runtime evidence and does not promote DR to `LIVE_VERIFIED`.

## 1. What Apache CloudStack already provides

The CloudStack B&R framework already supplies a substantial part of the control plane that LayerSentry should reuse:

- provider/plugin abstraction for VM backup/recovery;
- KVM NAS B&R provider;
- backup offerings and user/adhoc schedules;
- `createBackup`, `listBackups`, `restoreBackup`, volume restore and `createVMFromBackup` APIs;
- metadata captured with VM backups for service offering, template, disks, networks and VM details;
- create a new VM from an older selected backup;
- since CloudStack 4.22, cross-Zone create-from-backup for the NAS B&R provider;
- cross-Zone backup repository flag, destination Zone selection and resource remapping where destination resources differ;
- documented DRaaS extension model using Zone-local NAS repository replicas or a global repository;
- KVM incremental Volume Snapshots for supported file-based storage when the required KVM/libvirt/QEMU versions and `kvm.incremental.snapshot` setting are satisfied;
- snapshot retention and multi-Zone snapshot copy mechanisms;
- native LINSTOR KVM primary-storage integration;
- CloudStack 4.22.1.x support for NAS B&R when the VM primary storage is LINSTOR;
- NAS B&R fixes/support for Ceph and SharedMountPoint primary-storage paths in the 4.22 line.

Important limitations for the intended near-Nutanix DR experience:

- CloudStack's native VM backup schedule is hourly/daily/weekly/monthly, not a generic sub-hour RPO scheduler;
- cross-Zone create-from-backup in 4.22 is currently a NAS B&R capability, not a generic storage-replication DR controller;
- native NAS B&R copies full VM disk data and does not by itself provide continuous/near-continuous replication;
- CloudStack does not provide a complete application Recovery Plan object with dependency ordering, witness/quorum, fencing, automatic site failover, traffic switching and automatic failback;
- CloudStack does not provide one generic enterprise-SAN replication abstraction that can drive arbitrary array-native asynchronous/synchronous replication;
- CloudStack volume snapshots are per-volume; a LayerSentry multi-disk/application recovery point must preserve an explicit consistency epoch across all participating disks;
- source/backup metadata retention rules remain important; a recovery point must not be advertised if its dependent metadata/data chain has been purged.

## 2. Product rule — one DR plan, storage-aware data plane

The customer sees one workflow:

```text
DR
 -> Create Protection Plan
 -> Select VM / Application Group
 -> Select DR Site
 -> Select DR VLAN / Network
 -> Select DR IP policy
 -> Select RPO / Retention policy
 -> Enable Protection
```

LayerSentry detects the source and destination storage capabilities and chooses the best **certified** replication provider. The normal user does not select low-level replication technology.

The controller must expose capability flags such as:

```text
continuous_replication
incremental_replication
sync_replication
snapshot_history
point_in_time_restore
application_consistency
reverse_replication
planned_failover
auto_failover
fencing
estimated_rpo_floor
```

If a backend cannot meet a requested RPO or failover mode, the UI must hide/disable that tier instead of pretending it is protected.

## 3. Recommended storage-provider matrix

| Source/DR storage | Preferred LayerSentry DR data plane | Recovery history / PITR | CloudStack role |
| --- | --- | --- | --- |
| NFS / SharedMountPoint / file-backed KVM | Reuse CloudStack/KVM incremental volume-snapshot primitives where safely applicable; use NAS B&R as full baseline/fallback and zone-local repository replication | Retained DR recovery-point catalog composed from periodic full/baseline plus incremental chain; older points verified before advertisement | VM metadata/lifecycle, backup APIs, snapshot APIs, create-from-backup, destination VM/network/storage orchestration |
| LINSTOR / DRBD SDS/HCI | LINSTOR/DRBD replication for current replica; LINSTOR snapshot/snapshot-shipping for retained points; DRBD Proxy or another certified WAN mode where needed | LINSTOR snapshots/backup shipping to DR cluster or S3-compatible target; catalog selected point and chain | Continue using native CloudStack LINSTOR primary storage; CloudStack remains authoritative for VM/network lifecycle |
| Ceph RBD | Ceph `rbd-mirror` for current replica, RBD snapshots for retained points | RBD snapshot lineage plus DR catalog | CloudStack VM/storage lifecycle and supported NAS B&R fallback/recovery paths |
| Enterprise SAN / block array | Certified array-native snapshot + async/sync replication adapter via vendor REST/CLI/API | Array snapshots/consistency groups replicated to DR, indexed by LayerSentry catalog | CloudStack owns VM/volume/network lifecycle; LayerSentry invokes only certified array operations outside CloudStack core |
| Unsupported/uncertified backend | CloudStack native B&R/full backup recovery only | Native backups at the supported schedule/retention | Show reduced `Backup DR` tier only; do not claim low RPO or automatic failover |

`rsync` may be used for small configuration/evidence files or for a specifically tested backup-repository synchronization implementation, but it is **not** the primary VM-block replication mechanism.

## 4. NAS/file-backed KVM approach

Do not immediately build a second QEMU snapshot engine if CloudStack's supported KVM incremental Volume Snapshot path can provide the changed-data lineage safely for the target storage.

Target flow:

```text
initial baseline/full recovery image
    -> establish recovery epoch
    -> take coordinated per-volume incremental checkpoints
    -> replicate/copy changed data to DR repository/storage
    -> seal DR epoch only after every disk is durable
    -> retain recovery points according to policy
```

For VMs with multiple disks, LayerSentry must create a single logical Recovery Point that lists every disk checkpoint belonging to the same epoch. If any member disk is incomplete/corrupt, the Recovery Point is not usable.

The native NAS B&R path remains valuable for:

- full VM baseline;
- simpler hourly+ Backup DR tier;
- cross-Zone create-from-backup fallback;
- independent older restore points;
- recovery when incremental lineage must be re-seeded.

## 5. LINSTOR SDS/HCI approach

CloudStack already supports LINSTOR as KVM primary storage, and the 4.22.1 line added NAS B&R support for VMs whose primary storage is LINSTOR.

For a stronger DR tier, LayerSentry should use LINSTOR/DRBD capabilities rather than exporting the LINSTOR volume and copying it through a generic file transport.

Recommended modes:

1. **Async/near-sync DR** — DRBD/LINSTOR remote replica across independent sites, optionally using a certified WAN-optimization/proxy mode where required.
2. **Snapshot-shipping DR** — scheduled/triggered LINSTOR snapshots shipped to a second LINSTOR cluster or an object-storage target.
3. **Metro/synchronous DR** — available only when latency, quorum, fencing, topology and storage protocol are explicitly certified.

For PITR, retain independently addressable LINSTOR snapshots/backup points at the DR side. Promotion of the latest replica and restore of an older snapshot are separate operations and must not be conflated.

## 6. Enterprise SAN approach

Do not try to create one host-side replication method that bypasses enterprise-array consistency and replication primitives.

Implement a narrow provider adapter interface. A certified SAN adapter should be able to:

- discover source/destination array, pool/LUN/volume identity;
- create consistency-group snapshot;
- start/pause/resume replication;
- query replication lag/state;
- create/bookmark a DR recovery point;
- promote/demote or split/reprotect replica;
- reverse replication for failback;
- map/present destination LUNs to DR KVM hosts;
- verify multipath/WWID/host access before VM start;
- enforce fencing/ownership so the same writable volume cannot be active at both sites;
- expose immutable audit identifiers for every storage operation.

Each vendor/model/firmware family is a separate certification target. An adapter existing in source does not mean every array is supported.

## 7. Point-in-time recovery / old checkpoint contract

The DR side must maintain a **Recovery Point Catalog**, not only one mutable replica.

Example user view:

```text
Protected VM: ERP-DB-01

Latest safe point     2026-09-05 01:25:00
01:20                 Healthy
01:15                 Healthy
01:10                 Healthy
00:55                 App-consistent
Yesterday 23:00       Daily retained
```

The user chooses **Recover** or **Test Recovery**, selects a point in time and destination network/IP mapping, and LayerSentry resolves the correct provider-specific snapshot/backup/replica chain.

A Recovery Point must record at least:

- plan/application/VM IDs;
- source and DR Site IDs;
- consistency epoch ID;
- timestamp and source clock reference;
- consistency type: crash/filesystem/application;
- all disk/provider checkpoint IDs;
- parent/baseline dependencies;
- destination storage/object identifiers;
- checksums/integrity state where supported;
- retention class and expiry;
- replication lag/RPO measurement;
- validation status and last test time.

Never show an old point as `Healthy` solely because metadata exists. The data chain and required destination storage objects must be verifiably present.

## 8. Recovery/failover orchestration still missing from upstream

LayerSentry must add outside CloudStack core:

```text
Protection Plan
Recovery Point Catalog
Storage Provider Adapter layer
Recovery Group / dependency order
DR Site + network/VLAN/IP mapping
Health engine
Witness/quorum
Fencing/exclusive recovery lease
Test Recovery
Planned Failover
Emergency/automatic Failover
Traffic switch integration
Reverse replication
Failback
Audit/event/RPO/RTO reporting
```

CloudStack remains authoritative for VM, Zone/Site, network, volume, account, RBAC and KVM lifecycle. LayerSentry must not create a competing VM scheduler/database.

## 9. Rough extra engineering effort after native cross-Zone proof

These are engineering planning ranges, not delivery promises. They assume aggressive reuse of CloudStack 4.22.1.1 and a working disposable two-site test environment.

| Workstream | Estimate |
| --- | ---: |
| DR controller foundation, Protection Plan, capability model, Recovery Point Catalog, network/IP mapping | 6–9 man-days |
| NAS/SharedMountPoint incremental + native B&R integration and PITR | 4–6 |
| LINSTOR/DRBD replication + snapshot shipping adapter and PITR | 4–6 |
| First enterprise SAN family adapter, including snapshot/replication/promote/reverse/map | 5–8 |
| Test Recovery + Recovery Groups + health gates | 3–5 |
| Witness/fencing + automatic failover + failback | 5–8 |
| RBAC/audit/error/idempotency/security hardening | 3–5 |
| failure injection, old-checkpoint restores, performance/scale/soak and upgrade regression | 6–10 |
| **Advanced multi-backend DR subtotal** | **36–57 engineering man-days** |

A Ceph RBD adapter, if included, is an additional roughly 3–5 man-days plus release-specific testing because much of the data plane can reuse `rbd-mirror` and RBD snapshots.

This is materially more work than the historical 5–7 day advanced-DR placeholder because the current requirement includes multi-backend storage, point-in-time recovery history, safe automatic site failover, reverse replication/failback and production-grade negative/scale testing.

Calendar time can be reduced with parallel agents only where live mutations and shared lab resources do not conflict.

## 10. Mandatory live evidence path

Runtime-affecting implementation changes must use the authorized `adaptgurus/cozystack` GitHub runner/integration path for live validation before `LIVE_VERIFIED`.

Controlled direct SSH to the authorized test VM may be used for discovery, deployment, diagnostics and validation when injected through approved secrets/existing access. Never commit or log reusable SSH credentials.

For each DR storage backend being claimed, live evidence must include:

- source and DR storage/provider inventory;
- exact source VM/disks/network IDs;
- initial baseline/seed;
- at least two incremental/recovery epochs where the backend supports them;
- latest-point recovery;
- recovery of at least one older retained checkpoint;
- data validation inside the recovered VM, using authorized SSH/guest checks where appropriate;
- DR VLAN/IP mapping verification;
- an isolated Test Recovery;
- one failure/retry/idempotency negative case;
- measured bytes/lag/RPO and recovery timing for that test;
- cleanup/rollback state.

Automatic failover/failback is R4 and requires the separate failure-domain/witness/fencing gates defined by the canonical context.

## 11. Public upstream references used in this research

- Apache CloudStack 4.22 Backup and Recovery documentation: `https://docs.cloudstack.apache.org/en/4.22.1.1/adminguide/backup_and_recovery.html` (or the version-pinned 4.22.1.x equivalent where published).
- Apache CloudStack 4.22.1.1 release changes: `https://docs.cloudstack.apache.org/en/4.22.1.1/releasenotes/changes.html`.
- Apache CloudStack 4.22 API reference: `https://cloudstack.apache.org/api/apidocs-4.22/`.
- Apache CloudStack storage documentation for KVM incremental snapshots and LINSTOR.
- LINBIT public LINSTOR/DRBD material on snapshots, snapshot shipping and DRBD/DRBD Proxy disaster-recovery patterns.

Revalidate provider/version behavior against the exact installed release before implementation or certification.
