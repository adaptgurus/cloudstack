# LayerSentry — Legacy Codex Master Context

**Status:** `SUPERSEDED_FOR_EXECUTION`

This filename is retained only for compatibility with old prompts/bookmarks. It is **not** current execution authority and must not be used to start historical parallel Codex workstreams.

Current startup:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`
3. `docs/layersentry/LAYERSENTRY_CURRENT_STATUS.md`
4. exactly one assigned workstream/module-status pointer
5. actual current source/workflow/live state

Current Codex launcher:

`docs/layersentry/LAYERSENTRY_CODEX_EXECUTION_RUNBOOK.md`

Current workstream activation index:

`docs/layersentry/codex/README.md`

Do not load the full historical Progress Ledger, old multi-agent contexts or historical handoffs by default.

Key current decisions:

- one standing Codex source writer: RKE2/Kubernetes Workstream E;
- UI is a deferred bounded final pass;
- B/C are milestone/concrete-defect gated;
- D/F/bootstrap are separate non-overlapping streams by default;
- one RKE2 lifecycle serves user K8s, DBaaS, APaaS and Streaming;
- OpenEverest/OpenBao/Harbor/Strimzi are upstream integration targets;
- V1 uses one logical signed `layersentry-platform-<release>.iso` carrier;
- hard module file fences and writer-collision detection prevent cross-module drift.

Historical detail formerly stored in this file remains available in Git history. Do not resurrect old execution routing, two-bundle assumptions or multi-agent integration ordering.