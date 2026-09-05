# LayerSentry V1 — Four-Agent Codex Runbook

## Purpose

Operator runbook for four parallel LayerSentry Codex workstreams without shared-worktree corruption, duplicate work, false status promotion or conflicting live mutations.

This file contains operational setup/prompts only. It does not duplicate product status.

## Authority/read order

Each Codex window reads:

1. applicable `/AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. its assigned workstream file under `docs/layersentry/codex/`.

Read specialist upgrade/IP or upstream-delta documents only when the workstream needs them.

Never use a SHA in a handoff/runbook instead of fetching the current integration ref.

---

## Workstreams

### A — UI / Self-service

- context: `docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`
- suggested branch: `codex/layersentry-ui-self-service`
- owns customer product profile/navigation/dashboard/wizard/terminology UI.

### B — Release / Installer / Build

- context: `docs/layersentry/codex/WORKSTREAM_B_RELEASE_INSTALLER.md`
- suggested branch: `codex/layersentry-release-installer`
- owns CI-built artifacts, build-only settings, installer/resume/rollback, manifest/SBOM/provenance/digest/signature.

### C — Security / Validation

- context: `docs/layersentry/codex/WORKSTREAM_C_SECURITY_VALIDATION.md`
- suggested branch: `codex/layersentry-security-validation`
- owns RBAC/negative tests, SELinux/firewall/package/update/snapshot/CKS security validation and support/evidence tooling.

### D — DR / HA / Upgrade

- context: `docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`
- suggested CloudStack branch: `codex/layersentry-dr-ha-upgrade`
- suggested runner branch: `codex/layersentry-dr-ha-upgrade`
- owns runner/Hyper-V/DR/HA/upgrade proof automation and evidence.

D must not build a custom DR controller before native CloudStack recovery is proven.

---

## WSL prerequisite verification

Before creating worktrees, make the base tooling work in the current WSL shell:

```bash
source ~/.bashrc
whoami
pwd
command -v codex
codex --version
git --version
gh --version || true
gh auth status || true
ssh -V
```

If Codex was installed but `command -v codex` fails, inspect PATH and the existing installation before reinstalling. Do not install a random package merely because the shell suggests one.

Never paste passwords/tokens/private keys into repository files or Codex prompts.

---

## Recommended local layout

```text
~/layersentry/
  cloudstack-base/          # integration reference checkout; agents do not edit
  agent-a/                  # CloudStack worktree A
  agent-b/                  # CloudStack worktree B
  agent-c/                  # CloudStack worktree C
  agent-d/
    cloudstack/             # CloudStack worktree D
    cozystack/              # runner worktree D
  cozystack-base/           # runner integration reference checkout
```

Never run two writing agents in the same worktree.

---

## Base clone/fetch

For a fresh local setup:

```bash
mkdir -p ~/layersentry
cd ~/layersentry

git clone https://github.com/adaptgurus/cloudstack.git cloudstack-base
cd cloudstack-base
git fetch --all --tags --prune
git fetch origin layersentry/4.22.1.1-ui
BASE=$(git rev-parse origin/layersentry/4.22.1.1-ui)
printf 'CloudStack integration base: %s\n' "$BASE"

git status --short --branch
```

If `cloudstack-base` already exists, do **not** reclone or reset it blindly. Inspect its remotes/status and fetch the current ref.

Runner repository when D is required:

```bash
cd ~/layersentry
git clone https://github.com/adaptgurus/cozystack.git cozystack-base
cd cozystack-base
git fetch --all --tags --prune
git fetch origin ops/layersentry-hyperv-inventory
RUNNER_BASE=$(git rev-parse origin/ops/layersentry-hyperv-inventory)
printf 'Runner integration base: %s\n' "$RUNNER_BASE"
```

Again, reuse/inspect an existing clone instead of deleting it.

---

## Worktree creation

Create a workstream branch only after verifying whether the suggested branch/worktree already exists.

Example discovery:

```bash
cd ~/layersentry/cloudstack-base
git worktree list
git branch --list 'codex/layersentry-*'
```

If the intended branch does not exist and the path is free:

```bash
BASE=$(git rev-parse origin/layersentry/4.22.1.1-ui)

git worktree add ../agent-a -b codex/layersentry-ui-self-service "$BASE"
git worktree add ../agent-b -b codex/layersentry-release-installer "$BASE"
git worktree add ../agent-c -b codex/layersentry-security-validation "$BASE"
mkdir -p ../agent-d
git worktree add ../agent-d/cloudstack -b codex/layersentry-dr-ha-upgrade "$BASE"
```

For D runner work:

```bash
cd ~/layersentry/cozystack-base
RUNNER_BASE=$(git rev-parse origin/ops/layersentry-hyperv-inventory)
mkdir -p ~/layersentry/agent-d
git worktree add ~/layersentry/agent-d/cozystack -b codex/layersentry-dr-ha-upgrade "$RUNNER_BASE"
```

If any branch/path already exists, stop and inspect it. Reuse it only if it is the intended current workstream; otherwise create a clearly suffixed new branch. Never force-delete a branch/worktree just to make these commands pass.

---

## Start Codex windows

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

Window D begins at the parent containing both repositories; its prompt must tell it which `AGENTS.md` applies before editing either repository.

---

## Common startup requirement for every window

Every window must first:

1. read `AGENTS.md`, canonical Super Master Context, progress ledger and assigned workstream;
2. run `git status --short --branch`;
3. fetch/inspect actual integration refs;
4. compare worktree base to current integration HEAD;
5. identify whether newer integration changes need rebasing/cherry-picking before implementation;
6. report scope/files expected to change;
7. proceed only inside its ownership.

Do not load historical re-audit/handoff files unless investigating history.

---

## Copy/paste prompt — A

```text
You are LayerSentry Workstream A: UI / Self-service.

