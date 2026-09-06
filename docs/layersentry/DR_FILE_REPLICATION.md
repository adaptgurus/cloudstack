# DC/DR file-backed replication module

Status: `NOT_TESTED`. Source implementation and manual logic review only; no tests, lint, build, CI, provider calls, transfer, reconstruction or deployment were run. This module implements the NAS/QCOW2 replication data path. It does not claim LINSTOR/Ceph/array support or production DR certification.

## Components

| Source file under `tools/layersentry/` | Responsibility |
| --- | --- |
| `dr_replication.py` | Completed native NAS backup copying with disk membership, digests and atomic publication |
| `dr_native_provider.py` | Exact selected-backup binding to the existing native CloudStack adapter and recovery journal |
| `dr_file_replication.py` | File-provider plans, immutable full/incremental manifests, dependency catalog, retention and standalone image reconstruction |
| `dr_libvirt_capture.py` | Single-workload source journal, bounded libvirt capture, restart reconciliation, destination-acknowledged cursor and scheduled single-step execution |
| `dr_replication_transport.py` | Pinned SSH streaming receiver/sender and an operator-mounted storage alternative |
| `dr_replication_cli.py` | Explicit operator commands; mutations require enabled configuration and `--execute` |

The native binding also imports the existing `dr_state_machine.py`. Install these reviewed files together; the SSH receiver command intentionally fixes the installation path to `/opt/layersentry/dr/dr_replication_cli.py` and its configuration to `/etc/layersentry/dr/receiver.json`. No installation has been performed by this work.

## Operator configuration

Configuration is JSON in a root/service-owned directory, with no symlink components or group/world write access. `schema` is `1`, `enabled` is a boolean and starts `false`. `role` is `source` or `receiver`. Both configurations embed the same `plan` object; credentials never belong in that object or its manifest.

Required plan fields are `plan_id`, `tenant_id`, `workload_id`, `source_site_id`, `recovery_site_id`, `repository_id`, `domain_uuid`, `domain_name`, `disks`, `libvirt_version` and `qemu_version`. IDs are canonical UUIDs. A disk has `device`, `volume_id`, `source_path` and `virtual_bytes`. Record every writable disk in a stable order. Source paths and sizes must match the actual domain; capture refuses raw/block disks, changed membership, active domain jobs and existing VM snapshots.

Version pins use libvirt's integer encoding: major × 1,000,000 + minor × 1,000 + patch. Populate them from the actual installed provider. The source daemon and reconstruction `qemu-img` must match their pins; the minimum API floor is libvirt 7.2/QEMU 4.2, not a recommendation to install obsolete versions. Changed domain/disk/version identity requires a new reviewed plan identity; old manifests retain their original scope.

Optional policies are `max_chain` (24), `retention_count` (24, minimum 2), `minimum_retention_seconds` (86400), `rpo_seconds` (300), `capture_timeout` (3600), `transfer_timeout` (3600), `max_bytes` (16 TiB), `reserve_bytes` (1 GiB) and `max_points` (4096). RPO is an objective, never an advertised guarantee. Capacity limits include QCOW2 file overhead. Parent dependencies remain retained even when they exceed the nominal point count.

The source additionally requires `state_root`, `capture_root`, `qemu_uid`, `qemu_gid`, `qemu_img` and `transport`. The state root is an existing private `0700` directory. The separate capture root is owned by the operator, traversable by the configured QEMU group and not group/world writable. Root capture creates a QEMU-owned private epoch directory, then removes QEMU write access only after successful backup completion. SELinux labels and filesystem access must be provisioned through the appliance policy; the module never disables SELinux or changes source primary-disk permissions.

For mounted transfer, `transport` contains `kind: "mounted"` and `destination_root`. For SSH, it contains `kind: "ssh"`, `host`, `user`, `port`, `identity_file` and `known_hosts`. The latter files must already be provisioned securely. SSH uses strict host-key verification, an explicit identity, no agent forwarding, no password fallback and a fixed receiver command. Restrict its server-side account/key to that command and disable forwarding. There is no automatic host-key enrollment.

The receiver additionally requires `destination_root`, `allowed_scope_sha256` and `qemu_img`. `inspect` prints the scope digest to pin independently on the receiver. The destination root contains `.layersentry-repository.json` with exactly `schema: 1`, `site_id` equal to the recovery Site and the plan's `repository_id`. This marker pins operator configuration; it is not remote attestation. A mounted transport's authentication/encryption is external to the module. SSH provides the implemented authenticated transport alternative.

