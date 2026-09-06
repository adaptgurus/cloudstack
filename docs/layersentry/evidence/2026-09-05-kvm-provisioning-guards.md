# KVM provisioning guards — decision and source evidence

Risk: R1. Status: SOURCE_COMPLETE. Runtime: NOT_TESTED.

## Research and design review

Baseline: `d9681b8b51beddbdd19880a1ef47531c3d89ce17`, workstream A.
The existing profile filters hypervisor choices but VM image lists remain unrestricted,
CKS leaves its optional hypervisor unset, and old Site responses/selections can persist.

Checked the 4.22 API references for [listTemplates](https://cloudstack.apache.org/api/apidocs-4.22/apis/listTemplates.html),
[listIsos](https://cloudstack.apache.org/api/apidocs-4.22/apis/listIsos.html) and
[createKubernetesCluster](https://cloudstack.apache.org/api/apidocs-4.22/apis/createKubernetesCluster.html)
against this 4.22.1.1 source: `ListTemplatesCmd`, `ListIsosCmd`,
`CreateKubernetesClusterCmd`, `QueryManagerImpl.templateChecks`, `VolumeResponse`
and `SnapshotResponse`. `TemplateAdapterBase.prepare(RegisterIsoCmd)` explicitly
registers ISO media with `HypervisorType.None`. Template search supports `hypervisor`; native CKS supports
`hypervisor` and `nodetemplates`. Snapshots expose `volumeid`, not a hypervisor.
ISOs may be hypervisor-neutral (`None`), so an unconditional KVM-only ISO query
would exclude valid boot media.

Selected approach: retain the existing explicit profile and supported APIs; filter
KVM template responses as well as requests; allow neutral ISO media; validate the
actual selected Site and image IDs immediately before the native mutation. Resolve
snapshot hypervisor through its source volume. An unavailable source volume makes
that snapshot unverifiable in this UI and blocks submission. CKS custom images are
Site-scoped and KVM-only; its native hypervisor is set after a successful Site check.
Loading, unavailable and failed capability checks have distinct messages. Ignore
responses belonging to a prior Site selection. Recheck the loading flag after form
validation to prevent concurrent validation callbacks from submitting twice.

Alternatives: deleting upstream hypervisors or adding backend API restrictions
violates the core-preservation boundary. Selector-only checks miss stale/deep-linked
IDs. Hard-coding KVM without a Site lookup falsely asserts capability. The chosen
approach adds bounded read requests at submit, preserves upstream behavior outside
the profile, adds no dependency, and keeps maintenance confined to UI code.

Trust boundary: this is a product UX guard, not authorization. CloudStack RBAC,
scheduler, readiness checks and async jobs remain authoritative. API failures deny
the UI mutation; no mutation is retried. No new secret, HTML, shell or server boundary
is introduced. Source metadata may change after validation; the server remains the
final authority. No availability, HA or security certification is implied.

## Validation and recovery

Validation executed with official Node 16.20.2/npm 8.19.4 and the existing installed
UI dependencies in workstream B's `agent-b2/ui/node_modules`, accessed through an
ignored local symlink. No package/lockfile changes were made here.

- Focused Jest suites: `productProfile.spec.js`, `kvmProvisioning.spec.js` and
  `KvmProvisioningForms.spec.js`; final run passed all 36 tests across three suites,
  including two concurrent-submit regressions.
- Narrow `npm run lint -- --no-fix` across the eight changed JS/Vue source/test
  files passed. Initial lint found routine test formatting and the older linter's
  unsupported optional-call expression; both were corrected.
- `@vue/compiler-sfc` parsed and compiled the complete templates for `DeployVM`
  and `CreateKubernetesCluster` without errors.
- `git diff --check` passed.
- Focused form tests execute actual SFC methods with mocked native APIs, including
  positive VM/CKS requests, stale Site responses, changed selection during checks,
  no-KVM/failed Site discovery, incompatible or missing image metadata, custom CKS
  node templates, snapshot source-volume checks and upstream profile compatibility.
  These method tests do not claim rendered-browser coverage.
- Source wrong-label review: no new non-KVM choices, DBaaS/APaaS labels, or invented
  storage/API fields. Existing upstream non-KVM implementation branches remain.
- Full production build is owned by the integration/release workstream and was not
  duplicated here. Unit or lint success is not a release artifact.

No deployment or runtime mutation is authorized in this workstream. Browser/API
acceptance on the exact Rocky Linux 9 artifact in Chrome and Firefox is NOT_TESTED.
Rollback is a revert of the coherent UI commit; no backend/data migration exists.
No stable product relationship or policy changes, so no knowledge graph or master
context update is required. The lead owns the shared ledger and release gates.
