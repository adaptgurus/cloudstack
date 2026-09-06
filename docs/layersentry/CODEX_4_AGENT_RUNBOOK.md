# LayerSentry V1 — Codex Parallel Workstream Runbook

## Purpose

Operator runbook for parallel LayerSentry Codex workstreams without shared-worktree corruption, duplicate work, false status promotion or conflicting live mutations.

This file historically started as the four-agent A–D runbook. The product now also has Workstream E for LayerSentry-managed K8s/DBaaS/APaaS/Streaming. Existing A–D setup remains valid; E is an additional isolated workstream and does not require unrelated agents to be restarted.

This file contains operational setup/prompts only. It does not duplicate product status.

## Authority/read order

Each Codex window reads:

1. applicable `/AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. its assigned workstream file under `docs/layersentry/codex/`.

Workstream E, and any A/B/C/D task touching that module, additionally reads:

`docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`

Read specialist upgrade/IP, security, debugging or upstream-delta documents only when the workstream needs them.

Never use a SHA in a handoff/runbook instead of fetching the current integration ref.

---

## Workstreams

### A — UI / Self-service

- context: `docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`
- suggested branch: `codex/layersentry-ui-self-service`
- owns customer product profile/navigation/dashboard/wizard/terminology UI and shared UI components.
- coordinates with E for K8s/Data Services presentation; does not own CAPI/RKE2/package lifecycle.

### B — Release / Installer / Build

- context: `docs/layersentry/codex/WORKSTREAM_B_RELEASE_INSTALLER.md`
- suggested branch: `codex/layersentry-release-installer`
- owns CI-built artifacts, build-only settings, installer/resume/rollback, manifest/SBOM/provenance/digest/signature.
- coordinates with E for K8s/Data Services offline release and incremental bundle requirements.

### C — Security / Validation

- context: `docs/layersentry/codex/WORKSTREAM_C_SECURITY_VALIDATION.md`
- suggested branch: `codex/layersentry-security-validation`
- owns RBAC/negative tests, SELinux/firewall/package/update/snapshot/Kubernetes security validation and support/evidence tooling.

### D — DR / HA / Upgrade

- context: `docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`
- suggested CloudStack branch: `codex/layersentry-dr-ha-upgrade`
- suggested runner branch: `codex/layersentry-dr-ha-upgrade`
- owns runner/Hyper-V/DR/HA/upgrade proof automation and evidence.

D must not build a custom DR controller before native CloudStack recovery is proven. Kubernetes/Data Services workload-specific DR hooks integrate with D's global DR authority rather than creating a second framework.

### E — K8s / DBaaS / APaaS / Streaming

- context: `docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`
- mandatory specialist context: `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`
- suggested branch: `codex/layersentry-k8s-data-services`
- owns CAPI/CAPC/CAPRKE2/RKE2, central Flux, module storage/network/VIP/WAF integration, DBaaS/OpenEverest/Redis, APaaS/OpenBao/Harbor, Strimzi/Kafka and GPU worker-pool integration.

E must preserve CloudStack core and must not bypass exact CAPC/CSI/OpenEverest/offline/data-safety qualification gates.

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
  agent-e/                  # CloudStack worktree E
  cozystack-base/           # runner integration reference checkout
```

E may use an additional runner worktree only when its live validation task requires runner changes and those changes are coordinated with D/integration ownership.

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

Runner repository when D or coordinated E live validation is required:

```bash
cd ~/layersentry
git clone https://github.com/adaptgurus/cozystack.git cozystack-base
cd cozystack-base
git fetch --all --tags --prune
# Inspect the actual current LayerSentry integration branch before using it.
git branch -r | grep -i layersentry || true
```

Do not hardcode a stale runner branch from this runbook as current authority.

---

## Worktree creation

Create a workstream branch only after verifying whether the suggested branch/worktree already exists.

Example discovery:

```bash
cd ~/layersentry/cloudstack-base
git worktree list
git branch --list 'codex/layersentry-*'
```

If the intended branches do not exist and the paths are free:

