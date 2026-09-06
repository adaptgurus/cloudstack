# Native CSI review bundle

Status: `SOURCE_COMPLETE`. This is an offline render and artifact collection path, not an installer or deployment approval. It never runs Helm install, kubectl, a controller, a registry push or a live CloudStack command. `release-candidate-lane-b.json` retains `image: null`; all qualification flags remain false.

## Produce the review bundle

Use Python 3 with the repository's PyYAML dependency. Download the exact Helm archive in `inputs.lock.json` from the official URL, check its SHA-256 before extracting, and check the extracted binary SHA-256. The renderer independently rejects another Helm binary. It uses only the vendored chart, fixed values and a private empty Helm environment; it does not fetch chart dependencies or load user plugins/configuration.

```bash
python3 tools/layersentry/k8s/downstream/cloudstack-csi/native/render.py \
  --helm /private/tools/helm \
  --output /private/review/csi-native
```

The new output directory contains `review-manifests.yaml` and `bundle.json`. The 16 objects are native Namespace, ServiceAccounts, ClusterRoles/Bindings, lease Role/Binding, CSIDriver, controller Deployment and node DaemonSet. All workload images use exact linux/amd64 runtime digests. The retained driver has **no published reference**: `registry.invalid` is a planned local runtime alias, not a published reference. Before an installer can consume these manifests, the trusted runtime owner must establish either exact preloading on every workload node or a publication binding that preserves the retained index/SBOM/provenance and independently confirms destination digests. The hosted offline qualification below verifies the preloading mechanism; actual node preloading and the remaining E0 gates are separate. Editing `deployable` cannot establish this evidence.

The chart is byte-identical to upstream commit `a84477e922d62b82387ab55134fafc9c0b5aaf64`. The limited overlay pins image references, restricts credentials to one read-only Secret key and narrows cloud-init metadata to one read-only file. Chart version 3.0.2 has appVersion 3.0.0; checked digest replacement prevents its default image tag from selecting different bytes. There is no user-supplied chart, values, API key, join credential or project identity input.

## Collect immutable image bytes

Retrieve the exact successful GitHub artifact identified in adjacent `artifact-lock.json`; preserve both OCI archives and their `*-inspect.json` evidence. No rebuild is required. Then:

```bash
python3 tools/layersentry/k8s/downstream/cloudstack-csi/native/prepare_images.py \
  --artifact-directory /private/retained-csi-artifact \
  --output /private/review/csi-images
```

This copies and verifies the unchanged driver/syncer full OCI indexes, SBOM and actual unsigned SLSA source predicates against the approved lock. It reads only digest-addressed HTTPS blobs from the primary sidecar registry; downloads enforce size, digest and time bounds and reject plaintext redirects. Each sidecar archive contains its selected amd64 runtime, config and exact layers. Checks cover compressed layer digests and config `rootfs.diff_ids`. The original primary multi-platform indexes, signature-manifest probes and Kubernetes promotion file are retained separately as public metadata: a selected-platform archive is **not** represented as a complete multi-platform publication. The completion receipt `images.json` is written last; a partial directory without that receipt is incomplete. No credentials are accepted; no archive is imported or published.

Sidecars remain the exact chart versions: provisioner v5.0.1, attacher v4.6.1, resizer v1.11.1, livenessprobe v2.12.0 and registrar v2.10.1. Registry tag/index/runtime/config consistency and the pinned Kubernetes image-promotion mapping are verified. Cosign signature manifests were found but signature payloads, trust identity, transparency evidence and provenance were **not** cryptographically verified. Their availability is not certification. The historical version selection is not proof of compatibility with Kubernetes 1.36.

## Installation gates and boundaries

- One workload cluster must bind to one native CloudStack project. CSI acts cluster-wide; a tenant namespace is not a CloudStack project security boundary. The trusted runtime must verify the actual Secret's `global.project-id`, HTTPS endpoint, API permissions and native VM/project ownership before applying anything. No root/admin-wide key or caller-supplied identity is allowed.
- `layersentry-cloudstack-csi` must be platform-owned and tenant-nonwritable. Its privileged Pod Security setting is required by the native node driver's host device/kubelet mounts; never grant tenants Pod creation, Secret read or ServiceAccount impersonation there. The upstream node role can patch Nodes; this is trusted platform access. No wildcard or Secret API permission is granted. Existing cluster-scoped CSI/RBAC objects require exact ownership checks; do not adopt or replace an unrelated installation. Controller affinity requires at least two schedulable control-plane nodes.
- The only credential mount is existing Secret `cloudstack-project-credentials`, key `cloud-config`, mode 0440 and read-only. No Secret is emitted. No storage-class syncer Job or syncer RBAC is emitted, including suspended Jobs. Its image is inventory-only. No StorageClass, default class, PVC or application is created; resize capability still requires its separate qualified lifecycle gate.
- Native CSI reads `/run/cloud-init/instance-data.json`, requiring `v1.cloud_name` equal to `cloudstack` (case-insensitive), and uses `v1.instance_id` as native VM UUID. The image permits `[CloudStack, NoCloud, None]`; neither the bootstrap userdata nor a NoCloud fixture proves the CloudStack datasource result. Before starting CSI, require completed cloud-final and each real workload node's metadata UUID matching its CloudStack VM, project, Machine and Node binding. The read-only file bind must occur after cloud-final to avoid a stale inode. Never inject `NODE_ID` or fabricate providerID; do not treat the native VM-name fallback as project-scoped identity proof.
- The expected kubelet root is `/var/lib/kubelet`; the trusted runtime must confirm the exact RKE2 workload configuration, mount propagation, Rocky SELinux behavior, service-account/PSA admission, registry authentication and Secret access before applying. The renderer does not change host SELinux policy or network policy.
- Live CSI install, project isolation, PVC create/attach/detach/delete, safe retries, expansion and Machine replacement data survival remain false gates. DBaaS/APaaS stateful qualification must wait for E0 survival. No source test or artifact hash can satisfy those gates.

