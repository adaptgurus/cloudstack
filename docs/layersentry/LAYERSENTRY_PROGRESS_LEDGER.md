# LayerSentry V1 — Durable Progress Ledger

## Purpose

This file is the **volatile, frequently updated, Git-backed operational checkpoint** for LayerSentry work. Current HEADs, workflow/job/artifact IDs, live target observations, completion state, blockers and next execution gates belong here rather than in the canonical Super Master Context.

Stable architecture, safety, evidence/status governance and production-certification rules are authoritative in:

`docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`

Specialist stable policy:

- secure implementation/trust boundaries: `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`
- upgrade/supply-chain/IP protection: `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`
- upstream/fork deltas: `LAYERSENTRY_UPSTREAM_DIFF.md`
- DR target architecture: `LAYERSENTRY_DRAAS_ARCHITECTURE.md`
- stable relationship index: `LAYERSENTRY_KNOWLEDGE_GRAPH.md`

Historical re-audits/handoffs are audit history after their findings are incorporated and are not normal startup authority.

## Mandatory checkpoint rule

After every meaningful atomic task, and before starting a risky/long/destructive task, persist progress to GitHub/evidence where practical:

1. Commit source/config/document changes in a small atomic commit.
2. Record the task status and exact commit SHA here when shared project state changed.
3. Record workflow run/job/artifact IDs when CI or live deployment was used.
4. Record live assertions actually executed.
5. Record unresolved limitations and the exact next action.
6. If runtime changed without a source change, persist evidence/status in this ledger, workflow evidence or another versioned evidence artifact.
7. Never rely on chat text, hidden scratchpad, browser state or model memory as the only record of completion.

A page refresh or new chat recovers from Git/repository/workflow/live evidence rather than restarting work from memory.

## Recovery after refresh/reconnect/new chat

Before changing anything:

1. Read `/AGENTS.md`.
2. Read `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`.
3. Read this progress ledger.
4. Read the assigned workstream file when applicable.
5. Use `LAYERSENTRY_KNOWLEDGE_GRAPH.md` when the task crosses components/decisions.
6. Fetch the actual current HEAD of `adaptgurus/cloudstack` branch `layersentry/4.22.1.1-ui`.
7. Fetch the actual current `adaptgurus/cozystack` runner integration branch when relevant.
8. Inspect the latest relevant workflow/run/artifact.
9. If the previous action may still be running, inspect its exact state before retrying.
10. Resume from the first unmet evidence gate.

## Current checkpoint

### PARTIAL / CI_VERIFIED — 2026-09-06 management bootstrap, provider artifacts and DR host prerequisites

Combined source branch `codex/k8s-service-completion` preserves the current history and incorporates first-management native bootstrap, caller-visible qualified image discovery, exact provider artifact builders and the Rocky/RKE2 CPU image builder. Source through `7c4c866415b1163e78df827d8866e8e0fbed5838` passed Rocky container run `34050272795`: **126 Kubernetes and 27 DR tests**, no skips. The image/boot continuation through `e96e9b8d211d39bcde00704cda70b22f347d1f07` adds 11 passing source tests. These are bounded code/artifact results, not complete module acceptance.

- Bootstrap uses native CloudStack VM/LB/firewall/temporary port-forwarding APIs, exact image attestations and QGA-pinned guest SSH. It escrows a fixed-endpoint management kubeconfig into a protected runtime file before closing owned forwarding. Reconcile never silently reopens SSH after escrow. Actual three-node formation and provider installation remain `NOT_TESTED`.
- Caller-visible template discovery intersects the user's native CloudStack inventory with the server's qualified SHA-256 catalog. Empty/unqualified bindings offer no image; the UI cannot submit arbitrary merely-Ready templates.
- CAPC/CCM hosted run `34050386205` passed at source `6162cc1e40`. CAPC artifact `9994484772` and CCM artifact `9994441961` contain verified OCI archives, SBOM/provenance and component manifests referencing the actual imported OCI index digests. Exact records are in `evidence/k8s/2026-09-06-capc-ccm-hosted-build-qualification.json`. Provider activation, public distribution/signing and live compatibility are unverified.
- CPU image run `34050507635`, job `101533146612`, passed at `f05710874613c3a38c2704c28650a04f7bae2aef`. Artifact `9994542246`; ZIP SHA `b9a4abd099ebbd08a5585bc17d6bfad8b7e801c737e1b074f5ddb905201e8ce3`; standalone QCOW2 SHA `8ee4a820fd427abf3f00e0f55b0421c8cb9d5fa054cd84bc0aab62fc1fc4bf77`. Signed Rocky9.8 and 312 exact signed RPMs plus pinned RKE2/Canal inputs built offline; the output remains unsigned, runtime-unqualified and unregistered. RKE2 was not started in the image builder.
- Strict read-only DR host run `34049342997` established Rocky9.8 and missing libvirt/QEMU/storage prerequisites. The bounded package/socket preparation runs `34049966021`, `34050379479` and completion `34050627512` installed signed libvirt `11.10.0-12.3.el9_8`, QEMU `10.1.0-17.el9_8.5` and xorriso `1.5.4-5.el9`. The missing read-only libvirt socket caused the initial provider-read failure; starting that exact socket restored native read-only access. Final evidence proves zero domains and preserved SELinux Enforcing/firewalld active. No guest, disk formatting, bridge/network or CloudStack API change occurred in this preparation.
- Versioned boot runner `7e51ac2aa` binds the successful image and boot harness `e96e9b8d211d39bcde00704cda70b22f347d1f07`. Run `34051209929`, job `101535049972`, is pending actual networkless `.20` boot/QGA acceptance. Its passing owned transient guest may be retained for DR provider capture only; no production image or cluster gate is inferred.
- DC console trust remains under exact-VM verification. A password was sent once only after a visually and programmatically bound empty Password prompt. Root shell was independently established from a tightly scoped prompt image; host-key proof is still pending. No DC SSH login or configuration change is claimed.

Production readiness is not a defensible percentage yet. Native two-Zone NAS recovery, latest/older live libvirt recovery, restart/failback/fencing, management cluster/provider/CSI validation, client provisioning, DBaaS/APaaS lifecycle and GUI acceptance remain unfinished. Repository-wide RAT licensing failures remain unresolved; no license declaration or certification flag was fabricated to bypass them.

### PARTIAL / CI_VERIFIED — 2026-09-06 DC/DR and Kubernetes customer lifecycle continuation

User reassigned completion of DC/DR replication and Kubernetes provisioning,
DBaaS/APaaS to this session. Source is isolated on
`codex/k8s-service-completion`; exact qualified source is
`14aa468554d8220eb3dd5d3bb3a2b61297ca30c8`. No historical reset or shared
worktree overwrite occurred. Latest observed integration refs are CloudStack
`ae719e0c0a` (Single-OS writer still active) and Cozystack
`c8ad45c4dca0755ba3091a4ee3f445e5ba9b8361`.

- Kubernetes GUI now connects native discovery to authenticated BFF create,
  operation recovery/polling, cluster inventory/detail, scale and delete.
  Project-scoped native reads and durable pagination replace lost-browser-state
  dependence. Submitted IDs are revalidated through the caller's CloudStack
  session before privileged reconciliation; exact server-owned image checksum
  bindings remain required. A same-origin Unix-socket proxy route is supplied.
