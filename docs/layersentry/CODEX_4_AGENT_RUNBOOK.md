# LayerSentry V1 — Four-Agent Codex Runbook

## Purpose

This runbook tells the human operator how to run four parallel Codex workstreams without agents overwriting each other, hallucinating project state, or repeating already verified work.

The coding authority remains:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md`
4. `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`
5. `docs/layersentry/LAYERSENTRY_UPSTREAM_DIFF.md`
6. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
7. `docs/layersentry/CODEX_MASTER_CONTEXT.md`
8. assigned workstream file under `docs/layersentry/codex/`

Repository/workflow/live evidence overrides historical text. Never use a SHA written in this file as a substitute for fetching current HEAD.

## Parallel workstreams

### A — UI / Self-service

Workstream file:

`docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`

Suggested branch:

`codex/layersentry-ui-self-service`

Owns customer UI/navigation/dashboard/wizard/terminology work. Does not own installer/release/DR runner automation.

### B — Release / Installer / Build

Workstream file:

`docs/layersentry/codex/WORKSTREAM_B_RELEASE_INSTALLER.md`

Suggested branch:

`codex/layersentry-release-installer`

Owns immutable CI artifact, installer/resume/rollback, release manifest, SBOM, digest/signature verification, production source-map policy, and build-only settings.

### C — Security / Validation

Workstream file:

`docs/layersentry/codex/WORKSTREAM_C_SECURITY_VALIDATION.md`

Suggested branch:

`codex/layersentry-security-validation`

Owns RBAC/negative tests, SELinux/firewalld validation, package-lock validation, snapshot-safety tests, CKS metadata/CSI validation, and evidence/support tooling.

### D — DR / HA / Upgrade

Workstream file:

`docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`

Suggested branches:

- CloudStack context/support branch: `codex/layersentry-dr-ha-upgrade`
- runner repository branch: `codex/layersentry-dr-ha-upgrade` from `adaptgurus/cozystack:ops/layersentry-hyperv-inventory`

Primarily owns the runner/Hyper-V/DR/HA/upgrade proof harness and evidence. It must not build a custom DR controller before native CloudStack recovery is proven.

## Local directory layout

Recommended under WSL:

```text
~/layersentry/
  cloudstack-base/            # integration checkout, do not let agents edit
  agent-a/                    # CloudStack worktree A
  agent-b/                    # CloudStack worktree B
  agent-c/                    # CloudStack worktree C
  agent-d/
    cloudstack/               # CloudStack worktree D/context
    cozystack/                # runner repo worktree D
```

Never run two agents in the same worktree.

## One-time clone/worktree setup

```bash
mkdir -p ~/layersentry
cd ~/layersentry

git clone https://github.com/adaptgurus/cloudstack.git cloudstack-base
cd cloudstack-base
git fetch origin layersentry/4.22.1.1-ui
git switch --detach origin/layersentry/4.22.1.1-ui
BASE=$(git rev-parse HEAD)
printf 'Current LayerSentry integration base: %s\n' "$BASE"

git worktree add ../agent-a -b codex/layersentry-ui-self-service "$BASE"
git worktree add ../agent-b -b codex/layersentry-release-installer "$BASE"
git worktree add ../agent-c -b codex/layersentry-security-validation "$BASE"
mkdir -p ../agent-d
git worktree add ../agent-d/cloudstack -b codex/layersentry-dr-ha-upgrade "$BASE"

cd ~/layersentry
git clone https://github.com/adaptgurus/cozystack.git cozystack-base
cd cozystack-base
git fetch origin ops/layersentry-hyperv-inventory
RUNNER_BASE=$(git rev-parse origin/ops/layersentry-hyperv-inventory)
printf 'Current runner integration base: %s\n' "$RUNNER_BASE"
git worktree add ../agent-d/cozystack -b codex/layersentry-dr-ha-upgrade "$RUNNER_BASE"
```

If any suggested branch already exists, do not force/delete it. Inspect it first and either reuse it if it is the intended current workstream or create a timestamped/suffixed branch.

## Codex startup commands

Open four separate WSL terminals.

Window A:

```bash
cd ~/layersentry/agent-a
codex
```

Window B:

```bash
cd ~/layersentry/agent-b
codex
```

Window C:

```bash
cd ~/layersentry/agent-c
codex
```

Window D:

```bash
cd ~/layersentry/agent-d
codex
```

Window D starts from the common parent so it can inspect both `cloudstack/` and `cozystack/`. Its prompt must explicitly tell it to read `cloudstack/AGENTS.md` and the D workstream context before editing either repository.

## Copy/paste prompt — Window A

```text
You are LayerSentry Codex Workstream A: UI / Self-service.

Before editing anything, read AGENTS.md and every mandatory document it references, then read docs/layersentry/CODEX_MASTER_CONTEXT.md and docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md. Fetch/inspect the actual integration HEAD and compare it with this worktree base. Repository/workflow/live evidence overrides historical context.

Mission: implement the KVM-first LayerSentry product profile, role-aware Platform Admin/Department Admin/User experience, dashboards, and simplified VM/CKS/Bucket/Site workflows by reusing native CloudStack 4.22.1.1 APIs/RBAC/components. Do not modify CloudStack Java backend, DB schema, KVM-agent/core orchestration, installer/release pipeline, or DR runner automation. Do not reintroduce DBaaS/APaaS.

