# LayerSentry — Workstream Index

Current execution routing is defined by:

`docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`

The active Codex scopes are now:

- **Workstream A — UI / Self-Service finishing**;
- **Workstream E — RKE2 / Kubernetes / Data Services**, the primary technical stream.

Do not restart the old broad multi-agent A/B/C/D/E/F model.

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
| A — UI / Self-service | **Codex**, bounded finishing/optimization/integration only; no broad redesign |
| B — Release / Installer | ChatGPT by default; exact K8s artifact blockers may be handled inside E |
| C — Security / Validation | ChatGPT for shared controls; A/E own UI/K8s-specific qualification cases |
| D — DR / HA / Upgrade | ChatGPT-led, native CloudStack recovery first |
| E — K8s / DBaaS / APaaS / Streaming | **Primary Codex workstream** |
| F — VM-native Single-OS | ChatGPT-led, Go + Ansible |

## Workstream A objective

```text
existing LayerSentry UI
 -> audit current defects
 -> optimize/wire APIs
 -> fix RBAC/routes/status/errors
 -> preserve KVM-only UX
 -> exact-artifact browser acceptance
```

Do not design a replacement UI.

## Workstream E objective

```text
existing E0/E1 source
 -> immutable artifacts
 -> deployed controller stack
 -> one real RKE2 lifecycle
 -> 6443/9345
 -> CNI/CCM/CSI/Flux
 -> status/scale/replacement/delete/upgrade
 -> air-gap/failure evidence
 -> install selected upstream services through Flux
```

User K8s, DBaaS, APaaS and Streaming profiles reuse the **same RKE2 lifecycle**.

For current V1, upstream services are integrations, not rewrite projects:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB;
- OpenBao Helm content;
- Harbor Helm content;
- Strimzi for Kafka.

Do not create replacement database/Kafka/application operators or spend Codex on upstream application UI rebranding unless the owner explicitly assigns it.

## V1 release carrier

Current execution uses one logical signed platform carrier:

`layersentry-platform-<release>.iso`

It may contain both platform and optional Data Services/APaaS/Streaming artifacts. Bundled content is `AVAILABLE`; Flux installs only what the selected profile requests.

## Concurrency

A and E may run separately only with clean file ownership. Coordinate router/config/API-contract changes. Do not run multiple overlapping E implementations against the same K8s source or live cluster.

## Handoff rule

Use repository/workflow/live evidence as authority. State exact commit/artifacts, vertical step reached, tests/live actions, first unmet gate and next action. Keep handoffs concise.