## Verify

```bash
LAYERSENTRY_TEST_HELM=/private/tools/helm python3 -m unittest discover \
  -s tools/layersentry/k8s/downstream/cloudstack-csi/native -p 'test_*.py' -v
```

Tests run real pinned Helm rendering twice, check exact scoped resources, and reject chart/tool/metadata drift, unpinned images, namespace/RBAC escapes, unexpected syncers/storage/Secrets, changed credential references, writable metadata, forged node IDs and platform drift. Archive tests reject corrupt/oversized downloads, downgraded redirects and false uncompressed layer identities. Without `LAYERSENTRY_TEST_HELM`, rendered-manifest tests explicitly skip; such a run alone is not render evidence.

Primary sources: [exact CSI chart](https://github.com/cloudstack/cloudstack-csi-driver/tree/a84477e922d62b82387ab55134fafc9c0b5aaf64/charts/cloudstack-csi), [native metadata parser](https://github.com/cloudstack/cloudstack-csi-driver/blob/a84477e922d62b82387ab55134fafc9c0b5aaf64/pkg/cloud/metadata.go), [pinned promotion mapping](https://github.com/kubernetes/k8s.io/blob/1ef244cd3da91d917effac12cebdf0d5ef22410e/registry.k8s.io/images/k8s-staging-sig-storage/images.yaml), [Helm tool release](https://github.com/helm/helm/releases/tag/v3.18.6). Full content hashes are in `inputs.lock.json` and `registry-evidence/`.

## Separate offline preload qualification

`qualify_offline.py` and `.github/workflows/layersentry-csi-native-qualification.yml` qualify local image naming on a disposable hosted runner only. This is an independent route for an airgap lab: registry publication is not required when each workload node has independently verified exact preloaded runtime descriptors and the native manifests retain `IfNotPresent`. `registry.invalid` names are local runtime aliases, never published references. The shared `image: null`, signature, live-node and production gates remain unchanged.

The harness verifies the original successful GitHub run/source/workflow/artifact ZIP binding, reuses both existing CSI images, fetches only locked sidecar layers, and checks the exact RKE2 v1.36.4+rke2r1 containerd/ctr/runc/shim binaries against retained hashes. It starts a private containerd socket/root/state directory with CRI disabled, imports all seven image archives using `--local`, checks runtime name-to-descriptor equality, then repeats the imports and checks equality again. No pod, API, VM, lab daemon or registry push is involved.

Containerd's native importer creates digest names for top-level descriptors. Original CSI archives have the attestation index at top level. A supplemental runtime-selector envelope exposes the existing runtime descriptor alongside that unchanged index; it changes only the outer OCI layout index, preserves every image blob and never overwrites the original archive. Both original index names and runtime names must resolve to their own exact digests. A name ending in a runtime digest but pointing to the attestation index is rejected. The source archives and supplemental envelope hashes remain distinct evidence.

The native manifests use `IfNotPresent`. Before a real airgap test, the integration owner must verify these exact local names on **every** selected workload node, confirm CRI observes the imported images, bind the real node/project/Secret prerequisites, then deploy under the live reservation. Hosted imports do not prove CRI pod execution, SELinux, attach/mount, PVC survival or a production supply-chain trust gate. No shared installer code is changed by this harness.

Hosted offline qualification passed on source `234b76f2ed320968ece48689d0f28a6bb1ddc89d`: [run 34060514601](https://github.com/adaptgurus/cloudstack/actions/runs/34060514601). Its exact receipt is retained in `docs/layersentry/evidence/k8s/2026-09-07-csi-offline-import-receipt.json`. This is CI verification of image import/reimport only. The repository-wide RAT license check failed and remains unresolved; no license headers, vendor bytes or shared exclusions were changed to conceal that result.
