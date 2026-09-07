# LayerSentry Workstream D — DC/DR / HA / Upgrade

**Default execution owner:** ChatGPT  
**Codex use:** only when explicitly reassigned  
**Primary rule:** native Apache CloudStack 4.22.1.1 recovery first

## 1. Mission

Make the existing DC/DR environment and CloudStack-native recovery path work end to end before adding provider-specific low-RPO integration. Do not build a second backup/replication platform.

## 2. Startup

Read only:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. `LAYERSENTRY_DRAAS_ARCHITECTURE.md` only when provider semantics are needed;
5. current DR runner/live evidence;
6. actual CloudStack/runner refs.

Do not reread historical DR handoffs by default.

## 3. Hard file fence

Writable:

- `tools/layersentry/dr*`;
- DR-specific tests/evidence;
- explicitly authorized DR runner files in the runner repository.

Do not edit:

- `ui/**`;
- `tools/layersentry/k8s/**`;
- `tools/layersentry/single-os/**`;
- unrelated Ansible application/hypervisor roles;
- global authority files.

If DR proves a UI or CloudStack-core defect, record the exact API/job/resource evidence and hand it to the owning module. Do not cross-edit it here.

## 4. Native V1 path

```text
fix DC/DR infrastructure health
 -> enable/configure supported CloudStack B&R
 -> create disposable source workload
 -> Recovery Point OLD
 -> mutate root/data markers
 -> Recovery Point NEW
 -> recover OLD using exact selected backup UUID
 -> recover NEW using exact selected backup UUID
 -> isolated destination network
 -> exact guest root/data verification
 -> retry/idempotency/RBAC negatives
 -> thin LayerSentry recovery state/API integration
```

Current environment faults such as Zone/storage/image-store/SystemVM/B&R provider/API/RBAC/DR KVM readiness are higher priority than new DR source.

A failed API call is not proof that a resource does not exist; resolve the API/provider failure first.

## 5. Native API preference

Use supported CloudStack B&R and `createVMFromBackup` behavior. Preserve explicit recovery-point identity and reconcile timed-out/ambiguous async mutations from authoritative CloudStack job/resource state before retry.

`tools/layersentry/dr_state_machine.py` is a retained source foundation for product state/journal/idempotency. Do not expand it merely to increase code percentage.

Until native recovery passes, do not implement:

- a generic VM block-copy engine;
- all LINSTOR/Ceph/SAN/libvirt adapters in parallel;
- witness/fencing/traffic switching/auto-failover runtime;
- another backup catalog/scheduler.

## 6. Advanced DR after native proof

Select only the provider-native low-RPO path required by the chosen V1 profile:

- LINSTOR/DRBD for the selected HCI path;
- Ceph RBD mirroring for the selected Ceph path;
- certified array-native replication for enterprise SAN;
- libvirt/file fallback only when no better provider-native mechanism exists.

Certification order:

```text
Test Recovery
 -> Planned Failover
 -> reverse replication/reprotect
 -> Failback
 -> witness/quorum
 -> source fencing/no-dual-writer proof
 -> Automatic Failover
```

Do not make every provider a V1 blocker.

## 7. Lab/time optimization

Use disposable workloads and manual environment preparation when that is faster than building one-off automation. If a DR test VM/guest must be recreated manually, record the required clean state and resume after reset rather than writing general reimage automation solely for the lab.

Do not weaken production recovery/fencing/data-integrity requirements because the lab is disposable.

## 8. Evidence

Native DR is `LIVE_VERIFIED` only after exact OLD and NEW recovery points are independently restored on the intended destination topology and guest root/data contents are verified.

Same-host nested Hyper-V can prove function but cannot certify independent-site DR/fencing.

## 9. Handoff

Report exact source/runner refs, environment changes, native APIs/jobs/recovery-point IDs, guest-data results, blocker/root cause and next native-recovery gate. Do not edit another module or generate a broad architecture handoff.