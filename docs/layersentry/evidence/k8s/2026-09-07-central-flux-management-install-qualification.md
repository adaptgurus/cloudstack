# Central Flux management installer qualification — 2026-09-07

Status: **CI_VERIFIED** for the stated source/artifact scope only.
`liveVerified=false`, `productionCertified=false`, `signed=false`. No DC, DR,
Hyper-V, KVM guest or management Kubernetes runtime was mutated by this task.

Source: `codex/k8s-central-flux-install`, based on package commit
`a37a1f6fa561b62e7bea97a29bb6d5792f677dc2`. Implementation
`fcc9e9c6bd755711a90adf1d820ef932c6bb30d6`; per-object intent hardening
`42812d0cb515a0c3db794cc959d1b96392fe79bd`; final execution-field correction
`b9b39935b3c440bbbdaa744efcc79dbd40ad1b17`. Only the management bundle/installer,
its source tests and build-only workflow changed. Native CloudStack core, bootstrap
guest transport, image sealing, package catalog and production gates were untouched.

[Nonce-hardening hosted run 34057556047](https://github.com/adaptgurus/cloudstack/actions/runs/34057556047)
passed **177 source tests without skips**, exact native generation of all four CAPI
providers and the minimal Flux export, and two strict native-local import/reimport
passes of all **11 images** in the exact pinned RKE2 containerd runtime. A legacy
transfer-API diagnostic is recorded separately and is not a passing gate.
The preceding [run 34057107223](https://github.com/adaptgurus/cloudstack/actions/runs/34057107223)
passed 176 source tests and the same artifact checks.

[Final hosted run 34058039241](https://github.com/adaptgurus/cloudstack/actions/runs/34058039241)
passed **180 source tests without skips** and the same native generation,
attestation and eleven-image import/reimport gates at the final execution-field
correction. It reports the same bundle manifest digest. Artifact 9996595533 expires
2026-09-20T20:28:56Z; its duplicate bundle was not downloaded again.

Root review identified additive execution drift: desired-subset matching accepted
extra command/envFrom/lifecycle/workingDir and template inputs. The final observer
compares execution templates after narrowly audited Kubernetes 1.36.4 default and
conversion normalization. Negative tests cover these fields, routing/credential
inputs and template annotation injection. Positive tests cover native defaults,
CPU quantity canonicalization, field selectors, probes and ServiceAccount alias.
Native projected ServiceAccount volumes are added only to Pods, not Deployment
templates; the observer reads Deployments and does not reject actual Pod admission.
Exact upstream source references and the boundary are recorded in DESIGN.md.

The complete [downloaded artifact 9996325314](https://github.com/adaptgurus/cloudstack/actions/runs/34057107223/artifacts/9996325314)
was independently extracted with executable modes preserved. Its retained tar,
24 listed files, all OCI blob/descriptor closures and Flux runtime-bound SPDX/SLSA
statements verified. GitHub ZIP size is 1,206,110,983 bytes; expiry is
2026-09-20T20:11:50Z. Copy the public candidate to approved durable storage before
expiry. This evidence does not claim publisher-signature verification.

- Retained tar SHA-256: `8e7d7920dd8fdc07d3d7b6ce6d98ff5e103667255bbae14faea0ca6878cebe43`.
- Bundle manifest SHA-256: `a9e19cc5e01178f7c08966dee0e38ce49b4754b26699e3987a6706fd82215649`.
- Reviewed central Flux manifest SHA-256: `859af77c8c34f59a157e0a67c7591ea86fab50d04083e7e55d5681119245484f`.

Both hardening runs report the identical bundle manifest digest after source-only
changes. Their additional artifacts were not downloaded redundantly;
the already fully verified identical bundle remains usable with the final installer.
The JSON evidence records both run/source/artifact bindings without conflating them.

Flux 2.9.5 supplies source-controller 1.9.5, kustomize-controller 1.9.5 and
helm-controller 1.6.4. Exact index digests and upstream asset checksums are in
`tools/layersentry/k8s/management/inputs.lock.json`. The native CLI's embedded
export becomes 21 reviewed resources; optional controllers and their unused
permissions, aggregate tenant roles and the management cluster-admin reconciler
binding are removed. Cross-namespace references and remote Kustomize bases are
denied. Same-namespace remote CAPRKE2 credentials remain runtime-only.

The existing importer stages every image on all three nodes before CAPI setup.
After native CAPI readiness, create-only Flux reconciliation saves a separate
random nonce for each exact resource before its POST, observes before retry,
records native UIDs, and rejects copied public markers, foreign objects, deleted
owned objects, changed RBAC/controller authority, stale generations and CRD
readiness failures. A timeout remains unknown until observed; a successful POST
is never readiness. Both CAPI and Flux must be observed ready before the existing
bootstrap completion gate can close SSH transport. Completed inspection uses the
protected management API credentials and cannot reopen SSH.

Design and official references are in `management/DESIGN.md`; operation and
recovery are in `management/README.md`. No default remote ServiceAccount is invented
before workload namespace/SA bootstrap. The internal central plane requires denied
tenant direct Flux writes; native egress NetworkPolicy does not itself establish
air-gap policy. Future remote least-privilege SA bootstrap remains explicit.

Meaningful negative tests cover stale generation, absent CRD establishment, delayed
namespace activation, wrong API namespace/type, foreign/copy-marker races, ambiguous
POST completion, stable intent retry, UID replacement/deletion, changed controller
images/args, extra containers/host authority, aggregate RBAC injection, and missing
or mismatched OCI SBOM/provenance subjects. Existing bootstrap cleanup/interruption
and package tests continue to pass. Unrelated branch Java/UI/License jobs were
canceled to avoid duplicate work; no repository-wide RAT pass is claimed.

Actual Rocky three-node bootstrap, native Flux installation/restart, namespace
negative tests, qualified catalog/operator/package reconciliation, stateful E0
storage/recovery, release signing and authorized GUI acceptance remain required.
No DBaaS/APaaS or whole-product production claim follows from this build.

Recovery: preserve the same approved bundle digest and private journal; observe
before retry. Do not overwrite/adopt resources, retarget a journal to another
bundle, reopen completed transport, or blindly uninstall CRDs. Before any live
installation, source rollback is an isolated revert; after installation, any
version/ownership migration needs explicit operator scheduling.

Root owns shared Ledger/Knowledge Graph integration: connect management bootstrap
→ immutable provider/Flux bundle → central remote project package resources →
separate stateful/live qualification gates, with this evidence as the source link.
