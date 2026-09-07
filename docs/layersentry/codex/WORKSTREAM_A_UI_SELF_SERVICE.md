# Codex Workstream A — LayerSentry UI / Self-Service Finishing

**Execution owner:** Codex  
**Primary objective:** finish, optimize and validate the existing LayerSentry UI without broad redesign  
**Cloud baseline:** Apache CloudStack 4.22.1.1 + KVM

The UI is already substantially implemented. This workstream is a **bounded finishing/integration stream**, not a new product-design exercise.

## 1. Startup

Read only:

1. `/AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. this file;
5. `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` only when touching K8s/Data Services UI;
6. fetch the actual integration branch and current UI/runtime evidence.

Do not load old UI re-audits/handoffs unless a concrete regression requires history.

## 2. Scope

Codex owns the remaining UI completion work:

- defects;
- broken/missing routes or actions;
- API/BFF wiring;
- RBAC/direct-route behavior;
- KVM-only customer presentation;
- loading/empty/error/partial states;
- progress/operation timelines;
- exact K8s/DR/Single-OS feature integration;
- responsive/accessibility/security fixes;
- exact-artifact browser E2E.

Do **not** redesign the dashboard/navigation/terminology/provisioning UX from scratch unless an acceptance defect requires it.

## 3. CloudStack/UI boundary

The browser must not become an infrastructure orchestrator.

Use:

1. existing CloudStack 4.22.1.1 APIs;
2. existing LayerSentry BFF/controller contracts;
3. current CloudStack UI components/patterns where appropriate.

Do not modify CloudStack Java/backend/schema/KVM agent merely to simplify UI. UI hiding is presentation only; server-side authorization remains authoritative.

## 4. Existing UI must be reused

Before adding source, inspect the actual current implementation including:

- `ui/src/views/layersentry/QuickProvision.vue`;
- `ui/src/views/layersentry/quickProvision.js`;
- `ui/src/views/layersentry/KubernetesDataServices.vue`;
- `ui/src/views/layersentry/k8sDataServices.js`;
- current LayerSentry dashboard/navigation/config/router files;
- current UI tests.

Do not replace working components with a new parallel UI.

## 5. Customer outcomes

### 5.1 KVM IaaS

Finish/validate:

- role-aware dashboards/navigation;
- Quick Provision;
- compute profiles;
- storage profiles and multiple disks where supported;
- OS image/template selection;
- network/VPC selection;
- public/private IP and firewall/LB surfaces only when supported;
- VM/volume/snapshot/image actions;
- KVM-only normal customer filtering.

### 5.2 RKE2/Kubernetes

The same LayerSentry RKE2 lifecycle is reused for user K8s, Data Services, APaaS and Streaming profiles.

UI supplies intent only:

- project/Site;
- profile/release;
- control-plane/worker sizing;
- node pools;
- CNI;
- storage profiles;
- network/VIP choices;
- optional package/service selections;
- Review/Preflight/Deploy;
- status/scale/delete/upgrade actions exposed by the backend.

Do not implement CAPI/CAPC/CAPRKE2 logic in Vue/browser code. No normal workflow requires YAML, kubectl, SSH or pasted RKE2 tokens.

### 5.3 DBaaS/APaaS/Streaming

Do not build replacement application UIs merely because the services exist.

For current V1, LayerSentry UI needs only the customer-facing catalog/access/status/integration required by the selected workflow. The underlying services are installed through Workstream E using Flux and upstream products such as OpenEverest, OpenBao, Harbor and Strimzi.

Do not spend this workstream rebranding upstream application UIs unless the owner explicitly assigns that exact task.

### 5.4 VM-native DBaaS/APaaS

Wire the existing VM-native mode to its Go+Ansible backend contract. Do not expose Ansible playbooks, shell commands or package-manager internals.

### 5.5 Backup/DR

Keep DR UI thin and capability-driven: recovery Site, recovery point, network/IP mapping, Test Recovery/Recover and only qualified failover/failback actions. Do not create a replication engine in the browser.

## 6. Feature/capability gating

Never show a feature as ready merely because source exists.

Render or enable actions only when role/RBAC, CloudStack capability, LayerSentry feature policy and backend/provider prerequisites permit them.

Unqualified features are hidden, disabled with an actionable reason, or clearly marked unavailable according to actual capability data.

## 7. Terminology and KVM-only contract

Normal LayerSentry customer UI must not leak unsupported VMware/XenServer/XCP-ng/Hyper-V/Proxmox/MaaS selectors or labels.

Presentation terminology remains context-aware, for example:

- Zone -> Site;
- Pod -> Infrastructure Group;
- CloudStack Cluster -> Compute Cluster;
- Host -> KVM Host / Compute Host;
- Service Offering -> Compute Profile;
- Disk Offering -> Storage Profile where it truly maps to one;
- Template -> OS Image.

Do not confuse Kubernetes Cluster/StorageClass/worker pool concepts with CloudStack Compute Cluster/Storage Profile concepts.

## 8. UI defect loop

For each issue:

1. reproduce on the current source/artifact;
2. identify whether it is UI, BFF/backend, capability data or environment;
3. fix the smallest correct owner;
4. add/update the narrowest regression test;
5. build the exact UI artifact;
6. rerun the same browser/API scenario.

Do not paper over a backend defect by fabricating UI state.

## 9. Validation

Run, as applicable:

- affected unit tests;
- lint/static checks;
- production build;
- route/navigation tests;
- KVM-only rendered-DOM checks;
- RBAC/direct-route negatives;
- form validation and duplicate-submit behavior;
- loading/empty/error/partial states;
- affected API integration tests;
- current Chrome and Firefox exact-artifact browser acceptance where the runner environment permits.

For K8s surfaces coordinate with Workstream E so the UI tests the **real backend contract**, not a mock definition of readiness.

Do not claim `LIVE_VERIFIED` from unit/build tests alone.

## 10. File/concurrency ownership

Primary UI ownership:

- `ui/src/config/**`;
- `ui/src/views/**`;
- `ui/src/components/**` only when needed;
- `ui/src/locales/**`;
- UI-specific tests.

Workstream E owns K8s controller/provider/runtime source. Coordinate before changing shared API contracts/router/config files.

UI and K8s Codex sessions may run concurrently only when file ownership is clean. Preserve unrelated concurrent commits and fetch/reconcile before each meaningful batch.

## 11. Completion target

This workstream is complete for V1 when:

- customer navigation/dashboard shell is coherent;
- KVM-only provisioning surfaces work;
- Quick Provision is integrated;
- RKE2 UI is correctly wired to Workstream E;
- Data Services/APaaS/Streaming catalog/status surfaces reflect actual capabilities without rebuilding upstream UIs;
- VM-native and DR integration surfaces are wired to their real backends;
- RBAC/direct routes are correct;
- no obvious dead routes/buttons remain;
- build/lint/unit tests pass or exact blockers are recorded;
- browser acceptance is performed where the environment permits.

## 12. Handoff

Report:

- exact branch/base/final commit;
- files changed;
- tests/build/browser cases run;
- exact failures/root causes if blocked;
- backend dependencies still unavailable;
- next exact acceptance defect if any.

Keep the handoff concise and evidence-based.