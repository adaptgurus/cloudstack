# LayerSentry — Codex Execution Runbook

**Historical filename retained:** `CODEX_4_AGENT_RUNBOOK.md`  
**Current model:** two bounded Codex scopes — UI finishing and RKE2/Kubernetes E2E

The old broad multi-agent model is not the default. `LAYERSENTRY_EXECUTION_CONTRACT.md` is authoritative.

## 1. Why this model

Previous parallel Codex streams produced useful source but also repeated context loading, overlapping architecture work and source growth without proportional live E2E progress.

Current strategy:

- **Workstream A:** finish/optimize the existing UI;
- **Workstream E:** finish the existing RKE2/Kubernetes stack end to end;
- ChatGPT handles VM-native Go+Ansible, bootstrap/control-plane HA, native DR and context maintenance.

## 2. Active Codex scopes

### A — UI / Self-Service finishing

`docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`

Owns only the remaining bounded UI work:

- route/action defects;
- API/BFF wiring;
- RBAC/direct-route behavior;
- KVM-only customer presentation;
- status/progress/errors;
- integration with real K8s/DR/Single-OS backends;
- browser E2E/responsive/accessibility/security fixes.

Do not start another product redesign.

### E — RKE2 / Kubernetes / Data Services

`docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`

Owns:

- CAPI/CAPC/CAPRKE2/RKE2;
- LayerSentry K8s controller/BFF integration;
- CNI/CCM/CSI;
- Flux package plane;
- immutable K8s artifacts;
- K8s-specific UI contract coordination with A;
- package integration for OpenEverest/OpenBao/Harbor/Strimzi;
- K8s failure/upgrade/air-gap E2E.

Primary technical goal: **one complete reusable RKE2 lifecycle before service breadth**.

## 3. One lifecycle, many profiles

Do not build separate cluster engines for user K8s, DBaaS, APaaS and Streaming.

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> Flux
 -> selected upstream packages/operators
```

Profiles change node pools, storage, networking, security and packages. Lifecycle ownership stays the same.

## 4. Upstream-first service rule

For current V1, do not spend Codex building functionality mature upstream projects already provide.

Use pinned/qualified:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB;
- OpenBao Helm content;
- Harbor Helm content;
- Strimzi for Kafka.

Codex work is manifest/Helm/Flux integration, storage/network policy, local artifact packaging and E2E qualification.

Do not build replacement database operators, backup/PITR engines, DB failover engines, Kafka operators, OpenBao controllers or Harbor controllers.

Do not spend Codex on upstream application UI rebranding unless the owner explicitly asks for it.

## 5. One V1 release carrier

Current V1 uses one logical signed release carrier:

`layersentry-platform-<release>.iso`

It may contain both platform and optional service artifacts. Bundled content is `AVAILABLE`; Flux installs only the selected packages.

This supersedes the older execution idea of separate K8s and Data Services ISO carriers for current V1.

## 6. Minimal Codex startup

### UI session

```text
Read AGENTS.md
 -> LAYERSENTRY_EXECUTION_CONTRACT.md
 -> LAYERSENTRY_PROGRESS_LEDGER.md
 -> WORKSTREAM_A_UI_SELF_SERVICE.md
 -> fetch actual integration ref
 -> inspect current UI defects/build/browser state
 -> fix first blocking acceptance defect
```

### K8s session

```text
Read AGENTS.md
 -> LAYERSENTRY_EXECUTION_CONTRACT.md
 -> LAYERSENTRY_PROGRESS_LEDGER.md
 -> LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md
 -> WORKSTREAM_E_K8S_DBAAS_APAAS.md
 -> fetch actual integration ref/release candidate/workflow/live state
 -> close first failing E0/E1 gate
```

Do not start by loading every historical handoff.

## 7. Recommended worktree discipline

Use clean non-overlapping worktrees when Codex requires isolated edits.

Conceptually:

```text
~/layersentry/
  cloudstack-base/
  ui-codex/
  k8s-codex/
  cozystack-base/
  k8s-runner/      # only when runner changes are needed
