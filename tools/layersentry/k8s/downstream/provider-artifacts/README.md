# First-plane downstream provider artifact qualification

Audit before implementation (2026-09-06): CAPC v0.6.1 at
`7521b14a31e6c46f81f16aae3738a27c08ad063f` packages a prebuilt manager into
floating `gcr.io/distroless/static:nonroot`; it does not pin a compiler or
runtime digest. CCM v1.2.0 at `4740dbcacc7fc5892354b03b2f0be7ebf5c92584`
uses floating Go 1.23 and distroless upstream; the existing LayerSentry overlay
pins Go 1.26 and distroless but its upstream Makefile still uses wall-clock
build dates and obsolete Kubernetes version symbol paths. Neither overlay
contained usable downstream OCI archives or digest-bound installation YAML.

Official inputs inspected:
- [CAPC exact Dockerfile](https://github.com/kubernetes-sigs/cluster-api-provider-cloudstack/blob/7521b14a31e6c46f81f16aae3738a27c08ad063f/Dockerfile)
- [CAPC exact pinned Kustomize module](https://github.com/kubernetes-sigs/cluster-api-provider-cloudstack/blob/7521b14a31e6c46f81f16aae3738a27c08ad063f/hack/tools/go.mod)
- [CCM exact Dockerfile](https://github.com/apache/cloudstack-kubernetes-provider/blob/4740dbcacc7fc5892354b03b2f0be7ebf5c92584/Dockerfile)
- [CCM exact Makefile](https://github.com/apache/cloudstack-kubernetes-provider/blob/4740dbcacc7fc5892354b03b2f0be7ebf5c92584/Makefile)

The hosted workflow checks exact upstream commits and existing patch digests,
then uses dedicated immutable multi-stage builds. Both use the existing
approved Go 1.26.0 builder and distroless digest, with automatic Go toolchain
download disabled, checked-in module sums, static binaries, no build VCS
path leakage, and source-commit build timestamps. CAPC runs only offline
mock cloud tests (`!integ`), CCM runs its mock unit suite. No credentials or
CloudStack endpoints are supplied. Kustomize v5.4.3 is built from CAPC's exact
`hack/tools` go.mod/go.sum. Buildx, BuildKit, SBOM scanner and Actions are pinned.

Every archive retains SBOM and provenance; a second cached Docker export
executes non-root, read-only, network-disabled smoke checks. Verification
binds that executable image config to the OCI runtime manifest and checks all
blob hashes, descriptor sizes and attestation subjects. CAPC installation YAML
is rendered from the patched CRDs, with finite concrete provider defaults and
the actual verified image digest. CCM keeps upstream RBAC and its native
`cloudstack-secret` reference; no Secret data is emitted.

Images use the logical local name `layersentry.local/<component>@sha256:...`.
Import each retained OCI archive into every scheduled node's containerd
`k8s.io` namespace, or mirror it preserving the digest and explicitly rewrite
its repository before installation. The archive tag is `<component>:qualification`
under that same repository. Build output is unsigned and retained 14 days by
GitHub; it is not a production release or durable distribution channel.
Install pinned CAPI core, CAPRKE2 and cert-manager separately before CAPC;
this workflow does not install anything. Live Rocky provider reconciliation,
VM/LB/disk ownership and CCM activation remain required acceptance gates.
