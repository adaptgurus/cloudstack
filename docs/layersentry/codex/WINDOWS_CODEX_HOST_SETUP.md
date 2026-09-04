# LayerSentry — Windows Codex Host Setup

## Goal

Use the existing Windows Hyper-V/GitHub-runner host as the Codex development/control machine while keeping the Rocky Linux CloudStack VM (`sen`) as a deployment/test target, not as the development workstation.

Do not install ChatGPT/Codex, IDEs, or new build toolchains inside the production-style CloudStack VM just to run agents. The long-term LayerSentry direction is the opposite: production management nodes should receive immutable built artifacts, not development dependencies.

## Existing host components to preserve

The current runner workflows already depend on and have successfully used:

- Windows x64 self-hosted GitHub Actions runner
- Hyper-V PowerShell module
- Git for Windows
- OpenSSH/`ssh.exe` and `ssh-keygen.exe`
- PowerShell

Do not reinstall or replace these unless diagnostics prove a problem. Do not change the GitHub Actions runner service account/permissions casually because current Hyper-V automation depends on them.

## Recommended Codex setup

Preferred interactive client:

- current ChatGPT desktop app for Windows with Codex mode

Recommended Linux developer environment:

- WSL2
- Ubuntu 22.04 LTS as a conservative builder environment for the legacy CloudStack 4.22 UI toolchain

WSL is recommended because this repository contains Bash/Linux installers and the current UI toolchain is Linux-oriented. If WSL enablement requires a Windows reboot, schedule it because rebooting the Hyper-V host interrupts the lab VM and GitHub runner.

Check before changing anything:

```powershell
wsl --status
wsl --list --verbose
Get-Service actions.runner* -ErrorAction SilentlyContinue
Get-VM | Format-Table Name,State,MemoryAssigned
```

If WSL is not installed, install it only during an approved maintenance window. Example on a supported Windows build:

```powershell
wsl --install -d Ubuntu-22.04
```

A reboot may be required.

## WSL developer packages

Inside the Ubuntu WSL distribution:

```bash
sudo apt update
sudo apt install -y \
  git curl ca-certificates jq python3 python3-venv \
  rsync tar gzip unzip make g++ openssh-client
```

Optional developer tools:

- GitHub CLI (`gh`) for authenticated push/PR workflows
- VS Code with WSL integration
- Java 17 + Maven only if a workstream genuinely needs CloudStack Java build/test coverage

Do not install Java/Maven merely because CloudStack is a Java project when the assigned workstream touches UI/docs/scripts only.

## UI build runtime

The current lab has proven the CloudStack 4.22 UI with Node.js 16.20.2 and npm 8.19.4, but Node 16 is EOL. Treat it as a build-only compatibility toolchain.

Do not install Node 16 system-wide on the Windows host or rely on it on production management servers.

For temporary WSL development, use an isolated version manager or equivalent and pin the exact version. Workstream B should replace this ad-hoc setup with a deterministic CI builder/artifact pipeline.

## Repository layout

Recommended WSL layout:

```text
~/layersentry/
  cloudstack/
  cozystack/
  worktrees/
    cloudstack-ui/
    cloudstack-release/
    cloudstack-security/
    cloudstack-dr/
    cozystack-dr/
```

Initial clone:

```bash
mkdir -p ~/layersentry/worktrees
cd ~/layersentry

git clone https://github.com/adaptgurus/cloudstack.git
git -C cloudstack fetch origin
git -C cloudstack switch layersentry/4.22.1.1-ui

git clone https://github.com/adaptgurus/cozystack.git
git -C cozystack fetch origin
git -C cozystack switch ops/layersentry-hyperv-inventory
```

Authenticate Git pushes using GitHub's normal credential flow/`gh auth login`; never paste PATs or passwords into Codex prompts or committed files.

## Manual worktrees if not using Codex built-in worktrees

From `~/layersentry/cloudstack`:

```bash
git fetch origin

git worktree add ../worktrees/cloudstack-ui \
  -b codex/layersentry-ui-self-service \
  origin/layersentry/4.22.1.1-ui

git worktree add ../worktrees/cloudstack-release \
  -b codex/layersentry-release-installer \
  origin/layersentry/4.22.1.1-ui

git worktree add ../worktrees/cloudstack-security \
  -b codex/layersentry-security-validation \
  origin/layersentry/4.22.1.1-ui

git worktree add ../worktrees/cloudstack-dr \
  -b codex/layersentry-dr-ha-upgrade \
  origin/layersentry/4.22.1.1-ui
```

From `~/layersentry/cozystack` for Workstream D:

```bash
git fetch origin

git worktree add ../worktrees/cozystack-dr \
  -b codex/layersentry-dr-ha-upgrade \
  origin/ops/layersentry-hyperv-inventory
```

If the Codex Windows app creates isolated worktrees itself, prefer its built-in worktree flow and do not create duplicate manual worktrees unnecessarily.

## How to open the four Codex agents

Recommended: one Codex project with four separate agent threads, each attached to its own isolated worktree. Four separate application windows are optional, not required.

- A opens `cloudstack-ui`
- B opens `cloudstack-release`
- C opens `cloudstack-security`
- D opens `cozystack-dr` and uses `cloudstack-dr` for CloudStack context/changes when required

Copy the first-task prompts from `docs/layersentry/codex/README.md`.

## Resource guard

Do not run four heavy builds simultaneously just because four agents are active. Agent reasoning is remote, but build/test commands execute locally.

The current lab CloudStack VM consumes a large share of the Hyper-V host's memory. Check host free RAM/CPU before WSL setup and before parallel builds. A safe pattern is:

- all four agents may inspect/edit in parallel;
- at most one or two heavy UI/Java builds at a time depending on measured free memory;
- serialize destructive/live deployment workflows;
- only one agent/integration lead mutates the `sen` runtime at a time.

## Network and runtime access model

Codex works on local repository worktrees. GitHub Actions remains the preferred controlled path for Hyper-V/live `sen` deployment and evidence capture.

Do not give all four agents unrestricted root access to `sen`.

Recommended flow:

```text
Codex worktree -> branch/commit -> review/integration -> GitHub workflow -> ephemeral SSH -> sen -> evidence artifact
```

This keeps development parallel while runtime mutation remains serialized and auditable.

## What not to install on `sen`

Do not add development software to `sen` just to support Codex:

- ChatGPT/Codex desktop/CLI
- VS Code
- arbitrary npm/Node toolchains for future production flow
- Docker Desktop
- unrelated developer packages

The present Node/npm tooling on the lab target is historical/temporary. Workstream B should remove production dependence on it by deploying CI-built artifacts.

## First-day readiness checks

Before starting the four agents, confirm:

```text
Windows host:
- GitHub runner service healthy
- Hyper-V VM `sen` healthy
- sufficient free RAM/disk
- Git works
- Codex app or CLI sign-in works
- WSL available if chosen

CloudStack repo:
- current integration branch fetched
- root AGENTS.md visible
- CODEX_MASTER_CONTEXT.md visible
- four workstream files visible

Runner repo:
- current `ops/layersentry-hyperv-inventory` fetched
- no unknown in-flight destructive workflow
```

Do not start live DR/HA mutation until Workstream D completes read-only discovery and the second disposable Rocky Linux 9 VM is available.
