# LayerSentry Single-OS — Current Status

**Role:** volatile evidence checkpoint for VM-native Single-OS DBaaS/APaaS  
**Stable architecture:** `LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`  
**Execution:** `LAYERSENTRY_EXECUTION_CONTRACT.md`

Always fetch the actual current branch before acting. Source/live evidence overrides this status if newer.

## Current reconciled state — 2026-09-07

| Scope | Status | Current truth |
| --- | --- | --- |
| Architecture | `DESIGN_DEFINED` | Go orchestration/control + local Ansible execution + Rocky Linux 9 |
| Go engine/providers | `PARTIAL` | substantial API/auth/plan/idempotency/journal/secrets/reconciliation/provider source exists and must be preserved |
| Go→Ansible boundary | `PARTIAL` | transactional Ansible execution, private ephemeral vars, timeout/UNKNOWN handling and RPM packaging exist |
| Ansible tree | `PARTIAL` | Rocky baseline, LVM/storage, network/VIP and DB/app/runtime provider roles/modules/playbooks exist |
| PostgreSQL standalone | `PARTIAL` | install/config/init/service/repair/upgrade/uninstall source plus dedicated Rocky acceptance clients exist; live qualification remains |
| MySQL/MariaDB | `PARTIAL` | external data/log/TLS/bootstrap source exists; live qualification remains |
| Redis/Valkey | `PARTIAL` | ACL/data/SELinux/uninstall source exists; live qualification remains |
| Nginx/HTTPD/Tomcat/runtime | `PARTIAL` | provider roles and data-preserving cleanup source exist; live qualification remains |
| Fresh source validation | `PENDING` | current exact branch still needs durable Go test/vet/build + Python/Ansible syntax evidence |
| Rocky 9 live provider qualification | `NOT_TESTED` | acceptance tooling is substantially prepared; a clean disposable target is required |
| PostgreSQL multi-node HA | `NOT_TESTED` | requires real multi-node evidence |
| Keepalived VRRP failover | `NOT_TESTED` | requires real multi-node evidence |
| Production certification | `NOT_TESTED` | signed release, provider/security/backup/recovery/upgrade/performance gates remain |

## Current implementation to preserve

### Go

`tools/layersentry/single-os/agent/` contains the active control plane: schema/API/auth, immutable plan, idempotency/locking, journal/state, encrypted secrets/backups, provider metadata, reconciliation, support and the Ansible execution boundary.

### Ansible

`tools/layersentry/ansible/` contains the current Single-OS execution project, including:

- safe storage/LVM and bind-mount modules;
- Rocky security baseline;
- root/root-parent destructive-storage exclusion;
- NetworkManager/firewalld/Keepalived VIP handling;
- PostgreSQL, MySQL/MariaDB, Redis/Valkey, Nginx, HTTPD, Tomcat, Node.js/runtime roles;
- apply/repair/upgrade/service/uninstall playbooks.

Do not regress this implementation to `PENDING` because an older handoff predates it.

## Acceptance tooling now present

Current branch includes acceptance assets for:

- exact RPM installation and SHA/signature checks;
- verified local PGDG repository asset handling;
- two-phase PostgreSQL Rocky acceptance;
- storage inventory;
- product-level rejection of the live OS/root disk from destructive LVM plans;
- source validation entrypoint.

Recent acceptance commits before the governance optimization include:

- `3c92deeff713a5ad138f4c29086f35fc9c2ba324` — verified local PGDG repo asset support;
- `d249517457e845986283ccbb9ecd2d0063bf71ff` — two-phase PostgreSQL Rocky acceptance client;
- `ad9f0f57c7bdf6ed958a7b2e68a8a2778555083d` — live root-disk destructive-plan rejection test.

These are source facts, not live-pass claims.

## Manual disposable-VM reset policy

The owner can manually reinstall/recreate Rocky Linux 9 test VMs.

If a destructive or failed acceptance run leaves a guest dirty or ambiguous:

1. capture the exact failure;
2. stop mutating the guest;
3. report `LAB_RESET_REQUIRED` with the clean-host prerequisites;
4. resume the same gate after a fresh Rocky VM is supplied.

Do not build automated lab reimage/snapshot rollback solely to clean disposable test VMs. This saves time/credits but does **not** remove product requirements for idempotency, repair, upgrade, uninstall, backup/restore and recovery.

## First unmet gates

1. fetch/reconcile current source;
2. execute/persist fresh source validation;
3. build exact RPM and record SHA/signature state;
4. prepare a clean disposable Rocky 9 VM with a separate non-OS data disk;
5. install exact artifact;
6. prove root/OS-disk exclusion;
7. complete PostgreSQL standalone live path: storage, install, health/read-write, idempotent rerun, reboot, backup/restore, repair/upgrade, uninstall/residue;
8. request manual OS reset whenever a dirty lab state would otherwise require reimage automation;
9. then qualify MySQL-family, Redis/Valkey and representative APaaS/runtime providers;
10. keep real DB HA and VRRP failover `NOT_TESTED` until a real multi-node lab is provided.

## File fence

This workstream writes only `tools/layersentry/single-os/**`, Single-OS-specific `tools/layersentry/ansible/**` provider execution files and Single-OS evidence. UI, K8s, DR, bootstrap/hypervisor and global authority changes are handed to their owning workstreams.