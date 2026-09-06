# First management provider installation

Decision checkpoint, 2026-09-06. Existing source91a0b9da0d contains the native
three-node bootstrap, verified SSH transport and protected kubeconfig escrow,
plus a restricted tenant reconciliation REST client. No executable first-plane
CAPI provider installer exists. This addition reuses those bootstrap contracts
and native clusterctl installation, rather than creating another provider
inventory/upgrade authority.

The approved sequence is: form three native RKE2 nodes; transfer a digest-bound
immutable OCI bundle through still-open, QGA-pinned SSH; import and verify exact
containerd image names on every node; export a protected fixed-endpoint
kubeconfig; run pinned clusterctl with only local repositories and exact CAPI,
CAPRKE2/CAPC versions; verify provider inventory, CRDs and controller readiness;
record successful bundle identity; close temporary SSH. A failed stage keeps
owned transport pending. Completed reconciles do not reopen SSH. CCM is staged
as a qualified candidate artifact but is not activated where its release gate
is false.

Official source inspected:
- CloudStack4.22 native PF/Firewall/VM identity source, already documented in
  the bootstrap evidence. No CloudStack core/API changes are required.
- CAPIv1.13.5 cmd/clusterctl/client/cluster/components.go: native createObj first
  GETs and then creates or patches the exact object; installation is reentrant.
- CAPIv1.13.5 repository_local.go: local provider repositories use exact
  provider-label/version/components.yaml layout and metadata.yaml.
- CAPIv1.13.5 cert_manager_client.go pins default cert-managerv1.21.1.
- RKE2v1.36.4+rke2r1 main.go has no `rke2 ctr` command. pkg/bootstrap/bootstrap.go
  creates /var/lib/rancher/rke2/bin from the exact runtime image; use its native
  ctr against /run/k3s/containerd/containerd.sock in namespace k8s.io.

Alternatives: boot-time image baking remains valid for release production but
would require rebuilding the currently unqualified CPU candidate for every
provider change. An API privileged importer introduces a circular image input
and another host-level trust surface. Reopening SSH after completed bootstrap
violates the accepted lifecycle. Bounded staging during the existing owned
transport window avoids those problems and leaves native containerd/clusterctl
as lifecycle owners.

Failure history reviewed: RKE2issue5944 reports multi-platform archive import
content omissions; complete OCI blob graphs and exact imported digest checks
are required. RKE2discussions5628/7645 document archive placement and import
identity issues. CAPI's init documentation requires version pins and preserves
clusterctl labels/provider inventory; neither contract labels nor inventory
may be falsified. CAPCv0.6.1 remains v1beta1 contract. No production/release
qualification gate is promoted by installer completion.

Threat boundary: an approved operator supplies a protected runtime config and
an exact trusted bundle digest. Immutable public artifacts are never trusted
by filenames alone. Transfers use verified existing host keys and fixed remote
paths, atomic partial-file handling and finite bounds. Private kubeconfig and
provider credentials remain runtime-only; journal/evidence contain only safe
identity/digest/status. Preexisting foreign provider resources or version drift
must block rather than be overwritten. Timeout/partial installation is observed
before a reentrant retry; no destructive uninstall or rollback is automatic.

Validation must cover archive/digest/name drift, unsafe paths/ownership, stale
bundle reuse, partial transfer/import, foreign provider inventory, version or
image drift, restart after ambiguous clusterctl completion, bounded readiness,
credential redaction and unchanged bootstrap cleanup gates. Source/hosted CI
are authorized here. Live Rocky formation/provider reconciliation and GUI
acceptance remain separate required gates.

References: https://cluster-api.sigs.k8s.io/clusterctl/commands/init ;
https://github.com/kubernetes-sigs/cluster-api/blob/v1.13.5/cmd/clusterctl/client/repository/repository_local.go ;
https://github.com/kubernetes-sigs/cluster-api/blob/v1.13.5/cmd/clusterctl/client/cluster/components.go ;
https://github.com/rancher/rke2/issues/5944 ;
https://github.com/rancher/rke2/discussions/5628 ;
https://github.com/rancher/rke2/discussions/7645 .


