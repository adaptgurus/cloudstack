# LayerSentry — Codex Workstream Startup Index

This directory contains scoped Codex workstream contracts. It does not contain the authoritative current project state.

## Common read order

Every Codex workstream starts with:

1. repository `/AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. the assigned workstream file below.

Read specialist upgrade/IP, upstream-delta or four-agent runbooks only when the current task needs them.

Always fetch the actual current integration refs before editing. Do not use historical SHAs/run IDs/live addresses from old handoffs.

## A — UI / Self-Service

Workstream:

`docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`

Starter prompt:

```text
You are LayerSentry Workstream A: UI / Self-service. Read AGENTS.md, the canonical Super Master Context, current progress ledger and WORKSTREAM_A_UI_SELF_SERVICE.md. Fetch/inspect the actual current integration ref before editing. Work only inside A ownership on an isolated worktree/branch. Preserve CloudStack core and server-side RBAC, do not recreate DBaaS/APaaS, use the governed status/risk/evidence rules, run real relevant tests, commit atomically and stop at a reviewable branch with the standard evidence handoff. Do not self-merge or edit the shared progress ledger unless explicitly assigned.
```

## B — Release / Installer / Build

Workstream:

`docs/layersentry/codex/WORKSTREAM_B_RELEASE_INSTALLER.md`

Also read `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`.

Starter prompt:

```text
You are LayerSentry Workstream B: Release / Installer / Build. Read AGENTS.md, the canonical Super Master Context, current progress ledger, upgrade/supply-chain policy and WORKSTREAM_B_RELEASE_INSTALLER.md. Fetch/inspect the actual current integration ref before editing. Own only release/build/installer scope on an isolated worktree/branch. Build verified CI artifacts, manifest/SBOM/provenance/digest/signature and safe fresh/resume/repair/rollback behavior without CloudStack-core changes or dashboard redesign. Apply governed status/risk/evidence rules, never commit secrets/signing keys, run real relevant tests and stop at a reviewable branch with the standard handoff. Do not self-merge or edit the shared ledger unless assigned.
```

## C — Security / Validation

Workstream:

`docs/layersentry/codex/WORKSTREAM_C_SECURITY_VALIDATION.md`

Starter prompt:

```text
You are LayerSentry Workstream C: Security / Validation. Read AGENTS.md, the canonical Super Master Context, current progress ledger and WORKSTREAM_C_SECURITY_VALIDATION.md. Fetch/inspect the actual current integration ref before editing. Work only inside C ownership on an isolated worktree/branch. Build evidence-driven RBAC/direct-URL, feature-gating, SELinux/firewall/package/update/snapshot/CKS security and support validation. Do not weaken safeguards to pass tests. Use governed statuses and R0-R4 risk gates, preserve uncertainty honestly and stop at a reviewable branch with exact evidence. Do not self-merge or edit the shared ledger unless assigned.
```

## D — DR / HA / Upgrade

Workstream:

`docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`

D normally uses both `adaptgurus/cloudstack` context and `adaptgurus/cozystack` runner automation. Also read `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`.

Starter prompt:

```text
You are LayerSentry Workstream D: DR / HA / Upgrade. From the parent containing cloudstack/ and cozystack/, read cloudstack/AGENTS.md, canonical Super Master Context, current progress ledger, upgrade policy and WORKSTREAM_D_DR_HA_UPGRADE.md. Fetch/inspect actual current refs in both repositories plus relevant workflow/live state before mutation. Own safe runner/Hyper-V/DR/HA/upgrade proof automation only; do not change CloudStack core to make a test pass or build advanced DR before native recovery is proven. Apply R0-R4 gates rigorously, never duplicate an in-flight operation, use disposable approved data for destructive tests and hand off exact commits/workflow/artifact/live evidence. Do not self-merge or edit the shared ledger unless assigned.
```

## Integration / Lead

A separate integration/lead session should:

1. fetch current integration refs;
2. review each branch diff and ownership overlap;
3. reject unexplained CloudStack-core changes;
4. integrate one coherent change at a time;
5. run combined tests;
6. coordinate all live deployment/mutation;
7. update `LAYERSENTRY_PROGRESS_LEDGER.md` only when evidence changes project status.

Default dependency order when overlap exists: **B -> A -> C -> D**.

## Local setup

Use `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md` for WSL/worktree/launch commands. Never allow two writing agents to share one worktree, and serialize conflicting live mutations/heavy tests on the same runner/Hyper-V target.
