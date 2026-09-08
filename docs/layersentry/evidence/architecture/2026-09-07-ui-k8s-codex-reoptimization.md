# LayerSentry UI + RKE2 Codex execution reoptimization

**Date:** 2026-09-07  
**Status:** `DESIGN_DEFINED` / execution-policy change only  
**Cloud baseline:** Apache CloudStack 4.22.1.1 + KVM  
**Branch:** `layersentry/4.22.1.1-ui`

## Decision

The product owner reassigned the remaining LayerSentry UI finishing work to Codex and requested a lower-custom-code Kubernetes execution model.

Current Codex scopes are therefore:

1. bounded UI finishing/optimization/integration;
2. RKE2/Kubernetes E2E, the primary technical stream.

ChatGPT remains the default for VM-native Go+Ansible, bootstrap/control-plane HA, native DC/DR and context maintenance.

## Assumptions used for the optimized K8s plan

The plan is based on current repository/source evidence and the selected upstream ownership model:

- the LayerSentry UI already has substantial implementation and needs finishing rather than redesign;
- the K8s tree already contains BFF/auth/RBAC, durable workflow state, CloudStack preflight/client, CAPI/CAPC/CAPRKE2 resources, lifecycle executor, CAPC endpoint/volume work, CCM/CSI downstream work, NodeDiskSet, Flux resources, runtime wiring and tests;
- the largest remaining K8s risk is live E2E integration, not another broad source implementation phase;
- user K8s, Data Services, APaaS and Streaming can reuse the same RKE2 cluster lifecycle with different profiles/package selections;
- Flux is the shared package plane;
- OpenEverest/OpenBao/Harbor/Strimzi are upstream integration targets, not LayerSentry rewrite projects;
- current V1 does not require Codex to rebrand those upstream application UIs unless explicitly reassigned;
- one signed logical `layersentry-platform-<release>.iso` can carry both platform and optional service artifacts; bundled content is available locally but installed only when selected;
- production certification still requires exact live/destructive/failure/upgrade/air-gap evidence and is not implied by this policy change.

## RKE2 critical path

```text
immutable artifacts
 -> exact controller deployment
 -> GUI/API create
 -> CAPC CloudStack resources
 -> CAPRKE2 automatic join
 -> 6443 + 9345
 -> primary CNI
 -> CCM
 -> one safe CSI path
 -> Flux remote reconcile
 -> status/scale
 -> replacement + PVC/data survival
 -> delete/cleanup
 -> restart/UNKNOWN recovery
 -> upgrade
 -> air-gap proof where claimed
```

Only after this shared substrate passes should Codex install/qualify OpenEverest, OpenBao, Harbor and Strimzi through Flux.

## CAPC stop-loss

CAPI/CAPC/CAPRKE2 remains preferred because significant source already exists. However LayerSentry will not preserve it at any cost.

If a bounded focused qualification campaign repeatedly fails to achieve CloudStack VM creation, automatic RKE2 join, reachable 6443/9345 and cluster Ready, and evidence shows disproportionate provider-maintenance cost, the release may switch to the already-approved native CloudStack API + QCOW2/cloud-init + Ansible Runner + RKE2 + Flux fallback.

One release must have one lifecycle owner.

## Authority files updated

This decision was applied to:

- `/AGENTS.md`;
- `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`;
- `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`;
- `docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`;
- `docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`;
- `docs/layersentry/codex/README.md`;
- `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md`.

The execution contract explicitly supersedes conflicting V1 execution-routing, package-carrier and implementation-sequencing language in older contexts. Detailed storage/network/security/data-safety rules remain unchanged.

## Evidence/status impact

This is an execution/architecture optimization only.

It does **not** promote any runtime module to `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED`, and it does not change the formal progress score by itself. Runtime status must move only after the exact artifact/profile passes its required evidence gates.