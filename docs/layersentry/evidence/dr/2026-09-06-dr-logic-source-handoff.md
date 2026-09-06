# LayerSentry DR Logic Source Handoff — 2026-09-06

## Status

`NOT_TESTED`

This handoff records source implementation only. No tests, builds, lint, CI,
deployments, live DR operations, failover drills, fencing tests, provider
promotion tests, recovery validation, or failback validation were run for this
change. Nothing in this handoff is `CI_VERIFIED` or `LIVE_VERIFIED`.

## Repository / branch

- repository: `adaptgurus/cloudstack`
- branch: `layersentry/4.22.1.1-ui`
- historical DR checkpoint: `b6149b9848de8a067e2d655c7336725ef6a03537`
  - historical context only;
  - the branch was **not** reset to this commit.
- provider-neutral DR state implementation commit:
  `8304bab4c3e8c209de9929c9f718053e32210724`
- implementation file: `tools/layersentry/dr_state_machine.py`
- branch HEAD observed immediately before this handoff write:
  `9922324cb569ffbce74c2c2a5a78c91edd180ea4`

The branch is shared with other active agents. Unrelated commits were preserved;
no reset, force-push, history rewrite, broad revert, or overwrite was used.

## Source scope completed in `8304bab...`

The new source layer is intentionally provider-neutral and inactive by default.
It does not create a second scheduler or RBAC authority and it does not modify
CloudStack core DB/API contracts.

Implemented source contracts/primitives:

1. DR domain objects:
   - `SitePair`;
   - `ProtectionPlan`;
   - `RecoveryPoint`;
   - `RecoveryGroup`;
   - `NetworkMapping`;
   - `IpMapping`.
2. Explicit DR operation types:
   - Test Recovery;
   - selected-recovery-point Recovery;
   - Planned Failover;
   - Failback;
   - Auto Failover.
3. Durable operation state model:
   - requested;
   - exclusive lease acquired;
   - prechecked;
   - provider mutation submitted/pending;
   - destination validation;
   - application validation;
   - traffic-switch pending;
   - completed / blocked / failed;
   - `RECONCILIATION_REQUIRED` for ambiguous mutation outcomes.
4. Idempotent mutation journal:
   - unique idempotency key;
   - immutable request fingerprint;
   - conflicting reuse fails closed;
   - append-only operation journal events.
5. Exclusive operation lease:
   - resource-scoped lease;
   - generated opaque lease token;
   - expiry/renew/release semantics;
   - post-lease state transitions require the live matching token;
   - terminal operations cannot acquire a new lease.
6. Explicit recovery-point safety:
   - Test Recovery, Recovery and Failback require an explicit
     `recovery_point_id`;
   - supplied recovery point must belong to the selected Protection Plan and
     provider;
   - there is no silent "latest recovery point" selection in this source.
7. Test Recovery isolation contract:
   - Test Recovery requests must explicitly declare an isolated test network.
8. Provider capability contract:
   - CloudStack native;
   - LINSTOR/DRBD;
   - Ceph RBD;
   - SAN array;
   - libvirt backup;
   - provider-specific implementations are not embedded in the state machine.
9. Planned Failover / Failback capability gates:
   - safe promotion;
   - fencing;
   - no-dual-writer proof;
   - destination validation;
   - application validation;
   - reverse replication/failback where required.
10. Fail-closed Auto Failover transition path:
    - the generic state-transition API cannot advance Auto Failover;
    - Auto Failover requires the dedicated evidence-gated path;
    - the Protection Plan must explicitly enable automatic failover;
    - operation, plan and provider identities must match;
    - provider capability requirements must pass;
    - witness/quorum, source fencing and no-dual-writer proof are required
      before provider mutation stages;
    - provider-safe promotion is required before destination validation stages;
    - destination validation is required before application-validation stages;
    - application validation and traffic-switch readiness are required before
      traffic switching/completion.
11. Ambiguous mutation handling:
    - uncertain non-auto provider mutation outcomes transition to
      `RECONCILIATION_REQUIRED`;
    - the journal records `FAIL_CLOSED_NO_AUTOMATIC_REPLAY`;
    - automatic failover ambiguity cannot use the generic retry path.

## Existing native recovery foundation

The historical DR checkpoint documents the existing native CloudStack
`createVMFromBackup` recovery foundation, explicit recovery-point handling,
mutation journaling, Advanced-Zone constraint and fail-closed retry behavior.
That native adapter remains authoritative for the actual CloudStack recovery
mutation.

`tools/layersentry/dr_state_machine.py` deliberately does **not** duplicate or
replace the native `createVMFromBackup` implementation. It exposes a
`RecoveryProvider` contract so the native adapter can be bound to the durable
state machine in the next integration step.

No historical native-adapter implementation SHA is invented in this handoff.
Only SHAs directly observed from the repository are recorded.

## Persistence boundary

`DurableDrStore` currently provides a LayerSentry-owned SQLite durable source
primitive for DR objects, operations, journal and leases. It does not write to
CloudStack core tables.

This does **not** certify SQLite as the final distributed production
coordination backend. A production multi-controller deployment still requires
an approved shared transactional/consensus-capable persistence and lease model,
plus runtime validation. The current implementation is therefore source
progress only and remains `NOT_TESTED`.

## Intentionally not implemented in this source step

- no background scheduler;
- no alternate RBAC/authorization authority;
- no CloudStack core schema/API changes;
- no automatic traffic switching;
- no actual witness/quorum implementation;
- no actual source fencing implementation;
- no LINSTOR/DRBD replication adapter;
- no Ceph RBD replication adapter;
- no SAN-array replication adapter;
- no libvirt replication engine;
- no `rsync` primary VM replication path;
- no provider promotion/failback side effects;
- no new call path that replaces the established native CloudStack recovery
  adapter;
- no deployment or production enablement of Auto Failover.

## Next DR-only source task

Continue from the actual live branch HEAD and bind the established native
CloudStack recovery adapter behind the new `RecoveryProvider` contract without
reimplementing `createVMFromBackup`.

That integration should:

1. preserve the existing Advanced-Zone guard;
2. require the caller-selected recovery-point UUID end-to-end;
3. translate native async-job submission/result into the durable operation
   journal;
4. reconcile uncertain async outcomes by querying provider state/job state
   instead of blindly resubmitting a mutation;
5. support isolated Test Recovery without production network/IP collision;
6. keep Planned Failover, Failback and Auto Failover provider-side actions
   capability-gated until their actual providers/fencing/witness paths exist;
7. keep every new source change `NOT_TESTED` until the user explicitly permits
   validation.

Before that write, re-read root `AGENTS.md`, the current Progress Ledger, DR
architecture and DR workstream, then fetch the actual current branch HEAD to
avoid clobbering concurrent agents.

## Verification statement

No verification command was executed for `8304bab...` by this DR continuation.
The implementation is therefore **`NOT_TESTED`**. Source presence and commit
identity are repository facts only; they are not evidence of runtime
correctness, CI success, deployment success, failover safety or production
readiness.
