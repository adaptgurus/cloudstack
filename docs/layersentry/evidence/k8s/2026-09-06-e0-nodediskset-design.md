# Workstream E0 — NodeDiskSet ownership design

**Date:** 2026-09-06  
**Status:** `SOURCE_COMPLETE` for the policy/planning contract; execution and destructive evidence remain `NOT_TESTED`  
**CloudStack core impact:** none

## Decision

NodeDiskSet is a LayerSentry node-pool lifecycle object, separate from CSI/PVC storage. It uses the existing CloudStack `createVolume`, `attachVolume`, `detachVolume`, `resizeVolume`, `deleteVolume`, `createTags`, `listTags`, `listVolumes` and async-job contracts in the exact 4.22.1.1 source.

Source validation used `api/src/main/java/org/apache/cloudstack/api/command/user/volume/{CreateVolumeCmd,AttachVolumeCmd,DetachVolumeCmd,ResizeVolumeCmd,DeleteVolumeCmd}.java` and `api/src/main/java/org/apache/cloudstack/api/command/user/tag/CreateTagsCmd.java` at integration commit `0a02add7245e92fc5c4dccfad600b734e9e557b0`. `createVolume`, attach, detach, resize and tag creation are asynchronous in that source; delete is synchronous. The planner therefore gives each step a stable idempotency key and requires a future executor to re-read the resource/job outcome before replaying a timed-out request.

Every binding records the exact CloudStack volume ID. Every mutation is scoped to exact project, Site, disk-offering, node-pool, Machine and logical-disk IDs. Destruction requires the recorded ID plus the complete ownership tag set. Missing, conflicting, cross-project, cross-Site, wrong-offering or ambiguous state fails closed. Resize is expand-only with CloudStack `shrinkok=false` and emits no operation once capacity is satisfied. Replacement is explicit `reattach` or `recreate`; retain policy never emits volume deletion.

The initial source enables only scratch/cache purposes. Durable database/application/container data continues to require a certified CSI/PVC path.

## Alternatives and risks

- CAPC's single deploy-time `DiskOffering` cannot express multiple independent disks and policies.
- Discovering by name/offering/attachment is ambiguous and was rejected.
- A Kubernetes PVC is not a NodeDiskSet and remains CSI-owned.
- Tags alone are not sufficient authorization; the future BFF/controller must also check durable bindings and caller/project scope immediately before each mutation.
- CloudStack async timeouts remain `UNKNOWN` until job/resource reconciliation; the execution engine must not blindly replay.

## Rollback/recovery

Stop new reconciliation, inventory exact bindings and tags, detach or retain volumes according to recorded policy, and remove the NodeDiskSet desired state only after reconciliation. Uncertain ownership is retained for operator reconciliation rather than deleted.

## Remaining gate

Bind these plans to the durable BFF saga/CloudStack adapter, test job interruption/restart and execute destructive scratch/cache replacement tests. NodeDiskSet does not remove the separate CAPC+CSI PVC-survival gate.
