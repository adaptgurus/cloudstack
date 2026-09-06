# LayerSentry V1 — Historical WSL/Codex Handoff (2026-09-04)

> **Status: SUPERSEDED / ARCHIVAL.** This file captured one workstation/session handoff during initial WSL/Codex setup. Do not use its historical SHAs, read order or workstation observations as current project state.

Current startup authority is:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. assigned workstream file under `docs/layersentry/codex/`

For four-agent WSL operation, use:

`docs/layersentry/CODEX_4_AGENT_RUNBOOK.md`

For current repository/workflow/live state, fetch/inspect the actual sources rather than this historical handoff.

## Historical workstation observation preserved for troubleshooting only

At the time this handoff was written:

- WSL Ubuntu 22.04 had been installed;
- the observed WSL Linux user was `opc`;
- the Codex standalone installer reported a successful installation and version `0.153.2` at that moment;
- the immediately following shell returned `codex: command not found`, consistent with PATH/`.bashrc` not yet being reloaded or the installed path needing inspection.

If the same symptom still exists, diagnose the current installation rather than reinstalling blindly:

```bash
source ~/.bashrc
printf '%s\n' "$PATH"
command -v codex || true
ls -la ~/.local/bin ~/.codex 2>/dev/null || true
codex --version
```

Do not use `sudo snap install codex` or another unrelated package as an automatic fallback simply because the shell suggests it. Inspect the current Codex installation and current official setup path first.

Do not store passwords, tokens, API keys or private keys in handoff/context files.

## Historical project note

This handoff was created after the LayerSentry V1 DBaaS/APaaS placeholder-removal work had been live-verified. The exact current evidence and all subsequent work are maintained in `LAYERSENTRY_PROGRESS_LEDGER.md`; they are intentionally not copied here.

Git history preserves the original full handoff if audit reconstruction is ever required.