Read AGENTS.md, docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md, docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md, and docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md. Fetch and inspect the actual current integration ref before editing. Repository/workflow/live evidence overrides historical text.

Implement only the KVM-first LayerSentry customer product profile, role-aware Platform Admin/Department Admin/User UX, dashboards, terminology and simplified VM/CKS/Bucket/Site workflows using supported CloudStack APIs/RBAC/components. Do not change CloudStack Java backend/DB/KVM-agent/core orchestration, release/installer ownership or DR runner automation. Do not recreate DBaaS/APaaS.

Use the governed status/evidence and R0-R4 rules. Run real UI/static tests, commit coherent changes and hand off exact base/final commit, files, core impact, tests, limitations and next gate. Do not edit the shared progress ledger or self-merge.
```

## Copy/paste prompt — B

```text
You are LayerSentry Workstream B: Release / Installer / Build.

Read AGENTS.md, docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md, docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md, docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md, and docs/layersentry/codex/WORKSTREAM_B_RELEASE_INSTALLER.md. Fetch and inspect the actual current integration ref before editing.

Own release/build/installer only. Move production UI compilation off management nodes; build deterministic CI artifacts with production source maps disabled; implement manifest/SBOM/provenance/digest/signature verification and safe fresh/resume/idempotent/atomic deployment/rollback. Preserve minimal upstream delta and CloudStack upgrade semantics.

Do not redesign dashboards or modify CloudStack core. Never commit signing/private keys. Use the R0-R4 gates for runtime/package/upgrade actions. Commit coherent source changes and report exact evidence/limitations/next gate. Do not edit the shared ledger or self-merge.
```

## Copy/paste prompt — C

```text
You are LayerSentry Workstream C: Security / Validation.

Read AGENTS.md, docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md, docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md, and docs/layersentry/codex/WORKSTREAM_C_SECURITY_VALIDATION.md. Fetch and inspect the actual current integration ref before editing.

Own evidence-driven RBAC/direct-URL tests, feature-prerequisite validation, SELinux/firewall/package/update controls, KVM snapshot-safety tests, CKS metadata-isolation/CSI validation and support/evidence tooling. Do not weaken security/test controls to make checks pass. Do not broadly rewrite UI/installer or mutate DR infrastructure.

Use UNKNOWN/NOT_TESTED where evidence is unavailable. Commit coherent test/validation changes and report exact base/final commit, tests actually executed, blockers and next gate. Do not edit the shared ledger or self-merge.
```

## Copy/paste prompt — D

```text
You are LayerSentry Workstream D: DR / HA / Upgrade.

You are in a parent directory containing cloudstack/ and cozystack/. Read cloudstack/AGENTS.md, the canonical Super Master Context, current progress ledger, relevant upgrade/IP policy, and WORKSTREAM_D_DR_HA_UPGRADE.md. Inspect actual current refs in both repositories, current workflows and live state before mutation.

Own read-only discovery and safe runner/Hyper-V/DR/HA/upgrade proof automation. Prove native two-Zone NAS B&R recovery on disposable approved workloads before advanced DR automation. Do not change CloudStack core to make tests pass.

Every R3/R4 action requires exact-target verification, durable pre-action checkpoint, rollback/recovery plan, task authorization and immediate evidence. Never duplicate an in-flight workflow/backup/recovery/VM create after timeout/refresh. Same-host nested Hyper-V cannot certify physical-site independence or hardware fencing.

Commit coherent owned changes and report exact commits, workflow/job/artifact evidence, live mutations, results, timings/limitations and next gate. Do not edit the shared ledger or self-merge.
```

---

## Integration discipline

Agents stop at reviewable branches.

Integration lead:

1. fetches current integration HEAD;
2. inspects each agent diff and file ownership overlap;
3. rejects unexplained CloudStack-core changes;
4. integrates/cherry-picks one coherent branch at a time;
5. runs combined relevant tests;
6. deploys only reviewed exact artifacts;
7. updates `LAYERSENTRY_PROGRESS_LEDGER.md` only after evidence changes status.

Default dependency order: **B -> A -> C -> D**. Independent non-overlapping changes may be integrated differently when documented.

---

## Resource/concurrency rule

Do not run four heavyweight builds or live mutations simultaneously on the same Windows/Hyper-V/self-hosted-runner resources.

Parallel source analysis/editing is fine. Serialize/limit:

- UI/Maven/package builds when resource contention matters;
- deployments to the same target;
- VM/reboot operations;
- storage/network tests;
- backup/recovery/DR actions;
- upgrade/HA failure tests.

---

## Recovery after terminal/host/session loss

Do not recreate work from memory.

For each affected worktree:

```bash
git status --short --branch
git rev-parse HEAD
git log -5 --oneline --decorate
```

Then reread the canonical context + progress ledger + workstream, inspect any in-flight remote workflow/live action, and resume from the first unmet evidence gate.

Never claim uncheckpointed work persisted. Inspect source/runtime and classify uncertain state as `UNKNOWN` until proven.
