# LayerSentry Single-OS DBaaS/APaaS — Super Master Context

**Role:** stable specialist architecture and production contract  
**Execution owner:** ChatGPT by default  
**Architecture:** Go orchestration + Ansible Runner  
**Guest baseline:** Rocky Linux 9  
**Kubernetes dependency:** none

This context governs the VM-native LayerSentry DBaaS/APaaS path only. Current progress belongs in `LAYERSENTRY_CURRENT_STATUS.md`, `docs/layersentry/evidence/single-os/CURRENT_STATUS.md`, focused evidence and actual Git/workflow/live state. Historical expanded narrative remains available in Git history and is not normal startup context.

## 1. Hard separation from Kubernetes services

Single-OS DBaaS/APaaS does **not** require:

- Kubernetes/RKE2;
- CAPI/CAPC/CAPRKE2;
- CRDs/operators;
- Flux.

The Kubernetes and Single-OS service models may share CloudStack APIs, identity/RBAC, release trust, observability presentation and UI design language, but they do not share lifecycle state machines, provider implementations or runtime certification evidence.

A Kubernetes audit/workstream must not modify Single-OS source, and a Single-OS workstream must not modify Kubernetes source.

## 2. Architecture and ownership

```text
LayerSentry UI/API
 -> Go control/orchestration
 -> Ansible Runner / ansible-core
 -> versioned roles/modules/playbooks
 -> Rocky Linux 9 guest
```

CloudStack remains authoritative for VM creation/deletion/start/stop, attached volumes, networks/IPs, templates, project/account/RBAC/quota and infrastructure lifecycle.

### Go owns

- authentication/authorization and project/target binding;
- strict schema/provider/version policy;
- immutable execution plan and confirmation digest;
- operation UUID/idempotency/locking;
- durable state/journal and reconciliation decisions;
- secret references;
- target inventory selection;
- allowlisted Ansible invocation/result handling;
- health/evidence aggregation;
- support/recovery state.

### Ansible owns

- repositories/packages;
- users/groups/files/directories/permissions;
- templated configuration;
- systemd lifecycle;
- SELinux labels/policy application;
- firewalld rules;
- LVM/filesystems/mounts;
- NetworkManager/static secondary VIP/Keepalived where supported;
- database/application initialization and configuration;
- patch/upgrade/repair/uninstall.

Do not create a second provider engine and do not rewrite the Go control plane from zero.

## 3. No shell-script product lifecycle

Bash/sh is not the customer/runtime installation engine.

Prefer dedicated Ansible modules/templates/handlers. Use fixed argv-safe command/module semantics only for unavoidable vendor CLIs. Never use `curl | bash`, `wget | sh`, `eval`, caller-controlled shell expressions or arbitrary playbook paths.

Build/developer wrappers may exist only when they are not the production lifecycle boundary.

## 4. Intent, secrets and mutation safety

The UI/API sends schema-versioned non-secret intent plus secret references. Go resolves the exact approved version and immutable plan before mutation. Customer confirmation binds to the exact plan digest when destructive/privileged work requires confirmation.

Secrets must not be stored in Git, browser code, normal logs, plan/journal/evidence or Ansible defaults. Use bounded runtime injection and `no_log` only around the exact Ansible tasks that can expose a secret.

Every mutation must define:

- target and ownership identity;
- idempotency semantics;
- observation before mutation;
- timeout/UNKNOWN handling;
- authoritative observation before retry;
- rollback/recovery class;
- bounded temporary/cache cleanup.

Do not blindly replay a failed/unknown destructive operation.

## 5. Storage and LVM

CloudStack creates/attaches infrastructure volumes. Inside the guest, LayerSentry may manage only approved attached devices.

Required safeguards:

- stable device identity such as `/dev/disk/by-*` where feasible;
- live root/OS-disk and root-parent exclusion;
- explicit destructive confirmation before PV/filesystem initialization;
- reserved LayerSentry ownership naming for managed VG/LV/filesystem objects;
- idempotent observation before mutation;
- repair never replays stale destructive initialization;
- persistent mounts;
- provider-specific owner/permission/SELinux labels.