- Rocky source workflow `34048152518` passed **84 Kubernetes and 27 DR tests**,
  without skips, using unprivileged Rocky 9.8 userspace, Python 3.9.25,
  QEMU 10.1.0 and Nginx 1.20.1. This is container CI, not a running Rocky guest,
  live libvirt capture or full GUI/API provisioning proof.
- UI workflow `34048138570` passed after replacing the incompatible Node16 CI
  toolchain with the previously verified locked Node24.20.0 path. Local combined
  UI build, lint and **22 suites / 318 tests** also passed. The latest new UI
  candidate has not been deployed by this continuation; previous served UI
  evidence remains at `ce1e19934f6ce9eb9f336b97e83f7ae2c890b720` on DR.
- DR source now preserves native NAS and libvirt file replication, including
  fixed sealed-partial and pre-capture-journal interruption recovery. Real QEMU
  tests reconstruct latest and two older points and verify unchanged retained
  replicas. Native recovery authorization/routing and CloudStack guest import
  still need complete live integration; no RPO/RTO or failover claim is made.
- CSI run `34047140051` built both unsigned OCI images with locked APK closure,
  SBOM/provenance and filesystem smoke checks. The missing XFS grow utility is
  included. See `evidence/k8s/2026-09-06-csi-oci-build.json` for exact digests.
  Signing, registry distribution, arm64 build and real CSI lifecycle gates remain.
- Fresh read-only DC API run `34046294664`: Basic Zone Disabled, one KVM host
  Up/Enabled, no primary/image storage or guest VMs reported; both templates are
  not Ready and the shared guest network is Setup. Optional API failures are
  UNKNOWN, not evidence of absence or bad credentials.
- Trusted exact Hyper-V DC console snapshot `34046965347` succeeded. The one
  guarded Login attempt `34047745757` stopped before any keyboard/password input
  at OCR. Subsequent Observe probes are read-only; Windows OCR type mismatches
  are being fixed before any credential retry. DC SSH trust is not established.
- First management RKE2 bootstrap and immutable CPU image build were missing.
  Dedicated isolated workers are implementing/qualifying them before tenant
  CAPI formation, E0 storage safety, and operator DBaaS/APaaS acceptance.

**Not complete:** live DC/DR fixtures, latest/older guest recovery, automatic
Kubernetes formation, stateful storage survival, DBaaS/APaaS lifecycles, browser
acceptance of those running services, signed release and production certification.
Generic RAT CI reports 182 unknown licenses across existing overlay/context and
candidate files; this is recorded, not hidden by broad exclusions or relicensing.
No release evidence booleans were fabricated. Runtime reservations remain
coordinated through the DR root thread; no storage/network/VM mutation has been
performed by this continuation. Detailed design and evidence:
`evidence/k8s/2026-09-06-customer-lifecycle-integration.md` and
`evidence/dr/2026-09-06-dr-module-source-qualification.md`.


### SOURCE_COMPLETE / BLOCKED — 2026-09-06 downstream CSI container inputs

Exact implementation commit:

`1913631225492969e402fd89c39c369814eab5bd`

The CloudStack CSI `3.0.2` idempotent-expansion overlay now also pins both
Dockerfile builder/runtime base manifests. Current overlay SHA-256 is
`ad1339342211b63d8c9c9a20994da20c66ae632e03c7ddc1c65d4215bf9c4f58`;
the E0 evaluator and release manifest require that digest. Fresh application,
exact patched `go test ./...` and repeat `ALREADY_APPLIED` checks passed, as did
74 Workstream E Python and 5 overlay tests. Evidence:
`docs/layersentry/evidence/k8s/2026-09-06-e1-csi-container-source.md`.

The Alpine `apk add` layer still resolves from a moving repository. The
release contract therefore records `apkPackageLayerDeterministic=false`, the
final downstream CSI image remains null, and E1 startup remains blocked.
Workstream B must supply a content-addressed mirror/locked package layer plus
image digest, SBOM, provenance and signature before live qualification.

### SOURCE_COMPLETE / NOT_TESTED — 2026-09-06 CCM Kubernetes 1.36 source overlay

Exact implementation commit:

`54121666698fde9e716bb3041ccf051a71e26726`

The selected Apache CloudStack CCM remains upstream `v1.2.0` commit
`4740dbcacc7fc5892354b03b2f0be7ebf5c92584`. Workstream E added a pinned
downstream overlay aligning its Go/Kubernetes build graph to Go `1.26.0` and
Kubernetes libraries `v0.36.0`, removed legacy v0.24 replacement pins, adapted
the current CCM command alias contract, fixed current-toolchain logging and
included resolved module checksums. Builder/runtime base images are pinned by
registry manifest digest. Overlay SHA-256 is
`a6689998f2a46b9622ac69f97f8e67e231f075ffa8cca16a85a97fd0f4893726`.

A fresh isolated worktree returned `APPLIED`, exact patched source passed
`go test ./...`, and re-materialization returned `ALREADY_APPLIED`. The 74
Workstream E Python tests and 5 overlay tests also passed. Evidence:
`docs/layersentry/evidence/k8s/2026-09-06-e1-ccm-kubernetes-136-source.md`.

This proves source build compatibility only. No downstream image/SBOM/
signature exists and no Kubernetes 1.36 node/LB lifecycle ran; therefore
`kubernetes136Qualified=false` and CCM image remain unresolved in the release
manifest. E1 startup remains blocked. Next gate is immutable CCM/CSI/catalog
artifact publication followed by live CCM/CSI/Flux qualification.

### SOURCE_COMPLETE / BLOCKED — 2026-09-06 E1 controller runtime wiring

Exact implementation commit:

`58e9e2e18e13d91422fe264530828fc6ba538b3d`

Workstream E now has strict runtime composition, secret-file-only config,
fail-closed immutable component loading, hardened BFF/reconciler systemd
examples, bounded restart-safe work selection and redacted retry persistence.
The BFF may use concurrent HTTP workers while one timer-driven reconciler owns
mutations; SQLite is still explicitly not an active/active store.

Every cluster now requires exact project and per-cluster frontend public-IP
IDs. CloudStack must report the IP Allocated in the selected project/Site.
Management namespaces are deterministic per project, and authoritative GETs
prevent adoption of foreign Namespace/CAPI/CAPRKE2/Flux resources before apply
or after an ambiguous outcome. The shared Flux source must match its exact
managed label, URL and commit; per-cluster Kustomizations carry project labels.

All 74 Workstream E Python tests and Python compilation passed locally.
Evidence: `docs/layersentry/evidence/k8s/2026-09-06-e1-controller-runtime-wiring.md`.
No package/systemd/reverse-proxy/SELinux/provider/Rocky test ran. The current
component manifest is non-deployable, so startup intentionally remains
`BLOCKED`. Next gate is Workstream B immutable artifact/catalog publication and
E0/E1 live qualification; PostgreSQL mutation remains blocked until those pass.

### SOURCE_COMPLETE / BLOCKED — 2026-09-06 E1 immutable component gate

Exact implementation commit:

`20f2336c93ea4ef57d70717261faf9f9ef6c7688`

The Lane B contract now includes exact CloudStack CCM `v1.2.0` commit
`4740dbcacc7fc5892354b03b2f0be7ebf5c92584`, downstream CSI image readiness
and central Flux catalog readiness. A strict validator requires digest-only
CCM/patched-CSI images, exact source/patch IDs, CSI project/resize evidence,
CCM Kubernetes 1.36 qualification, immutable Flux content and all four E1
runtime gates before deployment. Current unresolved fields remain null/false,
so the release correctly refuses deployment.