```

Before creation/reuse inspect actual refs/worktrees. Never delete/reset an existing worktree because an example differs from current state.

A and E may run concurrently only with clean ownership. Coordinate shared router/config/API-contract files before editing.

Do not run multiple overlapping K8s Codex implementations.

## 8. K8s E2E order

Workstream E must prioritize:

```text
immutable artifacts
 -> controller deployment
 -> GUI/API create
 -> CloudStack VM/resource creation
 -> CAPRKE2 automatic join
 -> 6443 + 9345
 -> CNI
 -> CCM
 -> CSI + PVC safety
 -> Flux
 -> status/scale
 -> replacement
 -> delete
 -> restart/UNKNOWN recovery
 -> upgrade
 -> air-gap
```

Only after the shared substrate passes should it install OpenEverest/OpenBao/Harbor/Strimzi through Flux.

## 9. CAPC stop-loss

Keep CAPI/CAPC/CAPRKE2 while it is a supportable provider integration.

If a focused qualification campaign repeatedly cannot achieve CloudStack VM creation + automatic RKE2 join + 6443/9345 + cluster Ready, and the remaining downstream maintenance is disproportionate, record a release decision and use:

```text
LayerSentry durable workflow
 -> native CloudStack APIs
 -> hardened QCOW2/cloud-init
 -> Ansible Runner
 -> RKE2
 -> Flux
```

One release, one lifecycle owner. Never run both paths as competing owners.

## 10. E2E defect discipline

At each failure:

1. reproduce exact live failure;
2. preserve resource/job/log evidence;
3. classify owner layer;
4. fix the smallest correct owner;
5. add regression coverage;
6. build immutable affected artifact;
7. redeploy exact artifact;
8. rerun the same step;
9. continue only when it passes.

Do not solve an E2E defect by adding another controller.

## 11. Resource/concurrency discipline

Serialize operations that contend for the same lab resources:

- cluster create/delete;
- VM mutation;
- storage/CSI tests;
- VIP/LB tests;
- node upgrade/replacement;
- destructive data-safety tests.

Source analysis may run in parallel only when edits are non-overlapping.

## 12. Copy/paste prompt — UI

```text
You are the LayerSentry UI finishing Codex engineer. Read AGENTS.md, LAYERSENTRY_EXECUTION_CONTRACT.md, LAYERSENTRY_PROGRESS_LEDGER.md and WORKSTREAM_A_UI_SELF_SERVICE.md. Fetch the actual current branch before editing.

Do not redesign the product. Continue the existing LayerSentry UI, reproduce the first current acceptance defect, fix the smallest correct owner, run the relevant unit/lint/build/browser checks and continue until the existing KVM-first UI is integrated with the real VM/K8s/DR/Single-OS backends. Preserve concurrent work and coordinate shared API/router/config files with Workstream E.
```

## 13. Copy/paste prompt — K8s

```text
You are the primary LayerSentry RKE2/Kubernetes Codex engineer. Read AGENTS.md, LAYERSENTRY_EXECUTION_CONTRACT.md, LAYERSENTRY_PROGRESS_LEDGER.md, LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md and WORKSTREAM_E_K8S_DBAAS_APAAS.md. Fetch the actual current branch, release candidate and live/workflow state before editing.

Your job is not to add more horizontal scaffolding. Close the first failing E0/E1 live gate using the existing source. Produce immutable artifacts, deploy the exact controller stack, create one real RKE2 cluster, prove automatic join, 6443/9345, one CNI, CCM, one safe CSI path and Flux, then prove status/scale/replacement/delete/reconciliation/upgrade/air-gap as required. Fix the smallest correct owner for each observed failure.

After the shared RKE2 substrate is live-proven, install OpenEverest/OpenBao/Harbor/Strimzi through the same Flux package plane. Do not rewrite their operators/controllers or build separate cluster engines. Use the approved native CloudStack + Ansible RKE2 fallback only after a recorded stop-loss decision shows CAPC/CAPRKE2 maintenance is disproportionate.
```

## 14. Handoff

Keep handoffs concise:

- source commit;
- exact release/artifact tuple;
- tests/live actions;
- vertical step reached;
- failure/root cause if blocked;
- exact next acceptance/E2E gate.

Do not generate another large master context unless architecture materially changes.