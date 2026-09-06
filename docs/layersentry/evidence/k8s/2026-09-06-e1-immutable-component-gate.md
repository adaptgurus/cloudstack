# E1 immutable CCM/CSI/Flux component gate

**Date:** 2026-09-06  
**Implementation:** `20f2336c93ea4ef57d70717261faf9f9ef6c7688`  
**Status:** validation source `SOURCE_COMPLETE`; deployable tuple `BLOCKED`  
**Runtime mutation:** none

## Current approach

The Lane B release candidate now records the exact CloudStack CCM source as
`v1.2.0` commit `4740dbcacc7fc5892354b03b2f0be7ebf5c92584`, the already pinned
downstream CloudStack CSI source/patch, and the central Flux catalog fields.
The component validator rejects deployment unless:

- every Lane B version remains exact;
- CAPC and CSI source/patch digests remain exact;
- CCM and the downstream-patched CSI are immutable `@sha256` images;
- CCM is explicitly qualified against Kubernetes `1.36`;
- CSI project lifecycle and resize idempotency are live-qualified;
- Flux has an HTTPS repository, exact 40-character commit and verified content;
- the four E1 runtime evidence gates are true.

The repository manifest deliberately leaves the unresolved image/catalog
fields null and every runtime gate false, so it is not deployable.

## Exact source findings

The official Apache CloudStack Kubernetes Provider tag `v1.2.0` resolves to
commit `4740dbcacc7fc5892354b03b2f0be7ebf5c92584`. Its checked-in deployment
uses `apache/cloudstack-kubernetes-provider:v1.2.0`; its module is compiled
against Kubernetes libraries `v0.24.17`. The Lane B candidate targets
Kubernetes `1.36.x`. Exact-source `go test ./...` passed locally, but that does
not prove compatibility across this Kubernetes version skew or L4
LoadBalancer reconciliation on RKE2 `1.36`.

CloudStack CSI `3.0.2`'s chart metadata reports `appVersion: 3.0.0`, and its
raw manifests still use mutable `main` driver tags. LayerSentry therefore must
publish the already patched downstream source as its own verified immutable
image; an upstream mutable tag cannot represent the LayerSentry resize fix.

## Advantages and disadvantages

The gate prevents source-only success, mutable tags or an upstream image that
lacks the LayerSentry patch from silently becoming a production deployment.
It also gives offline and connected releases one exact artifact contract.

The disadvantage is that E1 remains blocked until Workstream B publishes the
downstream images and real compatibility tests pass. That delay is preferable
to installing an unqualified storage/network controller in a stateful product.

## Alternatives considered

- Deploying the official tag immediately was rejected because it is mutable
  in the manifest and CCM's Kubernetes 1.36 compatibility is unproven.
- Deploying the upstream CSI release was rejected because it does not contain
  the LayerSentry downstream idempotency overlay.
- Reimplementing CCM was rejected; CloudStack CCM remains the selected owner,
  subject to qualification.
- Embedding package YAML in the BFF was rejected; central Flux remains package
  authority and must consume an immutable catalog revision.

## Risks, mitigations, tests and rollback

Risks are version skew, digest substitution, incomplete CSI behavior and Flux
catalog drift. Exact source IDs, digest-only images, strict JSON duplicate-key
rejection, bounded release-file permissions and explicit evidence booleans
mitigate them.

All 66 Workstream E Python tests passed locally, including current-candidate
blocking, exact qualified tuple acceptance, version drift, mutable image,
duplicate JSON key and writable-manifest rejection. Official CCM exact-source
`go test ./...` also passed. No container build, SBOM, signature, admission,
Kubernetes 1.36 CCM run, CSI lifecycle, Flux apply or Rocky test ran.

Rollback is removal of the new opt-in validator/fields; because the current
manifest is deliberately non-deployable, this milestone made no runtime
change. Production status remains `BLOCKED`, not `CI_VERIFIED` or
`LIVE_VERIFIED`.
