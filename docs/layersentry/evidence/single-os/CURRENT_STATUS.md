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
| PostgreSQL standalone | `PARTIAL` | install/config/init/service/repair/upgrade/uninstall source plus a two-phase live client covering idempotent install replay, backup/restore, reboot, repair/upgrade and data-preserving uninstall exists; live execution remains |
| MySQL/MariaDB | `PARTIAL` | external data/log/TLS/bootstrap source exists; live qualification remains |
| Redis/Valkey | `PARTIAL` | ACL/data/SELinux/uninstall source exists; live qualification remains |
| Nginx/HTTPD/Tomcat/runtime | `PARTIAL` | provider roles and data-preserving cleanup source exist; live qualification remains |
| Fresh source validation | `CI_VERIFIED` | exact source gate passed on `f2aee691867d974c2eb0b28184d92b4567100ce8`; run `34126279393`, job `101755596059`; Go tidy/format/test/vet/build, Python compile, Ansible syntax and shell syntax are green with durable evidence |
| Exact Rocky 9 RPM build | `CI_VERIFIED` | exact RPM `layersentry-single-os-0.2.0-1.el9.x86_64.rpm` built and inspected from `f2aee691867d974c2eb0b28184d92b4567100ce8`; run `34126279307`; RPM SHA-256 `5ddfa332d222a616f9d9749282540ab3a4acaad64b4b4cba767236a0d4b58fe1`; artifact `10020266864` |
| Rocky 9 live provider qualification | `NOT_TESTED` | a clean disposable target with a separate non-OS data disk is now the first unmet gate |
| PostgreSQL multi-node HA | `NOT_TESTED` | requires real multi-node evidence |
| Keepalived VRRP failover | `NOT_TESTED` | requires real multi-node evidence |
| Production certification | `NOT_TESTED` | signed release, provider/security/backup/recovery/upgrade/performance gates remain |

Durable CI evidence: `docs/layersentry/evidence/single-os/2026-09-07-source-and-rpm-ci-verification.md`.

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
- storage inventory and live OS/root/root-parent exclusion proof;
- two-phase PostgreSQL Rocky acceptance covering install, health/read-write, exact successful install replay/idempotency, backup/restore integrity, actual VM reboot recovery, repair, upgrade, restart, uninstall residue and customer-data preservation;
- source validation entrypoint.

Key acceptance commits include:

- `3c92deeff713a5ad138f4c29086f35fc9c2ba324` — verified local PGDG repo asset support;
- `d249517457e845986283ccbb9ecd2d0063bf71ff` — two-phase PostgreSQL Rocky acceptance client;
- `ad9f0f57c7bdf6ed958a7b2e68a8a2778555083d` — live root-disk destructive-plan rejection test;
- `f2aee691867d974c2eb0b28184d92b4567100ce8` — add exact install replay/idempotency and repair/upgrade data-integrity assertions to PostgreSQL live acceptance.

These are source/CI facts, not live-pass claims.

## Current exact package for live qualification

Use only the current CI-built artifact:

- artifact ID: `10020266864`;
- artifact name: `layersentry-single-os-rpm-34126279307-1`;
- RPM: `layersentry-single-os-0.2.0-1.el9.x86_64.rpm`;
- RPM SHA-256: `5ddfa332d222a616f9d9749282540ab3a4acaad64b4b4cba767236a0d4b58fe1`;
- artifact ZIP SHA-256: `6d06d4364a589ece107415b8c5734c6388e4030eeb47f897d7871f292aeea5fb`.

The prior RPM SHA-256 `a47d6fce81f19a87ce7c02374551775541f0a93aadaddf44c6bb96a25bd24d45` is historical/superseded evidence and must not be used for the next live qualification.

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
2. obtain or provision a clean disposable Rocky Linux 9 VM with a separate non-OS data disk;
3. transfer artifact `10020266864`, verify RPM SHA-256 `5ddfa332d222a616f9d9749282540ab3a4acaad64b4b4cba767236a0d4b58fe1`, then install it;
4. prove root/OS-disk exclusion with `acceptance/storage-inventory.py` and `acceptance/root-disk-negative.py` against the live host;
5. complete PostgreSQL standalone phase 1: storage, immutable plan, install, health/read-write, exact idempotent install replay, backup/restore and restart;
6. perform an actual VM reboot;
7. complete phase 2: post-reboot health/mount/data verification, repair, upgrade, post-upgrade data verification, restart, uninstall/residue and customer-data preservation;
8. request manual OS reset whenever a dirty/ambiguous lab state would otherwise require reimage automation;
9. then qualify MySQL-family, Redis/Valkey and representative APaaS/runtime providers;
10. keep real DB HA and VRRP failover `NOT_TESTED` until a real multi-node lab is provided.

## File fence

This workstream writes only `tools/layersentry/single-os/**`, Single-OS-specific `tools/layersentry/ansible/**` provider execution files and Single-OS evidence. UI, K8s, DR, bootstrap/hypervisor and global authority changes are handed to their owning workstreams.
