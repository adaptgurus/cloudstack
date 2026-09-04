# LayerSentry Codex Operating Rules

This repository is Apache CloudStack 4.22.1.1 with a LayerSentry product/UI/automation overlay. Codex agents working here must preserve CloudStack core behavior and must not turn assumptions into project facts.

## Mandatory startup sequence

Before changing code, read these files in this order:

1. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
2. `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md`
3. `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`
4. `docs/layersentry/LAYERSENTRY_UPSTREAM_DIFF.md`
5. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
6. `docs/layersentry/CODEX_MASTER_CONTEXT.md`
7. the workstream file explicitly named in the task prompt, if any

The progress ledger is the freshest status source. The re-audit and upgrade/IP documents override older conflicting wording in the Super Master Context. Actual current repository, workflow, and live-runtime evidence override all historical text.

Run `git status`, `git branch --show-current`, `git rev-parse HEAD`, and `git log -1 --oneline` before editing. Fetch the intended base branch before planning. Never force-reset or rewrite the shared LayerSentry branch.

## Non-negotiable architecture

Do not rewrite CloudStack core unless an explicitly documented, verified upstream defect makes it unavoidable. Default answer is NO to changes in:

- CloudStack Java backend APIs or API names
- CloudStack database schema
- KVM agent protocol or core orchestration
- RBAC enforcement semantics
- Zone/Pod/Cluster/Host internal model
- storage/network orchestration semantics
- asynchronous-job semantics
- upstream hypervisor implementations

Prefer LayerSentry-only files, UI/configuration, supported CloudStack APIs, external adapters/controllers, installers, CI, health checks, and tests. Keep the upstream delta small for future upgrades.

## Current V1 product rules

- Customer experience is KVM-only, but upstream non-KVM implementations remain in CloudStack core.
- DBaaS/APaaS placeholders are removed from V1 and are LIVE_VERIFIED on the current `sen` lab target. Do not recreate them.
- Future DBaaS belongs above Kubernetes, not in CloudStack core.
- Feature visibility requires RBAC permission plus actual prerequisite/provider/configuration state; route existence or API visibility alone is insufficient.
- Customer terminology is presentation only. Backend names and API semantics remain unchanged.
- Production management nodes must eventually deploy CI-built immutable UI artifacts rather than compile Vue locally.
- Production target is Rocky Linux 9 appliance-locked, SELinux enforcing after tested policy work, controlled package/update channel, and minimal customer shell access.
- Do not claim full air-gap CKS until an internal-registry/bootstrap solution is implemented and tested.
- NAS B&R is not the primary protection method for CKS cluster VMs.

## Anti-hallucination / evidence rules

Never invent or silently infer current IPs, VLANs, host/storage/network state, agent state, System VM state, K8s/object-store/backup health, HA/DB replication state, workflow IDs, commit SHAs, RPO/RTO, or test success.

If current evidence is missing, use `UNKNOWN`, `UNVERIFIED`, or `NOT_TESTED`.

Documentation proves supported capability, not current deployment health. HTTP 200 proves only the tested endpoint. A build proves compilation only. A commit proves source history only. A workflow proves only its explicit assertions.

Use only these project status labels when reporting material work:

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

Do not say `complete`, `fixed`, `healthy`, `HA`, `DR ready`, `air-gapped`, `immutable`, or `production ready` without the corresponding evidence gate.

## Safety and runtime mutation

Before any destructive, connectivity-affecting, storage/network, DB, reboot, VM-destroy/recovery, HA, or DR mutation:

1. inspect current live state;
2. create a durable pre-action checkpoint;
3. record rollback/recovery method;
4. identify whether the action is idempotent;
5. execute only after the task scope clearly authorizes it.

If an operation may already be in flight, inspect its exact state before retrying. Never launch a duplicate deployment, backup, recovery, network mutation, or VM creation merely because chat context was lost.

## Parallel-agent rules

Use a separate branch/worktree for every Codex workstream. Do not let two agents write to the same worktree.

Default workstream ownership:

- A UI/Self-service: `ui/src/**` and customer-facing UI tests; avoid installer/release files.
- B Release/Installer: installer scripts, release/build pipeline, `ui/vue.config.js`, artifact/signing/SBOM work; avoid dashboard/wizard implementation.
- C Security/Validation: validation/test tooling, RBAC/security test harness, SELinux/firewalld/snapshot/CKS security evidence; avoid large production UI rewrites.
- D DR/HA/Upgrade: primarily `adaptgurus/cozystack` runner/Hyper-V/DR/HA/upgrade workflows and evidence; CloudStack source changes only when specifically required and coordinated.

Do not edit `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md` from parallel workstreams unless the task explicitly assigns ledger ownership. Instead create/update the assigned workstream report under `docs/layersentry/codex/`. The integration/lead session updates the shared ledger after reviewing/merging.

## Validation and commits

Prefer small atomic commits. Run the narrowest relevant checks first, then broader checks before handoff. Do not disable tests or weaken security checks merely to make a build pass.

Every workstream handoff must state:

- exact branch and commit
- files changed
- tests/checks run and their real results
- known limitations
- any runtime mutation performed
- merge/conflict risks
- exact next gate

Leave the worktree clean or explicitly explain remaining uncommitted files.
