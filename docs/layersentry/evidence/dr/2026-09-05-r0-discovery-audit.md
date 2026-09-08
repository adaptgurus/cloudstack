# LayerSentry DR — R0 Discovery / Source Revalidation Checkpoint

Date: 2026-09-05 (Asia/Kolkata)

Status: `PARTIAL` — repository/source facts revalidated; fresh live CloudStack/Hyper-V DR inventory remains `UNKNOWN` and must not be inferred from historical workflow evidence.

## Scope

This checkpoint resumes Workstream D from the current Git-backed handoff without mutating CloudStack, KVM guests, Hyper-V topology, storage, networks, backup repositories, backup offerings, or DR state.

No live DR operation was executed.

## Current repository state observed before this checkpoint

### `adaptgurus/cloudstack`

- branch: `layersentry/4.22.1.1-ui`
- HEAD before this evidence commit: `90ee5ded17162a27b5431aa66a22915e1b670430`
- commit message: `docs: link Codex index to control-plane and XaaS policy`
- branch protection: disabled
- required status checks: none
- HEAD signature verification: unsigned
- target source version from root `pom.xml`: `4.22.1.1`

### `adaptgurus/cozystack`

- current LayerSentry integration branch used by the latest verified deployment lineage: `ops/layersentry-hyperv-inventory`
- observed branch HEAD: `af484d1b6e063c4929634ed045560f95f3891d7d`
- commit message: `ops: retry cleaned LayerSentry V1 UI deployment`

Historical workflow/run evidence is not promoted to current live DR state merely because it is recent or successful.

## Mandatory source read order completed

The following authoritative files were re-read from the current CloudStack branch:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. `docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`
5. `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`

The current progress ledger still leaves native NAS B&R proof, two-zone cross-zone DR, RPO/RTO measurement, DR mapping, Test Recovery, planned/emergency failover and failback in `PENDING / NOT_TESTED`.

## R0 workflow audit

### Safe read-only workflow

`.github/workflows/layersentry-hyperv-inventory.yml` in the runner repository is a genuine read-only Hyper-V inventory workflow: it uses PowerShell discovery/read operations and emits evidence without intentionally changing guest or hypervisor state.

### Workflows that must NOT be classified as R0

The following workflows perform a temporary guest authorization mutation by injecting an ephemeral SSH public key through the Hyper-V console before gathering CloudStack data:

- `.github/workflows/layersentry-cloudstack-phase2-inventory.yml`
- `.github/workflows/layersentry-cloudstack-api-discovery-v2.yml`

Although the key is intended to be removed during cleanup and the subsequent inventory queries are read-oriented, the guest `authorized_keys` mutation means these workflows are not pure R0/read-only discovery. They require an explicit controlled-mutation checkpoint or should be redesigned to use an already-authorized read-only API/credential path.

No such workflow was dispatched as part of this checkpoint.

## Apache CloudStack 4.22 revalidation

Official 4.22 documentation was revalidated against the target architecture.

### B&R framework

- `backup.framework.enabled` enables B&R.
- `backup.framework.provider.plugin` selects the provider per zone.
- `backup.framework.sync.interval` defaults to 300 seconds and is documented as the internal background interval for metrics/usage collection, backup reconciliation and backup scheduling.
- Therefore `backup.framework.sync.interval=300` is not evidence of a five-minute VM backup or five-minute incremental replication stream.

Reference:
https://docs.cloudstack.apache.org/en/latest/adminguide/backup_and_recovery.html

### Cross-zone recovery

CloudStack 4.22 supports creating an Instance from Backup in another Zone; the current documented cross-zone implementation is supported only by the NAS B&R plugin.

The Backup Repository must have Cross-Zone Instance Creation enabled. Destination hosts must be able to reach and mount the repository. Zone-local resources such as guest networks may require explicit destination selection/mapping.

The official documentation also describes a DRaaS pattern based on a source-zone repository plus background synchronization to NAS servers in other zones, optionally using DNS so the same repository identity resolves to the site-local copy.

