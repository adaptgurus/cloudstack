# Codex Workstream A — LayerSentry UI / Self-Service Finalization

**Execution owner:** Codex when activated  
**Activation:** **deferred by default** until backend contracts are stable enough for final integration  
**Objective:** finish/validate the existing UI; no redesign

The UI is already substantially implemented. Do not keep this workstream continuously active while RKE2, DR or Single-OS APIs are still changing.

## 1. Startup

Read only:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_CURRENT_STATUS.md`;
4. this file;
5. fetch the actual UI/backend state.

Read a specialist backend context or historical Progress Ledger evidence only for the exact integration/failure being investigated.

## 2. Hard file fence

Writable:

- `ui/**`;
- UI-specific tests/evidence.

Do not edit:

- `tools/layersentry/k8s/**`;
- `tools/layersentry/single-os/**`;
- `tools/layersentry/ansible/**`;
- `tools/layersentry/dr*`;
- global authority files.

If a UI test proves a backend defect, record the exact API/request/response/failure and hand it to the owning backend workstream. Do not fix backend source from the UI session.

## 3. Reuse existing UI

Continue current Quick Provision, LayerSentry dashboard/navigation, Kubernetes/Data Services surfaces and current CloudStack UI components. Do not create a parallel portal or rewrite navigation/dashboard/provisioning from scratch.

Normal UI duties are limited to:

- broken routes/actions/buttons;
- API/BFF wiring;
- RBAC/direct-route correctness;
- KVM-only customer presentation;
- loading/empty/error/partial states;
- progress/operation timelines;
- VM/bucket/backup integration;
- RKE2 create/status/scale/delete integration;
- Data Services/APaaS/Streaming catalog/status integration;
- DR recovery integration;
- responsive/accessibility/security defects;
- exact-artifact browser acceptance.

## 4. Native API rule

Use existing CloudStack 4.22.1.1 APIs and LayerSentry BFF/controller contracts. The browser is not an infrastructure orchestrator.

Do not invent CloudStack API fields, duplicate CAPI/CAPRKE2/DR logic in Vue, expose provider secrets, or treat UI hiding as authorization.

## 5. Upstream service UI rule

OpenEverest/OpenBao/Harbor/Strimzi are upstream integration targets. Do not build replacement application UIs or spend V1 effort rebranding their own UIs unless explicitly assigned later.

LayerSentry UI needs only the customer-facing catalog/access/status/policy integration required by the V1 product.

## 6. Activation trigger

Start this workstream when at least one backend vertical slice exposes a stable real contract and the product owner wants final UI acceptance.

Preferred final-pass order:

```text
KVM/VM/bucket/backup
 -> RKE2 backend integration
 -> Data Services/APaaS/Streaming catalog/status
 -> DR recovery integration
 -> RBAC/routes/errors/progress
 -> production build
 -> Chrome/Firefox acceptance
```

Do not reopen completed UI areas because an unrelated backend is still pending.

## 7. Completion

V1 UI is complete when the existing customer portal is coherent, KVM-only, correctly wired to real supported backends, role-aware, has no obvious dead actions/routes, and passes the applicable build/unit/browser gates.

Handoff only exact commit, files changed, tests/browser cases, backend defects handed off and the next UI acceptance defect.