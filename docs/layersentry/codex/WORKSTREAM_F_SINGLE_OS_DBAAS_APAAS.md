# LayerSentry Workstream F — VM-Native Single-OS DBaaS/APaaS

**Default execution owner:** ChatGPT  
**Codex use:** disabled by default for this workstream  
**Architecture:** Go orchestration + Ansible Runner  
**Guest baseline:** Rocky Linux 9

This filename is retained for continuity. It is no longer a standing Codex workstream. The current execution authority is `LAYERSENTRY_EXECUTION_CONTRACT.md`.

## Mission

Finish the VM-native LayerSentry DBaaS/APaaS path without Kubernetes and without shell-script-based product installation.

Preserve the useful existing Go control-plane investment, migrate imperative guest installation/configuration to Ansible, then prove complete provider vertical slices.

## Startup

Read only:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. `LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
5. `docs/layersentry/evidence/single-os/CURRENT_STATUS.md`;
6. `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md` only when needed for a trust boundary;
7. fetch the actual branch and current source/tests.

Do not use old handoffs as source authority when the current branch is newer. Do not infer that implementation disappeared after a chat reset, and do not infer that the target Ansible tree exists before the repository proves it.

## Continuity rule

Current source is authoritative for what is implemented. `CURRENT_STATUS.md` is the concise Workstream-F evidence checkpoint. Dated handoffs are historical context after their durable findings have been reconciled.

At any fresh-session start:

- inspect `tools/layersentry/single-os/agent/` before proposing a rewrite;
- inspect whether `tools/layersentry/ansible/` actually exists before claiming Ansible is implemented;
- preserve existing Go schema/plan/idempotency/journal/secrets/security behavior during migration;
- do not inherit source-test pass claims whose exact evidence artifact is absent.

## Non-overlap with Kubernetes services

This path must not depend on CAPI, CAPC, CAPRKE2, RKE2, Kubernetes operators or Flux.

CloudStack provisions VM/network/storage. The Single-OS service manages software inside that VM.

## Selected architecture

```text
LayerSentry UI/API
 -> Go orchestration service
 -> Ansible Runner
 -> versioned roles/playbooks
 -> Rocky Linux 9 guest
```

### Go owns

- API/auth/project binding;
- schema validation;
- provider/version policy;
- immutable plan/confirmation digest;
- operation UUID/idempotency;
- lifecycle lock;
- durable journal/state;
- secret references;
- inventory/target selection;
- allowlisted Ansible invocation;
- result/health/evidence aggregation;
- rollback/recovery state;
- support diagnostics.

### Ansible owns

- OS baseline/hardening application;
- repositories and packages;
- users/directories/permissions;
- service configuration;
- systemd;
- SELinux;
- firewalld;
- LVM/filesystems/mounts;
- NetworkManager/VIP/Keepalived where selected;
- PostgreSQL/MySQL/MariaDB/Redis/Valkey;
- Nginx/Apache/Tomcat;
- Node.js/Python/Podman;
- provider-specific upgrade/repair/uninstall;
- provider-specific cluster bootstrap/join where appropriate.

This is the selected target boundary. Ansible is not current implementation evidence until the repository contains and wires the roles/playbooks/Runner contract.

## Shell-script prohibition

Do not implement runtime/product installation/configuration as Bash/sh scripts.

Existing shell-based installation/configuration assets are deprecated and must not be extended. Migrate the relevant behavior to Ansible.

Build-only developer/packaging wrappers may remain temporarily if they are not the customer/runtime installation boundary.

Inside Ansible, prefer dedicated modules and templates. Avoid `shell`/`raw`; use argv-safe command/module semantics for unavoidable vendor CLIs.

## Target Ansible structure

```text
tools/layersentry/ansible/
  ansible.cfg
  collections/requirements.yml
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

Do not create one monolithic playbook.

## Migration rule for existing source

Do not discard the current Go engine and rewrite from zero.

For each existing imperative Go/shell provider path:

1. identify control-plane logic that belongs in Go;
2. identify guest configuration logic that belongs in Ansible;
3. preserve the Go schema/state/security contract;
4. implement the Ansible role/playbook;
5. switch the Go provider/executor to the Ansible contract;
6. add idempotency/negative tests;
7. remove/deprecate the old runtime installation path after equivalent coverage exists.

Avoid maintaining two active provider implementations.

## First provider vertical slice

PostgreSQL standalone is first.

Definition of done:

```text
GUI/API intent
 -> CloudStack VM + attached volume(s)
 -> Go preflight/plan
 -> exact version resolved/pinned
 -> confirmation digest
 -> Ansible install/configure
 -> external data/WAL/log mapping where selected
 -> SELinux/firewalld proof
 -> service health
 -> idempotent rerun
 -> VM reboot recovery
 -> backup and actual restore proof
 -> patch/repair where supported
 -> uninstall/residue/security audit
```

Only then expand aggressively to MySQL/MariaDB, Redis/Valkey and APaaS/runtime providers.

## Storage safety

CloudStack remains volume authority.

Inside the guest:

- stable attached-device identity;
- root/OS-disk exclusion;
- explicit destructive confirmation before PV/filesystem initialization;
- managed ownership naming;
- idempotent observation before mutation;
- repair must not replay old destructive confirmations;
- persistent mounts;
- provider-specific permissions and SELinux labels.

Implement these through Ansible modules plus Go plan/confirmation safety while preserving any stronger guard already present in existing source.

## Cluster mode

Cluster support is provider-specific.

Go validates topology and peer identities; Ansible performs approved bootstrap/join/configuration; the database/application remains the consensus authority.

Mocks/local isolation can test planning and errors, but real replication/quorum/failover requires real multi-node evidence.

Exact current lab capacity/topology belongs in the progress/evidence status, not this stable workstream file.

## Security

- SELinux Enforcing;
- firewalld active/default-deny;
- no `curl | bash`, arbitrary remote scripts or `eval`;
- no caller-controlled shell interpolation;
- secrets by runtime reference and redacted from Ansible output with scoped `no_log` where required;
- TLS/signature/provenance validation for package sources;
- safe paths/symlinks;
- bounded timeouts/retries/cache/log growth;
- least-privilege Runner/Go service boundary;
- rollback must not disable security controls.

## Evidence

Source tests can promote a bounded migrated slice to `SOURCE_COMPLETE` only when the exact current architecture path and its tests are durably recorded.

The provider becomes `LIVE_VERIFIED` only after the exact artifact/Ansible content runs on the intended Rocky guest and actual service/data/restart/recovery assertions pass.

Do not claim cluster HA from single-node or mocked tests. Do not use an absent historical validation file as evidence.

## Handoff

Keep it short:

- branch/commit;
- Go boundary changed;
- Ansible roles/playbooks changed;
- old runtime path removed/deprecated;
- tests executed and exact evidence path;
- live target/evidence if any;
- first unmet provider vertical-slice gate.
