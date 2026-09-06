# E1 downstream CSI container source checkpoint

**Date:** 2026-09-06  
**Implementation:** `1913631225492969e402fd89c39c369814eab5bd`  
**Status:** source `SOURCE_COMPLETE`; deterministic artifact `BLOCKED`  
**Runtime mutation:** none

## Current approach

The exact CloudStack CSI `3.0.2` overlay continues to contain the project-aware
idempotent expansion fix. It now also replaces both CSI Dockerfiles' mutable
base tags with registry-manifest digests:

- builder: `docker.io/library/golang@sha256:383395...380b5f`;
- runtime: `docker.io/library/alpine@sha256:48b030...abc07d`.

The current combined overlay SHA-256 is:

`ad1339342211b63d8c9c9a20994da20c66ae632e03c7ddc1c65d4215bf9c4f58`

The earlier resize-only digest remains historical checkpoint evidence; live
qualification must use the current combined digest.

## Source validation and remaining deterministic-build gap

A fresh isolated worktree at upstream commit
`a84477e922d62b82387ab55134fafc9c0b5aaf64` accepted the current overlay,
the exact patched source passed `go test ./...`, and a second materialization
returned `ALREADY_APPLIED`. The E0 evidence evaluator was updated to require
the current digest.

The final Alpine image executes `apk add` for filesystem/mount/device tools.
Although the Alpine base is immutable, the remote APK repositories and package
selection are not yet content-pinned. Therefore a rebuild could receive a
different package layer. The release contract records
`apkPackageLayerDeterministic=false`; no final CSI image may be published or
deployed by the E1 runtime until Workstream B supplies a content-addressed
mirror/locked package input and then produces digest, SBOM, provenance and
signature.

## Advantages, disadvantages and alternatives

This removes base-tag drift and ensures runtime evidence identifies the
current LayerSentry code overlay. It deliberately exposes, rather than hides,
the remaining package-resolution nondeterminism.

Pinning package version strings against a moving Alpine repository was not
accepted as fully reproducible because packages may be replaced or removed.
Using the upstream published image was rejected because it does not contain
the LayerSentry expansion overlay. A prebuilt, digest-pinned LayerSentry CSI
runtime base or immutable APK mirror is the recommended release solution.

## Failure handling, rollback and status

The component validator blocks startup when the deterministic APK layer,
final CSI digest, project lifecycle, resize idempotency or other E1 gates are
false. Rollback selects the previous source checkpoint for analysis only; it
does not authorize a mutable/upstream image or disable live safety gates.

All 74 Workstream E Python tests and 5 overlay tests passed locally, plus the
exact patched CSI Go suite. No container build, package lock, SBOM, signature,
Kubernetes deployment, PVC lifecycle or Rocky test ran. This is not
`CI_VERIFIED`, `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED`.
