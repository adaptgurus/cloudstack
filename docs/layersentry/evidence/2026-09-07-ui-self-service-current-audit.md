# LayerSentry UI / Self-Service Current Audit — 2026-09-07

**Status:** `PARTIAL`  
**Repository:** `adaptgurus/cloudstack`  
**Shared branch:** `layersentry/4.22.1.1-ui`  
**Branch HEAD immediately before this checkpoint:** `6ce0cb84390fd4a7b1d1b23bc1bbc4b3a015d2be`  
**Scope:** existing LayerSentry customer UI, with Kubernetes/Data Services design/integration intentionally deferred by the product owner for this audit.

## Authority and execution routing

The current `AGENTS.md` and `LAYERSENTRY_EXECUTION_CONTRACT.md` route remaining UI/self-service finishing to **Codex** as a bounded integration/defect stream. Broad UI redesign remains frozen. ChatGPT therefore stopped additional UI source mutation after the bounded fixes listed below and produced this evidence checkpoint instead of competing with the active UI Codex stream.

CloudStack 4.22.1.1 remains authoritative for VM/KVM lifecycle, networking, public IP, firewall/native LB, storage, volumes, images, snapshots, Backup & Recovery, RBAC and async-job state. No CloudStack Java/backend/schema/KVM-agent/core files were changed by this audit session.

## Completion assessment

Two different percentages must not be conflated:

1. **Canonical evidence-certified KVM IaaS/UI score: 3.70 / 10 = 37%.** This is the current Progress Scoring V2 Category B value and includes the penalty for missing exact-artifact browser acceptance and incomplete onboarding/integration evidence.
2. **Non-canonical engineering estimate for implemented non-Kubernetes UI/source integration: approximately 60–65%.** This estimate reflects how much of the intended non-K8s customer surface is already present in source. It is not a release/certification score and must not replace the canonical 37% evidence score.

The source estimate is higher because substantial UI exists but major integration and runtime/browser proof are still missing.

## Audited non-Kubernetes surface

| Surface | Current state | Approximate source/integration view | Main remaining gap |
| --- | --- | ---: | --- |
| LayerSentry branding, shell, KVM-only profile, terminology | `SOURCE_COMPLETE` / partly `CI_VERIFIED` by prior evidence | ~85% | exact-artifact browser/regression acceptance |
| Persona dashboards/navigation/RBAC presentation | `SOURCE_COMPLETE` | ~85% | complete direct-route/browser persona matrix |
| Quick Provision + normal KVM VM deployment | `SOURCE_COMPLETE` | ~85% | CI regression cleanup; exact runtime/browser proof |
| Compute/storage/image/network/VPC/multiple-disk provisioning | `SOURCE_COMPLETE` for major source paths | ~85% | exact provider/runtime combinations and browser evidence |
| Public IP / firewall / native L4 LB integrated provisioning experience | `PARTIAL` | ~35–45% | integrate capability-driven native CloudStack actions into the intended customer workflow rather than relying only on separate native pages |
| Backup self-service integration | `PARTIAL` | ~50–55% | provider-ready evidence, complete recovery/browser flow and exact API/RBAC validation |
| VM-native DBaaS/APaaS main Vue portal integration | `PARTIAL` | ~25% | wire existing Go + Ansible service contract into the primary LayerSentry Vue portal; existing embedded Single-OS agent UI is not the final portal integration |
| DR customer UI | `PARTIAL` / backend-dependent | ~10–15% | thin recovery-point/Site/network/IP mapping/Test Recovery/Recover flow after native CloudStack recovery is live-qualified |
| Exact-artifact Chrome/Firefox acceptance | `NOT_TESTED` in this audit | 0% evidence | build exact artifact and execute persona/browser acceptance |

These percentages are engineering estimates only. Kubernetes/RKE2/Kubernetes DBaaS/APaaS/Streaming is excluded from this table at the product owner's request.

## What is already materially implemented

### KVM-only customer profile

The current product profile filters customer hypervisor choices to KVM and applies KVM scoping to key VM/host/cluster/template routes. KVM Site and image checks fail closed before LayerSentry VM mutation. Non-KVM upstream implementation remains preserved but is not intended to render in the LayerSentry customer profile.

### Role-aware customer shell

The UI contains Platform Administrator, Department Administrator, normal User/Operator and read-only presentation logic driven by CloudStack role/API grants. Platform and self-service dashboards use native CloudStack inventory/capacity/activity information rather than a second state database.

### Quick Provision

The existing one-page Quick Provision implementation already includes:

- current Account / Department+Account / Project scope selection where authorized;
- Site and KVM preflight;
- KVM OS Image validation;
- Compute Profile selection including customized CPU/speed/memory;
- SSH key selection where permitted;
- root Storage Profile/size;
- multiple new data volumes, deterministic device IDs and custom IOPS handling;
- optional attachment of detached Ready data volumes after VM creation;
- VPC and primary/additional workload networks;
- optional administrative private-IP override;
- resolved network facts;
- post-deploy Backup Offering assignment when the capability is actually ready;
- explicit review/preflight;
- asynchronous job polling with bounded timeout;
- duplicate-submit suppression;
- partial-success reporting for post-deploy failures;
- generated password presentation when CloudStack returns it.

The browser does not implement infrastructure orchestration or claim HA/Protected/DR Ready from intent alone.

### Normal CloudStack VM lifecycle

The normal CloudStack VM deployment and lifecycle surfaces remain available and LayerSentry adds KVM mutation guards. Existing UI provides VM actions, volumes, snapshots, templates/images/ISOs, networks and related native CloudStack functions. The remaining product gap is primarily integration/coherence and acceptance, not rebuilding those features.

