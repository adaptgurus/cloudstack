# LayerSentry — Legacy Codex Master Context

**Status:** `SUPERSEDED_FOR_EXECUTION`

This filename is retained only for compatibility with old prompts/bookmarks. It is **not** current execution authority and must not be used to start A/B/C/D/E parallel Codex workstreams.

Current execution order is:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. exactly one active workstream file
5. actual current source/workflow/live state

Current workstream activation is indexed in `docs/layersentry/codex/README.md` and the current Codex launcher is `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md` despite its historical filename.

Key current decisions:

- one standing Codex source writer: RKE2/Kubernetes Workstream E;
- UI Workstream A is a deferred bounded final pass;
- B/C are milestone/concrete-defect gated, not standing Codex streams;
- D and F are ChatGPT-led by default unless explicitly reassigned;
- one RKE2 lifecycle serves user K8s, DBaaS, APaaS and Streaming;
- OpenEverest/OpenBao/Harbor/Strimzi are upstream integration targets, not rewrite projects;
- current V1 uses one logical signed `layersentry-platform-<release>.iso` carrier;
- hard module file fences in `AGENTS.md` prohibit cross-module edits.

Historical detail formerly stored in this file remains available in Git history. Do not copy old execution routing, two-bundle packaging assumptions or multi-agent integration ordering from historical revisions into current work.
