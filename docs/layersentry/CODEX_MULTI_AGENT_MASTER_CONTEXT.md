# LayerSentry V1 — Multi-Agent Context

> **Purpose:** concise policy for parallel Codex execution. Detailed operator commands/prompts live in `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md`. Stable product/security/evidence rules live in `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`. Current completion state lives only in `LAYERSENTRY_PROGRESS_LEDGER.md`.

This file deliberately contains no current HEADs, run IDs, artifact IDs, live IPs or task-status duplication.

## Mandatory authority

Each agent must read:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. its assigned workstream file under `docs/layersentry/codex/`.

Use `CODEX_4_AGENT_RUNBOOK.md` for worktree setup and launch prompts.

## Workstream ownership

- **A — UI / Self-service:** customer product profile, role-aware navigation/dashboards, terminology, VM/CKS/Bucket/Site UX.
- **B — Release / Installer / Build:** CI artifacts, build settings, installer/resume/rollback, manifest/SBOM/provenance/digest/signature.
- **C — Security / Validation:** RBAC/negative tests, SELinux/firewall/package/update/snapshot/CKS security and evidence tooling.
- **D — DR / HA / Upgrade:** runner/Hyper-V discovery, DR/HA/upgrade proof automation and evidence.

Do not modify another workstream's primary files without coordination. If cross-workstream work is required, document the dependency rather than silently creating overlapping edits.

## Git isolation

- one writable Git worktree per agent;
- one branch per worktree;
- all branches start from the actual fetched integration HEAD;
- never force-push or rewrite another agent's branch;
- agents do not self-merge into the shared integration branch unless explicitly assigned;
- only the integration/lead path updates the shared progress ledger by default.

## Live-environment isolation

Parallel reasoning/editing is allowed. Conflicting live mutations are not.

Serialize:

- deployments to the same target;
- VM/network/storage operations;
- backup/recovery/DR operations;
- upgrades/reboots;
- heavy builds that would contend for the same runner capacity.

Every R3/R4 operation follows the canonical change-risk gate: current-state inspection, exact-target verification, durable checkpoint, rollback/recovery plan, authorization and immediate evidence capture.

## Integration order

When dependencies overlap, default review/integration order is:

1. B — release/build foundation;
2. A — product/UI behavior;
3. C — security/negative validation against integrated A/B state;
4. D — live DR/HA/upgrade validation after the source/deployment baseline is stable.

Independent, non-overlapping changes may be reviewed in another order when the integration lead documents why.

## Agent handoff

Every agent reports exact base/final commits, files changed, core impact, checks actually executed, runtime mutations, evidence, known limitations, retry/rollback state and next evidence gate.

No agent may promote status from model confidence, documentation support or another agent's unreviewed claim.
