# LayerSentry — Four-Agent Codex Startup Guide

Open the repository root in Codex so root `AGENTS.md` is in scope. Codex should read `AGENTS.md` automatically; each thread is also told exactly which workstream document to read.

## Agent A — UI / Self-Service

Paste this as the first task in the A thread:

> You are LayerSentry Codex Workstream A. Read `/AGENTS.md`, `docs/layersentry/CODEX_MASTER_CONTEXT.md`, and `docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`, plus every mandatory document referenced by AGENTS.md. First fetch/inspect the actual current `layersentry/4.22.1.1-ui` HEAD and current progress ledger. Use an isolated worktree/branch named `codex/layersentry-ui-self-service` or equivalent. Do not modify CloudStack Java/backend/database/KVM-agent code. Do not edit the shared progress ledger. Implement only your owned UI/self-service scope, run real tests, commit atomically, and finish with the standard evidence handoff. Do not call anything complete without its evidence gate.

## Agent B — Release / Installer / Build

Paste this as the first task in the B thread:

> You are LayerSentry Codex Workstream B. Read `/AGENTS.md`, `docs/layersentry/CODEX_MASTER_CONTEXT.md`, and `docs/layersentry/codex/WORKSTREAM_B_RELEASE_INSTALLER.md`, plus every mandatory document referenced by AGENTS.md. First fetch/inspect the actual current `layersentry/4.22.1.1-ui` HEAD and current progress ledger. Use an isolated worktree/branch named `codex/layersentry-release-installer` or equivalent. Own release/build/installer only. Do not redesign dashboards or modify CloudStack core. Do not edit the shared progress ledger. Prioritize moving production UI compilation to a deterministic CI-built immutable artifact with no production source maps, digest/signature/release manifest/SBOM and safe installer deployment/rollback. Run real tests, commit atomically, and finish with the standard evidence handoff.

## Agent C — Security / Validation

Paste this as the first task in the C thread:

> You are LayerSentry Codex Workstream C. Read `/AGENTS.md`, `docs/layersentry/CODEX_MASTER_CONTEXT.md`, and `docs/layersentry/codex/WORKSTREAM_C_SECURITY_VALIDATION.md`, plus every mandatory document referenced by AGENTS.md. First fetch/inspect the actual current `layersentry/4.22.1.1-ui` HEAD and current progress ledger. Use an isolated worktree/branch named `codex/layersentry-security-validation` or equivalent. Own test/security/evidence tooling only. Do not weaken SELinux, firewalld, RBAC, or tests merely to pass. Do not make broad UI or installer rewrites. Do not edit the shared progress ledger. Build evidence-driven RBAC, SELinux/firewalld, package-lock, snapshot-safety, CKS metadata-isolation/CSI validation and support-bundle coverage. Commit atomically and finish with the standard evidence handoff.

## Agent D — DR / HA / Upgrade

This thread normally needs the runner repository as well as the CloudStack context.

Paste this as the first task in D:

> You are LayerSentry Codex Workstream D. Read the LayerSentry root `/AGENTS.md`, `docs/layersentry/CODEX_MASTER_CONTEXT.md`, and `docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`, plus every mandatory document referenced by AGENTS.md. Inspect actual current HEADs of `adaptgurus/cloudstack:layersentry/4.22.1.1-ui` and `adaptgurus/cozystack:ops/layersentry-hyperv-inventory`, current workflows, and live evidence before mutation. Use isolated worktrees/branches. Own runner/Hyper-V/DR/HA/upgrade test automation. Do not alter CloudStack core to make tests pass. Do not edit the shared progress ledger. Before every destructive or connectivity-affecting action create a durable checkpoint and rollback plan. First prove native two-Zone B&R recovery on disposable workloads before advanced DR orchestration. Commit atomically and finish with exact workflow/job/artifact/live evidence.

## Integration / Lead thread

Keep one non-coding lead/review thread (ChatGPT or Codex) responsible for:

1. checking all four branch HEADs and handoff reports;
2. reviewing file overlap and CloudStack-core impact;
3. merging/cherry-picking in a controlled order;
4. running combined build/regression;
5. deploying only reviewed exact artifacts;
6. updating `LAYERSENTRY_PROGRESS_LEDGER.md` after evidence changes status;
7. resolving cross-workstream conflicts;
8. preserving the integration branch as the authoritative LayerSentry state.

Recommended integration order is B -> A -> C -> D unless a change is demonstrably independent and non-overlapping.

## Parallelism rule

Four agents may work simultaneously, but no two agents should share one writable worktree. The safest arrangement is one Codex project with four independent worktree-backed threads, or four Codex windows each opened on a different Git worktree.

Never have four agents directly commit to `layersentry/4.22.1.1-ui`.
