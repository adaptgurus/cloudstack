# Workstream E0 — CAPC endpoint and Machine-volume ownership design

**Date:** 2026-09-06  
**Status:** `SOURCE_COMPLETE` for the downstream source overlay; runtime/destructive evidence remains `NOT_TESTED`  
**CloudStack core impact:** none

## Decision

LayerSentry retains CAPC `v0.6.1` commit `7521b14a31e6c46f81f16aae3738a27c08ad063f` for Lane B qualification and applies one digest-pinned downstream overlay. CAPC remains the sole owner of the control-plane VIP lifecycle and reconciles both TCP `6443` and RKE2 supervisor/join TCP `9345` when the LayerSentry cluster annotation is present.

Machine deletion no longer treats every attached `DATADISK` as Machine-owned. The selected contract records the one CAPC deploy-time disk ID in `CloudStackMachine.status`, tags that volume with the CAPC creation marker and Machine UID, and includes it in `destroyVirtualMachine` only when both the recorded ID and tags match. CSI and otherwise unowned volumes are excluded. Pre-overlay/unmarked disks are retained rather than guessed.

## Exact source validation

| Source | Version/commit | Finding | Impact |
| --- | --- | --- | --- |
| CAPC | `v0.6.1` / `7521b14a31e6c46f81f16aae3738a27c08ad063f` | isolated network tracks one `6443` LB rule; deletion lists every attached `DATADISK` | downstream fix required |
| CAPRKE2 | `v0.25.2` / `38602b72a23faf719b94b250eba66ef804bf9706` | bootstrap registration URL uses TCP `9345` | both endpoint ports mandatory |
| CloudStack | `4.22.1.1` | supported LB, resource-tag and VM-destroy volume-ID APIs already exist | no CloudStack core change needed |

## Alternatives

- A second LayerSentry endpoint controller was rejected because it splits one VIP lifecycle between controllers.
- Deleting no data disks is safe but leaks the CAPC deploy-time disk and does not implement explicit ownership.
- Matching by attachment, name or disk offering was rejected as ambiguous after CSI/OEM volumes attach.
- CloudStack-core/API/schema changes were rejected because the provider can use existing APIs.

## Threat and failure model

- A tenant-attached or CSI volume must not become destructible solely by being attached to a CAPI Machine.
- Status ID and CloudStack tags must both match; missing/ambiguous ownership fails toward retention.
- Partial endpoint creation is retryable: persisted primary/supervisor IDs and live rule discovery make reconciliation idempotent.
- Partial two-rule membership is retryable per rule; readiness is not promoted until both IDs exist.
- Existing Machines require controlled adoption/migration if their deploy-time disk should later be garbage-collected.

## Tests and evidence

- Exact patched source compiled with verified Go `1.23.2`.
- CAPC `pkg/cloud` non-integration suite passed: 135 specs selected from 158, including new dual-port and owned/unowned-volume cases.
- v1beta1/v1beta2 API packages passed and v1beta3 test binary compiled.
- Full envtest and destructive CloudStack PVC-survival tests remain `NOT_TESTED`.

## Rollback/recovery

Remove the overlay and deploy the exact upstream CAPC artifact only after draining/pausing reconciliation. Existing additional `9345` rules and ownership tags must be inventoried and removed through CloudStack-supported APIs if rollback policy requires it. Rollback to upstream restores the unsafe all-attached-DATADISK behavior, so stateful Machine deletion/remediation must remain disabled.
