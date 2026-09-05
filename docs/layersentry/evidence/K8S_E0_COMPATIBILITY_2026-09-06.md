# Kubernetes E0 compatibility checkpoint

Status: `PARTIAL`. Source/documentation audit only; no controller build, cluster deployment or production compatibility claim. Reviewed 2026-09-06 against LayerSentry CloudStack branch baseline `75f2689a7d`. DR ownership is with the dedicated session identified in the runner handoff; this work does not mutate its target or deployment automation.

## Scope and current decision

Retain the selected CAPI/CAPC/CAPRKE2 architecture and CloudStack 4.22.1.1 authority. Establish a supported, reproducible controller combination before the E1 managed-cluster implementation. Do not infer compatibility from independently selecting the latest release of each controller. Do not introduce a second native-API cluster orchestrator while this selected path is being qualified.

The current evidence does not select a production tuple. The released CAPC contract is older than the current CAPRKE2 contract, and CAPC's published CloudStack matrix does not include 4.22.1.1. This is a qualification gap, not proof that the providers cannot interoperate: core CAPI documents temporary compatibility with older infrastructure contracts for specified operations.

## Exact source inventory

| Component | Observed release/source | Source finding | Qualification impact |
| --- | --- | --- | --- |
| CloudStack | Required 4.22.1.1 | LayerSentry fixed infrastructure baseline | Test exact release; never substitute 4.20 support evidence |
| CAPC | v0.6.1, commit `7521b14a31e6c46f81f16aae3738a27c08ad063f`, published 2025-07-15 | `metadata.yaml`: v1beta1 contract; `go.mod`: CAPI v1.9.6, Kubernetes libraries v0.31.3 | Library dependency is not a supported deployment matrix; old core v1.9 is EOL and is not selected for production |
| CAPRKE2 | v0.25.2, commit `38602b72a23faf719b94b250eba66ef804bf9706`, published 2026-08-26 | `metadata.yaml`: v1beta2 contract for 0.25; `go.mod`: CAPI v1.13.5, Kubernetes libraries v0.35.4 | Candidate research must assess contract compatibility and exact RKE2 version separately |
| CAPI core | Latest release API returned v1.14.1, published 2026-09-01 | Current support page lists 1.14/1.13 standard support and temporary v1beta1 infrastructure-provider compatibility | Latest does not imply qualified with CAPC; evaluate 1.13 and 1.14 source/behavior before choosing |
| CAPC migration proposal | PR 493, open/unmerged; observed head `242c9ba47d195ed7e15b0961b363329fe7fc73bc` | Proposal migrates to CAPI v1.13.2, provider API v1beta4 and infrastructure contract v1beta2 | Research candidate only; contributor-reported tests are not LayerSentry E2E evidence |

Primary source links: [CAPC pinned go.mod](https://github.com/kubernetes-sigs/cluster-api-provider-cloudstack/blob/7521b14a31e6c46f81f16aae3738a27c08ad063f/go.mod), [CAPC pinned metadata](https://github.com/kubernetes-sigs/cluster-api-provider-cloudstack/blob/7521b14a31e6c46f81f16aae3738a27c08ad063f/metadata.yaml), [CAPRKE2 pinned go.mod](https://github.com/rancher/cluster-api-provider-rke2/blob/38602b72a23faf719b94b250eba66ef804bf9706/go.mod), [CAPRKE2 pinned metadata](https://github.com/rancher/cluster-api-provider-rke2/blob/38602b72a23faf719b94b250eba66ef804bf9706/metadata.yaml), [CAPI support and contract policy](https://cluster-api.sigs.k8s.io/reference/versions), [CAPC migration PR](https://github.com/kubernetes-sigs/cluster-api-provider-cloudstack/pull/493).

## Source and issue findings

The [CAPC published matrix](https://github.com/kubernetes-sigs/cluster-api-provider-cloudstack#compatibility-with-apache-cloudstack-versions) lists tested CloudStack 4.19/4.20 and Kubernetes through 1.32 for provider 0.6. Newer releases may work but are explicitly not established by that matrix.

[CAPC issue 498](https://github.com/kubernetes-sigs/cluster-api-provider-cloudstack/issues/498) is open and reports that enabling `CLOUDSTACK_SYNC_WITH_ACS` includes unrelated VMs in CloudStack Kubernetes inventory. The reporter used CAPC 0.6.1, Kubernetes 1.32.3, Rocky 9 and CloudStack 4.22.0. Treat this as an upstream report, not a reproduced 4.22.1.1 defect. Keep this optional synchronization out of the initial managed-cluster profile pending exact-source review and scoped inventory tests; CAPC ownership must not leak into unrelated resources.

[CAPC PR 485](https://github.com/kubernetes-sigs/cluster-api-provider-cloudstack/pull/485) is open/unmerged and proposes early control-plane LB member removal during Machine deletion. Review the exact released deletion path and test control-plane scale-down/replacement under traffic. Do not inherit the proposed fix or contributor tests into release claims.

Pinned CAPC `pkg/cloud/instance.go` uses `DestroyVirtualMachine` and an expunge choice derived from capabilities; `controllers/cloudstackmachine_controller.go` explicitly uses the administrative client for deletion. This establishes a destructive infrastructure boundary requiring exact CloudStack API/source review and retained-PVC/data-disk tests. It does not establish whether independent CSI volumes are retained or lost.

Historical [issue 420](https://github.com/kubernetes-sigs/cluster-api-provider-cloudstack/issues/420) and [PR 422](https://github.com/kubernetes-sigs/cluster-api-provider-cloudstack/pull/422) were inspected to trace prior core-version migrations. Closed historical issues are not evidence that current provider/core compatibility is solved.

## Alternatives and next gates

1. Evaluate released CAPC 0.6.1 with a supported core and CAPRKE2 using the documented temporary contract compatibility. Benefit: released provider artifacts. Risks: legacy dependencies, incomplete exact-version matrix, conversion/conditions/topology/remediation behavior requiring proof.
2. Review and test the pinned CAPC migration proposal as a minimal experimental downstream candidate. Benefit: aligned current contract. Risks: unmerged API/conversion changes and additional upgrade/rollback burden. Do not deploy the moving PR branch or represent it as an upstream stable release.
3. Keep the specialist native-API fallback deferred. It adds significant custom lifecycle and recovery code and is justified only if the selected CAPC path cannot pass the required gates.

Next evidence required: inspect exact source/CRDs for the two candidates, confirm ClusterClass and RKE2 control-plane/supervisor endpoint integration, research exact RKE2/CNI/CCM/CSI/Flux pins and maintained versions, review remaining high-signal open/closed issues and provider/community material, define the machine-readable release/compatibility schema, build and run local controller/envtest checks, then coordinate a separate non-DR Rocky test environment for create/scale/replace/delete and data-retention tests. No production tuple, node image, package digest or air-gap certification has been invented.

## Validation and continuity

Fetched actual LayerSentry refs, inspected the full Kubernetes specialist contract and Workstream E contract, queried current upstream release and issue/PR metadata, and checked out CAPC/CAPRKE2 release sources at the exact commits above. No source build or runtime test ran. This documentation-only checkpoint requires no VM mutation. CloudStack-core impact: NO. Rollback is reverting the checkpoint documentation; there is no runtime state to restore.

Worktree: `/home/opc/layersentry/k8s-compatibility-foundation`; branch: `codex/k8s-compatibility-foundation`. The audit is intentionally incomplete at the compatibility selection gate and must not be relabeled as E1 implementation or live certification.
