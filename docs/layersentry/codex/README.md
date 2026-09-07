# LayerSentry — Workstream Index

Execution authority: `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`.

## Minimal startup

1. `/AGENTS.md`
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`
3. `LAYERSENTRY_PROGRESS_LEDGER.md`
4. one assigned specialist context/workstream
5. actual source/workflow/live state

Do not load every workstream or historical handoff.

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

Do not restart the old broad multi-agent model.

## Workstream E

One source writer only.

```text
existing K8s source
 -> immutable artifacts
 -> controller deployment
 -> one real RKE2 cluster
 -> automatic join + 6443/9345
 -> one CNI
 -> CCM
 -> one safe CSI path
 -> Flux
 -> status/scale/replacement/delete/upgrade/air-gap
 -> upstream service package qualification
```

User K8s, DBaaS, APaaS and Streaming reuse the same RKE2 lifecycle.

Use OpenEverest/OpenBao/Harbor/Strimzi as upstream products. Do not write replacements.

A separately provided healthy RKE2 cluster may run a **test-only package lane** for Flux/OpenEverest/OpenBao/Harbor/Strimzi while the primary writer fixes CAPI/CAPC/CAPRKE2. That test lane does not write cluster lifecycle source.

## Workstream A

Do not keep an active UI Codex session while backend contracts move. Activate one final pass when backends are ready enough to validate the existing portal.

## File fences

Each workstream obeys the hard writable-path fence in `AGENTS.md`. A foreign-module defect is handed to its owner; it is not fixed by the discovering session.

## Handoff

Keep it short: exact commit/artifact, tests/live actions, first unmet gate and next action. No new master context unless architecture materially changes.