```bash
BASE=$(git rev-parse origin/layersentry/4.22.1.1-ui)

git worktree add ../agent-a -b codex/layersentry-ui-self-service "$BASE"
git worktree add ../agent-b -b codex/layersentry-release-installer "$BASE"
git worktree add ../agent-c -b codex/layersentry-security-validation "$BASE"
mkdir -p ../agent-d
git worktree add ../agent-d/cloudstack -b codex/layersentry-dr-ha-upgrade "$BASE"
git worktree add ../agent-e -b codex/layersentry-k8s-data-services "$BASE"
```

For D runner work, create a runner worktree only after discovering the actual current runner integration ref and ensuring the intended branch/path does not already exist.

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

Window E:

```bash
cd ~/layersentry/agent-e
codex
```

Window D begins at the parent containing both repositories when it needs CloudStack + runner work; its prompt must tell it which `AGENTS.md` applies before editing either repository.

---

## Common startup requirement for every window

Every window must first:

1. read `AGENTS.md`, canonical Super Master Context, progress ledger and assigned workstream;
2. read the dedicated K8s/Data Services master context when the task touches that module;
3. run `git status --short --branch`;
4. fetch/inspect actual integration refs;
5. compare worktree base to current integration HEAD;
6. identify whether newer integration changes need rebasing/cherry-picking before implementation;
7. report scope/files expected to change;
8. proceed only inside its ownership.

Do not load historical re-audit/handoff files unless investigating history.

---

## Copy/paste prompt — A

```text
You are LayerSentry Workstream A: UI / Self-service.

Read AGENTS.md, docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md, docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md, and docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md. Fetch and inspect the actual current integration ref before editing. Repository/workflow/live evidence overrides historical text.

Implement only the KVM-first LayerSentry customer product profile, role-aware Platform Admin/Department Admin/User UX, dashboards, terminology and shared self-service UI using supported CloudStack APIs/RBAC/components. DBaaS/APaaS/K8s/Streaming are valid modules; when touching those surfaces, additionally read LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md and coordinate with Workstream E. Do not implement CAPI/RKE2/operator/package lifecycle in browser code.

Do not change CloudStack Java backend/DB/KVM-agent/core orchestration, release/installer ownership or DR runner automation. Use the governed status/evidence and R0-R4 rules. Run real UI/static tests, commit coherent changes and hand off exact base/final commit, files, core impact, tests, limitations and next gate. Do not edit the shared progress ledger or self-merge.
```

## Copy/paste prompt — B

```text
You are LayerSentry Workstream B: Release / Installer / Build.

Read AGENTS.md, docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md, docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md, docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md, and docs/layersentry/codex/WORKSTREAM_B_RELEASE_INSTALLER.md. Fetch and inspect the actual current integration ref before editing.

Own release/build/installer only. Move production UI compilation off management nodes; build deterministic CI artifacts with production source maps disabled; implement manifest/SBOM/provenance/digest/signature verification and safe fresh/resume/idempotent/atomic deployment/rollback. Preserve minimal upstream delta and CloudStack upgrade semantics. Coordinate with Workstream E for LayerSentry K8s/Data Services offline release and incremental-bundle artifact requirements; do not silently own CAPI/RKE2 lifecycle.

Do not redesign dashboards or modify CloudStack core. Never commit signing/private keys. Use the R0-R4 gates for runtime/package/upgrade actions. Commit coherent source changes and report exact evidence/limitations/next gate. Do not edit the shared ledger or self-merge.
```

## Copy/paste prompt — C

```text
You are LayerSentry Workstream C: Security / Validation.

Read AGENTS.md, docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md, docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md, and docs/layersentry/codex/WORKSTREAM_C_SECURITY_VALIDATION.md. Fetch and inspect the actual current integration ref before editing.

Own evidence-driven RBAC/direct-URL tests, feature-prerequisite validation, SELinux/firewall/package/update controls, KVM snapshot-safety tests, Kubernetes metadata/CSI validation and support/evidence tooling. When testing K8s/Data Services, read the dedicated master context and coordinate exact trust-boundary/data-safety cases with Workstream E. Do not weaken security/test controls to make checks pass. Do not broadly rewrite UI/installer or mutate DR infrastructure.

Use UNKNOWN/NOT_TESTED where evidence is unavailable. Commit coherent test/validation changes and report exact base/final commit, tests actually executed, blockers and next gate. Do not edit the shared ledger or self-merge.
```

