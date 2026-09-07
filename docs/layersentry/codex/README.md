# LayerSentry — Workstream Index

Current execution routing is defined by:

`docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`

This directory retains historical/scoped workstream files for continuity, but **only Workstream E is a standing Codex implementation stream by default**.

## Minimal common startup

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. one applicable specialist context/workstream
5. fetch actual source/workflow/live state

Do not load every workstream or historical handoff.

## Current routing

| Workstream | Current default |
| --- | --- |
| A — UI / Self-service | ChatGPT defect/integration only; broad UI feature work frozen |
| B — Release / Installer | ChatGPT by default; K8s artifact blockers may be handled inside coordinated E work |
| C — Security / Validation | ChatGPT for shared controls; E owns K8s-specific qualification cases |
| D — DR / HA / Upgrade | ChatGPT-led, native CloudStack recovery first |
| E — K8s / DBaaS / APaaS / Streaming | **Primary Codex workstream** |
| F — VM-native Single-OS DBaaS/APaaS | ChatGPT-led, Go + Ansible; no shell-script install lifecycle |

Older instructions that tell the operator to start A/B/C/D/F as separate Codex sessions are superseded by the execution contract.

## Active Codex contract

`WORKSTREAM_E_K8S_DBAAS_APAAS.md`

Primary objective:

```text
existing E0/E1 source
 -> immutable artifacts
 -> deployed controller stack
 -> one real RKE2 cluster
 -> 6443/9345
 -> CNI/CCM/CSI/Flux
 -> status/scale/replacement/delete
 -> failure/reconciliation/upgrade/air-gap evidence
 -> PostgreSQL DBaaS vertical slice
```

Do not expand provider breadth before the current vertical slice works.

## ChatGPT contracts retained here

- `WORKSTREAM_D_DR_HA_UPGRADE.md` — native CloudStack recovery/troubleshooting contract;
- `WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md` — Go + Ansible VM-native service contract;
- A/B/C files — specialist reference when a concrete UI/release/security task needs them.

## Handoff rule

Use repository/workflow/live evidence as authority. Handoffs should state exact commit, exact evidence, first unmet gate and next action. Do not create a new large master context after each small task.