### VM-native Single-OS services

The repository contains a substantial Go orchestration service, Ansible execution path and an embedded Single-OS agent web UI supporting immutable planning/confirmation, provider selection, storage/network/maintenance/backup intent, lifecycle actions, backup/restore, enrollment and UNKNOWN-operation reconciliation. The shared branch is actively advancing the Ansible provider matrix.

The important UI gap is that this service workflow is not yet integrated into the primary CloudStack/LayerSentry Vue customer portal.

### Backup / DR

Native CloudStack backup UI/actions exist, and Quick Provision can assign a Backup Offering only when required APIs and readiness policy permit it. Backup and DR default to fail-closed/not-ready in the LayerSentry customer profile. DR source/backend foundations exist, but native two-Zone recovery has not yet been proven sufficiently to expose a complete customer DR flow.

## Kubernetes/Data Services deferral corrections made in this audit

The dedicated `Kubernetes & Data Services` page was previously capable of appearing by default, and a hidden menu route could still be opened directly. Because Kubernetes-based design/integration is deferred for this audit, two bounded customer-facing corrections were committed without removing the source or changing backend contracts:

1. `ced29546bf8c9395ac7db13c336ce46302f3d2e1` — `fix(layersentry): hide deferred Kubernetes services UI`
   - changed `ui/public/config.json`;
   - added explicit default `kubernetesDataServices.enabled=false`.
2. `4a25e4886825ed572a901bcc0082e3bf53ab0771` — `fix(layersentry): remove disabled Kubernetes service route`
   - changed `ui/src/config/router.js`;
   - dedicated route is registered only when the LayerSentry KVM profile is active and the feature is explicitly enabled.

Lint-only follow-up corrections:

3. `31032cdd21027d0e28def938f3d6ff1e0e7d9518` — router final-newline lint fix.
4. `264629f6e4287e2a44b1e57ae5af0dcdff2ff5bb` — repaired two pre-existing indentation lint errors in `ui/src/views/dashboard/LayerSentryPlatformDashboard.vue`; no intended behavior change.

No further UI source changes were made after current authority rerouted UI finishing to Codex.

## Exact CI evidence for `264629f6e4287e2a44b1e57ae5af0dcdff2ff5bb`

### LayerSentry UI release candidate

- Workflow run: `34099626406`
- Result: **failure**
- Lint: **PASS** (`DONE No lint errors found!`)
- Unit tests: **265 passed / 269 total**; **4 failed**; **14 / 17 suites passed**
- Production build: **not reached** because the unit-test step failed
- Browser acceptance: **not run**

The four unit failures are stale expectations/fixtures against current hardened source behavior:

1. `ui/tests/unit/views/layersentry/quickProvision.spec.js` — a test fixture omits the selected Compute Profile from the available inventory, while current source correctly blocks a disappeared Compute Profile.
2. `ui/tests/unit/config/layersentryNavigation.spec.js` — backup visibility expectation supplies list APIs but omits `assignVirtualMachineToBackupOffering`; current capability policy intentionally requires assignment capability for backup self-service.
3. `ui/tests/unit/config/layersentryCapabilities.spec.js` — two expectations similarly assume backup readiness from listing capability alone; current source correctly requires both listing and assignment capability.

These failures prevent promotion to `CI_VERIFIED`. They should be reconciled by the current UI Codex stream against the intended hardened capability contract rather than weakening source validation merely to satisfy stale tests.

### Other exact-head workflow evidence

- `UI Build` run `34099626379`: **failure**.
- `PR Merge Conflict Check` run `34099626365`: **success**.

No exact-artifact Chrome/Firefox validation was performed in this audit. Do not claim `LIVE_VERIFIED`.

## Remaining non-Kubernetes customer-blocking gaps, in execution order

1. **Restore green UI CI:** reconcile the four stale unit expectations/fixtures with current hardened Quick Provision and backup capability contracts; rerun lint, full unit suite and production build.
2. **VM-native portal integration:** wire the existing Single-OS Go+Ansible API into the primary Vue LayerSentry service workflow for software/version/topology/sizing/disks/network/VIP/backup/maintenance/review/progress/health/lifecycle.
3. **Integrated native network services:** complete capability-driven public IP, security/firewall and native L4 LB customer workflow where the selected CloudStack Network Offering/API grants support them.
4. **Backup acceptance:** exercise provider-ready backup assignment/recovery/status/error/RBAC paths with exact artifact and backend.
5. **Thin DR UI after native proof:** expose recovery Site, recovery points, network/IP mapping, Test Recovery and Recover only after the native CloudStack recovery baseline is live-qualified. Planned Failover/Failback remain hidden until backend-qualified.
6. **Browser acceptance:** exact built artifact, Platform Admin + Department Admin + User/Operator + read-only where applicable, current Chrome and Firefox, including responsive/direct-route/error/duplicate-submit/KVM-only checks.

## Next exact UI action

Per current repository routing, the **UI Codex finishing stream** should start with the existing CI defect rather than a redesign:

```text
fetch current shared branch
 -> reproduce release candidate unit failures
 -> update the narrow test fixtures/expectations to the current hardened source contract
 -> run lint + complete unit suite + production build
 -> preserve exact workflow/artifact evidence
 -> continue to primary Vue Single-OS integration
```

Kubernetes/Data Services design/integration remains deferred from this non-Kubernetes audit and should be coordinated with Workstream E when the product owner resumes that scope.
