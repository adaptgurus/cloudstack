# First management provider installer qualification

Status: `CI_VERIFIED` for source, immutable bundle assembly, native provider
generation and isolated containerd import/reimport. Live provider installation
is `NOT_TESTED`; production certification remains `BLOCKED`.

Source commits, in order: `709d593466d75b85f6a3834091538b3f7e450648` then
`87cc2c84ef7126dc47cb44630c388c3bc02c838c`, based on combined root `91a0b9da0d`.
[Hosted run 34052983062](https://github.com/adaptgurus/cloudstack/actions/runs/34052983062)
passed at the second commit. All 142 E source tests passed on the hosted runner;
the local run passed with one existing environment-dependent skip.

## Implemented lifecycle

The existing native three-node RKE2 bootstrap now requires an exact provider
bundle before credential escrow completion and temporary SSH cleanup. Image
staging uses the existing native forwarding, QGA-pinned guest host key and
strict operator SSH transport. It imports at most one missing archive per
reconcile and observes all three nodes before proceeding. Bundle digests are
durably bound to the bootstrap journal; ambiguous native VM submissions retain
the existing no-replay rule.

After all image names/digests are present, pinned native clusterctl uses local
repositories, protected management kubeconfig and exact CAPI 1.13.5,
CAPRKE2 0.25.2, downstream CAPC 0.6.1 and cert-manager 1.21.1 versions. A process
exit is not readiness. Completion requires native provider inventory, unchanged
CRD served contracts, exact controller images and current-generation ready
replicas. Interrupted install is observed before reentrant native installation;
foreign resources, version/image drift and changed journal bindings block.
Completed inspection cannot reopen temporary SSH.

CAPC's v1beta1 metadata remains unchanged. The exact downstream CCM artifact is
included for complete image staging but is not activated. The unsigned bundle
installer only accepts the explicitly selected disposable qualification
environment. It does not bypass the separate signed/live-qualified image gate.
Runtime credentials are excluded from manifests, journal diagnostics and
artifacts. See the [operator contract](../../../../tools/layersentry/k8s/management/README.md).

## Causal failure and correction

[Initial run 34052790592](https://github.com/adaptgurus/cloudstack/actions/runs/34052790592)
passed source and bundle preparation but failed the strict image name gate.
The exact RKE2 containerd 2.3.4 default transfer path retained downstream
`:qualification` names pointing to the expected image index, but generated
digest names for the archive wrapper indices. It omitted both required CAPC
and CCM digest names. No qualified artifact was emitted by that failed run.

The successful run records the failed default-path names explicitly and then
checks native `ctr images import --local --all-platforms --digests --base-name`
for all eight archives twice. Both native local passes preserve the exact
expected index names. The executable guest installer now uses that same local
path. Older provider archive handoffs that omit `--local` need this correction
for the selected RKE2 runtime. This follows the exact
[containerd import implementation](https://github.com/k3s-io/containerd/blob/v2.3.4-k3s1.36/cmd/ctr/commands/images/import.go);
the digest gate was retained.

The retained bundle uses an inner tar because artifact ZIP transport discards
executable permissions. The tar preserves the pinned clusterctl executable,
and only the manifest-listed public files are included. Unit coverage checks
that unlisted files cannot enter this artifact. Native clusterctl generation
checks all four local repositories against expected controller identities and
immutable image references.

## Retained artifact and limits

[Artifact 9995125313](https://github.com/adaptgurus/cloudstack/actions/runs/34052983062/artifacts/9995125313)
contains `management-provider-bundle.tar` and `qualification.json`, with 14-day
retention through 2026-09-20. Its exact identities and native import evidence
are recorded in the adjacent JSON checkpoint. Copy verified bytes into approved
durable artifact storage before expiry; no public registry push was performed.

The bundle manifest SHA-256 is
`9b9c3e0f2aeb81b42866e06e58bb9315ea5c269ddbc4a8d38ab52167fcb81fe5`.
The artifact ZIP SHA-256 is
`4da85c8fc529aea69aa35f203560be519962dd28154f67130af13aa8300f9f3d`.

This hosted evidence does not prove a live Kubernetes API/controller install,
CRI pod startup, CloudStack credentials/reconciliation, Rocky formation,
independent host failure tolerance, Flux installation, release signing or
customer GUI acceptance. No DC/DR VM, KVM host, storage, network or management
cluster was mutated. Source integration owns the shared ledger/graph checkpoint
and subsequent approved live acceptance. DBaaS/APaaS remain separate gates.
