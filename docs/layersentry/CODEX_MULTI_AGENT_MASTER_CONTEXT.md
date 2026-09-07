# LayerSentry — Legacy Multi-Agent Context

**Status:** `SUPERSEDED_FOR_EXECUTION`

This file is retained only as historical compatibility context. The old parallel A/B/C/D/E Codex execution model is no longer valid for current V1 work.

Do not use this file to launch multiple source writers, recreate B -> A -> C -> D integration ordering, or assign Codex ownership based on historical workstream labels.

Current authority:

1. `/AGENTS.md` — hard file fences, one-writer rules and safety boundaries;
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md` — current activation/ownership/lab shortcuts;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md` — volatile evidence/status;
4. `docs/layersentry/codex/README.md` — current workstream activation index;
5. `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md` — current launcher despite historical filename.

Current lowest-credit model:

- one primary K8s/RKE2 Codex writer;
- optional test-only package qualification lane on a separate working RKE2 cluster;
- UI deferred until backend contracts stabilize;
- Single-OS, DR and bootstrap/hypervisor are separate non-overlapping writers by default;
- release/security work activates only at a concrete milestone/blocker;
- no cross-module source edits.

Historical content remains available through Git history when investigating why a prior decision/commit was made. It is not normal startup context.
