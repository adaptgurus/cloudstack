# LayerSentry Workstream D — DR / HA / Upgrade

**Default execution owner:** ChatGPT  
**Codex use:** only when explicitly assigned after native recovery proves a real need for new source  
**Primary rule:** native Apache CloudStack 4.22.1.1 recovery first

This filename is retained for continuity, but Workstream D is no longer a standing Codex coding stream. The current execution authority is `LAYERSENTRY_EXECUTION_CONTRACT.md`.

## Mission

Make the existing DC/DR environment and supported CloudStack recovery path work end to end before adding advanced custom DR code.

The objective is a simple LayerSentry recovery experience built on native CloudStack APIs and certified storage-provider primitives, not a second cloud/replication engine.

## Startup

Read only:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. `LAYERSENTRY_DRAAS_ARCHITECTURE.md` when provider/recovery semantics are needed;
5. current runner evidence for the exact lab operation;
6. fetch actual CloudStack and runner refs/live state.

Do not start by rereading historical DR handoffs.

## Architecture boundary

CloudStack remains authoritative for VM, network, volume, template, account/project/RBAC, async jobs and native Backup & Recovery lifecycle.

LayerSentry DR may own only thin product state needed for:

- Site pairing metadata;
- Protection Plan presentation;
- recovery point presentation;
- network/IP mapping policy;
- operation/evidence journal;
- provider capability selection;
- recovery workflow UX;
- later fencing/witness eligibility.

Do not create another VM scheduler or backup catalog authority.

## V1 execution order

```text
fix DC/DR infrastructure health
 -> prove native B&R APIs
 -> create disposable source workload
 -> Recovery Point OLD
 -> mutate root/data markers
 -> Recovery Point NEW
 -> recover OLD into isolated destination network
 -> recover NEW into isolated destination network
 -> verify exact guest data
 -> execute negative/retry/RBAC cases
 -> wire thin LayerSentry UI/API workflow
 -> add one advanced provider-native replication path only if required
 -> planned failover/failback
 -> witness/fencing/automatic failover last
```

## Current priority: resolve environment errors

Before new advanced DR source, inspect and resolve the current real blockers, including as applicable:

- Zone readiness and correct source/destination topology;
- primary storage;
- image/secondary storage;
- SystemVM template readiness;
- `backup.framework.enabled` and supported provider configuration;
- backup offerings/repository accessibility;
- API/RBAC failures;
- async-job visibility/reconciliation;
- DR KVM agent/libvirt/qemu-kvm/bridge readiness;
- CloudStack ownership of the intended DR host;
- Advanced destination network requirements for `createVMFromBackup`;
- source VM fixture and attached root/data volumes.

Do not interpret failed API calls as absence of resources without resolving the actual failure.

## Native API preference

Prefer supported CloudStack operations such as the native Backup & Recovery APIs and selected-backup `createVMFromBackup` path.

LayerSentry should call/compose the native operations, observe async jobs authoritatively and preserve selected recovery-point identity end to end.

A lost/timed-out mutation response must be reconciled from CloudStack job/resource state before retrying.

## Existing custom DR source

`tools/layersentry/dr_state_machine.py` is a source foundation, not the current critical path.

Until native recovery is live-proven:

- retain it but do not expand it merely to increase code percentage;
- do not build a generic VM block replication engine;
- do not implement witness/fencing/traffic switching/auto-failover runtime;
- do not duplicate native `createVMFromBackup` lifecycle;
- do not implement all LINSTOR/Ceph/SAN/libvirt adapters in parallel.

## Advanced DR after native proof

After native recovery passes, select one provider-native low-RPO path for the V1 profile.

Preferred principle:

- LINSTOR/DRBD for the LayerSentry HCI profile where selected/certified;
- Ceph uses native RBD mirroring when that profile is selected;
- enterprise SAN uses certified array-native replication;
- file-backed/libvirt fallback only where no better provider-native path exists.

Do not create host-level generic block copying for storage that already owns safe replication/promotion semantics.

## Planned failover before auto failover

Certification sequence:

```text
Test Recovery
 -> Planned Failover
 -> reverse replication/reprotect
 -> Failback
 -> witness/quorum
 -> source fencing/no-dual-writer proof
 -> Automatic Failover
```

Automatic failover is ineligible without independent witness/quorum and safe fencing/exclusivity.

## HA and upgrade

Management/DB/LB/host HA and upgrade testing remains evidence-driven, but do not let broad HA/upgrade research block the native DR vertical slice.

Use exact supported CloudStack/Rocky/database/provider mechanisms first. Add LayerSentry code only where product coordination/evidence is missing.

## Evidence

Native DR becomes `LIVE_VERIFIED` only when exact OLD/NEW recovery points are recovered and guest root/data content is verified on the intended destination topology.

API submission success alone is insufficient.

Same-host nested Hyper-V proves function only; it cannot certify independent-site production DR or hardware fencing.

## Handoff

Report only:

- exact source/runner refs;
- environment state changed;
- native APIs/operations executed;
- workflow/job/artifact IDs where used;
- exact recovery-point IDs;
- observed guest data checks;
- blocker/root cause;
- next unmet native-recovery gate.

Avoid large architecture handoffs unless the architecture itself materially changes.