Exact CCM `go test ./...` passed locally, but its Kubernetes libraries are
`v0.24.17` while Lane B targets `1.36.x`; runtime compatibility is not proven.
The CSI chart/raw manifests also cannot identify the patched LayerSentry image.
All 66 Workstream E Python tests passed. Evidence:
`docs/layersentry/evidence/k8s/2026-09-06-e1-immutable-component-gate.md`.

No image was built or deployed. SBOM/signature/digest publication, CCM 1.36
LB lifecycle, CSI project lifecycle, Flux apply and Rocky evidence remain
`NOT_TESTED`. Next E1 source gate: controller package/service configuration
that consumes this validator and remains fail-closed until artifacts exist.

### SOURCE_COMPLETE — 2026-09-06 E1 CloudStack-session BFF authentication/RBAC

Exact implementation commit:

`bc29df96b9405bca263d18cd6deb52c85753f1fb`

Workstream E now validates the existing browser login against the exact
CloudStack `/client/api` session contract rather than trusting caller-written
identity or role headers. The BFF requires the HttpOnly `JSESSIONID`, matching
session-key cookie/header proof and an exact allowlisted Origin for mutations.
It obtains effective API grants from authenticated `listApis` and active
project scope from authenticated `listProjects`; create/status/scale/delete
authorization requires both exact project membership and the corresponding
CloudStack API capabilities. No CloudStack Java/API/schema/KVM core changed.

All 62 Workstream E Python tests passed locally. They include spoofed readable
cookie rejection, missing/mismatched/duplicate token handling, cross-Origin
denial, incomplete inventory denial, custom effective capability checks,
project tampering and read-only mutation denial. Design/source evidence:
`docs/layersentry/evidence/k8s/2026-09-06-e1-bff-cloudstack-session-auth.md`.

This authenticator remains opt-in and the unwired BFF remains deny-all. Real
CloudStack login/logout/expiry/custom-role behavior, reverse proxy, TLS,
Chrome/Firefox and Rocky Linux 9 remain `NOT_TESTED`. E0/E1 live gates remain
false and PostgreSQL mutations remain blocked. Next E1 source gate: immutable
CCM/downstream-CSI/Flux component selection plus controller package/service
wiring that refuses unresolved digests.

### SOURCE_COMPLETE — 2026-09-06 E1 create/status/scale/delete lifecycle executor

Exact implementation commit:

`402cb3f40d`

Workstream E added the E1 step executor and read-only CloudStack preflight without modifying CloudStack core. CloudStack Signature V3 POST calls resolve exact authorized project/Site/network/service-offering/KVM-image/endpoint IP inputs before CAPI apply. Provider resources are reconciled through the restricted Kubernetes client; both exact Active 6443 and 9345 LB rules must resolve before the endpoint step advances. Central Flux is pinned to a full Git commit with per-cluster prune/wait reconciliation.

The BFF source now covers create/status/scale/delete. Status, scale and delete verify LayerSentry/project ownership. Scale-up converges on available replicas; scale-down remains blocked while CAPC volume ownership lacks live evidence. Delete requires exact cluster confirmation, retained workload volumes and the live CAPC gate, deletes only the CAPI Cluster, and waits for absence so CAPI/CAPC remain VM authority. Mutating timeouts still enter `UNKNOWN` and require authoritative observation.

All 52 Workstream E Python tests passed. Source evidence: `docs/layersentry/evidence/k8s/2026-09-06-e1-lifecycle-executor.md`. No live CloudStack/Kubernetes/CAPI/RKE2/CCM/CSI/Flux request ran; E1 remains `NOT_TESTED` at runtime. Remaining E1 work includes package/service wiring, authenticated CloudStack-backed RBAC, real provider admission/reconciliation, one CCM/CSI path, restart/rollback/failure and Rocky evidence. PostgreSQL remains blocked until E0/E1 live evidence passes.

### SOURCE_COMPLETE — 2026-09-06 E1 pinned provider resources and restricted Kubernetes client

Exact implementation commit:

`7060883e13`

Workstream E added exact resource builders for the pinned mixed contract: CAPI `Cluster`/`MachineDeployment` and CAPRKE2 objects at `v1beta2`, CAPC infrastructure objects at `v1beta3`, and exact CAPI `apiGroup` references. RKE2 uses `v1.36.4+rke2r1`, `registrationMethod: control-plane-endpoint`, CAPC dual-endpoint ownership and CAPC Machine-volume annotations. Builders require resolved project/Site/network/offering/template IDs and include only a Kubernetes credential Secret reference. Flannel was removed from policy/UI because the exact CAPRKE2 v1beta2 CRD does not accept it.

The restricted Kubernetes client accepts only an HTTPS origin with pinned CA/runtime token, disables redirects, allows only the exact E1/Flux kinds, uses server-side apply with `force=false`, bounds responses and treats mutating transport failures as `UNKNOWN`. All 40 Workstream E Python tests passed. Design/source evidence: `docs/layersentry/evidence/k8s/2026-09-06-e1-provider-resource-contract.md`.

No CRD/API/provider runtime was exercised. Tuple reconciliation, actual 6443/9345 rules, automatic join, CNI/CCM/CSI and Flux readiness remain `NOT_TESTED`. Next E1 gate: step executor, condition/status evaluation, CloudStack preflight, create/status/delete/scale and central Flux baseline reconciliation.

### SOURCE_COMPLETE — 2026-09-06 LayerSentry Kubernetes BFF/controller saga foundation

Exact implementation commit:

`0574697c8a`

Workstream E added a framework-neutral WSGI BFF and SQLite-WAL durable saga/event journal outside Apache CloudStack core. Authentication and authorization default to deny-all; mutation requests require canonical subject-bound idempotency fingerprints; server-owned release policy runs before persistence; optimistic versions reject stale writers; provider metadata with secret-bearing fields is not persisted. A mutation timeout enters `UNKNOWN`, normal advance refuses to replay it, and only an explicit authoritative observation path can reconcile it.

Local evidence: all 32 Workstream E Python tests passed, including BFF denial/idempotency, exact-project authorization, durable journal events, idempotency collision, stale-writer rejection, secret-output rejection and ambiguous mutation observation. Design evidence: `docs/layersentry/evidence/k8s/2026-09-06-controller-bff-saga-design.md`.

Provider authentication/RBAC, CAPI/Kubernetes/CloudStack/Flux adapters, controller packaging and Rocky deployment remain `NOT_TESTED`; SQLite is limited to one active reconciler and is not claimed as an active/active distributed store. Next gate: E1 exact CAPI/CAPC/CAPRKE2 resource builders plus supported Kubernetes/Flux API adapters for cluster create/status/delete/scale.

### SOURCE_COMPLETE — 2026-09-06 CloudStack CSI 3.0.2 source qualification and idempotent expansion

Exact implementation commit:

`d249be7dba`

Workstream E pinned exact upstream CloudStack CSI tag `cloudstack-csi-3.0.2`, commit `a84477e922d62b82387ab55134fafc9c0b5aaf64`, and added a digest-verified downstream overlay without changing Apache CloudStack core. Source review verified the configured project is installed as a cloudstack-go default option and explicitly passed on volume creation. The overlay makes expansion convergent at the CSI controller and CloudStack connector layers: observed capacity at or above the rounded request returns success with actual capacity and does not replay `resizeVolume`.

