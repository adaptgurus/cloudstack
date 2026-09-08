# LayerSentry bootstrap B0 physical-host preflight source checkpoint — 2026-09-07

Status: `SOURCE_COMPLETE` for the B0 source additions in this checkpoint; `NOT_TESTED` live.

## Implemented

- Added a dedicated B0 bootstrap preflight entrypoint over exactly three `layersentry_hypervisors`.
- Fail closed unless all three hosts declare distinct failure-domain identities.
- Extended per-host preflight with Rocky Linux 9, SELinux Enforcing, firewalld, chronyd, CPU virtualization, `/dev/kvm`, configured CPU/RAM floor, management bridge presence, exact MTU, required storage-path/mount checks, repository trust-contract validation, optional DNS resolution and management TCP reachability.
- Added controller-visible non-secret B0 evidence via `set_stats`.
- Pinned `community.libvirt` to 2.3.0 in `collections/requirements.yml` for the subsequent control-plane VM provisioning gate. Customer installation must consume a mirrored/signed offline artifact rather than resolve Galaxy at runtime.

## Research affecting implementation

Current Ansible documentation identifies `community.libvirt` 2.3.0 as the current collection and documents `virt_install` as declarative VM provisioning with full check-mode support. The module is not in ansible-core and requires libvirt Python bindings, lxml and virt-install on the executing host. These dependencies therefore belong in the signed offline execution/host artifact contract.

Open community.libvirt issues include current idempotency/provisioning concerns, so B1 must observe authoritative libvirt state after ambiguous outcomes and must not use `recreate: true` as a retry mechanism.

## Not yet proven

- live Rocky Linux 9 execution;
- multipath/iSCSI/NFS/NVMe provider-specific health beyond required-path/mount intent;
- signed offline collection artifact digest/SBOM/signature;
- B1 DB/control-plane VM creation;
- interruption/resume behavior;
- coexistence with CloudStack agent on the same KVM hosts.

No `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED` claim is made.
