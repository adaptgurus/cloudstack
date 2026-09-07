# LayerSentry Single-OS DBaaS/APaaS — Super Master Context

**Schema:** 2.0  
**Execution owner:** ChatGPT by default  
**Architecture:** Go orchestration + Ansible Runner  
**Guest baseline:** Rocky Linux 9  
**Kubernetes dependency:** none

This context governs the VM-native LayerSentry DBaaS/APaaS path. It is separate from the Kubernetes-managed service plane.

Current source/runtime status belongs in `LAYERSENTRY_PROGRESS_LEDGER.md` and evidence. The presence of existing Go/provider code does not by itself imply live certification.

## 1. Product objective

Provide one reusable hardened Rocky Linux 9 image and install/configure selected software after the customer chooses the product/version/topology.

Normal workflow:

```text
LayerSentry GUI
 -> select VM-native deployment mode
 -> select product/version/topology
 -> select CloudStack VM/storage/network/VIP requirements
 -> CloudStack provisions infrastructure
 -> Go control service validates and builds immutable plan
 -> customer confirms
 -> Go invokes approved Ansible content
 -> health/security validation
 -> durable evidence/status
```

Do not maintain one image per application/version.

## 2. Isolation from Kubernetes DBaaS/APaaS

This module must not require:

- Kubernetes;
- RKE2;
- CAPI/CAPC/CAPRKE2;
- CRDs/operators;
- Flux.

The two service models may share CloudStack APIs, identity/RBAC, secrets infrastructure, UI design language, release trust and observability presentation, but they do not share lifecycle state machines or runtime certification evidence.

## 3. CloudStack ownership

CloudStack remains authoritative for:

- VM create/delete/start/stop;
- volumes/disks and attachment;
- networks/IPs exposed by CloudStack;
- templates/images;
- project/account/RBAC/quota;
- infrastructure lifecycle.

The guest layer manages only software and OS-local storage/network configuration inside the assigned VM.

Never create a second volume scheduler or attach CloudStack volumes behind CloudStack's back.

## 4. Selected architecture

```text
LayerSentry UI/API
      |
      v
Go control/orchestration service
  - auth/project binding
  - schema validation
  - version/provider policy
  - plan generation
  - confirmation digest
  - operation UUID/idempotency
  - lifecycle lock
  - journal/state
  - secret references
  - execution/result/evidence handling
      |
      v
Ansible Runner / ansible-core
      |
      v
Versioned roles/playbooks
      |
      v
Rocky Linux 9 guest
```

### 4.1 Go responsibility

Retain the existing Go implementation where it provides durable product control:

- API and authorization boundary;
- configuration schema/model;
- immutable plan and confirmation;
- lifecycle/idempotency lock;
- journal/state;
- secret-reference handling;
- provider capability metadata;
- target/inventory selection;
- invoking Ansible Runner using allowlisted playbooks/roles;
- observing Ansible results;
- provider health/evidence aggregation;
- rollback/recovery decision state;
- support diagnostics.

Do not keep growing Go with large amounts of imperative package/configuration logic that Ansible handles more safely and maintainably.

## 5. Ansible responsibility

Ansible is the approved installation/configuration engine.

Target source layout:

```text
tools/layersentry/ansible/
  ansible.cfg
  collections/requirements.yml
  inventory/
  playbooks/
    single_os_apply.yml
    single_os_upgrade.yml
    single_os_repair.yml
    single_os_uninstall.yml
  roles/
    rocky9_base/
    storage_lvm/
    network_vip/
    postgresql/
    mysql/
    mariadb/
    redis/
    valkey/
    nginx/
    httpd/
    tomcat/
    nodejs/
    python/
    podman/
```

Exact structure may evolve, but roles must remain small, composable, versioned and idempotent.

Ansible owns, as applicable:

- repository configuration;
- package install/remove/update;
- users/groups/directories/permissions;
- templated service configuration;
- systemd lifecycle;
- SELinux labels/policy application;
- firewalld rules;
- LVM/filesystem/mount management;
- NetworkManager/static secondary VIP/Keepalived configuration;
- database initialization;
- product-specific standalone/cluster configuration;
- patch/upgrade;
- repair/reconcile;
- uninstall/residue cleanup.

## 6. No shell-script installation

Bash/sh is not the product lifecycle engine.

Do not implement provider installation/configuration, LVM/storage setup, database/application setup, cluster join, upgrade, repair or uninstall as shell scripts.

Existing shell-based runtime installation/configuration assets are deprecated and must not be extended. Migrate their behavior to Ansible.

Build/packaging developer wrappers may remain temporarily only when they are not the customer/runtime installation boundary.

Inside Ansible:

- prefer dedicated modules;
- prefer templates for configuration files;
- use handlers for service restart/reload;
- use `command`/purpose-built modules for unavoidable vendor CLIs;
- avoid `shell` and `raw` except a narrowly documented exception;
- never interpolate untrusted configuration into a shell expression.

## 7. Declarative intent

The UI/API sends strict schema-versioned intent containing non-secret configuration and secret references.

Minimum logical fields as applicable:

- schema version;
- operation UUID/idempotency key;
- project/VM target identity;
- product/provider identifier;
- release line/version policy;
- exact resolved version after planning;
- standalone/cluster topology;
- node/role identity;
- peer endpoints;
- storage/volume/mount purpose;
- network/listener/VIP requirements;
- feature flags;
- secret references;
- maintenance/upgrade policy;
- expected health assertions.

The Go service validates intent and generates an immutable execution plan before Ansible mutation begins.

Customer confirmation must bind to the exact plan digest.

## 8. Secret handling