Local source evidence: the exact patched upstream tree passed `go test ./...` using the module-declared Go `1.23.5` toolchain. Overlay preflight/apply/reapply returned `APPLICABLE`, `APPLIED`, then `ALREADY_APPLIED`; patch SHA-256 is `64853e92e82f4a6e5e298b9d114a1522aea21d04f84c02e1667079c54d4f9635`. All 26 Workstream E policy/evidence tests and 4 overlay tests passed. `e0_qualification.py` requires exact-source Rocky 9 evidence for project create/isolation, attach/detach, snapshot/restore, repeated expand/delete, CAPC PVC survival and NodeDiskSet replacement before it returns `LIVE_VERIFIED`. Design evidence: `docs/layersentry/evidence/k8s/2026-09-06-e0-cloudstack-csi-qualification.md`.

The resize-only digest above remains historical evidence for that checkpoint.
The current overlay also pins CSI builder/runtime base manifests and has digest
`ad1339342211b63d8c9c9a20994da20c66ae632e03c7ddc1c65d4215bf9c4f58`;
its Alpine package-install layer remains blocked pending an immutable mirror or
package lock, and no final downstream image is authorized.

This is not live CloudStack/Kubernetes qualification. `csiProjectScope=false`, `csiResizeIdempotent=false`, project PVC auto-grow remains disabled, and all destructive cases remain `NOT_TESTED`. Next Workstream E source gate: implement the LayerSentry BFF/controller execution contract with durable sagas, supported CloudStack/CAPI/Kubernetes adapters and fail-closed release gates; then implement E1 create/status/delete/scale and central Flux reconciliation.

### SOURCE_COMPLETE — 2026-09-06 E0 NodeDiskSet ownership/planning contract

Exact implementation commit:

`efcd97056b`

Workstream E added a LayerSentry-owned NodeDiskSet policy/planner without changing Apache CloudStack Java/API/schema/KVM source. Each disk definition carries an exact logical ID, disk-offering ID, size, scratch/cache purpose, retain/delete policy, expand-only/disabled resize policy and reattach/recreate replacement policy. Each durable binding records the exact CloudStack volume ID and CAPI Machine UID. Reconciliation and every destructive action verify the recorded ID, project, Site, disk offering and complete LayerSentry ownership tags; missing, conflicting, ambiguous, cross-scope or wrong-offering inventory fails closed. Durable workload/database data is rejected because it remains CSI/PVC-owned.

Local source evidence: all 22 Workstream E Python policy/planner tests passed, including create idempotency, binding/tag enforcement, expand/no-shrink, retain/delete, reattach/recreate, duplicate target rejection and project/Site/offering destructive guards. The release manifest now exposes `nodeDiskSetOwnership=false`, and the existing GUI remains fail-closed for direct node disks. Design evidence: `docs/layersentry/evidence/k8s/2026-09-06-e0-nodediskset-design.md`.

This is a source planning contract only. The BFF/saga executor, async timeout reconciliation, CloudStack mutation, Machine replacement and destructive Rocky tests remain `NOT_TESTED`; the gate stays false. Next Workstream E gate: qualify and, where needed, patch exact CloudStack CSI `3.0.2` project-scoped lifecycle and resize idempotency, then bind the policy/planners to the LayerSentry controller.

### SOURCE_COMPLETE — 2026-09-06 E0 CAPC endpoint and Machine-volume ownership overlay

Exact implementation commit:

`6f38f4a5954729706236e81bacdb2800444a1fe3`

Workstream E added a digest-pinned downstream overlay for exact CAPC `v0.6.1` commit `7521b14a31e6c46f81f16aae3738a27c08ad063f`; no Apache CloudStack Java/API/schema/KVM source changed. For LayerSentry-annotated clusters CAPC remains the one endpoint authority and now owns/reconciles both Kubernetes API TCP `6443` and RKE2 supervisor/join TCP `9345`. The overlay also replaces all-attached-`DATADISK` destruction with an explicit two-factor ownership check: the one deploy-time disk ID must be recorded in `CloudStackMachine.status` and its CloudStack CAPC/Machine-UID tags must match. CSI and otherwise unowned attached volumes are excluded; legacy/unmarked disks fail toward retention.

Source evidence: the overlay materializer verifies the exact upstream commit and patch SHA-256 `6d3fc88ccf986bd025fc6d714ec7b4fa19d0c2afe6f10c50ef02a198286cea74`, applies idempotently and rejects drift. Exact patched CAPC source compiled with verified Go `1.23.2`; the non-integration `pkg/cloud` suite passed 135 selected specs including the new two-rule assignment and owned-versus-CSI volume destruction cases; v1beta1/v1beta2 API tests passed and the v1beta3 test binary compiled. The existing LayerSentry policy suite passed 10 tests and overlay tooling passed 3 tests. This is local source evidence, not GitHub CI or live evidence.

`E0` remains incomplete. Full envtest, actual CAPC/CAPI/CAPRKE2 reconciliation, CloudStack LB creation, destructive PVC survival across delete/rollout/scale-down/remediation and rollback remain `NOT_TESTED`. Next Workstream E gate: implement explicit NodeDiskSet ID/tag/retain/delete/resize/replacement semantics and its failure/destructive test harness, then qualify CloudStack CSI `3.0.2` project lifecycle and idempotent resize.

### NOT_TESTED — 2026-09-06 provider-neutral DR state/journal/lease source foundation

DR-only source continuation added a provider-neutral, inactive control-plane foundation without changing CloudStack core DB/API contracts, without adding a scheduler/RBAC authority, and without executing any provider/runtime mutation.

Exact source implementation commit:

`8304bab4c3e8c209de9929c9f718053e32210724`

Exact source handoff/evidence commit:

`eeb71859e45924cb6a72439e8137874c87ecb300`

Handoff path:

`docs/layersentry/evidence/dr/2026-09-06-dr-logic-source-handoff.md`

Implemented in `tools/layersentry/dr_state_machine.py`:

- provider-neutral contracts for Site Pair, Protection Plan, Recovery Point, Recovery Group, network mapping and IP mapping;
- explicit operation types for Test Recovery, selected-recovery-point Recovery, Planned Failover, Failback and Auto Failover;
- durable operation state and append-only mutation journal primitives;
- idempotency-key binding to an immutable request fingerprint;
- resource-scoped exclusive lease with expiry/renew/release and live-token enforcement for post-lease transitions;
- explicit recovery-point requirements for Test Recovery, Recovery and Failback; no silent latest-point selection;
- isolated-Test-Recovery request invariant;
- provider capability contracts for CloudStack native, LINSTOR/DRBD, Ceph RBD, SAN array and libvirt backup paths, without embedding those provider implementations;
- capability gates for Planned Failover and Failback;
- dedicated fail-closed Auto Failover transition path that cannot be advanced through the generic state transition API and requires plan opt-in, provider identity/capability match, witness/quorum, source fencing, no-dual-writer proof, provider-safe promotion, destination/application validation and traffic-switch readiness at the required stages;
- ambiguous non-auto provider mutations transition to `RECONCILIATION_REQUIRED` with `FAIL_CLOSED_NO_AUTOMATIC_REPLAY` instead of blind mutation replay.

Scope/status limits:

