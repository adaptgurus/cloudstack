# Native CloudStack API / RKE2 POC admission

The existing signed read-only client complements CAPI/CAPC/CAPRKE2. It does
not deploy, scale, destroy, or register VMs. ExternalManaged registration is
NOT_REQUIRED for this module. Native async mutations and job persistence are
NOT_REQUIRED because this integration issues no native mutations; CAPC owns
those jobs. The existing durable saga observes Kubernetes resources after an
UNKNOWN apply and now compares desired fields before advancing.

`CloudStackResolver.observe_vm` accepts an exact CAPC-provided CloudStack VM ID
and resolved authorized infrastructure; it returns only ID/state. It is an
observation helper, not a second inventory or a new status/lifecycle authority.
Endpoint observation rechecks project, Site, network, public IP, both Active TCP
6443/9345 rules and matching private ports. It does not prove TCP reachability.

## Read-only POC command

```bash
python3 tools/layersentry/k8s/lab-capacity-preflight.py \
  --runtime-config /run/layersentry/k8s/runtime-config.json \
  --request /run/layersentry/k8s/poc-request.json \
  --host-evidence /run/layersentry/k8s/poc-host-evidence.json \
  --cluster-id VERIFIED_CLUSTER_UUID \
  --host-id VERIFIED_HOST_UUID \
  --pool-id VERIFIED_PRIMARY_POOL_UUID
```

Use the existing runtime configuration and a normal managed cluster request.
Do not put credentials in either request or host evidence. Credential files
must be regular files (not symlinks), mode 0600 or stricter; rotation is checked
on every request. TLS verification/custom CA remain enabled. HTTP requires the
existing explicit lab opt-in. The native client uses a 30-second request timeout
(default; direct config bounds 1–120 seconds), a 4 MiB response limit and at most
100 pages of 100 requested rows. It rejects redirects and ignores environment
proxy settings. Runtime startup needs its existing Kubernetes/Flux configuration;
the preflight only loads it and does not build/start the runtime or write its DB.

The trusted operator host receipt must contain these fields, measured on the
selected nested KVM host via already verified SSH or an out-of-band console:

```json
{
  "observed_at": "REPLACE_WITH_CURRENT_UTC_ISO_TIMESTAMP",
  "host_id": "VERIFIED_HOST_UUID",
  "nested_virtualization": "UNKNOWN",
  "total_cpu": null,
  "total_ram_bytes": null,
  "available_ram_bytes": null,
  "management_cpu_reserve": null,
  "management_ram_reserve_bytes": null
}
```

Set nested virtualization PASS only after verifying CPU virtualization flags,
/dev/kvm, KVM modules, libvirt capabilities and functional QEMU/KVM. Use nproc /
lscpu, MemTotal/MemAvailable, bounded virsh inventory and filesystem measurements;
retain that console/host evidence separately. Reserve fields must include measured
management/system overhead. The host receipt is trusted operator input, never a
tenant-submitted override. The example above intentionally cannot pass.

Admission requires a receipt no older than five minutes, one Up/Enabled KVM host,
one eligible shared cluster storage pool, Running System VMs, and exact healthy
project/Site/network/frontend/template/offering resolution. Multi-host placement,
local/custom disk offerings and additional node disks are not qualified by this
small POC check and fail closed. This does not change production HA policy.

CloudStack source contracts used:

- `Capacity.java`: memory type 0 bytes, CPU type 1 MHz, CPU cores type 90.
- `CapacityResponse.java` / `CapacityDaoImpl.java`: zone-wide `capacityallocated`
  is optional; missing means UNKNOWN. Compute `capacityused` includes reserved
  capacity and is not sampled CPU utilization.
- `ListCapacityCmd.java`: `fetchlatest`; `ListClustersCmd.java`: `showcapacities`.
  Each paginated call pairs `page` with `pagesize`.
- `StoragePoolResponse.java`: `disksizetotal`, `disksizeallocated`, `disksizeused`.
- `TemplateJoinDaoImpl.java`: template `size` is virtual bytes; `physicalsize`
  must not be substituted. Offering `rootdisksize` is GiB, `memory` is MiB.

The check intersects native allocatable capacity with physical host capacity and
MemAvailable. It never spends overcommit. Minimum remaining reserves are 2 CPU,
8 GiB RAM (or larger measured overhead) and 20% primary/secondary storage.
Root requirements use the larger exact template/offering root size per node.
The existing production topology remains odd control-plane replicas >=3 plus
at least one worker. No smaller qualification topology is introduced.

Exit 0 means an immediate POC capacity decision is allowed; exit 2 means BLOCKED.
This command never creates a cluster and is not a durable admission token. Re-run
it immediately before any separately gated CAPI request. Release/source gates,
valid management-cluster providers, endpoint reachability and eventual Cluster
Ready are separate proof requirements. An API metadata check cannot certify them.
