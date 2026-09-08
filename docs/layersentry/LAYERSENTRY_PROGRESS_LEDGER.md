# LayerSentry V1 — Historical Progress Ledger Index

**Role:** durable historical/evidence journal index.  
**Not mandatory startup context.**

Current startup/status authority is:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_CURRENT_STATUS.md`;
4. assigned module workstream/status;
5. actual Git/workflow/live evidence.

## 1. Why this file was compacted

The previous ledger had grown to approximately 51 KB and mixed current orientation with many historical K8s/UI/DR/release checkpoints. Requiring every UI, Single-OS, DR, bootstrap or K8s session to load that history wasted context and created stale routing/read-order ambiguity.

The full pre-compaction ledger remains permanently recoverable from Git history, including blob:

`e9f5c22b6c8619be57092e053df493ff0abed294`

and its ancestor commits. Durable dated evidence under `docs/layersentry/evidence/**` remains unchanged.

No historical evidence was promoted, deleted from Git history or converted into a stronger runtime claim by this compaction.

## 2. Current versus historical state

Use `LAYERSENTRY_CURRENT_STATUS.md` for the compact current module summary and first unmet gates.

Use module-specific current pointers where available, for example:

- K8s: `tools/layersentry/k8s/release-candidate-lane-b.json`;
- Single-OS: `docs/layersentry/evidence/single-os/CURRENT_STATUS.md`;
- DR: current Workstream D + DR evidence;
- Bootstrap/Hypervisor: current bootstrap/hypervisor evidence files;
- UI: current Workstream A + exact UI evidence when finalization is activated.

Use this ledger's Git history or dated evidence files only when older provenance, workflow IDs, previous failures or last-known-good/first-known-bad analysis is actually required.

## 3. Evidence retention rule

Meaningful implementation/runtime evidence belongs in a focused dated artifact under:

`docs/layersentry/evidence/<module>/...`

A module-specific CURRENT_STATUS/release manifest points to the latest durable evidence. The global `LAYERSENTRY_CURRENT_STATUS.md` summarizes only material current state and first unmet gates.

Do not append long logs, complete CI output or repeated architecture text here.

## 4. Historical checkpoint preservation

The former ledger contains important historical checkpoints including:

- K8s CAPI/CAPC/CAPRKE2/CCM/CSI/NodeDiskSet/controller source evidence;
- native DR inventory/recovery-adapter evidence;
- release/UI/security foundation evidence;
- earlier governance/context-normalization evidence;
- historical live UI deployment/placeholder-removal evidence;
- production source-governance observations.

Those records remain available in Git history and their referenced evidence files. They are not current execution routing.

## 5. Recovery after refresh/reconnect/new chat

Do **not** reread the old full ledger by default.

Resume with:

```text
AGENTS.md
 -> LAYERSENTRY_EXECUTION_CONTRACT.md
 -> LAYERSENTRY_CURRENT_STATUS.md
 -> assigned workstream/module status
 -> fetch actual branch/workflow/live state
 -> resume first unmet gate
```

If a prior action may still be running, inspect its authoritative job/resource state before retry.

## 6. Maintenance rule

This file should remain compact. New milestone detail goes to focused evidence/module status, not back into an ever-growing mandatory journal.

When an older historical fact is needed, use Git history/evidence rather than copying the entire old ledger back into startup context.