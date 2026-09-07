# LayerSentry hypervisor H2 network/security source slice — 2026-09-07

Status: `SOURCE_COMPLETE` for this narrow source slice; CI/live status is recorded separately.

## Reconciled baseline

This work was rebased conceptually on shared-branch HEAD `61e02664a0bccec0eeab277a740b777238020dea`, which was 51 commits ahead of the previous hypervisor H0/H1 checkpoint. The newer bootstrap preflight requirements for failure domain, management bridge/MTU, N+1 capacity, chronyd and required storage paths were preserved.

## Scope

This checkpoint adds the H2 network/security execution boundary:

- persistent SELinux enforcing/targeted configuration without disabling SELinux;
- validation-only support for pre-existing bridges;
- deterministic NetworkManager keyfiles for explicitly dedicated non-management bridges;
- a fail-closed guard that refuses to enslave the active default-route interface;
- exact bridge MTU reconciliation and validation;
- firewalld rich rules allowing CloudStack agent TCP/8250 only from signed management CIDRs;
- no implicit firewalld zone reassignment for the management bridge;
- CloudStack-agent startup moved after network/security reconciliation;
- standalone validation for SELinux persistence, bridges, MTUs, zone ownership and agent allow rules;
- host-intent schema reconciliation for the bootstrap fields already required by current preflight plus the H2 bridge/firewall contract.

No `shell`, `raw`, `eval`, `curl | bash`, dynamic playbook path or customer-supplied command execution was added. The unavoidable NetworkManager/firewalld CLIs are invoked through fixed executable paths and Ansible `command.argv` with schema/role validated values.

## Safety boundary

The management bridge must already exist and match the signed bootstrap MTU. H2 does not reconstruct it and does not move it between firewalld zones. A managed bridge may use `manage-dedicated` only for a non-default-route uplink. Management-interface migration remains outside this source slice until a separately validated procedure exists.

## Remaining gates

This source slice does not yet prove:

- live Rocky Linux 9 NetworkManager/firewalld behavior;
- CloudStack API registration/reconciliation;
- NFS/iSCSI/multipath storage;
- idempotent second-run live evidence;
- update/maintenance/reboot/resume/rollback;
- signed release manifest/artifact verification;
- offline deny-all-egress operation.

Do not label H2 `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED` without the exact live evidence above.
