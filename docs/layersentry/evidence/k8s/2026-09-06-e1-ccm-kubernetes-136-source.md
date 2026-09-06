# E1 CloudStack CCM Kubernetes 1.36 source qualification

**Date:** 2026-09-06  
**Implementation:** `54121666698fde9e716bb3041ccf051a71e26726`  
**Status:** source build `SOURCE_COMPLETE`; runtime compatibility `NOT_TESTED`  
**Runtime mutation:** none

## Current approach

LayerSentry retains the Apache CloudStack Kubernetes Provider/CCM as the owner
of supported Kubernetes `Service` type `LoadBalancer` reconciliation. The
exact released `v1.2.0` commit
`4740dbcacc7fc5892354b03b2f0be7ebf5c92584` remains the upstream base. A
digest-pinned downstream overlay updates its build contract from Kubernetes
libraries `v0.24.17` to `v0.36.0`, which matches the Lane B Kubernetes `1.36`
minor, without adding a competing controller or changing Apache CloudStack.

The overlay:

- updates the module/toolchain to Go `1.26.0` and Kubernetes `v0.36.0`;
- removes legacy replacement directives that force controller-manager,
  helpers and other modules back to `v0.24.17`;
- supplies the controller-alias argument required by the current Kubernetes
  cloud-controller-manager command API;
- fixes a non-constant logging format rejected by the current toolchain;
- records the fully resolved `go.mod` and `go.sum` dependency graph;
- pins the Docker build inputs to immutable manifest digests:
  `golang@sha256:fb612b...047b84` and
  `distroless/static@sha256:1c2c04...e5bbc7`.

Overlay SHA-256:

`a6689998f2a46b9622ac69f97f8e67e231f075ffa8cca16a85a97fd0f4893726`

## Logical/source validation

The official repository has no newer CCM implementation beyond `v1.2.0` at
this checkpoint; current `main` contains that release plus documentation. A
naive dependency bump initially demonstrated two real failures: legacy
replacement directives produced a mixed `v0.24`/`v0.36` graph, and the CCM
command call lacked the new controller-alias parameter. Removing the mixed
graph and making the narrow API adaptation produced a clean exact-source test
run.

Fresh materialization from the pinned upstream commit returned `APPLIED`, the
patched tree passed `go test ./...`, and a second materializer run returned
`ALREADY_APPLIED`. The common materializer now accepts both normal clones
(`.git` directory) and isolated Git worktrees (`.git` control file), while the
authoritative `git rev-parse HEAD` pin remains mandatory.

## Advantages and disadvantages

This keeps the supported ownership model and aligns compile-time Kubernetes
interfaces to the selected minor. The resolved module graph and immutable
base-image inputs make CI builds reproducible enough to generate a final
signed image digest.

Compilation does not establish behavioral compatibility. The CCM still needs
real Kubernetes `1.36` leader election, node initialization, CloudStack
provider-ID, public-IP, VPC/network, source-CIDR and complete create/update/
delete/restart `LoadBalancer` lifecycle tests. The broader dependency jump
also requires vulnerability/license/SBOM review.

## Alternatives

Using the upstream v0.24-linked binary was rejected because the selected
Kubernetes minor is 1.36. Replacing CCM with LayerSentry code was rejected
because CloudStack CCM remains the proper owner. Moving the whole product back
to Kubernetes 1.24 was rejected because it contradicts the pinned Lane B
contract. A future official CCM release may supersede this overlay only after
the same evidence matrix passes measurably better.

## Rollback, risks and production status

The overlay is opt-in and the release candidate still has
`kubernetes136Qualified=false` and no final CCM image digest. Rollback selects
the unmodified upstream commit in a non-production research build; it does not
authorize deploying the old binary on Kubernetes 1.36. No live CloudStack or
Kubernetes resources changed.

Risks include API behavior changes, dependency vulnerabilities, LB leakage
and failed cleanup. Mitigations are the immutable overlay, fail-closed release
gate, CloudStack-authoritative resource observation, destructive LB lifecycle
tests, signed image/SBOM/provenance and rollback evidence. Those tests remain
`NOT_TESTED`; this is not `CI_VERIFIED`, `LIVE_VERIFIED` or
`PRODUCTION_CERTIFIED`.
