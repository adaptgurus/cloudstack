# LayerSentry bootstrap B1 libvirt runtime dependency closure — 2026-09-07

Status: `SOURCE_COMPLETE` for the dependency guard; `NOT_TESTED` live.

The B1 DB-VM playbook now fails before any libvirt/storage mutation unless the signed hypervisor package intent contains exactly one version-pinned identity for each runtime dependency required by the pinned `community.libvirt 2.3.0` path:

- `virt-install`;
- `python3-libvirt`;
- `python3-lxml`;
- `python3-pycdlib`.

It also requires those package names to be installed and `/usr/bin/virt-install` to be an executable regular file. The installation source remains the signed/offline LayerSentry hypervisor package intent; B1 does not fetch Python packages, RPMs, collections or scripts from the Internet.

This guard was added because `community.libvirt.virt_install` requires the `virt-install` executable, while the selected `community.libvirt.virt_volume` CIDATA implementation imports libvirt/lxml and `pycdlib` on the managed host. Rocky Linux 9 AppStream carries `python3-pycdlib`, so no EPEL-only dependency or runtime `pip install` is required for the Rocky 9 profile.

No live Rocky 9 execution was performed in this checkpoint. B1 remains below `LIVE_VERIFIED` until the exact signed package identities, storage pool/base image, UEFI firmware, bridge/MTU, three DB VM identities, cloud-init and SSH readiness are exercised on three real KVM failure domains.
