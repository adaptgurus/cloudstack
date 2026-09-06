# CSI offline import qualification design

Status: SOURCE_COMPLETE; hosted execution is NOT_TESTED at this source checkpoint. Extends native renderer `1954066979` without changing service, UI, management installer or release gates. The airgap alternative accepts independently verified local runtime preloading; registry publication is a separate capability, not evidence that preloading failed.

Use the exact official digest-pinned RKE2 runtime and executable hashes already qualified for the management-provider artifact. Start only an isolated GitHub-hosted containerd daemon with private socket/root/state, no CRI workload execution. Reuse original successful CSI OCI/attestation bytes and verified sidecars; import twice with native `--local --digests --all-platforms`, record exact runtime target descriptors and original index bindings. Retain cleanup and bounded public evidence. Do not use a lab socket, start pods or invoke CloudStack.

Exact upstream containerd source confirms only top-level OCI descriptors become named images. Original CSI archives therefore need a supplemental runtime-selector envelope to create a runtime-qualified local name without pointing that name at the attestation index. The envelope retains the original index and all original blobs; its own archive hash is separate. This was resolved before hosted dispatch, rather than interpreting an index/runtime mismatch as success.

Local validation at implementation: exact runtime executable hashes match existing retained RKE2 evidence; source tests exercise runtime-vs-index mismatch, missing/changed local names, original-archive preservation, exact runtime envelope descriptors and refusal outside the hosted environment. Live preload, CRI image visibility, CloudStack node/project identity, storage lifecycle and data survival remain unverified gates.

Primary behavior: [containerd v2.3.4 import implementation](https://github.com/containerd/containerd/blob/v2.3.4/client/import.go), [native ctr import flags](https://github.com/containerd/containerd/blob/v2.3.4/cmd/ctr/commands/images/import.go). Actual qualification uses the pinned RKE2 containerd binary, not an upstream substitution.
