# LayerSentry V1 — Next Chat Handoff: WSL/Codex Setup

## Purpose

This handoff exists so the next ChatGPT/Codex session resumes from the current point without repeating verified work or losing the newly prepared Windows/WSL/Codex workstation state.

Repository/workflow/live evidence overrides every historical SHA or local observation written here.

## Mandatory read order in the next session

Before changing code or infrastructure, read:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md`
4. `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`
5. `docs/layersentry/LAYERSENTRY_UPSTREAM_DIFF.md`
6. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
7. `docs/layersentry/CODEX_MASTER_CONTEXT.md`
8. `docs/layersentry/CODEX_MULTI_AGENT_MASTER_CONTEXT.md`
9. `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md`
10. the assigned workstream file under `docs/layersentry/codex/`.

Then fetch actual current repository HEADs and latest workflow/live state. Never trust the historical HEAD recorded below as current.

## Authoritative repositories

Product source:

- repository: `adaptgurus/cloudstack`
- integration branch: `layersentry/4.22.1.1-ui`
- immutable upstream CloudStack 4.22.1.1 base: `71af23d73741cfeae854d2f1a6d36324307c32c4`

Runner/live lab:

- repository: `adaptgurus/cozystack`
- integration branch: `ops/layersentry-hyperv-inventory`

Historical CloudStack integration HEAD observed immediately before this handoff was created:

`55459c35604b611794e615027779cb9fe6d3e56a`

Do not use that SHA without fetching the branch again.

## Current proven project state

The durable progress ledger is authoritative. Important currently `LIVE_VERIFIED` scope includes LayerSentry branding/customer terminology baseline and V1 DBaaS/APaaS placeholder removal on the lab target `sen`.

Recorded successful placeholder-removal evidence:

- cleaned UI source: `6ce76d6c241629086ffcad794093dbdd5f2dd5ba`
- served repair: `85031bd2e394c16c631b6e493ced1af87c19fbd3`
- workflow run: `33879178031`
- job: `101043343720`
- artifact: `9939463820`
- artifact digest: `sha256:1a308fdcfff5a87348a4dad3783afc4bf24ea4b5efa6a583a6203064b8599813`
- assertions: HTTP 200, `V1_PLACEHOLDERS=ABSENT`, onboarding/logo/runtime config/terminology pass.

Do not redo this work unless current source/runtime evidence proves regression.

## Main remaining LayerSentry work

Still pending/partial/not-tested unless newer evidence proves otherwise:

- CI-built immutable production UI artifact; remove production-side npm builds
- production source-map suppression/support-build strategy
- signed release manifest/artifact/update channel and SBOM
- KVM-only `layersentry-kvm` product profile
- role-aware Platform Admin / Department Admin / User dashboards
- simplified VM / CKS / Bucket / Site onboarding workflows
- prerequisite/provider-aware feature gating
- RBAC/direct-URL negative testing
- KVM snapshot safety guard
- CKS metadata isolation and CSI validation
- Rocky Linux 9 SELinux-enforcing policy and validation
- firewalld-enabled KVM validation
- package/repository lockdown and controlled signed updates
- full air-gap CKS work
- live object-store/Bucket validation
- native NAS B&R proof
- two-Zone functional DR proof and RPO/RTO measurement
- DR source-record retention/purge negative test
- later Test Recovery/failover/failback automation
- later 3-management/2-LB/3-DB HA certification
- N-1 -> N upgrade/rollback/resume evidence
- production release certification.

## Windows / Hyper-V / GitHub runner workstation state

User-observed local state from the current session; verify locally before relying on it:

- Windows Server is the Hyper-V/test-runner host.
- GitHub Actions self-hosted runner service was shown Running.
- Hyper-V VM `sen` was shown Running.
- `sen` is the current CloudStack/LayerSentry lab VM; historical management address is `10.10.10.14`, but re-read live state before mutation.
- WSL has been enabled and Ubuntu 22.04 installed.
- Normal WSL entry command from Windows PowerShell: `wsl -d Ubuntu-22.04`.
- WSL Linux user: `opc`.
- Do not store, repeat, or commit WSL/Windows passwords, tokens, private keys, API keys or other credentials. Any password previously typed in chat is intentionally excluded from this file.

## Codex CLI state

User-observed setup:

- Codex CLI installer completed inside Ubuntu/WSL.
- installer reported Codex CLI version `0.153.2` at that time.
- installer placed the standalone package under `/home/opc/.codex/packages/standalone/releases/...` and added a PATH entry to `/home/opc/.bashrc`.
- immediately after installation, `codex --version` returned `command not found`, which is consistent with the current shell not having reloaded the updated PATH.

First action in the next session should be to verify/fix PATH without reinstalling blindly:

```bash
wsl -d Ubuntu-22.04
source ~/.bashrc
printf '%s\n' "$PATH"
command -v codex || true
ls -la ~/.local/bin ~/.codex 2>/dev/null || true
codex --version
```

If `codex` is still not found, inspect the actual install path and symlink before reinstalling. Do not use `sudo snap install codex` as an automatic fallback merely because Ubuntu suggests it; the ChatGPT Codex installer already reported a successful standalone install and should be diagnosed first.

## Four-Codex-window plan

Do not run four agents in one checkout. Use isolated Git worktrees/branches as defined in:

- `docs/layersentry/CODEX_MULTI_AGENT_MASTER_CONTEXT.md`
- `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md`

Workstreams:

- A — UI / Self-service
- B — Release / Installer / Build
- C — Security / Validation
- D — DR / HA / Upgrade

Recommended WSL layout from the runbook:

```text
~/layersentry/
  cloudstack-base/
  agent-a/
  agent-b/
  agent-c/
  agent-d/
    cloudstack/
    cozystack/
