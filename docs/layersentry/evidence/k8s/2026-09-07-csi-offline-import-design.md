# CSI offline import qualification design

Status: CI_VERIFIED for the explicitly bounded import/reimport scope below. No live-node, CSI storage or production certification. Extends native renderer `1954066979` without changing service, UI, management installer or release gates. The airgap alternative accepts independently verified local runtime preloading; registry publication is a separate capability, not evidence that preloading failed.

Use the exact official digest-pinned RKE2 runtime and executable hashes already qualified for the management-provider artifact. Start only an isolated GitHub-hosted containerd daemon with private socket/root/state, no CRI workload execution. Reuse original successful CSI OCI/attestation bytes and verified sidecars; import twice with native `--local --digests --all-platforms`, record exact runtime target descriptors and original index bindings. Retain cleanup and bounded public evidence. Do not use a lab socket, start pods or invoke CloudStack.

Exact upstream containerd source confirms only top-level OCI descriptors become named images. Original CSI archives therefore need a supplemental runtime-selector envelope to create a runtime-qualified local name without pointing that name at the attestation index. The envelope retains the original index and all original blobs; its own archive hash is separate. This was resolved before hosted dispatch, rather than interpreting an index/runtime mismatch as success.

Local validation at implementation: exact runtime executable hashes match existing retained RKE2 evidence; source tests exercise runtime-vs-index mismatch, missing/changed local names, original-archive preservation, exact runtime envelope descriptors and refusal outside the hosted environment. Live preload, CRI image visibility, CloudStack node/project identity, storage lifecycle and data survival remain unverified gates.

Primary behavior: [containerd v2.3.4 import implementation](https://github.com/containerd/containerd/blob/v2.3.4/client/import.go), [native ctr import flags](https://github.com/containerd/containerd/blob/v2.3.4/cmd/ctr/commands/images/import.go). Actual qualification uses the pinned RKE2 containerd binary, not an upstream substitution.


## Hosted result

[Run 34060514601](https://github.com/adaptgurus/cloudstack/actions/runs/34060514601) passed at exact source `234b76f2ed320968ece48689d0f28a6bb1ddc89d`. All 23 focused tests passed with locked PyYAML 6.0.2 and checksum-pinned Helm 3.18.6. Native RKE2 containerd `v2.3.4-k3s1.36 b92ab05c7f4bfac0033a4ce560c5698bfb2b26c9` imported and reimported all seven images; runtime name-to-descriptor equality passed both rounds. The two original CSI index name bindings and content digests also passed. Cleanup confirms the private daemon stopped. No container workload, CloudStack API, lab VM or existing runtime was touched.

Artifact `9997317899` has ZIP SHA-256 `f1d53616b822348d041fca7cf228816db5f56407d33668c16653bf97ab199b61`, size 165,226,658 bytes and expiry 2026-09-20T21:16:23Z. Its ZIP was downloaded and independently hashed; extracted public evidence is at `/tmp/layersentry-csi-native-qualified`, with the ZIP at `/tmp/layersentry-csi-native-34060514601.zip`. Exact receipt and artifact metadata are committed in `2026-09-07-csi-offline-import-receipt.json`. The native rendered manifest digest remains `5adcfb004bfafa92ae6b0da641cba79448e80e510ac2f50598b3e863ecff775b` under both local and hosted parser versions.

The independent repository License Check 34060514519 failed with 315 unapproved files, including existing LayerSentry files and newly authored/vendored files. That result is preserved as unresolved release evidence. Under the product IP policy, source is not assigned ASF contribution headers or relicensed to satisfy the checker; exact vendor bytes and licenses remain intact. No shared Maven exclusion or license waiver was introduced.

This CI result permits review of an airgap preload mechanism; it does not establish installed CSI or data safety. Registry references remain null, and signature, node identity, credentials/project scope, live CRI/preload, lifecycle, resize, Machine data survival and production gates remain false.
