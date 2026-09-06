# LayerSentry — Codex Workstream Startup Index

This directory contains scoped Codex workstream contracts. It does not contain the authoritative current project state.

## Common read order

Every Codex workstream starts with:

1. repository `/AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. the assigned workstream file below.

Read specialist architecture/security/release files only when the current task needs them.

For LayerSentry-managed RKE2, DBaaS, APaaS, Streaming, Kubernetes package/storage/network/VIP/WAF work, also read:

1. `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
2. `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_ARCHITECTURE_ADDENDUM.md`;
3. the latest applicable dated validation under `docs/layersentry/evidence/k8s/` (currently `2026-09-06-k8s-master-context-full-validation.md`).

For VM-native Single-OS DBaaS/APaaS work, read:

1. `docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
2. `docs/layersentry/codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`;
3. the secure-engineering policy and applicable live evidence.

The Kubernetes Super Master Context and architecture addendum contain stable design/guardrails; dated validation records contain volatile exact-version/source findings and must be revalidated before changing a release tuple. The Single-OS context is a separate lifecycle model and must not be merged into the Kubernetes lifecycle plane.

Always fetch the actual current integration refs before editing. Do not use historical SHAs/run IDs/live addresses from old handoffs.

## A — UI / Self-Service

Workstream:

`docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`

Starter prompt:

```text
You are LayerSentry Workstream A: UI / Self-service. Read AGENTS.md, the canonical Super Master Context, current progress ledger and WORKSTREAM_A_UI_SELF_SERVICE.md. Fetch/inspect the actual current integration ref before editing. Work only inside A ownership on an isolated worktree/branch. Preserve CloudStack core and server-side RBAC. K8s/DBaaS/APaaS/Streaming are no longer globally excluded; when touching those product surfaces, follow the dedicated LayerSentry Kubernetes/Data Services master context, its validated architecture addendum/current evidence, and coordinate with Workstream E rather than implementing lifecycle logic in the browser. For VM-native Single-OS DBaaS/APaaS, follow its separate master context/Workstream F and keep lifecycle state distinct. Use the governed status/risk/evidence rules, run real relevant tests, commit atomically and stop at a reviewable branch with the standard evidence handoff. Do not self-merge or edit the shared progress ledger unless explicitly assigned.
```

## B — Release / Installer / Build

Workstream:

`docs/layersentry/codex/WORKSTREAM_B_RELEASE_INSTALLER.md`

Also read `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`.

Starter prompt:

```text
You are LayerSentry Workstream B: Release / Installer / Build. Read AGENTS.md, the canonical Super Master Context, current progress ledger, upgrade/supply-chain policy and WORKSTREAM_B_RELEASE_INSTALLER.md. Fetch/inspect the actual current integration ref before editing. Own only release/build/installer scope on an isolated worktree/branch. Build verified CI artifacts, manifest/SBOM/provenance/digest/signature and safe fresh/resume/repair/rollback behavior without CloudStack-core changes or dashboard redesign. Coordinate with Workstream E for LayerSentry K8s/Data Services offline bundles and incremental package artifacts, using the current K8s architecture addendum/validation for exact tuple gates. Coordinate separately with Workstream F for Single-OS guest/package artifacts; do not merge the two lifecycle state models. Apply governed status/risk/evidence rules, never commit secrets/signing keys, run real relevant tests and stop at a reviewable branch with the standard handoff. Do not self-merge or edit the shared ledger unless assigned.
```

## C — Security / Validation

Workstream:

`docs/layersentry/codex/WORKSTREAM_C_SECURITY_VALIDATION.md`

Starter prompt:

```text
You are LayerSentry Workstream C: Security / Validation. Read AGENTS.md, the canonical Super Master Context, current progress ledger and WORKSTREAM_C_SECURITY_VALIDATION.md. Fetch/inspect the actual current integration ref before editing. Work only inside C ownership on an isolated worktree/branch. Build evidence-driven RBAC/direct-URL, feature-gating, SELinux/firewall/package/update/snapshot/Kubernetes security and support validation. Coordinate with Workstream E for Kubernetes/Data Services-specific trust boundaries, CAPC/PVC data safety, endpoint and negative cases, and with F for Single-OS guest hardening/engine negative tests. Do not weaken safeguards to pass tests. Use governed statuses and R0-R4 rules, preserve uncertainty honestly and stop at a reviewable branch with exact evidence. Do not self-merge or edit the shared ledger unless assigned.
```

## D — DR / HA / Upgrade

Workstream:

`docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`

D normally uses both `adaptgurus/cloudstack` context and `adaptgurus/cozystack` runner automation. Also read `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`.

Starter prompt:

```text
You are LayerSentry Workstream D: DR / HA / Upgrade. From the parent containing cloudstack/ and cozystack/, read cloudstack/AGENTS.md, canonical Super Master Context, current progress ledger, upgrade policy and WORKSTREAM_D_DR_HA_UPGRADE.md. Fetch/inspect actual current refs in both repositories plus relevant workflow/live state before mutation. Own safe runner/Hyper-V/DR/HA/upgrade proof automation only; do not change CloudStack core to make a test pass or build advanced DR before native recovery is proven. Coordinate with Workstream E for Kubernetes/Data Services workload-specific DR/upgrade evidence and Workstream F for VM-native Single-OS workload evidence rather than creating duplicate DR frameworks. Apply R0-R4 rules, never duplicate an in-flight operation, use disposable approved data for destructive tests and hand off exact commits/workflow/artifact/live evidence. Do not self-merge or edit the shared ledger unless assigned.
```

## E — LayerSentry K8s / DBaaS / APaaS / Streaming

Workstream:

`docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`

Mandatory specialist context suite:

- `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`
- `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_ARCHITECTURE_ADDENDUM.md`
- latest applicable dated validation under `docs/layersentry/evidence/k8s/`

Starter prompt:

```text
You are LayerSentry Workstream E: K8s / DBaaS / APaaS / Streaming. Read AGENTS.md, the canonical Super Master Context, current Progress Ledger, LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md, LAYERSENTRY_K8S_DBAAS_APAAS_ARCHITECTURE_ADDENDUM.md, the latest applicable dated K8s validation evidence and WORKSTREAM_E_K8S_DBAAS_APAAS.md. Fetch the actual LayerSentry branch before editing and revalidate volatile provider versions. Preserve CloudStack 4.22.1.1 core and use CAPI/CAPC/CAPRKE2 as the selected RKE2 lifecycle direction only after the exact tuple passes qualification. Do not infer that released CAPC/CAPRKE2 contract differences are automatically compatible or incompatible; test the defined lanes. Treat RKE2 9345 endpoint ownership, CAPC attached-DATADISK deletion/CSI data safety, multiple node-disk ownership, CloudStack CSI project resize/idempotency and full air-gap as hard gates. Central Flux owns LayerSentry package reconciliation. Keep normal customer workflows GUI-only; automatic RKE2 join, multiple StorageProfiles, Frontend/VIP/Gateway/WAF abstractions, DBaaS/APaaS/Streaming and offline bundle behavior must follow the dedicated context suite. The VM-native Single-OS DBaaS/APaaS path belongs to Workstream F and must not share E lifecycle state/controllers. Work on an isolated branch, run real tests, use governed statuses and hand off exact evidence. Do not self-merge or edit the shared ledger unless assigned.
```

## F — LayerSentry Single-OS DBaaS / APaaS

Workstream:

`docs/layersentry/codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`

Mandatory specialist context:

`docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`

Starter prompt:

```text
You are LayerSentry Workstream F: VM-native Single-OS DBaaS/APaaS. Read AGENTS.md, the canonical Super Master Context, current Progress Ledger, LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md, the secure-engineering policy and WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md. Fetch the actual current branch/source and live evidence before editing. Own only the Rocky Linux 9 guest appliance/layersentryd/provider lifecycle and the explicitly authorized one-VM acceptance path. Do not modify or merge CAPI/RKE2/Flux/operator lifecycle state owned by Workstream E. Preserve SELinux Enforcing, firewalld/default-deny, safe argv/path handling, signed package/repository verification, secrets by reference, durable idempotent operation state and truthful evidence status. The current one-VM/2-vCPU/2-GB Hyper-V lab cannot certify real multi-node HA/quorum/failover. Work on an isolated branch, run real tests and hand off exact evidence. Do not self-merge or edit the shared ledger unless assigned.
```

## Integration / Lead

A separate integration/lead session should:

1. fetch current integration refs;
2. review each branch diff and ownership overlap;
3. reject unexplained CloudStack-core changes;
4. integrate one coherent change at a time;
5. run combined tests;
6. coordinate all live deployment/mutation;
7. update `LAYERSENTRY_PROGRESS_LEDGER.md` only when evidence changes project status.

Dependency order is based on the change. For the existing base product, preserve the established B/A/C/D coordination. For Kubernetes/Data Services, E coordinates with B/A/C/D. For VM-native Single-OS DBaaS/APaaS, F coordinates through common platform contracts but keeps lifecycle/state independent from E.

## Local setup

Use `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md` for WSL/worktree/launch commands. If more than four active workstreams are run concurrently, allocate an additional isolated worktree/session rather than co-locating writers. Never allow two writing agents to share one worktree, and serialize conflicting live mutations/heavy tests on the same runner/Hyper-V target.
