# LayerSentry Single-OS — Current Status

**Role:** module-scoped volatile evidence checkpoint for VM-native Single-OS DBaaS/APaaS.  
**Global current-status authority:** `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md` **plus current evidence**, per `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`. This file is the Single-OS evidence component of that authority.  
**Stable architecture authority:** `docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`.  
**Execution routing:** `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`.

Always fetch the actual current branch before acting. Do not reset to a SHA copied from this file.

## Current reconciled state — 2026-09-07

| Scope | Status | Current truth |
| --- | --- | --- |
| Target VM-native architecture | `DESIGN_DEFINED` | Go orchestration/control + local Ansible execution + versioned roles/modules/playbooks |
| Existing Go Single-OS engine/providers | `PARTIAL` | substantial control/lifecycle/provider source remains under `tools/layersentry/single-os/agent/`; it is preserved rather than rewritten |
| Go→Ansible execution boundary | `PARTIAL` | typed root helper, private ephemeral vars, immutable local project root, transactional provider interface, timeout-to-UNKNOWN propagation and RPM packaging exist; fresh validation still required |
| Ansible Single-OS execution tree | `PARTIAL` | `tools/layersentry/ansible/` now exists with Rocky baseline, LVM/storage, network/VIP and provider roles/modules/playbooks; source validation/live qualification not yet complete |
| PostgreSQL standalone Ansible slice | `PARTIAL` | transactional install/config/init/service/repair/upgrade/uninstall path is source-written; live Rocky validation remains |
| MySQL/MariaDB Ansible slice | `PARTIAL` | external datadir/log/TLS/init, owner marker and no-log local admin bootstrap are source-written; fresh source/live validation remains |
| Redis/Valkey Ansible slice | `PARTIAL` | hashed ACL config, external data bind/SELinux, owner marker and data-preserving uninstall are source-written; fresh source/live validation remains |
| Nginx/Apache/Tomcat Ansible slice | `PARTIAL` | external app roots, SELinux, listener/config handling and data-preserving cleanup are source-written; fresh source/live validation remains |
| Node.js/Python/Podman runtime Ansible slice | `PARTIAL` | package-only runtime roles and data-preserving cleanup exist; Node.js 20 module ownership/reset logic requires source/live validation |
| Historical September 7 Go source-validation result | `UNKNOWN` | old handoff referenced a validation file that was never committed; do not inherit that result |
| Fresh Single-OS source validation | `PENDING` | `tools/layersentry/single-os/validate-source.sh` now defines Go test/vet/build, Python compile, Ansible syntax and shell syntax gates but has not yet been durably executed for the current branch |
| Rocky Linux 9 provider/runtime qualification | `NOT_TESTED` | acceptance harness exists; target VM installation is still being prepared by the owner |
| Real PostgreSQL multi-node HA/replication/failover | `NOT_TESTED` | requires real multi-node evidence |
| Real Keepalived VRRP failover | `NOT_TESTED` | requires real multi-node evidence |
| Production certification | `NOT_TESTED` | provider/security/backup/recovery/upgrade/performance and signed-release gates remain |

## Current implementation that must be preserved

### Go control/lifecycle

`tools/layersentry/single-os/agent/` contains the active schema, API/auth, immutable plan, idempotency/locking, journal/state, encrypted secrets/backups, health/residue/provider metadata, reconciliation and support logic.

The lifecycle engine recognizes transactional guest providers and routes confirmed mutations through one Ansible `Apply` boundary rather than executing the legacy imperative install path in parallel.

### Ansible execution

`tools/layersentry/ansible/` contains:

- immutable local Ansible configuration/inventory;
- custom safe modules for LayerSentry storage/LVM, bind mounts, Tomcat config and MySQL-family bootstrap;
- Rocky Linux security-baseline role;
- storage/LVM role with live root/root-parent exclusion and recovery-only mode;
- NetworkManager/firewalld/Keepalived VIP role;
- PostgreSQL, MySQL/MariaDB, Redis/Valkey, Nginx, HTTPD, Tomcat, Node.js and runtime roles;
- apply/repair/upgrade/service/uninstall playbooks.

The RPM packages this project under `/usr/lib/layersentry/ansible` and depends on `ansible-core`; it does not fetch Galaxy content at runtime.

### Transaction safety

- provider/plan/request identities are bound before mutation;
- exact repository version/digest policy remains Go-owned;
- secret refs are resolved to private ephemeral vars under `/run/layersentryd/ansible` and removed after execution;
- password-bearing Ansible tasks/modules use `no_log` and do not place plaintext secrets in command argv;
- LVM root-disk exclusion is re-evaluated from live `findmnt`/`lsblk` ancestry;
- PV/filesystem creation requires explicit destructive confirmation;
- repair/upgrade storage is observation/remount only;
- repair/upgrade fail closed when PostgreSQL/MySQL-family authoritative database identity is missing;
- firewall/VIP is reconciled before first network service start;
- Ansible timeout/cancellation identity propagates to the lifecycle engine so ambiguous mutations can enter `UNKNOWN` rather than being blindly retried;
- normal uninstall preserves customer data and attached filesystems.

## Acceptance assets

Source validation:

`tools/layersentry/single-os/validate-source.sh`

Disposable Rocky 9 lab preparation and artifact acceptance:

- `tools/layersentry/single-os/acceptance/prepare-rocky9-test-host.sh`
- `tools/layersentry/single-os/acceptance/storage-inventory.py`
- `tools/layersentry/single-os/acceptance/install-test-rpm.sh`

These files contain no VM/root password. The owner's temporary Rocky root credential remains runtime-only and must never be committed/logged.

## First unmet gates

1. fetch/reconcile the actual current branch;
2. run the fresh Single-OS source validation gate and persist exact evidence;
3. fix every compile/syntax/unit failure before source promotion;
4. build the exact RPM and record SHA-256/signature state;
5. when the disposable Rocky 9 VM is ready, run host preparation and exact-artifact install;
6. prove root/OS disk exclusion and inventory at least one separately attached non-OS data disk before any LVM destructive test;
7. execute PostgreSQL standalone first: external data/WAL/log LVs, service health, idempotent rerun, reboot recovery, backup/restore, repair/upgrade/uninstall/residue;
8. then qualify MySQL-family, Redis/Valkey and representative APaaS/runtime providers as resources permit;
9. static secondary VIP may be tested on one VM if the lab network permits it;
10. real VRRP failover and real database HA remain `NOT_TESTED` until a real multi-node environment is authorized.

## Continuity invariant

A new ChatGPT/Codex session must inspect current Git source first and read this status pointer. It must not regress the Ansible implementation to `PENDING` merely because an older handoff predates it, and it must not promote this source to `SOURCE_COMPLETE`/`CI_VERIFIED`/`LIVE_VERIFIED` without fresh durable evidence.
