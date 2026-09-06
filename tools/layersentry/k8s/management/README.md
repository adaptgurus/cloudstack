# First management provider bundle

This path installs the selected native CAPI controllers after first-plane RKE2
formation. It is restricted to a designated disposable lab and a `CI_VERIFIED`
bundle. It does not certify a production release, qualify a node image, activate
CloudStack CCM, or complete DBaaS/APaaS acceptance.

The public input lock fixes CAPI/clusterctl 1.13.5, CAPRKE2 0.25.2, downstream
CAPC 0.6.1, cert-manager 1.21.1 and the already built downstream CCM candidate.
Flux 2.9.5 supplies source 1.9.5, kustomize 1.9.5 and helm 1.6.4.
All eleven image indices and all release assets are immutable. CAPC retains its
native v1beta1 contract metadata. The bundle includes complete OCI archives,
native local provider repositories, reviewed central Flux JSON and exact clusterctl
and Flux executables. Flux export uses embedded manifests with no runtime download.

The hosted qualification workflow builds this bundle from public inputs,
verifies every OCI blob/descriptor, generates each provider using native
clusterctl, regenerates the exact minimal Flux export, checks its runtime-bound
OCI SBOM/provenance (without claiming signature verification), and imports/reimports every archive into an isolated instance of
the exact RKE2 containerd runtime. Only those successful checks promote the
candidate bundle from `SOURCE_COMPLETE` to `CI_VERIFIED`. The artifact includes
`qualification.json` and `management-provider-bundle.tar`; its retention is 14 days. Copy it into
approved durable artifact storage before expiry. This qualification is
unsigned; no runtime credentials or deployment inputs are included.

Verify the retained tar SHA-256 against `qualification.json`, then extract it
with file modes preserved into the approved artifact directory. Its `bundle/`
directory includes executable clusterctl and Flux. The artifact ZIP itself does not
preserve Unix executable modes, which is why the complete bundle is inside a tar.

Add the following object to the existing protected bootstrap runtime config,
using the SHA-256 of the exact downloaded `bundle/bundle.json` from the successful
workflow evidence:

```json
{
  "providerBundle": {
    "directory": "/opt/layersentry/management-provider-bundle/bundle",
    "sha256": "EXACT_64_HEX_MANIFEST_SHA256_FROM_QUALIFICATION",
    "qualificationEnvironment": "disposable-lab"
  }
}
```

This is an operator input example, not a usable digest. Files must be regular,
without links, owned by root or the operator, and not writable by group/others.
The existing signed, live-qualified node-image attestation gate still applies.
No unsigned image or release gate is bypassed by selecting a lab environment.

Repeat the existing `bootstrap_management.py reconcile --config ...` command.
After formation and protected kubeconfig export, each reconcile first observes
the existing state and stages at most one missing OCI archive across the three
nodes. Transfers reuse the exact owned public SSH forwarding and QGA host-key
pinning. Native containerd imports retain index names and verify digest identity.
The journal binds the bundle before mutation; changed bundles cannot resume the
same bootstrap. Repeating an interrupted import uses the same immutable bytes.

Once all three nodes contain every image, native clusterctl installs through
the protected kubeconfig using local repositories and exact provider versions.
Its output is never journaled. A timeout is `UNKNOWN`, followed by native state
observation before any reentrant install. Foreign inventories, namespace
ownership, image/version drift and changed CRD contracts block execution.
Installed but unhealthy controllers remain pending; no automatic destructive
repair or uninstall occurs.

Completion requires observed native provider inventory, established expected
CRDs, exact controller image identities and current-generation ready replicas.
Central Flux then creates at most one reviewed native object per reconcile. All
objects carry bundle/nonce ownership annotations; the journal records observed
UIDs. It rejects foreign objects, changed permissions/args/images, extra containers,
deleted objects, stale deployment generations and unestablished CRDs. Namespace
and CRD readiness precede controllers. API timeouts remain unknown until observed,
and create-only retries cannot overwrite an existing object. Both CAPI and all
three Flux controllers must be observed ready before credential escrow is marked
complete and temporary SSH is cleaned up.

Central Flux resides in layersentry-flux-system and reconciles approved project
resources remotely with same-namespace CAPRKE2 kubeconfig Secrets. Cross-namespace
source references and remote Kustomize bases are denied; optional controllers,
tenant aggregate roles and the management cluster-admin binding are removed.
Default remote ServiceAccount impersonation is intentionally absent until a
workload SA bootstrap exists. Customer direct Flux CRD writes must remain denied.
NetworkPolicy retains native controller egress and does not prove Internet denial.

Later inspection uses only the protected API credentials and cannot reopen SSH.
An older completed journal without provider proof stays pending for an explicit
operator migration; it does not silently create a new transport.

Run source qualification with:

```bash
PYTHONPATH=tools/layersentry/k8s python3 -m unittest discover -s tools/layersentry/k8s -p 'test_*.py' -q
```

Actual Rocky three-node formation, controller reconciliation, failures/recovery,
release signing, durable catalog integration and GUI acceptance remain required
before production readiness can be reported.
