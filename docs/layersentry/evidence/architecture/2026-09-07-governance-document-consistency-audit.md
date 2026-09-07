# LayerSentry Governance / Document Consistency Audit — 2026-09-07

## Scope

Audited the current execution/governance stack against current repository state and selected external upstream contracts:

- `/AGENTS.md`;
- `LAYERSENTRY_EXECUTION_CONTRACT.md`;
- `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`;
- `LAYERSENTRY_PROGRESS_LEDGER.md` startup/current-checkpoint semantics;
- current Codex index/runbook;
- Workstreams A/B/C/D/E/F;
- legacy `CODEX_MASTER_CONTEXT.md` / `CODEX_MULTI_AGENT_MASTER_CONTEXT.md`;
- historical `WORKSTREAM_A_ACTIVE_HANDOFF.md`;
- K8s specialist master/addendum and release-candidate contract;
- Single-OS specialist/current-status contract;
- DR and bootstrap/control-plane architecture contracts;
- current source-layout/concurrent-change evidence relevant to module ownership.

This is a governance/document audit, not a line-by-line review of every historical evidence file in the repository and not production-certification evidence.

## High-signal findings and corrections

1. **Legacy Codex master contexts could reactivate obsolete parallel A/B/C/D/E execution.** Corrected: both files are now compatibility shims marked `SUPERSEDED_FOR_EXECUTION`.
2. **`WORKSTREAM_A_ACTIVE_HANDOFF.md` still claimed mandatory active UI continuation.** Corrected: archived as history; current UI Workstream A is deferred finalization.
3. **K8s/Single-OS startup loaded large specialist master contexts on every session.** Corrected: Workstreams E/F and the Codex runbook now start from the small active workstream/current-status contract; large specialist masters are on-demand for real architecture/provider conflicts.
4. **Shared Ansible ownership was ambiguous.** Corrected: Single-OS vs bootstrap/hypervisor normal paths are separated; `ansible.cfg`, collection requirements and deliberately shared roles/modules require an explicitly serialized shared-Ansible task.
5. **Module-specific CI workflow ownership was missing.** Corrected: Single-OS may own `.github/workflows/layersentry-single-os-*`; K8s may own `.github/workflows/layersentry-k8s-*`; generic release/signing workflows remain milestone-owned.
6. **Second working RKE2 package lane could be over-interpreted as full LayerSentry certification.** Corrected: package-lane evidence is scoped to that target and cannot by itself promote full LayerSentry K8s/DBaaS to `LIVE_VERIFIED`.
7. **Dormant release/security workstreams still looked like standing Codex streams and release work referenced the old two-bundle model.** Corrected: B/C are now milestone/concrete-defect gated; B uses the current one-carrier V1 model.

## External contract validation

Current public upstream documentation supports the core architecture decisions:

- Apache CloudStack 4.22 supports creation of a new instance from NAS B&R backup in another Zone, so native cross-Zone recovery is a valid DR baseline.
- RKE2 requires TCP 9345 for supervisor/registration and TCP 6443 for the Kubernetes API; the dual-endpoint LayerSentry gate is correct.
- Cluster API v1beta2 temporarily supports v1beta1 infrastructure-provider contracts with limitations, so the current CAPI 1.13 / older CAPC Lane-B approach is a legitimate qualification candidate but not a permanent compatibility assumption. The CAPC stop-loss/fallback remains necessary.
- OpenEverest stable v1.16.2 documentation supports Kubernetes 1.33-1.36 and states upstream air-gap is not currently supported; LayerSentry offline OpenEverest must therefore remain a LayerSentry-engineered/qualified profile.
- CloudStack Management Server HA behind an administrator-provided load balancer with persistence is consistent with the control-plane policy; current LayerSentry preference for native management-address distribution for KVM/System-VM agents remains a release-specific qualification item.

## Residual gaps / intentional blockers

### Progress Ledger embedded startup text

The Progress Ledger still contains an older recovery/read-order and historical owner labels (for example older Workstream-B references). `AGENTS.md` now explicitly states that these embedded historical instructions are superseded by current AGENTS/Execution Contract routing. A future ledger compaction may rewrite the header, but it is not necessary to reopen every historical checkpoint.

### Large specialist masters still contain historical execution alternatives

The K8s specialist master still contains older conceptual two-carrier and OpenEverest-branding sections; the Single-OS specialist master contains historical migration-state language. They are no longer mandatory startup context. Current Workstreams E/F and the Execution Contract explicitly supersede those execution assumptions. Preserve the detailed architecture/history until a dedicated specialist-document compaction is justified.

### No automatic writer lock

One-writer-per-module is a governance rule, not a distributed lock. Sessions must still fetch/reconcile before meaningful batches and the operator must avoid launching two source writers for the same module.

### Bootstrap-managed libvirt domains on CloudStack KVM hosts

The bootstrap architecture intentionally creates only allowlisted control-plane domains before CloudStack exists, then registers those KVM hosts. Coexistence with CloudStack agent ownership remains a required live qualification gate and must not be inferred from design.

### Production evidence

This governance audit changes execution efficiency only. It does not promote K8s hard gates, DR recovery, Single-OS providers, control-plane HA, release trust or any other runtime capability.

## Current recommended execution model

```text
ACTIVE WRITER: one RKE2/K8s Codex session
TEST-ONLY: second healthy RKE2 package qualification lane
ACTIVE WRITER: one Single-OS ChatGPT session when lab ready
ACTIVE WRITER: one DR ChatGPT session
OPTIONAL WRITER: bootstrap/hypervisor ChatGPT when lab ready
DEFERRED: one final UI Codex pass after backend contracts stabilize
MILESTONE ONLY: release/signing/security
```

Manual recreation/reinstall of disposable Rocky Linux lab VMs is the preferred lab-reset shortcut when a destructive acceptance test dirties a guest; do not build general reimage automation solely for test cleanup.

## Outcome

The **core technical approach is validated as coherent**. Remaining risk is primarily live integration/certification rather than an architectural need to rebuild CloudStack, RKE2, OpenEverest, OpenBao, Harbor, Strimzi or DR data-plane functionality. The corrected governance model should reduce duplicate context loading, cross-module edits, stale-handoff restarts and unnecessary Codex spend.
