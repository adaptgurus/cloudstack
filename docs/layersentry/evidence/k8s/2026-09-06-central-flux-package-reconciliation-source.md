# Central Flux remote package reconciliation: source checkpoint

Status: bounded adapter `SOURCE_COMPLETE`; Flux runtime and application package
qualification remain `NOT_TESTED`. No production gate has been promoted.

## Dependency audit and decision

Workstream E requires E0 volume survival before stateful DBaaS, E1 central Flux
before package enablement, and exact operator/application profiles before E3/E4
customer lifecycle. Current source had a GitRepository/Kustomization baseline,
but its Kustomization lacked `kubeConfig` and lived in `flux-system`, so it could
target the management cluster. No qualified package catalog, native package
adapter, OpenEverest engine adapter or OpenBao/Harbor HA lifecycle existed.

The selected bounded step fixes that remote target and adds an executable
native Flux adapter. It does not fabricate a DBaaS/APaaS service from generic
Helm success. CloudStack core, shared shell/UI, BFF routes, image/bootstrap,
release flags and shared progress ledger remain outside this source change.

Official Flux 2.9.5 release assets were revalidated. Its `install.yaml` SHA-256 is
`cc3dcd743af16215838b6937e1fce83745bf24c0dcc6c59737c59df15429caaf`.
That release contains source/kustomize controllers 1.9.5 and helm-controller
1.6.4. This is a schema-audited target, not a installed or certified Flux tuple.
The exact schema lock is `tools/layersentry/k8s/package-schema-lock.json`.