Work only inside Workstream A ownership. Use exact project status labels from AGENTS.md. Never claim a feature healthy/complete without evidence. Run relevant UI/static tests and commit coherent changes. At handoff report exact base/final commit, files changed, tests run/not run, core impact, known limitations, cross-workstream dependencies, and next evidence gate. Do not edit the shared progress ledger.
```

## Copy/paste prompt — Window B

```text
You are LayerSentry Codex Workstream B: Release / Installer / Build.

Before editing anything, read AGENTS.md and every mandatory document it references, then read docs/layersentry/CODEX_MASTER_CONTEXT.md and docs/layersentry/codex/WORKSTREAM_B_RELEASE_INSTALLER.md. Fetch/inspect the actual integration HEAD and compare it with this worktree base. Repository/workflow/live evidence overrides historical context.

Mission: move production UI compilation off CloudStack management nodes; create deterministic CI-built immutable LayerSentry UI artifacts; disable production source maps by default; add release manifest, SBOM, digest/signature verification design, installer artifact verification, fresh/resume parity, idempotent/atomic deployment and rollback; preserve easy future CloudStack upgrades and minimal upstream diff.

Do not redesign dashboards/wizards and do not modify CloudStack Java backend/DB schema/KVM-agent/core orchestration. Never commit signing/private keys. Do not run destructive package/CloudStack upgrades on sen unless explicitly authorized with a durable checkpoint.

Run relevant build/static tests and commit coherent changes. At handoff report exact base/final commit, artifact/provenance behavior, files changed, tests run/not run, runtime mutation, rollback behavior, known limitations, dependencies, and next evidence gate. Do not edit the shared progress ledger.
```

## Copy/paste prompt — Window C

```text
You are LayerSentry Codex Workstream C: Security / Validation.

Before editing anything, read AGENTS.md and every mandatory document it references, then read docs/layersentry/CODEX_MASTER_CONTEXT.md and docs/layersentry/codex/WORKSTREAM_C_SECURITY_VALIDATION.md. Fetch/inspect the actual integration HEAD and compare it with this worktree base. Repository/workflow/live evidence overrides historical context.

Mission: build evidence-driven RBAC/direct-URL negative tests, feature-prerequisite validation, SELinux-enforcing and firewalld validation assets, package/repository-lock validation, KVM snapshot-conflict tests/guard requirements, CKS metadata-isolation and CSI validation, and safe support/evidence tooling.

Do not weaken SELinux/firewall/RBAC to make a test pass. Do not broadly redesign production UI, do not refactor installer/release code owned by B, and do not mutate DR/Hyper-V infrastructure owned by D. Use UNKNOWN/NOT_TESTED when the lab cannot prove something.

Commit coherent test/validation changes. At handoff report exact base/final commit, tests/specs added, tests actually executed, evidence, untestable items, blockers/dependencies, and next evidence gate. Do not edit the shared progress ledger.
```

## Copy/paste prompt — Window D

```text
You are LayerSentry Codex Workstream D: DR / HA / Upgrade.

You are running from a parent directory containing cloudstack/ and cozystack/. Before editing anything, read cloudstack/AGENTS.md and every mandatory document it references, then read cloudstack/docs/layersentry/CODEX_MASTER_CONTEXT.md and cloudstack/docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md. Inspect the actual current integration HEADs in BOTH repositories, latest relevant workflows, and current live state before mutation. Repository/workflow/live evidence overrides historical context.

Mission: create/read-only discovery and safe test automation for the existing Hyper-V/self-hosted-runner lab, then prove native CloudStack two-Zone NAS B&R recovery when the second disposable Rocky 9 VM is available. Later add HA and supported upgrade/resume/rollback test harnesses. Do not build a custom DR controller before native recovery is proven. Do not change CloudStack core to make a test pass.

Every destructive/connectivity-affecting action requires a durable pre-action checkpoint, rollback method, disposable data, and explicit task authorization. Never duplicate an in-flight workflow/backup/recovery/VM create. Physical OOBM/site independence cannot be certified from same-host nested Hyper-V.

Commit coherent automation/evidence changes only in owned scope. At handoff report repository/branch/final commit, workflow run/job/artifact IDs, exact live mutations, test results/timings, failures, rollback state, scope limits, dependencies, and next gate. Do not edit the shared progress ledger.
```

## Integration discipline

The four agents must not merge themselves into `layersentry/4.22.1.1-ui` or the runner integration branch unless the human/lead explicitly assigns integration responsibility.

Recommended integration sequence:

1. review B first because A/C may rely on the new artifact/test foundation;
2. review A customer UI changes;
3. run C against the integrated A/B state and apply narrow safety fixes;
4. run D live validation only after the deployment pipeline/source baseline is stable.

For every merge/cherry-pick, the integration lead must re-fetch upstream integration HEAD, inspect overlap, run relevant tests, and then update `LAYERSENTRY_PROGRESS_LEDGER.md` only after evidence supports the new status.

## Resource/concurrency rule

Do not run four heavy builds simultaneously on the Hyper-V/runner host. Codex reasoning/editing may run in parallel, but serialize or limit CPU/RAM-heavy UI builds, Maven builds, VM operations, storage tests, and live deployments. Workstream D live mutations must be coordinated so A/B/C do not simultaneously modify the same live `sen` environment.

## Anti-refresh rule

If a Codex terminal closes or the Windows host reboots, do not recreate work from memory. Reopen the same worktree, run `git status`, `git rev-parse HEAD`, read AGENTS/master/progress/workstream context, inspect any in-flight remote workflow, and resume from the first unmet evidence gate.