A plan that can target the live OS/root disk must fail closed before mutation.

## 6. Network/VIP

CloudStack remains authoritative for cloud-side network/IP resources.

Guest-local configuration may include provider listeners, persistent secondary IP, Keepalived/VRRP and provider firewalld rules when explicitly supported.

Do not create a cloud-side VIP behind CloudStack's back. Real VRRP/failover claims require real multi-node live evidence.

## 7. Provider model and current priorities

Provider definitions describe supported versions/topologies, package source policy, Ansible content, storage purposes, ports/VIP behavior, health checks, backup/restore, patch/upgrade, uninstall and recovery semantics.

Current execution priority remains:

1. PostgreSQL standalone live vertical slice;
2. MySQL/MariaDB;
3. Redis/Valkey;
4. representative Nginx/HTTPD/Tomcat/runtime providers;
5. provider-specific multi-node/HA only after standalone quality is proven.

Current source already contains substantial Go control/provider code and Ansible roles/playbooks. The exact current implemented/CI state is defined only by the module `CURRENT_STATUS.md`; do not regress it because an older handoff predates current source.

## 8. First production vertical slice

PostgreSQL standalone is the first proof:

```text
fresh Rocky 9 VM + separate non-OS data disk
 -> exact current RPM install
 -> live root/OS-disk rejection proof
 -> immutable Go plan/confirmation
 -> Ansible PostgreSQL install/configure
 -> external data/WAL/log mapping as selected
 -> SELinux/firewalld preserved
 -> health/read-write
 -> exact idempotent rerun
 -> backup + actual restore/data-integrity verification
 -> VM reboot and mount/service/data recovery
 -> repair/upgrade where supported
 -> uninstall/residue audit with customer-data preservation
```

Do not expand provider breadth while this vertical slice's first live gate fails.

## 9. Backup/recovery

Every provider must expose a truthful backup/recovery contract.

CloudStack VM backup may be integrated where appropriate, but VM backup/snapshot success is not automatically application-consistent DB recovery. Database-native logical/physical backup or PITR is exposed only when supported and proven by actual restored data.

Cross-site DR remains governed by the independent global DR workstream. This Single-OS context does not invent a competing DR system.

## 10. Security baseline

Minimum:

- Rocky Linux 9 supported baseline;
- SELinux Enforcing;
- firewalld active/default-deny with explicit provider ports;
- least-privilege systemd/Runner boundary;
- no normal root-password SSH for production appliance use;
- safe canonical path/symlink handling;
- bounded timeouts/retries/cache/log growth;
- no secrets in argv/logs/evidence;
- rollback cannot disable security controls simply to make a provider start.

## 11. Lab reset optimization

Disposable acceptance VMs may be manually reinstalled/recreated by the owner after a destructive/dirty failed test.

When that happens:

1. capture exact failure/evidence;
2. stop mutating the guest;
3. report `LAB_RESET_REQUIRED` with clean-host prerequisites;
4. resume the same gate on the fresh Rocky VM.

Do not spend engineering/Codex effort building automatic test-VM reimage/snapshot rollback solely for lab cleanup. This does not remove product idempotency, repair, upgrade, uninstall, backup/restore or recovery requirements.

## 12. Evidence ceiling

Use repository-wide statuses only.

- source/tests may reach `SOURCE_COMPLETE`;
- reproducible exact automation/artifact evidence may reach `CI_VERIFIED`;
- actual Rocky execution may reach `LIVE_VERIFIED` for the exact provider/topology;
- real multi-node replication/quorum/failover requires real multi-node evidence;
- `PRODUCTION_CERTIFIED` additionally requires provider-specific security, backup/recovery, upgrade/rollback, resource/performance and supported-topology evidence.

Current exact RPM/workflow/live gate belongs in `docs/layersentry/evidence/single-os/CURRENT_STATUS.md`, not this stable master.