Secrets must not be persisted in plaintext in:

- intent files committed to Git;
- plan/state/journal;
- browser code;
- Ansible role defaults/vars;
- normal Ansible logs;
- evidence bundles.

Use approved runtime secret references/injection.

Where Ansible receives a secret value, apply `no_log: true` to the exact task/result scope that could expose it while preserving useful non-secret evidence separately.

## 9. Storage and LVM

CloudStack creates/attaches infrastructure volumes. Inside the guest, Ansible may manage LayerSentry-owned LVM/filesystems/mounts only after the Go plan identifies the approved attached devices and destructive confirmations.

Safety requirements:

- stable device identity such as `/dev/disk/by-*` where feasible;
- explicit root/OS-disk exclusion;
- explicit confirmation before PV initialization or filesystem formatting;
- `ls_` or another reserved LayerSentry ownership naming convention for managed VG/LV objects;
- idempotent observation before mutation;
- repair does not replay destructive initialization from old confirmations;
- persistent mount definitions;
- product-specific ownership/permissions/SELinux labels.

## 10. Network and VIP

CloudStack remains authoritative for cloud network/IP resources.

Inside the guest Ansible may configure, when explicitly selected and supported:

- provider listener addresses;
- persistent secondary IP through NetworkManager;
- Keepalived/VRRP for a guest-local floating VIP;
- provider-specific firewalld rules.

Do not invent a cloud-side VIP behind CloudStack's back.

Real VRRP failover requires a real multi-node test environment before live/production claims.

## 11. Provider model

Provider definitions should describe:

- supported release lines;
- package/repository source policy;
- Ansible role/playbook identity;
- supported standalone/cluster topologies;
- required storage purposes/mounts;
- ports/listeners/VIP support;
- health assertions;
- backup/restore method;
- patch/upgrade path;
- rollback/recovery semantics;
- resource requirements;
- destructive operations and confirmations.

Initial provider priorities:

1. PostgreSQL standalone vertical slice;
2. MySQL/MariaDB family;
3. Redis/Valkey;
4. Nginx/Apache/Tomcat;
5. Node.js/Python/Podman runtime providers;
6. cluster topologies only after standalone lifecycle quality is proven.

Do not claim whole-provider support from plan-only logic.

## 12. Cluster mode

Cluster semantics are provider-specific.

Before mutation validate:

- node role/topology;
- peer uniqueness/addressing;
- version compatibility;
- required ports/connectivity;
- time/DNS assumptions;
- storage readiness;
- quorum/bootstrap prerequisites;
- existing provider-native cluster state.

Ansible may orchestrate bootstrap/join where supported, but LayerSentry must not become a competing consensus authority.

Real multi-node replication/quorum/failover evidence requires a real multi-VM environment. Mocks/local namespaces prove only parser/planner/error handling.

## 13. Backup/recovery

Every DB/application provider must define a truthful backup/recovery contract.

Where CloudStack VM backup is appropriate, integrate with the global Backup/DR authority rather than creating a second DR system. Where database-native logical/physical backup/PITR is required, expose it through the provider contract and validate actual restored data.

Do not equate VM snapshot success with application-consistent database recovery.

## 14. Hardening

Required baseline:

- Rocky Linux 9 supported baseline;
- SELinux Enforcing;
- firewalld active/default-deny;
- explicit provider ports only;
- no `curl | bash`, arbitrary remote scripts or `eval`;
- no normal root-password SSH for production appliances;
- safe canonical path/symlink handling;
- bounded timeouts/retries/cache/log growth;
- least privilege/systemd hardening for the Go service and Runner boundary;
- no secrets in argv/logs/evidence;
- rollback cannot disable SELinux/firewall/security controls to make a provider start.

## 15. Lifecycle contract

A normal mutation follows:

```text
validate intent
 -> authorize target
 -> acquire operation lock
 -> inspect current guest state
 -> resolve exact approved version
 -> validate repositories/signatures/provenance
 -> build immutable plan
 -> customer confirmation
 -> optional safe checkpoint
 -> execute approved Ansible playbook/roles
 -> health/security assertions
 -> commit durable state/evidence
 -> cleanup bounded temporary/cache state
```

An ambiguous mutation must be observed/reconciled before retrying. Do not blindly rerun a failed/unknown playbook if duplicate execution could be destructive.

## 16. First vertical slice definition of done

PostgreSQL standalone is the first proof.

Required path:

```text
GUI/API intent
 -> CloudStack VM + attached data volume(s)
 -> Go immutable plan
 -> approved Ansible execution
 -> PostgreSQL exact package/version installed
 -> external data/WAL/log mapping as selected
 -> SELinux/firewalld preserved
 -> service health
 -> idempotent rerun
 -> reboot/recovery
 -> backup + actual restore validation
 -> same-line patch/repair where supported
 -> uninstall/residue audit
```

Only after this is proven should provider breadth expand aggressively.

## 17. Evidence ceiling

Use repository-wide statuses.

- source + source tests may reach `SOURCE_COMPLETE`;
- reproducible automation may reach `CI_VERIFIED`;
- actual Rocky execution may reach `LIVE_VERIFIED` for the exact tested provider/topology;
- real multi-node HA/replication/failover remains below live certification until exercised on a real multi-node environment;
- `PRODUCTION_CERTIFIED` requires provider-specific security, backup/recovery, upgrade/rollback, resource/performance and supported-topology evidence.

## 18. Execution ownership

This workstream is **ChatGPT-led by default** to conserve Codex credits for Kubernetes/RKE2.

Codex must not be started for routine Single-OS provider/Ansible implementation unless the owner explicitly changes the execution contract.
