# LayerSentry Workstream F — VM-Native Single-OS DBaaS/APaaS

**Default execution owner:** ChatGPT  
**Codex use:** disabled by default unless explicitly reassigned  
**Architecture:** Go orchestration + Ansible Runner  
**Guest baseline:** Rocky Linux 9

## 1. Mission

Finish the current VM-native LayerSentry path without Kubernetes, preserve the existing Go control plane, and use Ansible for guest configuration. Do not restart from zero.

## 2. Minimal startup

Read only:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_CURRENT_STATUS.md`;
4. this file;
5. `docs/layersentry/evidence/single-os/CURRENT_STATUS.md`;
6. current branch/source/tests/workflow/live target.

Read `LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` or historical Progress Ledger evidence only when a provider/architecture/history conflict cannot be resolved from this workstream, current source and module `CURRENT_STATUS.md`.

When working from a normal Git worktree, initialize/check the `single-os` writer guard from `tools/layersentry/governance/module-writer-guard.sh` before meaningful batches.

## 3. Hard file fence

Writable:

- `tools/layersentry/single-os/**`;
- `tools/layersentry/ansible/playbooks/single_os_*`;
- Single-OS provider roles/modules actually invoked by the Single-OS lifecycle;
- `.github/workflows/layersentry-single-os-*`;
- Single-OS tests/evidence.

Current normal provider-role scope includes PostgreSQL, MySQL/MariaDB, Redis/Valkey, Nginx, HTTPD, Tomcat, Node.js/runtime, `storage_lvm`, `network_vip` and their purpose-built modules.

Do not edit UI, K8s, DR, bootstrap/hypervisor roles, generic release/security tooling or global authority files.

Shared Ansible platform files such as `ansible.cfg`, `collections/requirements.yml` or a deliberately shared common role/module require a separately assigned serialized shared-Ansible task.

If a CloudStack/UI/DR/K8s dependency is wrong, report the exact failing contract to that workstream instead of fixing it here.

## 4. Existing implementation must be preserved

Current source already contains substantial Go schema/API/auth, immutable planning, idempotency/locking, journal/state, secrets/backups, reconciliation/support, Ansible execution integration, provider source, RPM packaging and acceptance assets.

Current Ansible source includes Rocky baseline, LVM/storage, network/VIP and provider roles/playbooks for PostgreSQL, MySQL/MariaDB, Redis/Valkey, Nginx, HTTPD, Tomcat, Node.js/runtime and lifecycle operations.

Do not create a parallel provider engine.

## 5. Selected architecture

```text
LayerSentry UI/API
 -> Go orchestration service
 -> Ansible Runner / ansible-core
 -> versioned roles/modules/playbooks
 -> Rocky Linux 9 guest
```

Go owns authorization, schema/version policy, plan/confirmation, UUID/idempotency, locking, state/journal, secret refs, inventory, Ansible invocation/results, evidence and recovery state.

Ansible owns repositories/packages, users/files, services, SELinux, firewalld, LVM/filesystems/mounts, NetworkManager/VIP and provider configuration.

Do not implement product lifecycle as Bash/sh. Prefer dedicated Ansible modules/templates; shell/raw is exceptional.

## 6. V1 lab reset optimization

The owner can manually reinstall/recreate disposable Rocky Linux 9 VMs.

For acceptance testing, if a destructive or failed provider run leaves the guest dirty/ambiguous:

1. capture exact failure/evidence;
2. stop mutating that guest;
3. report `LAB_RESET_REQUIRED` and the clean-host prerequisites;
4. resume the same test after the owner supplies a fresh Rocky 9 VM.

Do not spend engineering/Codex effort building VM snapshot rollback, automatic OS reinstall, automatic reimage or lab-reset orchestration solely for test cleanup.

This shortcut applies only to disposable lab reset. Product requirements for safe installation, idempotent rerun, repair, upgrade, uninstall, backup/restore and recovery remain.

## 7. Current completion path

The module `CURRENT_STATUS.md` contains the exact current CI/RPM identity and first live gate. PostgreSQL standalone remains first live qualification:

```text
fresh Rocky VM
 -> exact current RPM install
 -> root/OS-disk rejection proof
 -> attached non-OS disk inventory
 -> Go plan/confirmation
 -> Ansible PostgreSQL install/configure
 -> external data/WAL/log LVs as selected
 -> SELinux/firewalld
 -> health/read-write
 -> idempotent rerun
 -> backup + actual restore
 -> restart/reboot recovery
 -> repair/upgrade
 -> uninstall/residue/data preservation
```

Then qualify MySQL/MariaDB, Redis/Valkey and representative APaaS/runtime providers using the same control-plane/Ansible boundary.

Do not spend time on provider breadth while the current provider's first live gate fails.

## 8. Storage/security invariants

CloudStack remains volume authority. Guest storage uses stable device identity, live root/root-parent exclusion, explicit destructive confirmation, idempotent observation and persistent mounts.

Keep SELinux Enforcing and firewalld active. Never use `curl | bash`, eval, caller-controlled shell interpolation or plaintext secrets in logs/argv/evidence.

## 9. Cluster mode

Cluster support is provider-specific. Planning/mocks do not prove HA. Real DB replication/quorum/failover and Keepalived VRRP require real multi-node evidence.

Do not build automatic multi-node lab provisioning merely to simulate that evidence when the owner can provide/reinstall test VMs manually.

## 10. Status and handoff

At a meaningful evidence milestone, update `docs/layersentry/evidence/single-os/CURRENT_STATUS.md` and focused evidence. Do not append long history to the Progress Ledger. An integration/status reconciliation pass refreshes `LAYERSENTRY_CURRENT_STATUS.md` when the global summary materially changes.

Report only exact commit/files changed, source/live tests actually run, exact RPM/artifact identity, current provider gate reached, `LAB_RESET_REQUIRED` when applicable and the next exact provider gate.

Do not edit other modules or create broad handoff documents.