- this source does **not** replace or duplicate the established native CloudStack `createVMFromBackup` recovery adapter;
- actual native adapter binding behind `RecoveryProvider` is the next DR-only source integration task;
- SQLite is only the current LayerSentry-owned durable source primitive and is **not** certified as the final distributed production coordination backend;
- LINSTOR/DRBD, Ceph RBD, SAN-array and libvirt provider-side replication/promotion implementations remain unimplemented/capability-gated unless an existing adapter is subsequently located and bound;
- no witness service, fencing executor, traffic-switch executor, provider promotion, failback mutation or automatic-failover runtime path was enabled;
- no test, build, lint, CI, deployment, live DR validation, recovery drill, failover drill, fencing validation or failback validation was run for this continuation.

Therefore this checkpoint is strictly `NOT_TESTED`. It is not `CODE_VERIFIED`, `CI_VERIFIED` or `LIVE_VERIFIED`, and it does not promote native recovery or advanced DR runtime readiness.

Next DR-only source action: bind the established native CloudStack recovery adapter behind the new `RecoveryProvider` contract while preserving its Advanced-Zone guard, caller-selected recovery-point UUID, intent-before-mutation journal behavior and fail-closed async-job reconciliation; keep provider-side Planned Failover/Failback/Auto Failover disabled until their real provider/fencing/witness implementations exist.

### PARTIAL — 2026-09-06 native DR baseline and acceptance tooling

