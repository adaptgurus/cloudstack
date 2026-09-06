# Downstream CAPC and CCM hosted build qualification

Status: **CI_VERIFIED for exact build artifacts and component manifests**. Live
provider installation/reconciliation, production certification and artifact
signing remain **NOT_TESTED / false**. Repository-wide RAT licensing findings
remain unresolved; this task adds no new license declaration or release flag.

[Hosted run 34050386205](https://github.com/adaptgurus/cloudstack/actions/runs/34050386205)
passed both provider jobs at LayerSentry source
`6162cc1e40afebd56edbd42cff7325fb2abc5d05`. Exact artifact IDs, ZIP/OCI checksums,
index/runtime/config digests, attestation digests and component YAML checksums
are recorded in the adjacent JSON evidence file.

The build uses CAPC v0.6.1 at `7521b14a31e6c46f81f16aae3738a27c08ad063f`
and CCM v1.2.0 at `4740dbcacc7fc5892354b03b2f0be7ebf5c92584`, applying
verified existing LayerSentry endpoint/volume-ownership and Kubernetes 1.36
compatibility overlays. Compiler, runtime, BuildKit, Buildx and SBOM scanner
inputs are pinned in the qualification source. No provider API credentials,
lab addresses, production secrets or registry publishing are used.

Qualification performed:

- CAPC's offline cloud mock suite (`!integ`, with the exact upstream fixture
  root), static manager compilation and upstream-pinned Kustomize v5.4.3 build.
- CCM's mock Go unit suite, static binary compilation and exact version smoke.
- Non-root, network-disabled, read-only container smoke for both images.
  CAPC's exact upstream pflag implementation returns exit 2 for `--help`;
  the gate checks that exit code, expected usage and provider flags explicitly.
- Retained OCI archives with SBOM and provenance; all blob digests, descriptor
  sizes, runtime architecture, entrypoint, non-root identity, smoke-image config
  identity and attestation subjects verified. Downloaded archives were verified
  independently again using the same strict local checker.
- CAPC YAML rendered from patched source, including all three versions of
  `ownedDataDiskID` and `rke2SupervisorLoadBalancerRuleID`; finite audited
  provider defaults replace all runtime text placeholders. CCM retains its
  upstream RBAC and native `cloudstack-secret` reference without secret data.
- Each component YAML binds the actual named OCI **index digest**, preserving
  runtime/SBOM/provenance identity. Runtime image and config digests are recorded
  separately. Downloaded YAML checksums and image references were verified.

The archives and manifests are in the two linked run artifacts. On each
scheduled management node, import the approved archive using the node's native
containerd CLI in namespace `k8s.io`, with `images import --all-platforms
--digests --base-name layersentry.local/<component> <component>.oci.tar`, and
verify that the exact index-digest image reference exists before installation.
An approved mirror may instead preserve that index digest and explicitly update
only the repository part of the bound image reference. No registry is created
or published by this build task.

CAPI core, CAPRKE2, cert-manager and scoped provider credentials must be installed
through the separately approved management-plane installer. CAPC v0.6.1's exact
upstream `metadata.yaml` advertises the v1beta1 provider contract; do not relabel
it as v1beta2 without an implemented and verified contract migration. This
handoff does not assert live CAPI/CAPC/CAPRKE2 compatibility or activate CCM.

Earlier causal failures are preserved in GitHub: run 34049713368 failed CAPC
mock setup because `REPO_ROOT` was missing; run 34049959713 produced the CAPC
image but the original smoke gate wrongly expected `--help` exit 0. Those
causes were corrected and the full pipeline passed at run 34050221874. The
final run above additionally verifies the named OCI index binding.

Artifacts are unsigned and GitHub retention is 14 days, with exact expiration
in JSON. They are reviewable build evidence and candidate installation inputs,
not a durable production release. Real Rocky formation, provider reconciliation,
LB/disk ownership, failover/upgrade/security and GUI evidence remain required.

Integration handoff: source commits `a4fdea0d1e`, `80d63efc3b`, `35026cd770`,
`6162cc1e40` on isolated branch `codex/k8s-provider-artifact-qualification`.
Management bootstrap correction is separate commit `3ac3248c17` on base
`0857b44a09`, with 114 full E source tests passing. No lab or integration-branch
mutation occurred in this provider qualification task.
