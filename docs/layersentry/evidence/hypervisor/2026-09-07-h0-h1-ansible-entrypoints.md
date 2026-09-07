# LayerSentry hypervisor Ansible H0/H1 entrypoints — 2026-09-07

Status: `SOURCE_COMPLETE` for this narrow source slice; `NOT_TESTED` live.

## Scope

This checkpoint adds dedicated hypervisor Ansible entrypoints for:

- fail-closed preflight;
- serialized fresh installation through the existing `hypervisor_preflight` and `hypervisor_base` roles;
- local post-install validation;
- controller-visible non-secret evidence including operation UUID, release/profile identity, SELinux state and managed-file SHA-256 observations.

The implementation deliberately does not add shell-based installation logic, a second hypervisor scheduler, CloudStack core changes, or persistent Ansible control source on the target host.

## Current limits

This does **not** yet prove:

- network bridge configuration;
- NFS/iSCSI/multipath profiles;
- CloudStack API registration/reconciliation;
- rolling update/maintenance integration;
- reboot/resume/rollback;
- offline release qualification;
- signed release-manifest verification;
- Rocky Linux 9 live execution.

Those remain subsequent gates. No `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED` claim is made by this checkpoint.