## Commands

All commands take `--config PATH`. Nothing below has been executed for this change.

| Command | Behavior |
| --- | --- |
| `inspect` | Print offline plan scope digest and enablement |
| `status` | Read source cursor and active epoch; destination health remains `UNKNOWN` |
| `capture --epoch UUID --mode AUTO --execute` | Create a first full point or incremental from the acknowledged parent; periodically choose a new full baseline at the chain limit |
| `resume --epoch UUID --execute` | Reconcile existing capture proof and retry sealed-byte transfer; never resubmit an uncertain capture |
| `tick --execute` | One bounded scheduler step; resume the active epoch or capture when due; no daemon or busy polling |
| `abandon --epoch UUID --execute` | Stop only the recorded capture child through a PID-safe handle, require fresh idle-domain evidence, retain provider objects and force the next full baseline |
| `receive --execute` | Fixed SSH receiver protocol; only a pinned plan can push or verify a point |
| `list --offset 0 --limit 100` | Paginated destination metadata; listing alone is not integrity proof |
| `verify --epoch UUID` | Rehash every disk in the selected dependency chain |
| `materialize --epoch UUID --output-root PATH --execute` | Reconstruct the chosen full/incremental point into new standalone QCOW2 files under a private root |
| `retention --pin UUID` | Compute dependency-aware retirement candidates; pins can repeat |
| `retire --catalog-sha256 DIGEST --pin UUID --execute` | Re-evaluate the exact catalog and move eligible points to recoverable trash |

`capture` requires an explicit epoch UUID. Reusing one with different intent fails. `tick` generates an ID only for a new operation. Source state progresses through `PREPARED`, `CAPTURING`, `TRANSFERRING` and `COMMITTED`; missing durable completion proof becomes `RECONCILIATION_REQUIRED`. A destination acknowledgement is journaled before source-head advancement. An acknowledgement lost in transit is resolved by re-sending the same manifest and only missing files. Capture creates a new tracking checkpoint, but the acknowledged source cursor remains on its prior point until complete destination acknowledgement; older tracking checkpoints are retained.

`materialize` verifies all parent hashes and disk identities, copies each layer into a fresh workspace, attaches predecessor paths only on those private copies, and flattens each final disk. It never redefines a libvirt domain, edits a retained replica, imports a fake native backup record, attaches storage, starts a VM or changes traffic. CloudStack-supported VM/volume import and isolated guest validation remain the recovery integration boundary. Failed workspaces are retained for inspection and do not receive a completion receipt.

## Lifecycle and evidence boundaries

Only one enabled protection strategy may own a workload's capture window. The local workload lock does not prevent unrelated CloudStack/administrator backup, snapshot or migration commands; integration must serialize them. SQLite/file locks and SSH are not distributed witness or source fencing. No automatic failover, VM promotion, application health or traffic switching is enabled here. Reverse-direction data replication uses a separately authorized plan with the Sites and actual recovered workload/disk identities reversed, after the recovery owner establishes exclusivity.

Retirement preserves data in trash and intentionally reclaims zero bytes. Source captured files and libvirt checkpoint metadata are also preserved. Explicit, independently reviewed garbage collection is required before long-term capacity limits are reached; it must retain the acknowledged source checkpoint and every catalog dependency. The module fails closed at capacity limits instead of silently discarding recovery history. No automatic destructive garbage collection is claimed.

Runtime acceptance must cover full plus at least two incremental epochs, changed-to-zero blocks, multiple disks, latest/older reconstruction and guest hashes, source restart, failed/ambiguous capture, partial transfer, lost acknowledgement, parent corruption, capacity exhaustion, concurrent writers, clock changes, pinned-key rejection and retention dependencies. Test exact provider packages and filesystem `fsync`/`renameat2(RENAME_NOREPLACE)` behavior on Rocky Linux 9. Network filesystem calls can remain blocked in the kernel despite Python deadlines. A same-host lab cannot establish independent-site certification.

Design/source references are recorded in [the source decision](evidence/dr/2026-09-06-replication-source-design.md). Current implementation does not alter CloudStack Java/API/schema, Workstream E or any lab VM.
