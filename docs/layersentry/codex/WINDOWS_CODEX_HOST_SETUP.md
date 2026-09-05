# LayerSentry — Windows / WSL Codex Host Setup

## Purpose

Use a Windows/Hyper-V workstation plus WSL as the LayerSentry engineering/control environment while keeping CloudStack/LayerSentry lab or production-style VMs as deployment/test targets rather than development workstations.

This is a **setup runbook**, not current inventory. Verify every host/VM/runner observation locally before relying on it.

For the canonical four-agent layout and prompts, use:

`docs/layersentry/CODEX_4_AGENT_RUNBOOK.md`

## Design principles

- Keep Git/Codex/build tools in the engineering workstation/CI environment, not on production management nodes.
- Production LayerSentry management nodes should ultimately consume verified CI-built artifacts.
- Preserve a working self-hosted GitHub runner/Hyper-V configuration unless diagnostics and the current task justify a change.
- Never put passwords, PATs, API keys or private keys in prompts, shell history examples or repository files.
- Treat workstation/runner reconfiguration that can interrupt VMs/workflows as R3 under the canonical risk model.

## Verify Windows state first

From an elevated PowerShell only when privileges are needed:

```powershell
wsl --status
wsl --list --verbose
Get-Service actions.runner* -ErrorAction SilentlyContinue
Get-VM | Format-Table Name,State,MemoryAssigned
Get-Volume | Format-Table DriveLetter,FileSystemLabel,SizeRemaining,Size
```

Do not assume a reboot is harmless. WSL/Windows feature changes or host reboots can interrupt Hyper-V guests and self-hosted workflows; plan them as controlled maintenance.

## WSL recommendation

Use WSL2 with a supported Ubuntu distribution suitable for the repository tooling. If Ubuntu 22.04 is already installed and functioning, there is no reason to reinstall it merely to start Codex.

Example installation only when WSL is genuinely absent and the maintenance impact is accepted:

```powershell
wsl --install -d Ubuntu-22.04
```

After entering WSL, verify the existing environment before installing packages:

```bash
whoami
uname -a
printf '%s\n' "$PATH"
command -v git || true
command -v codex || true
command -v gh || true
df -h ~
```

## Codex CLI troubleshooting

If a Codex installer previously reported success but `codex` is not found, diagnose PATH/install locations before reinstalling:

```bash
source ~/.bashrc
command -v codex || true
find ~/.codex ~/.local/bin -maxdepth 4 -type f -name 'codex' -o -type l -name 'codex' 2>/dev/null
codex --version || true
```

Do not install an unrelated package simply because the shell suggests a similarly named command. Use the current official Codex installation path/instructions when a reinstall is actually necessary.

## Base WSL tooling

Install only missing tools needed by the assigned workstream. A typical baseline is:

```bash
sudo apt update
sudo apt install -y \
  git curl ca-certificates jq python3 python3-venv \
  rsync tar gzip unzip make g++ openssh-client
```

Optional by workstream:

- GitHub CLI (`gh`) for authenticated GitHub workflow/PR tasks;
- VS Code with WSL integration;
- Java 17/Maven only when Java build/test work is actually required;
- a pinned isolated Node/npm environment only for local UI compatibility testing until Workstream B provides the controlled CI builder.

Do not install development dependencies on LayerSentry management/KVM appliances just to make Codex convenient.

## Repository location

Prefer the WSL Linux filesystem for Linux-heavy CloudStack/UI/scripts work, e.g.:

```text
~/layersentry/
```

Avoid making `/mnt/c/...` the default build location unless a Windows-side tool specifically requires it, because filesystem semantics/performance can differ.

## Authentication

Use normal GitHub credential/SSH/`gh auth login` mechanisms appropriate to the user's account and repository access.

Never paste a PAT/password/private key into Codex prompts or commit it. If a credential is exposed, rotate it rather than only redacting future output.

Before branch/worktree setup verify access non-destructively:

```bash
git ls-remote https://github.com/adaptgurus/cloudstack.git HEAD
git ls-remote https://github.com/adaptgurus/cozystack.git HEAD
```

For authenticated push capability, verify through the configured Git/GitHub credential path rather than embedding credentials in URLs.

## Worktrees and parallel Codex

Do not reproduce the worktree commands here; use the canonical `CODEX_4_AGENT_RUNBOOK.md` so there is one operator source of truth.

The invariant is:

- one writable worktree per Codex writing agent;
- one branch per worktree;
- actual current integration refs fetched first;
- no self-merging into integration branches;
- integration/lead controls combined tests and live mutation.

## Resource/concurrency guard

Before heavy parallel work, measure free Windows/WSL/runner resources rather than relying on historical VM sizing.

Safe policy:

- all agents may inspect/edit in parallel;
- limit heavy UI/Maven/package builds based on measured CPU/RAM/disk;
- serialize deployments to the same target;
- serialize VM/network/storage/backup/DR/upgrade operations;
- only one coordinated lead/workstream owns a given live mutation at a time.

## Runtime access model

Preferred flow:

```text
Codex worktree
  -> branch/commit
  -> review/integration
  -> controlled CI/GitHub workflow
  -> short-lived authenticated remote access
  -> LayerSentry lab/staging target
  -> immutable evidence artifact
```

Do not give every parallel agent unrestricted direct root access to the same target.

## Readiness checklist

Before launching multiple agents, verify current state rather than assuming names/IPs/versions:

```text
Windows/WSL:
- WSL launches successfully
- Codex CLI/app authentication works
- Git/GitHub access works
- enough CPU/RAM/disk exists for planned work
- self-hosted runner/Hyper-V state is understood if those resources will be used

CloudStack repo:
- current integration ref fetched
- root AGENTS.md visible
- canonical Super Master Context visible
- current progress ledger visible
- workstream files visible

Runner repo (when D is used):
- current integration ref fetched
- no unknown in-flight destructive workflow
```

Then follow `CODEX_4_AGENT_RUNBOOK.md` rather than improvising a second branch/worktree layout.
