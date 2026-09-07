# LayerSentry production-context compaction — 2026-09-08

Status: `SOURCE_COMPLETE` for governance/context only. No product runtime/source capability is promoted by this change.

## Purpose

Reduce repeated ChatGPT/Codex context spend while preserving production architecture, module separation and evidence history.

## Scope decisions

- Kubernetes-backed DBaaS/APaaS remains separate from VM-native Single-OS DBaaS/APaaS.
- Current Workstream-E scope explicitly excludes cross-site RKE2 application DR, Kubernetes-backed DBaaS DC->DR promotion/failback, APaaS DR, RKE2 RPO/RTO, cross-site DNS/VIP switching and RKE2 DR UI.
- Independent CloudStack/VM/provider-native DC/DR remains a separate workstream.
- CSI/PVC project isolation, resize, stateful Machine replacement/data survival and DB backup/restore/PITR where advertised remain in K8s scope because they are normal stateful lifecycle/data-protection capabilities, not cross-site DR.
- K8s/DBaaS/APaaS production audit now uses per-action vertical traceability rather than an overall UI percentage.

## Context compaction

Approximate file-size changes:

| File | Before | After |
| --- | ---: | ---: |
| Kubernetes specialist Super Master | 53,991 B | 11,814 B |
| Kubernetes architecture addendum | 16,184 B | 5,827 B |
| Single-OS specialist Super Master | 14,251 B | 8,364 B |
| Bootstrap/control-plane context | 18,612 B | 9,360 B |
| Execution Contract immediate pre-compaction state | 10,816 B | 6,992 B |

Combined above: approximately 113,854 B -> 42,357 B, a reduction of about 62.8%.

The compact `LAYERSENTRY_CURRENT_STATUS.md` remains the startup orientation file. The already-compacted Progress Ledger remains historical/on-demand only.

## Production invariants preserved

- CloudStack remains IaaS authority.
- one RKE2 lifecycle remains CAPI -> CAPC/CAPRKE2 -> RKE2 -> CNI/CCM/CSI -> Flux;
- CAPC stop-loss/fallback remains explicit;
- CAPC/CSI/NodeDiskSet data-safety gates remain mandatory;
- upstream OpenEverest/OpenBao/Harbor/Strimzi remain integration targets rather than rewrite projects;
- Single-OS remains Go + Ansible on Rocky Linux 9;
- bootstrap remains a narrow pre-CloudStack control-plane exception, not a second scheduler;
- independent DC/DR remains native CloudStack B&R first;
- source/CI evidence remains distinct from live/production certification.

## Concurrency verification

This pass was reconciled against shared-branch base `993388405062c6d8dce758509b94ab17250f08ad`. The product-source changes already present at that base were preserved. The compaction batch itself modified only context/status/workstream documentation.

## New-session rule

Normal startup remains:

```text
AGENTS.md
 -> LAYERSENTRY_EXECUTION_CONTRACT.md
 -> LAYERSENTRY_CURRENT_STATUS.md
 -> assigned workstream/module status
 -> actual Git/workflow/live state
 -> first unmet gate
```

Specialist masters/addenda are read only when the current gate needs their production constraints. Historical expanded versions remain available through Git history and must not be restored as normal startup context merely for narrative completeness.