```

Each Codex window must read the master docs and its workstream context, fetch current refs, work only on its owned branch/worktree, make small atomic commits, run real tests, and stop before merging into the shared integration branch.

Do not run four heavy UI/Maven/build/live-deployment jobs concurrently on the same Hyper-V host. Parallel reasoning/editing is fine; serialize CPU/RAM-heavy builds and all live mutations of `sen`.

## Recommended immediate next-chat mission

The next ChatGPT session should first help the user finish and verify the WSL/Codex workstation setup, then create the four isolated Git worktrees and launch the four Codex windows using the repo-resident runbook. It should not start implementing product code until:

1. `codex --version` works in WSL;
2. Git authentication/access for both repositories is verified;
3. the current integration HEADs are fetched;
4. four distinct worktrees/branches are created safely;
5. each window receives only its assigned workstream prompt.

After the four agents are running, this ChatGPT thread should remain the integration/architecture/evidence coordinator. It reviews agent commits, resolves cross-workstream conflicts, validates against CloudStack 4.22.1.x documentation, controls live deployment, and updates the shared progress ledger only after evidence warrants a status change.

## Copy-paste starter for the next ChatGPT chat

```text
Continue LayerSentry from the repository, not memory.

Primary repo: adaptgurus/cloudstack, branch layersentry/4.22.1.1-ui.
Runner repo: adaptgurus/cozystack, branch ops/layersentry-hyperv-inventory.

First fetch the ACTUAL current HEADs; repository/workflow/live evidence overrides every historical SHA.

Read in order:
1. AGENTS.md
2. docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md
3. docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md
4. docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md
5. docs/layersentry/LAYERSENTRY_UPSTREAM_DIFF.md
6. docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md
7. docs/layersentry/CODEX_MASTER_CONTEXT.md
8. docs/layersentry/CODEX_MULTI_AGENT_MASTER_CONTEXT.md
9. docs/layersentry/CODEX_4_AGENT_RUNBOOK.md
10. docs/layersentry/LAYERSENTRY_NEXT_CHAT_HANDOFF_2026-09-04_WSL_CODEX.md

Enforce all anti-hallucination, completion-label, wrong-label, refresh-safe checkpoint, upgradeability and no-core-change rules. Do not redo LIVE_VERIFIED work.

Current workstation context to verify, not assume: Windows Server hosts the GitHub self-hosted runner and Hyper-V VM `sen`; WSL Ubuntu 22.04 is installed; WSL user is `opc`; Codex CLI standalone installer reported success/version 0.153.2 but the same shell then returned `codex: command not found`, likely because ~/.bashrc PATH was not reloaded. Do not reinstall blindly. First run `source ~/.bashrc`, inspect PATH/install locations, and make `codex --version` work.

My immediate goal is to prepare four safe parallel Codex windows/worktrees exactly as the repo runbook specifies, then use this ChatGPT session as the integration/architecture/evidence coordinator. Guide me command-by-command. Do not expose or store passwords or secrets.
```