Reference:
https://docs.cloudstack.apache.org/en/latest/adminguide/backup_and_recovery.html

### NAS B&R is still full-disk backup in the 4.22 baseline

The NAS B&R plugin uses libvirt push backup for running KVM instances and exports QCOW2 backup disks. Its documented support/limitation section states that instance backups are full-disk backups.

Reference:
https://docs.cloudstack.apache.org/en/4.22.0.0/adminguide/nas_plugin.html

### Native user backup schedule does not provide a five-minute cadence

The CloudStack 4.22 `createBackupSchedule` API accepts `HOURLY`, `DAILY`, `WEEKLY`, and `MONTHLY` interval types.

Reference:
https://cloudstack.apache.org/api/apidocs-4.22/apis/createBackupSchedule.html

Therefore the LayerSentry target of approximately five-minute async RPO remains a LayerSentry replication-provider/controller requirement, not a capability that should be represented as native NAS B&R scheduling.

## Upstream incremental NAS backup watch

Apache CloudStack issue `#12899`, `[RFC] Incremental NAS Backup Support for KVM Hypervisor`, targets CloudStack `4.23+` / milestone `4.23.0`. It must not be treated as functionality present in the LayerSentry 4.22.1.1 baseline.

Reference:
https://github.com/apache/cloudstack/issues/12899

If/when LayerSentry moves to a CloudStack release that actually contains and supports this functionality, Workstream D should re-evaluate whether some provider responsibilities can move back to supported native CloudStack B&R while preserving the external DR orchestration boundary.

## Static DR implementation check

No current source match was found on `adaptgurus/cloudstack` for the product-level labels/objects `DR Protection` or `Recovery Group` during this revalidation. This is consistent with the durable ledger: advanced LayerSentry DR orchestration has not yet been promoted to implemented/live status.

This is a source-search observation only, not proof that no related generic backup/recovery code exists.

## Evidence conclusion

The handoff architecture remains valid for the 4.22.1.1 baseline:

- CloudStack remains authoritative for VM/account/zone/network/storage lifecycle and native backup metadata/recovery APIs.
- Native NAS B&R remains the supported Phase-A cross-zone recovery baseline/fallback.
- LayerSentry must not market native NAS full backups as five-minute incremental DR.
- The approximately five-minute async RPO path still requires a certified incremental/storage-replication provider abstraction.
- No synchronous option should be exposed until the selected backend, network latency, fencing and application topology are explicitly certified.

## Current truth after this checkpoint

`SOURCE/ARCHITECTURE REVALIDATED`

`LIVE CLOUDSTACK DR INVENTORY = UNKNOWN`

`NATIVE TWO-ZONE NAS CREATE-FROM-BACKUP PROOF = PENDING / NOT_TESTED`

`ADVANCED 5-MINUTE REPLICATION IMPLEMENTATION = NOT YET UNBLOCKED`

No DR state is promoted to `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED` by this checkpoint.

## Exact next safe execution gate

Before any Phase-A mutation, obtain a fresh read-only inventory and persist the evidence for:

1. active CloudStack runtime version/build;
2. Zones/Sites, Pods, Clusters and KVM hosts;
3. VM HA state (confirmation only);
4. primary and secondary storage;
5. `backup.framework.*` effective global/zone configuration;
6. NAS B&R plugin availability;
7. Backup Repositories and Backup Offerings;
8. Cross-Zone Instance Creation setting;
9. current disposable test VMs;
10. second DR Zone / second KVM host readiness;
11. source-to-destination network/resource mapping candidates;
12. current async jobs/workflows that could conflict with the test.

Prefer a genuinely R0 API/runner discovery path that does not inject or rotate guest credentials. If the only available discovery path requires temporary guest authorization changes, classify and checkpoint that mutation explicitly before using it.

After fresh inventory passes, resume at the first unmet evidence gate: **native two-Zone NAS create-from-backup recovery end-to-end**, with boot/data/network validation, repeated restore points, RPO/RTO measurement, negative tests and source-record retention/purge validation.