## Central Flux 2.9.5 installation design (2026-09-07)

Existing bootstrap imports immutable CAPI/RKE2/provider OCI archives on all three
management nodes, installs native providers, and closes the temporary SSH transport
only after API-observed readiness. Central Flux was absent despite remote package
resources depending on it. Extend that same digest-bound bundle and completion gate;
do not create a second importer or reopen transport. Native CloudStack VM ownership
and the CloudStack 4.22.1.1 bootstrap APIs remain unchanged. XaaS does not replace
Kubernetes controller installation.

Use the pinned Flux 2.9.5 CLI's embedded manifests in offline export mode, with only
source-controller 1.9.5, kustomize-controller 1.9.5, and helm-controller 1.6.4. Replace
image tags with immutable OCI index digests and retain the complete graph including
upstream in-toto attestations. The exact release assets, hashes and image indices are
in inputs.lock.json. Do not call an online `flux install`, use floating manifests, or
claim that source-release provenance attests an OCI image.

Controllers reside in layersentry-flux-system and watch project namespaces. Sources,
reconciliation objects and CAPRKE2 kubeconfig Secrets are colocated per project.
Set no-cross-namespace-refs on Helm/Kustomize, and no-remote-bases on Kustomize. Remove
unselected subjects/API groups, unused serviceaccounts/token creation, aggregate
tenant edit/view ClusterRoles, and the management cluster-admin reconciler binding.
Keep only native reconciliation, event, leader-election and read-credential rights.
Do not set default-service-account=default: remote impersonation would require a
workload project namespace/ServiceAccount before its first package. The central
internal plane instead uses protected CAPRKE2 remote credentials and denies direct
tenant Flux mutation. A separate namespace-restricted remote SA bootstrap remains a
future hardening dependency, not an invented ready prerequisite. Native NetworkPolicy
allows controller egress; it does not itself prove air-gap or deny Internet access.

Alternatives considered: native online Flux install loses immutable manifest closure;
installing full optional controllers adds unused images/permissions; per-workload
platform Flux contradicts the authoritative central remote package owner; using
cluster-admin locally is unnecessary for remote reconciliation. Official guidance
permits removing aggregate roles and unused token creation. No upstream core patches
or new package readiness claims result.

The installer creates only exact approved native resource identities, saves independent per-object
nonce/bundle binding before POST (an earlier public annotation cannot predict the
next resource intent), observes before retry, rejects foreign or changed
resources and records native UIDs. It never overwrites an existing object or repairs
a deleted owned object silently. Exact controller args/images, CRD served schemas,
RBAC and current-generation readiness gate completion. CAPI readiness alone cannot
close transport while Flux installation is incomplete. Runtime credentials stay in
the existing protected kubeconfig path and never enter bundle/journal/artifacts.

Research: https://github.com/fluxcd/flux2/releases/tag/v2.9.5 ;
https://fluxcd.io/flux/cmd/flux_install/ ;
https://fluxcd.io/flux/installation/configuration/multitenancy/ ;
https://fluxcd.io/flux/security/ ;
https://fluxcd.io/flux/components/helm/helmreleases/#remote-cluster-api-clusters ;
https://fluxcd.io/flux/components/kustomize/kustomizations/#remote-clusters-cluster-api .
Exact release CRDs and generated CLI YAML were inspected, including native kubeConfig
Secret and cross-namespace policy fields. This is an extension of the approved
architecture, not a new CloudStack lifecycle decision. Relevant native containerd
import naming failure and recovery are already covered by the provider qualification.

Qualification is source and hosted native import only until actual Rocky RKE2
controller deployment, restart, namespace-negative, remote package, storage and
recovery tests pass. No production/signature/live gate is changed. Failed installation
retains credentials and exact owned transport for resume; incompatible existing
resources require explicit operator recovery, never automatic delete/upgrade.
