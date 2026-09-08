# LayerSentry — Workstream Index

Execution authority: `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`.

Current Codex launcher: `docs/layersentry/LAYERSENTRY_CODEX_EXECUTION_RUNBOOK.md`.

## Minimal startup

1. `/AGENTS.md`
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`
3. `LAYERSENTRY_CURRENT_STATUS.md`
4. assigned workstream/module status
5. actual source/workflow/live state

The full Progress Ledger, specialist masters, Knowledge Graph and historical handoffs are on-demand only.

## Current activation

| Workstream | Default state |
| --- | --- |
| A — UI / Self-Service | **DEFERRED**; one bounded final Codex integration/browser pass after backend contracts stabilize |
| B — Release / Installer | milestone-gated only |
| C — Security / Validation | milestone/concrete-defect gated only |
| D — DC/DR | ChatGPT by default; native CloudStack recovery first |
| E — RKE2 / Kubernetes / Data Services | **ACTIVE PRIMARY CODEX WRITER** |
| F — VM-native Single-OS | ChatGPT by default; Go + Ansible; manual disposable-VM reset allowed for lab cleanup |
| Bootstrap/Hypervisor | ChatGPT by default when its lab is available |

Do not restart the historical broad multi-agent Codex model.

## Primary K8s rule

One source writer only. Work the first failing gate in Workstream E/current release candidate. A separately supplied healthy RKE2 cluster may run a test-only package lane for Flux/OpenEverest/OpenBao/Harbor/Strimzi but does not write lifecycle source or certify the full LayerSentry-created cluster path.

Use `tools/layersentry/governance/module-writer-guard.sh` from normal Git worktrees to detect same-module remote changes between meaningful batches.

## UI rule

Do not keep an active UI Codex session while backend contracts move. Activate one final pass when real backend contracts are ready for integration/browser acceptance.

## File fences / handoff

Obey `AGENTS.md` hard file fences. Foreign-module defects are handed to their owners.

Handoff only exact commit/artifact, tests/live actions, current gate, blocker/root cause and next exact action. Do not create another master context unless architecture materially changes.