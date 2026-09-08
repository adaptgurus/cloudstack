# Workstream E0 — CloudStack CSI 3.0.2 qualification and resize overlay

**Date:** 2026-09-06  
**Status:** source qualification and downstream overlay `SOURCE_COMPLETE`; CloudStack/Kubernetes lifecycle `NOT_TESTED`  
**CloudStack core impact:** none

## Exact source decision

The qualification candidate remains upstream tag `cloudstack-csi-3.0.2`, commit `a84477e922d62b82387ab55134fafc9c0b5aaf64`, using `cloudstack-go/v2 v2.16.1`.

Source review established that `pkg/cloud/cloud.go` installs `cloudstack.WithProject(config.ProjectID)` as a default option when `global.project-id` is configured. `pkg/cloud/volumes.go` also sets that project ID explicitly on `createVolume`, while snapshot restore carries the project ID returned by the project-scoped snapshot lookup. The exact cloudstack-go helper applies default options to `listVolumes` lookups, and the CSI controller performs those lookups before attach, detach and expansion. These are source findings, not proof against CloudStack 4.22.1.1.

Upstream `ExpandVolume` always issued `resizeVolume`, even after CloudStack already reported capacity at or above the requested GiB. The LayerSentry overlay adds two idempotency guards:

1. the CSI controller returns the observed current capacity and correct node-expansion flag without calling the connector when capacity is already satisfied;
2. the CloudStack connector independently skips `resizeVolume` when rounded current GiB is already at or above the request.

The overlay is pinned by manifest and SHA-256 `64853e92e82f4a6e5e298b9d114a1522aea21d04f84c02e1667079c54d4f9635`. Project PVC auto-grow remains disabled.

That digest identifies the original resize-only source checkpoint. The current
overlay extends the identical resize fix with immutable builder/runtime base
manifest pins and is SHA-256
`ad1339342211b63d8c9c9a20994da20c66ae632e03c7ddc1c65d4215bf9c4f58`.
The Alpine `apk add` package layer still requires an immutable mirror or exact
package lock before a deterministic release build; the final image remains
unresolved and disabled.

## Advantages, alternatives and risks

- The fix is confined to the external CSI provider and preserves CloudStack as storage authority.
- Returning actual capacity follows CSI idempotency semantics and avoids turning a retry into a shrink-like request.
- Relying only on CloudStack accepting a repeated resize was rejected because retry behavior then depends on backend-specific error semantics.
- Source-level project propagation is necessary but insufficient: an actual project account, foreign-project fixtures and CloudStack 4.22.1.1 authorization responses must be tested.
- CloudStack async timeout is ambiguous. A live harness must re-read the exact volume before retrying and prove no duplicate/replayed mutation.

## Tests performed

- exact patched CSI source: `go test ./pkg/cloud/... ./pkg/driver/...` passed using the module-declared Go `1.23.5` toolchain;
- the added controller test proves a request below observed capacity returns the observed capacity and preserves filesystem node expansion;
- overlay preflight, apply and repeated apply produced `APPLICABLE`, `APPLIED`, then `ALREADY_APPLIED`;
- `tools/layersentry/k8s/e0_qualification.py` fail-closes the future live result unless project create/isolation, attach/detach, snapshot/restore, repeated expand/delete and all CAPC/PVC/NodeDiskSet destructive cases carry durable evidence.

## Required live/destructive evidence

On Rocky Linux 9 with CloudStack `4.22.1.1`, prove in one disposable project and a foreign project:

1. create and repeated create by CSI name;
2. attach/detach and repeated calls;
3. snapshot, restore and content hash equality;
4. expand, repeated expand and no shrink/replayed CloudStack mutation;
5. delete and repeated delete;
6. denial of foreign project volume/snapshot/VM identifiers;
7. PVC data survival across Machine delete, rollout, scale-down and remediation;
8. exact NodeDiskSet retain/delete replacement behavior.

## Rollback/recovery and readiness

Roll back to the unpatched digest only while project PVC auto-grow and stateful remediation remain disabled. If resize outcome is ambiguous, stop replay, read the exact CloudStack volume and Kubernetes PVC/PV state, and reconcile from observed capacity. No project storage capability is promoted by this source work: `csiProjectScope=false`, `csiResizeIdempotent=false`, `capcVolumeOwnershipSafe=false` and `nodeDiskSetOwnership=false` remain authoritative until live evidence passes.