[Native HelmRelease documentation](https://fluxcd.io/flux/components/helm/helmreleases/)
and [remote Kustomization documentation](https://fluxcd.io/flux/components/kustomize/kustomizations/)
require the reconciliation object to share the CAPI kubeconfig Secret namespace.
The adapter uses `<cluster>-kubeconfig`, key `value`, and no cross-namespace
source or credential references. The
[OCIRepository contract](https://fluxcd.io/flux/components/source/ocirepositories/)
supports an exact digest and copying the Helm chart layer without rewriting it.
The [helm-controller 1.6.4 source](https://github.com/fluxcd/helm-controller/blob/v1.6.4/internal/controller/helmrelease_controller.go)
records that OCI digest in `status.lastAttemptedRevisionDigest`.

CAPRKE2 0.25.2's
[control-plane reconciler](https://github.com/rancher/cluster-api-provider-rke2/blob/v0.25.2/controlplane/internal/controllers/rke2controlplane_controller.go)
creates the kubeconfig Secret with an RKE2ControlPlane controller owner reference.
The package adapter binds live Cluster UID → native control-plane reference and
owner UID → kubeconfig Secret owner UID. The Secret read explicitly requests
`PartialObjectMetadata`; full Secret responses are rejected and no credential
bytes are serialized into package state.

Alternatives rejected: direct Helm subprocesses would add a package lifecycle
owner beside Flux; direct application CRs without an installed/qualified
operator would invent readiness; stateful application installation before E0
would violate the data-safety contract. Shared `flux-system` remote sources
would require avoidable cross-namespace references. Sources now live beside
their CAPI project namespace; the legacy `sourceNamespace` config field remains
accepted for configuration compatibility and does not select workload targets.

Failure history reviewed includes
[Helm deletion with unavailable impersonation identity](https://github.com/fluxcd/helm-controller/issues/554),
[interrupted Helm operations](https://github.com/fluxcd/helm-controller/issues/644)
and [CRD rollback/uninstall limitations](https://github.com/fluxcd/helm-controller/issues/1524).
The adapter therefore never strips finalizers, independently deletes PVCs,
forces a Helm rollback or declares a submitted request Ready.

## Implemented behavior

- E1 baselines are placed in the selected CAPI namespace and explicitly target
  its native kubeconfig. Readiness requires current generation and exact Git
  revision from both GitRepository and Kustomization. Missing remote target,
  source drift or stale status cannot pass.
- `PackageCatalog` accepts only an operator-supplied release-approved exact
  file digest, protected regular input, audited Flux tuple, independent platform
  OCI registry, exact chart digest and public fixed values. It rejects duplicate
  keys/profiles, dependency cycles, credential fields and unresolved artifacts.
  The global release verifier owns signatures; this loader does not invent a
  second signing authority. No fabricated qualified catalog is shipped.
- `PackageExecutor` accepts a normalized package/version/profile and native
  cluster/project identity. The existing authorizer is called before discovery
  or mutation. No raw Helm values, kubeconfig, server URL or credential material
  can be supplied in its request.
- Native OCIRepository and HelmRelease resources carry exact immutable
  request/catalog/Cluster-UID bindings. The HelmRelease uses the CAPI Secret and
  explicitly sets target/storage namespaces from the approved package profile.
  Flux remains the only Helm lifecycle owner.
- Each reconcile first observes authoritative resources, checks dependency
  generation/digest/ownership, and submits at most one create. Create-only POST
  avoids adopting a foreign resource in a GET/apply race. A repeated or ambiguous
  submission is observed before any next create; existing bound objects are not
  blindly rewritten. Mutating server errors/unreadable responses are UNKNOWN.
- Ready requires current-generation native Ready conditions, no active
  Reconciling/Stalled/deletion/suspend state, and exact OCI/Helm digest evidence.
  Package readiness does not claim engine data integrity or application HA.
- Uninstall requires its own qualified profile, blocks known dependents and all
  stateful entries, and waits for native Helm finalization before deleting the
  OCI source. Native deletion uses observed UID/resourceVersion preconditions.
  No finalizer/retention bypass or automatic destructive repair is implemented.

## Integration and remaining production gates

This adapter is intentionally not exposed through a new BFF route yet. The
normal runtime authorizer currently denies unregistered package actions; GUI/API
integration must register reviewed effective capabilities for
`kubernetes.package.read/install/delete`, reuse the existing durable saga and
serialize conflicting package operations per cluster. Package readiness/status
must remain distinct from DBaaS/APaaS engine readiness. Retain each operation's
approved catalog digest for resume; changing it requires explicit migration,
not resetting annotations/journals.

Old baseline resources in `flux-system`, if any were deployed outside current
false release gates, require an explicit inventory/migration before enabling
the corrected namespace target. No old object is automatically adopted/moved.
Cluster deletion still needs a package-first finalization contract so the remote
API and CAPI kubeconfig outlive Helm/Kustomization uninstall. That orchestration
is not silently inferred from Kubernetes garbage collection.

Remaining dependencies are real: install and qualify central Flux with locked
images before bootstrap transport cleanup; supply signed durable catalog/chart/
image closure; qualify native remote reconciliation; prove E0 volume survival,
CSI/backup/restore and worker replacement; then implement OpenEverest PostgreSQL
and explicit OpenBao/Harbor HA profiles, application APIs, storage/secret/VIP
resolution and customer GUI acceptance. No stateful package profile is enabled
by this source change. Node-image capability requirements remain visibly blocked
until their actual rollout path is qualified.

## Qualification

Generated OCIRepository v1, HelmRelease v2, GitRepository v1 and Kustomization v1
objects passed validation against the hash-verified official Flux 2.9.5 release
OpenAPI schemas. This checks source structure, not Kubernetes CEL/admission or
live controller behavior. Offline tests cover remote targeting, exact generation
and revision, denied project access, credential ownership, stale/foreign Cluster
UIDs, profile drift, ambiguous create/restart, dependency ordering, stateful and
uninstall gates, fenced deletion, no metadata-only Secret fallback, and mutating
HTTP ambiguity. No DC/DR, guest, Kubernetes or external application mutation was
performed.

Full E source regression: 163 tests passed locally, with one existing
environment-dependent skip. The focused package/E1/native-client run passed
30 tests before the additional explicit uninstall-gate check; the full run
includes that check. No hosted or live qualification is claimed for this commit.