## Copy/paste prompt — D

```text
You are LayerSentry Workstream D: DR / HA / Upgrade.

You are in a parent directory containing cloudstack/ and cozystack/. Read cloudstack/AGENTS.md, the canonical Super Master Context, current progress ledger, relevant upgrade/IP policy, and WORKSTREAM_D_DR_HA_UPGRADE.md. Inspect actual current refs in both repositories, current workflows and live state before mutation.

Own read-only discovery and safe runner/Hyper-V/DR/HA/upgrade proof automation. Prove native two-Zone NAS B&R recovery on disposable approved workloads before advanced DR automation. Do not change CloudStack core to make tests pass. K8s/Data Services workload-specific backup/upgrade/DR hooks from E must integrate with the same global DR/fencing truth model rather than creating another one.

Apply the standing disposable-test R0-R4 rules. Never duplicate an in-flight workflow/backup/recovery/VM create after timeout/refresh. Same-host nested Hyper-V cannot certify physical-site independence or hardware fencing.

Commit coherent owned changes and report exact commits, workflow/job/artifact evidence, live mutations, results, timings/limitations and next gate. Do not edit the shared ledger or self-merge.
```

## Copy/paste prompt — E

```text
You are LayerSentry Workstream E: K8s / DBaaS / APaaS / Streaming.

Read AGENTS.md, docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md, docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md, docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md and docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md. Fetch and inspect the actual current LayerSentry integration ref before editing.

Own the LayerSentry-managed CAPI/CAPC/CAPRKE2/RKE2 stack, central Flux package plane, module StorageProfiles, Frontend/VIP/Gateway/WAF providers, DBaaS/OpenEverest/Redis, APaaS/OpenBao/Harbor, Strimzi/Kafka and GPU-pool integration. Preserve CloudStack 4.22.1.1 core and CloudStack authority. Treat CAPC 4.22.1.1 compatibility, CAPC/CSI Machine/PVC safety, CloudStack CSI project resize, OpenEverest air-gap, NVMe/RDMA/GPUDirect and every OEM integration as explicit qualification gates rather than assumptions.

Normal customer flows are GUI-only; managed RKE2 join is automatic; unselected Kubernetes drivers/packages remain absent even if their artifacts exist offline; users can install compatible packages later without reinstalling the ISO. Use exact source/issues/docs plus real destructive/storage/upgrade tests before status promotion. Coordinate shared UI with A, release artifacts with B, security gates with C and DR/upgrade evidence with D.

Commit coherent owned changes and report exact base/final commit, files, CloudStack-core impact, version tuple, checks, runtime evidence, blockers, rollback/recovery state and next gate. Do not edit the shared ledger or self-merge unless assigned integration responsibility.
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

For the established base product, preserve the B -> A -> C -> D ordering where dependency requires it. For the new K8s/Data Services module, integrate E in dependency-aware slices with B/A/C/D rather than treating E as a monolithic final step.

---

## Resource/concurrency rule

Do not run heavyweight builds or live mutations simultaneously on the same Windows/Hyper-V/self-hosted-runner resources when they contend.

Parallel source analysis/editing is fine. Serialize/limit:

- UI/Maven/package/OCI/QCOW2 builds when resource contention matters;
- deployments to the same target;
- VM/Kubernetes/reboot operations on the same target;
- storage/network/VIP tests;
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

Then reread the canonical context + progress ledger + workstream (+ dedicated K8s/Data Services context where applicable), inspect any in-flight remote workflow/live action, and resume from the first unmet evidence gate.

Never claim uncheckpointed work persisted. Inspect source/runtime and classify uncertain state as `UNKNOWN` until proven.
