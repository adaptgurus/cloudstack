# LayerSentry bootstrap B1 DB VM provisioning source — 2026-09-07

Status: `SOURCE_COMPLETE` for the B1 source slice; `NOT_TESTED` live.

## Scope

This checkpoint adds the narrow bootstrap-owned libvirt provisioning path for the three database control-plane VMs only.

- `LS-DB-01`, `LS-DB-02`, and `LS-DB-03` are the only DB names admitted by the B1 playbook.
- the generic role is still hard-allowlisted to the eight documented LayerSentry control-plane VM identities and cannot provision tenant/customer VM names;
- one DB intent is required per preflight-qualified hypervisor and UUID/MAC/IP/failure-domain identities must be unique across the three hosts;
- the exact base libvirt volume is SHA-256 verified before cloning;
- deterministic root and CIDATA volume names are bound to the controller-issued VM UUID;
- a same-name existing domain is observed before storage mutation and is rejected unless its UUID and LayerSentry ownership marker match;
- interrupted deterministic volumes are observed and validated rather than blindly recreated/resized;
- VM creation uses `community.libvirt.virt_install` with `recreate: false`, fixed UUID/MAC/bridge/MTU, UEFI, autostart and crash restart policy;
- a persistent deterministic CIDATA ISO is attached read-only for NoCloud first-boot network/key bootstrap;
- an ambiguous create failure triggers authoritative `get_xml` observation before any retry; unresolved absence stops as `UNKNOWN`;
- final UUID/domain XML and SSH reachability are required before B1 evidence is emitted.

No Bash/sh lifecycle, CloudStack core change, second tenant scheduler, plaintext password, dynamic Galaxy dependency, or force-recreate behavior was added.

## Targeted upstream findings

The pinned `community.libvirt` collection remains `2.3.0`. Its `virt_install` implementation checks for an existing domain by name and does not recreate it unless explicitly requested. `virt_volume` returns authoritative pool volume paths/XML and its CIDATA helper always reports changed when called, including an already-existing seed volume; therefore this implementation first observes and only invokes CIDATA creation when the deterministic volume is absent.

Current upstream issue history also reports disk-creation problems in `virt_cloud_instance`, incomplete inactive-domain listing in `virt list_vms`, and historical `virt_install.cloud_init` problems. B1 therefore does not use `virt_cloud_instance`, does not use `list_vms` as ownership authority, and uses deterministic `virt_volume` CIDATA plus direct `get_xml`/`uuid` observation.

## Current limits

This source checkpoint has not run against Rocky Linux 9/libvirt and does not prove:

- the certified per-host VM sizing values or actual site IPs;
- the exact customer storage pool/base image contents;
- UEFI firmware availability on the target hosts;
- first-boot cloud-init execution and SSH reachability;
- coexistence with an active CloudStack agent on the same KVM hosts;
- DB package installation, quorum, writer failover or CloudStack DB compatibility.

The next gate is live B1 qualification on three dedicated KVM failure domains. Only after all three DB VMs pass exact storage/network/identity validation does B2 database HA begin.