The dedicated DR session owns DC/DR lab runtime operations; the other session acknowledged a source-only reservation. Fresh authenticated DC and Hyper-V inventories supersede the historical single-VM/API-secret blockers below. Both Rocky lab VMs now exist, but native recovery has not passed. See the [runner evidence and readiness matrix](https://github.com/adaptgurus/cozystack/blob/ops/layersentry-hyperv-inventory/hack/layersentry/evidence/dr-native-baseline-20260906.md).

- Hyper-V R0 run `33998994352`: two Running nested lab VMs on `TESTSER`, 12/16 vCPU and 40 GiB RAM each, same host/switch/storage failure domain; DR has attached 100 GiB OS and 500 GiB data virtual disks.
- DC API run `33999356386`, source `6d06709e3a824f3a8fb410a6c3e4a228e5c460a0`: CloudStack 4.22.1.1, one Up KVM Host, Basic Zone `dc` Disabled, empty primary/image-storage/user-VM collections, SystemVM template not ready. B&R framework is disabled with provider `dummy`; backup APIs return HTTP/API 401 and async-job listing returns 431. The run deliberately fails overall with `InventoryComplete=false`; failed API calls do not prove absent resources.
- Native recovery adapter: `SOURCE_COMPLETE` for its bounded metadata/clone/journal scope only, fourteen offline tests passed. It creates stopped fresh clones from explicit older/latest backup UUIDs, journals intent before mutations and refuses blind retries. Actual guest hashes, restore, RPO/RTO and full E2E remain `NOT_TESTED`.
- Exact 4.22.1.1 source audit identifies a Basic destination constraint: backup allocation supplies network IDs, while Basic allocation rejects them. An Advanced recovery Zone with explicit recovery networks is the supported candidate; no core patch was made. Both Zones must belong to the same management database, and DR's KVM agent must have only one controlling deployment.
- UI run `33999043753`: CI built exact UI source `c4a2bb29457634e38a9375d5de33b04eb3a9c825`; DR live preflight rejected the assumed WEB-INF/META-INF layout before UI changes. Runtime layout/configuration preservation and browser/API validation remain `PENDING`.
- DR guest probe `33999431832`: Rocky 9.8, hostname `layersentry-dr-mgmt1`, Management 4.22.1.1-1 active, SELinux Enforcing and firewalld active. `/dev/kvm` is accessible, but agent/libvirt/qemu-kvm are absent; data disk `/dev/sdb` reports 500 GiB without a filesystem or mount. The package-owned `WEB-INF/web.xml` exists and optional inner `META-INF` is absent. Backend fingerprint/configuration-preservation deployment corrections passed twenty-one local tests; live redeployment remains separate.
- Pinned-trust DC collector, exact-VM console snapshot and expanded API/DR inventory tests passed locally. The `.14` host key still requires independent out-of-band verification before password SSH; `.20`'s pinned key is not interchangeable.

Next gates are guest inventory/trust, functional source storage/templates/networking, Advanced destination registration, NAS B&R enablement, disposable workload plus two distinct recovery points, actual root/data-disk recovery checks and failure/RBAC negatives. Same-host function tests cannot certify independent-site DR. Advanced replication, planned failover/failback, witness/fencing and production DR remain `NOT_TESTED`.

### SOURCE_COMPLETE — 2026-09-05 integrated release/UI/security/R0 foundation

The integration lead fetched the authoritative repositories, created isolated worktrees, reviewed each workstream, and integrated the source batches in dependency order B -> A -> C -> D. No live runtime mutation was performed by this integration batch.

Integrated CloudStack branch commits, based on fetched integration head `26a5e4b092b37ff0693c6b3154a2090171440bd6`:

- release-contract foundation: `f8d5cccea6`;
- lockfile-strict release workflow correction: `d8bf0dd72b`;
- KVM-only LayerSentry UI product-profile foundation: `05d82af2c1`;
- RBAC/direct-route/direct-API evidence contract: `45a3d98a03`;
- control-plane database/R0 evidence decision: `0080e12477`.

Integrated cozystack runner commit, based on fetched runner head `605866aa1b3736e52357cc9aff52272c73cb2ded`:

- dispatch-only authenticated read-only CloudStack API inventory: `16234a1e2`.

Latest live R0 evidence inspected:

- workflow run `33913985331`;
- job `101156784267`, conclusion `success`;
- artifact `9952447606`, `layersentry-dr-r0-live-inventory-33913985331`;
- runner/host `TESTSER`, one running nested-virtualization VM `sen`, Hyper-V VMMS running, one internal LayerSentry switch, no VM checkpoints;
- CloudStack UI probe HTTP 200 and unauthenticated `listCapabilities` HTTP 401;
- artifact states `MUTATION_PERFORMED=false`.

The evidence proves only the listed R0 host/VM/reachability assertions. It does not prove authenticated CloudStack inventory, a second Site, independent failure domains, B&R, DR, DB/LB/Management HA, upgrade, fencing, or production certification.

Exact Apache CloudStack documentation tag `4.22.1.1` contains conflicting database statements: the compatibility matrix lists MySQL 8.4 or equivalent, while the installation guide says MySQL 8.0 was tested. Therefore the LayerSentry database version/topology remains a measured compatibility decision; neither version is promoted as the HA baseline until the required Rocky Linux 9 matrix passes.

#### Evidence-backed module readiness matrix

| Module | Current status | Evidence in this checkpoint | First unmet gate |
| --- | --- | --- | --- |
| Release artifact contract | `SOURCE_COMPLETE` | deterministic archive foundation, manifest, SHA-256, CycloneDX SBOM, provenance, source-map rejection, six passing contract tests | execute real Node/Vue CI build; implement signature/trust, installer consumption, atomic deployment and rollback |
| KVM-only customer profile | `SOURCE_COMPLETE` | explicit `layersentry-kvm` config and shared KVM filtering on five provisioning surfaces; source unit specification | execute UI unit/lint/build, deploy exact artifact, Chrome/Firefox Rocky Linux 9 workflows and no-KVM empty/error behavior |
| RBAC/negative validation | `SOURCE_COMPLETE` | four-role/11-case matrix, direct route/API/object-ID negatives, fail-closed linter, redacted evidence schema, six passing tests | add runner/browser/API adapters and execute with scoped role credentials and authorized foreign-object fixtures |
| Hyper-V/Rocky reachability discovery | `LIVE_VERIFIED` | run `33913985331` and artifact `9952447606` for the exact assertions above | authenticated CloudStack inventory through the new no-guest-mutation workflow |
| Authenticated CloudStack inventory | `BLOCKED` | dispatch-only R0 workflow integrated; repository currently exposes no configured LayerSentry API secret names | provision scoped `LAYERSENTRY_CLOUDSTACK_API_KEY` and `LAYERSENTRY_CLOUDSTACK_SECRET_KEY`, dispatch, review artifact |
| Native NAS B&R/two-Zone recovery | `BLOCKED` | current live inventory has one VM on one Hyper-V host; no B&R evidence | authenticated inventory plus approved second Rocky Linux 9/KVM target and disposable workload |
| DB HA/version selection | `PENDING` / `NOT_TESTED` | exact 4.22.1.1 documentation conflict recorded; no DB topology deployed | compare/test 8.0 and 8.4 candidates, routing, failover, quorum, backup/PITR, restore and upgrade |
| 3 Management / 3 DB / 2 LB HA | `NOT_TESTED` | no matching live topology exists in current evidence | provision independent failure domains and execute the complete failure/recovery matrix |
| Advanced DR/failover/failback/fencing | `NOT_TESTED` | provider-neutral state/journal/lease source foundation is committed at `8304bab4c3e8c209de9929c9f718053e32210724`; provider/runtime implementations remain unproven | bind native recovery to the provider contract, then provider/Test Recovery/planned failover/failback before automatic failover |
| Production certification | `PENDING` | mandatory Rocky Linux 9 release gates are incomplete | all release-specific functional, security, HA, DR, upgrade, recovery, performance and soak gates |

Combined source verification for this checkpoint is recorded in the final integration commit and command evidence. Runtime-affecting claims remain below `LIVE_VERIFIED` until exact artifacts are exercised on Rocky Linux 9.

Pinned-toolchain build attempt after integration:

- official Node.js `v16.20.2` Linux x64 archive was downloaded to temporary storage and its SHA-256 `874463523f26ed528634580247f403d200ba17a31adf2de98a7b124c6eb33d87` matched the official Node.js `SHASUMS256.txt` entry;
- bundled npm version was `8.19.4`;
- `npm ci --no-audit --no-fund` failed before build because the checked-in `ui/package-lock.json` is not synchronized with `ui/package.json` and old-lock metadata resolution also reported no matching `vue-loader-v16@16.8.3`;
- no tracked file changed and no artifact/runtime deployment occurred;
- the release workflow was not dispatchable from the non-default integration branch because GitHub had not registered the newly added workflow on the repository default branch.

This is a failed evidence gate, not `CI_VERIFIED`. The next release-build action is to research and repair the upstream UI dependency/lock contract in a controlled change, including the `vue-loader-v16` alias and the package-version mismatches, then repeat the exact pinned clean install, lint, unit, build, deterministic artifact comparison, and verifier negatives.

### SOURCE_COMPLETE — DR architecture revalidation + Super Master Context v3 + knowledge graph

Before advanced DR implementation, the existing LayerSentry DR direction was revalidated against CloudStack 4.22.1.1 source/documentation plus current public libvirt/QEMU, Ceph, LINSTOR/DRBD and Nutanix DR architecture material.

CloudStack branch at the completion of the canonical-context update before this ledger checkpoint:

`a9d9c906292e4df58f84076aaad9c12902b47a1f`

Runner/integration branch re-fetched during this review:

- repository: `adaptgurus/cozystack`;
- branch: `ops/layersentry-hyperv-inventory`;
- current observed HEAD: `605866aa1b3736e52357cc9aff52272c73cb2ded`.

Source commits produced by the research/governance pass:

- DR pre-implementation revalidation decision record: `ef8b4c9e511f2485f9976f6c14c478d2e4ab8ea5`;
- stable engineering knowledge graph: `770f256b0c4f59f10caceb9d99352d9a20358317`;
- refined storage-native-first DR architecture: `a9dd8cd8767e885cf7ee30f5ca697e2e9752ab91`;
- root `AGENTS.md` research-first/Rocky9 lifecycle rules: `4058bac7f6671247c0a8214e58f233f99ee0e28d`;
- consolidated Super Master Context schema 3.0: `a9d9c906292e4df58f84076aaad9c12902b47a1f`.

Architecture decision:

1. keep CloudStack authoritative for VM/network/storage/account/Zone/KVM lifecycle;
2. prove/reuse native CloudStack B&R/cross-Zone recovery first;
3. use one provider-neutral LayerSentry Protection Plan/Recovery Point experience;
4. prefer certified storage-native replication for low-RPO current replicas;
5. LayerSentry HCI preference: LINSTOR/DRBD, without forcing SAN/NAS customers to migrate;
6. Ceph path: native RBD mirroring when selected/certified;
7. enterprise SAN path: array-native consistency-group replication/promotion/reverse replication adapters;
8. generic QCOW2/file-backed NAS fallback: libvirt backup/checkpoint APIs rather than a LayerSentry-owned raw QMP/NBD protocol;
9. CloudStack NAS B&R remains baseline/fallback/long-retention/reseed path;
10. `rsync` is not the generic primary running-VM replication engine;
11. Hot Replica and historical point-in-time Recovery Point Catalog are separate;
12. planned failover/failback is certified before automatic emergency failover;
13. automatic failover requires independent witness/quorum plus safe fencing/exclusivity.

CloudStack capabilities revalidated during research include:

- B&R provider abstraction and NAS KVM provider;
- selected old-backup restore/new-VM creation;
- 4.22 cross-Zone create-from-NAS-backup use case;
- KVM file-backed incremental snapshot mechanisms and documented VM/Volume snapshot safety limitations;
- native LINSTOR primary storage;
- 4.22.1.x NAS B&R support for LINSTOR primary storage;
- backup scheduling is HOURLY/DAILY/WEEKLY/MONTHLY, so the 300-second framework sync interval is not a 5-minute backup SLA.

Static/source verification:

- comparison from prior branch checkpoint `ad80b8ba47450fe21501d4114cae2428fc4ac515` to `a9d9c906292e4df58f84076aaad9c12902b47a1f` was a fast-forward of five commits;
- changed files were limited to `AGENTS.md`, `LAYERSENTRY_DRAAS_ARCHITECTURE.md`, new `LAYERSENTRY_KNOWLEDGE_GRAPH.md`, `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`, and new DR revalidation evidence;
- no CloudStack Java/API/DB/KVM-agent/UI runtime/infrastructure implementation was changed;
- supplied temporary password values were deliberately not persisted; stable context records only authorized identities and runtime secret-reference names;
- Support Cluster UUID remains `UNKNOWN / PENDING` until implemented/discovered from live evidence; no UUID was fabricated.

Scope/status limits:

- this checkpoint is `SOURCE_COMPLETE` for research/design/governance only;
- no DR runtime implementation was deployed or mutated by this pass;
- no architecture claim is promoted to `LIVE_VERIFIED`;
- advanced DR implementation remains `PENDING`;
- independent-site automatic failover/failback remains `NOT_TESTED`;
- current lab still requires a second independent failure domain before production DR certification can be claimed.

The previously documented `+5–7 engineering man-day` advanced-DR estimate is superseded. The current multi-backend advanced DR planning range after native two-Zone proof is approximately **36–57 engineering man-days**, excluding additional storage-family adapters/certification. This is planning effort, not a delivery promise.

### SOURCE_COMPLETE — canonical context governance v2 / context-cleanliness + production-engineering re-audit

The LayerSentry AI/Codex context stack was re-audited and normalized so stable policy and volatile execution state no longer compete with one another, while production/security controls are carried in focused stable specialist policies rather than duplicated across every context file.

Source commits in this documentation-only context-governance update:

- canonical stable Super Master Context v2: `74658e14e887a9fde2687d947e63e477cd4d485e`;
- simplified root `AGENTS.md` authority/read order: `ea9d4fbf9e67f92fe1a4ffd686bdf0c4f2549417`;
- old master-context re-audit converted to archival pointer: `f3ad1588ee54c5f74644c171f9a571c7ccce61ed`;
- `CODEX_MASTER_CONTEXT.md` converted to concise execution index: `3e2a787908aa1cf4bbe99e45aab11180fc9078c1`;
- multi-agent master deduplicated: `63d2f4230e365c6bc4e09325523481b87d9fdb9f`;
- four-agent runbook authority/startup flow simplified: `0af02405d8094ca3353407877d9b462a3e706406`;
- upgrade/supply-chain/IP policy converted to stable-only production policy: `6fa3ff7aa24ed84584325e311a8d38a5cc9ecec1`;
- historical WSL/Codex handoff archived: `f759377e299d33caa42b9e21f0731d285d2157a3`;
- Workstream A aligned to canonical model: `33a89352a9a6b1b7620b5036b83fe1f4fac6e89a`;
- Workstream B aligned to release/supply-chain model: `2c9d26002b4f4bd255a8920db4f2f69c0fb3d240`;
- Workstream C aligned to security/evidence model: `6dd96eeb0d54cbb5096d184e038c0441457b52fe`;
- Workstream D aligned to governed statuses/R0-R4 safety: `adf720404be86cad2d3c8275146d11ffc5e732f2`;
- Codex startup README reduced to a minimal workstream index: `179134a9168c342e4c43d47a35a0ed471274bdc9`;
- Windows/WSL setup made stable/non-duplicative: `13ea3926b736818749b1f9011d7b7c7bb39535b2`;
- secure engineering specialist policy added: `0e288f3d05f4730ac5404e88c06af1635c7039bd`;
- root `AGENTS.md` linked/enforced secure-engineering baseline: `581cfd2c4c82a7c580491e78cac6d37d3ee0da5d`;
- Codex execution index linked secure-engineering policy: `85e2a1082f998b147d5ad0c49e3884ece58fb996`.

Key governance changes:

- volatile HEADs/run IDs/artifact IDs/live IPs/current statuses removed from the Super Master Context;
- current execution state now lives only in this progress ledger plus underlying evidence;
- historical re-audit/handoff files are no longer mandatory startup context;
- mandatory Codex startup reduced to `AGENTS.md` + canonical Super Master Context + progress ledger + assigned workstream;
- specialist documents are loaded on demand;
- duplicate Codex/multi-agent/host-setup instructions were reduced to indexes/runbooks with one source of truth per concern;
- explicit instruction-injection isolation added for logs/issues/web/API/customer-controlled content;
- R0-R4 change-risk classification added and propagated to workstreams;
- one stray non-governed DR pseudo-status (`FUNCTIONAL_POC`) was removed; functional POC is now scope narrative under a governed status such as `LIVE_VERIFIED`, never a separate status;
- production certification gates expanded to cover supply chain, installation/recovery, RBAC, appliance security, optional integrations, HA, upgrade and reliability/performance evidence;
- release policy explicitly covers trust/signing, SBOM/provenance, dependency/secret scanning, key rotation/revocation and rollback classes;
- secure-engineering policy now covers threat modeling, untrusted input, authorization/confused-deputy prevention, browser security, command/path/archive/SSRF/SQL/parser safety, cryptography/TLS, CI signing-secret boundaries, dependency build-script risk, privacy/redaction, resource-exhaustion/retry safety, source governance, incident response and production documentation gates;
- effort arithmetic corrected: historical component ranges sum to **20–29 engineering man-days**, not 20–27.

Scope limit: this is `SOURCE_COMPLETE` documentation/governance work only. It changes no CloudStack Java/API/DB/KVM-agent/orchestration code and performs no live runtime mutation. It does not promote any product capability to a stronger runtime status.

### PENDING — production source/release repository governance

Current branch metadata still reports the active LayerSentry integration branch as unprotected and current documentation commits as unsigned. This is source-governance state, not runtime product vulnerability and not evidence that artifact signing exists.

Before a production stable-release control plane, establish an appropriate branch/ruleset/release governance model including as applicable:

- protected integration/stable refs;
- required CI/status checks;
- review requirements for release/security-sensitive changes;
- restricted force-push/deletion;
- least-privilege promotion/signing permissions;
- deliberate commit/tag-signing policy if used;
- auditable stable-release approval/promotion.

Production LayerSentry artifact signing/trust verification remains a separate `PENDING` release-engineering gate.

### LIVE_VERIFIED — LayerSentry V1 DBaaS/APaaS placeholder removal on `sen`

Customer-facing DBaaS/APaaS placeholder routes, placeholder section files, the LayerSentry ServiceCatalog placeholder, and the remaining onboarding text reference have been removed from the V1 UI and the exact cleaned build has been deployed to the current `sen` test target.

Exact UI commit deployed:

`6ce76d6c241629086ffcad794093dbdd5f2dd5ba`

Key source changes leading to this UI:

- `ui/src/config/router.js`: DBaaS/APaaS imports and route registration removed;
- `ui/src/config/section/dbaas.js`: removed;
- `ui/src/config/section/apaas.js`: removed;
- `ui/src/views/layersentry/ServiceCatalog.vue`: removed;
- `ui/src/views/dashboard/OnboardingDashboard.vue`: obsolete DBaaS/APaaS service-catalog wording removed and replaced with truthful Kubernetes/object-storage/backup wording conditional on provider configuration.

No CloudStack Java backend, API, database schema, KVM-agent or orchestration-core functionality was changed by this task.

Served-UI repair commit:

`85031bd2e394c16c631b6e493ced1af87c19fbd3`

It pins UI `6ce76d...`, fails if `DBaaS` or `APaaS` remains in built/served JavaScript, and emits diagnostic file names if a placeholder marker is found.

Resume path commit:

`8ccb2e7af9b3109e8d39c76d64e8943766158310`

Main installer pin-alignment commit:

`6cc23984c253a7ea9618b9c7553d12a495dcc971`

Runner workflow/request:

- workflow pin update commit: `675f6e433feb85ce9320a1b8a6d073e8f758fd0d`;
- request commit: `af484d1b6e063c4929634ed045560f95f3891d7d`;
- workflow run: `33879178031`;
- job: `101043343720`;
- conclusion: `success`;
- evidence artifact ID: `9939463820`;
- artifact name: `layersentry-customer-ui-deploy-33879178031`;
- artifact digest: `sha256:1a308fdcfff5a87348a4dad3783afc4bf24ea4b5efa6a583a6203064b8599813`.

Live assertions proven by this exact run:

- build passed from immutable UI source `6ce76d...`;
- `BUILD_CONFIG_CHECKS` passed;
- build contained no `DBaaS`/`APaaS` placeholder markers under the enforced V1 check;
- runtime backup created at `/var/backups/layersentry/20260904-191720/served-ui-before-branding` before deployment;
- management service restarted and returned HTTP 200 after its normal startup window;
- `RUNTIME_CONFIG_CHECKS` passed;
- `HTTP=200`;
- served config `/etc/cloudstack/management/config.json`;
- `V1_PLACEHOLDERS=ABSENT`;
- `ONBOARDING=PASS`;
- `LOGO_ASSETS=PASS`;
- `RUNTIME_CONFIG=PASS`;
- `TERMINOLOGY=PASS`;
- independent `--verify-only` verification repeated the same assertions successfully;
- Hyper-V console capture succeeded and VM `sen` remained Running.

Scope limit: this `LIVE_VERIFIED` status proves the current V1 placeholder removal and the assertions above only. It does not certify the future KVM-only profile, self-service dashboards, Kubernetes, object storage, HA architecture, appliance lockdown, upgrade path, backup or DR.

### Historical diagnostic run — FAILED BEFORE DEPLOY, superseded by the successful run above

First removal attempt:

- run `33877641094`;
- job `101038334940`;
- artifact `9938829995`;
- digest `sha256:c10be571cefc3896602107b7c3ef2611ee28fbde0410cf53be113360d0e95b1d`.

The build completed but pre-deployment validation correctly blocked deployment because `OnboardingDashboard.vue` still contained DBaaS/APaaS wording. Because failure occurred in build validation before runtime backup/deploy, that run did not replace the live UI. The source was corrected and the later run `33879178031` is authoritative for the completed removal.

### LIVE_VERIFIED — historical served LayerSentry branding/customer terminology baseline on `sen`

Earlier evidence remains useful for provenance:

- workflow run: `33856746145`;
- job: `100971705863`;
- conclusion: `success`;
- artifact: `9930784385`;
- artifact digest: `sha256:6a6751c9c07723f73df36e02b9f66ee3a41cb3098ac2f2834945af4759e9a50b`.

This historical run has been superseded for the DBaaS/APaaS-removal scope by run `33879178031` but remains evidence for the earlier branding lineage.

### PARTIAL

- full LayerSentry UI experience: the page/section/persona contract is now
  `DESIGN_DEFINED` in `LAYERSENTRY_UI_EXPERIENCE_SPEC.md`; shared token
  unification is implemented and the Node 24 release builder is `CI_VERIFIED`
  at UI source `c4a2bb29457634e38a9375d5de33b04eb3a9c825` by workflow run
  `33992718987` (230 tests passed; artifact `9977160930`). This evidence includes
  semantic action icons and preservation of the emitted API-backed action;
  exact-artifact Rocky deployment and
  four-persona Chrome/Firefox evidence remain required before live promotion;
- customer terminology: substantial work exists and current onboarding terminology passed live verification, but full role/context wrong-label audit remains pending;
- installer: current V1 UI/resume/served-repair pins are aligned for the placeholder-removal scope, but CI-built UI artifact deployment, SELinux final state/policy, firewall-policy validation, appliance lockdown and signed update controls remain incomplete;
- self-service foundation: upstream CloudStack components exist, but final LayerSentry Department Admin/User UX is not yet implemented/live-proven;
- IP protection: stable architecture/policy is defined, but production artifact/source-map/signing/appliance controls remain dependent on implementation/evidence;
- upgrade engineering: architecture is defined, but supported N-1 -> N upgrade automation and release-specific evidence are pending.

### PENDING / NOT_TESTED

- KVM-only `layersentry-kvm` product profile;
- Platform Admin dashboard redesign;
- Department Admin self-service dashboard;
- normal User self-service dashboard;
- simplified VM wizard;
- simplified Kubernetes wizard;
- simplified Bucket UX;
- final Site/Infrastructure onboarding simplification;
- CI-built immutable UI artifact deployment;
- production source-map suppression/support-build strategy implementation;
- signed release manifest/artifact/update channel;
- N-1 -> N LayerSentry upgrade test automation;
- CloudStack schema-aware upgrade orchestration/rollback evidence;
- SELinux-enforcing appliance policy/modules and live validation;
- firewalld-enabled LayerSentry KVM traffic/security validation;
- package/repository lockdown;
- controlled signed update mechanism;
- full air-gap CKS;
- CKS metadata-isolation NetworkPolicy live validation;
- CKS CSI integration live validation for the selected Kubernetes ISO/profile;
- live Kubernetes validation;
- live object-store/Bucket validation;
- KVM snapshot-conflict guard implementation/test;
- native NAS B&R proof;
- DR source-record retention/purge negative test;
- two-zone cross-zone DR proof;
- RPO/RTO measurement;
- DR Site Pair binding/inventory sync runtime integration;
- provider capability adapters/runtime integration and certification;
- Protection Plan + Recovery Point Catalog service integration/runtime validation;
- LINSTOR/DRBD provider certification;
- NAS/libvirt incremental provider certification;
- first enterprise SAN provider certification;
- automated DR network/IP mapping;
- old-checkpoint recovery runtime validation;
- Test Recovery provider binding/runtime validation;
- Planned Failover/Failback provider-side implementation and runtime validation;
- witness/fencing/emergency automatic-failover implementation and runtime validation;
- 3-Management/2-LB/3-DB HA deployment/certification;
- physical OOBM/fencing certification on supported hardware;
- rolling upgrade certification;
- production release certification;
- proprietary Support Cluster UUID implementation/live discovery.

## Exact next execution sequence

1. Before runtime implementation, run fresh read-only discovery of the intended Rocky Linux 9/CloudStack target through the approved runner path and establish a secure non-mutating API/SSH credential injection method; do not reintroduce guest `authorized_keys` mutation for R0 discovery.
2. Establish/obtain a second independent Rocky Linux 9/KVM DR failure domain with sufficient compute/storage/network capacity; a same-host nested lab can prove function only, not production site independence.
3. Prove native CloudStack 4.22.1.1 NAS B&R two-Zone recovery first: backup, selected old backup, cross-Zone VM create, network mapping, data validation, source-record retention negative case and measured timings.
4. Bind the established native recovery adapter behind the provider-neutral `RecoveryProvider` contract, then implement Site Pairing/capability sync and the Protection Plan/Recovery Point Catalog service layer outside CloudStack core.
5. Certify the first real production storage path. Prefer LINSTOR/DRBD if building the LayerSentry HCI profile; otherwise certify the actual NAS/SAN backend required by the target deployment first.
6. Implement/verify older-point recovery and isolated Test Recovery before failover automation.
7. Implement and repeatedly test Planned Failover + reverse replication + Failback.
8. Add witness/exclusive lease/fencing and only then test emergency automatic failover under R4 controls.
9. Run security/RBAC, restart/idempotency, corruption/stale-point, performance/scale/soak and upgrade/rollback regression on Rocky Linux 9 for every certified provider.
10. Continue separate V1 UI/appliance/release governance work without conflating those milestones with DR certification.

## Refresh-safe invariant

**If the user refreshes the page in the middle of work, already committed/evidenced completed tasks remain completed. The next session must discover and preserve them from GitHub/workflow/live evidence. It must not restart from the beginning or mark them lost merely because the chat UI no longer contains the previous assistant output.**
