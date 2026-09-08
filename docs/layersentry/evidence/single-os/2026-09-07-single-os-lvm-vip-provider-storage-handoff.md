# LayerSentry Single-OS — LVM / Provider Data Roots / VIP / File Workflow Handoff

> **SUPERSEDED STATUS / EVIDENCE NOTE — 2026-09-07:** This file is historical implementation context, not current startup authority. Its original source-validation section referenced `2026-09-07-single-os-lvm-vip-provider-storage-source-validation.md`, but that file was never committed on the shared branch. The original test/vet/build pass claims therefore do not have the durable evidence required by `AGENTS.md`. Do not inherit `SOURCE_COMPLETE`, `CI_VERIFIED`, or a passed source-validation result from this handoff. Use `docs/layersentry/evidence/single-os/CURRENT_STATUS.md` and `2026-09-07-single-os-continuity-authority-reconciliation.md`. The selected current target architecture is now Go orchestration + Ansible Runner; the substantial Go source below must be preserved while imperative guest execution is migrated, and Ansible remains `PENDING` until its source tree exists.

**Date:** 2026-09-07  
**Repository:** `adaptgurus/cloudstack`  
**Required shared branch:** `layersentry/4.22.1.1-ui`  
**Workstream:** F — VM-native Single-OS DBaaS/APaaS  
**CloudStack baseline:** Apache CloudStack 4.22.1.1  
**Guest baseline:** Rocky Linux 9  
**CloudStack Java/backend/schema/KVM-core impact:** **NO**  
**Kubernetes/RKE2/CAPI dependency:** **NO**

> Fetch the actual current branch HEAD before changing anything. Other agents may advance the same shared branch after this handoff. Never reset the branch to a SHA copied from documentation and never force-push.

## 1. Historical evidence status and correction

The original version of this handoff claimed:

- engine/security/LVM/provider-data/VIP/file-workflow source: `SOURCE_COMPLETE`;
- Go unit/security tests passed;
- `go vet ./...` passed;
- `go build ./cmd/layersentryd ./cmd/layersentryctl` passed;
- shell syntax passed;
- an exact validation record existed at `docs/layersentry/evidence/single-os/2026-09-07-single-os-lvm-vip-provider-storage-source-validation.md`.

The referenced validation file is absent and has no path history on the shared branch. Those historical test-result claims are therefore **not durable evidence** and are superseded for status purposes.

Current reconciliation is:

- existing Go guest-engine/provider implementation: `PARTIAL`;
- Go→Ansible target architecture: `DESIGN_DEFINED`;
- Ansible roles/playbooks/Runner implementation: `PENDING` until source exists;
- historical September 7 source-validation outcome: `UNKNOWN`;
- `CI_VERIFIED`: `NOT_TESTED` for this Single-OS scope;
- Rocky Linux 9 live qualification: `NOT_TESTED`;
- real PostgreSQL multi-node replication/failover: `NOT_TESTED`;
- real Keepalived MASTER/BACKUP takeover: `NOT_TESTED`;
- production certification: `NOT_TESTED`.

Do not translate historical source assertions into current CI/live/production evidence.

## 2. Current startup sequence

Do **not** use this historical handoff as the normal startup sequence.

Read current authority in this order:

1. `/AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. `docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`;
5. `docs/layersentry/evidence/single-os/CURRENT_STATUS.md`;
6. fetch the actual current shared branch/source/tests;
7. use `docs/layersentry/evidence/single-os/2026-09-07-single-os-continuity-authority-reconciliation.md` only when the continuity discrepancy itself matters.

Continue existing source; never rewrite it from an older chat summary.

## 3. Infrastructure/software ownership boundary

CloudStack remains authoritative for:

- VM creation/deletion;
- disk/volume creation and attachment;
- networks/IPs exposed by CloudStack;
- tenancy/project/account/RBAC/quota;
- template/power/infrastructure lifecycle.

The Single-OS guest engine is authoritative only for software/storage layout **inside an already-provisioned guest**:

- stable attached-disk discovery;
- root-disk exclusion;
- confirmed PV/VG/LV creation;
- filesystem creation and persistent mounts;
- provider data/content directory ownership;
- SELinux data/content labels;
- exact package install/config/init;
- provider firewall rules;
- optional guest-local secondary/VRRP VIP;
- service lifecycle/health;
- backup/restore/patch/repair/uninstall/residue.

The guest must never invent a second CloudStack volume scheduler or attach cloud volumes behind CloudStack's back.

Under the newer execution contract, the control/state/security parts of this historical implementation are retained in Go while imperative guest package/configuration/LVM/SELinux/firewall/VIP/provider actions are migration candidates for versioned Ansible roles/playbooks. Historical Go implementation details below describe source that exists and should be mined/preserved during migration; they do not override the newer execution boundary.

## 4. Reusable-image contract

The reusable Rocky 9 image contains only the hardened OS, LayerSentry binaries/services and orchestration prerequisites including LVM2, NetworkManager/nmcli, SELinux management tooling, firewalld and filesystem utilities.

It deliberately does **not** contain PostgreSQL, MySQL, MariaDB, Redis, Valkey, Nginx, HTTPD, Tomcat, Node.js, Python 3.12, Podman or Keepalived. Provider packages and Keepalived are resolved/pinned/installed only after the customer selects the service and confirms the immutable plan.

`image/validate-image.sh` was implemented to fail a sealed image if a provider package or Keepalived was accidentally left installed. This remains source history until the current migrated execution path is revalidated.

## 5. LVM and OS-disk safety

The historical Go intent/source supports LayerSentry-owned LVM with:

- `lvm[].name` — `ls_` prefix;
- `lvm[].devices[]` — stable `/dev/disk/by-*` only;
- `initialize_pvs` plus independent `confirm_pv_initialize`;
- logical volumes with `ls_` names;
- explicit sizes (`10G`, `100G`, etc.) or one final `100%FREE`;
- XFS/ext4;
- independent `format` and `confirm_format`;
- provider storage purposes and approved mount roots.

The historical implementation intended OS/root disk protection twice:

1. ordinary preflight resolves `/` ancestry using `findmnt`/`lsblk` and rejects root/root-parent devices;
2. the isolated root `lvmexec` helper repeats the live root-ancestry check before PV/VG mutation.

These invariants must be preserved by the Ansible `storage_lvm` migration. Ansible migration must not weaken destructive confirmation or OS-disk rejection.

LVM creation belongs only in the original confirmed install transaction. Repair/recovery must remain observation/idempotency safe and must not replay historical destructive authorization.

## 6. Provider external-data semantics to preserve during migration

### PostgreSQL

Historical source supports external roots for `database-data`, `database-wal` and `database-logs` through direct filesystems or LVs.

For a friendly external data root such as `/data/postgresql` the intended model is:

- create `/data/postgresql/data` owned by `postgres`, mode 0700;
- persistent SELinux equivalence to `/var/lib/pgsql`;
- bind the child `data` directory to `/var/lib/pgsql/<major>/data`;
- keep PGDG systemd/service semantics standard;
- run `initdb -D /var/lib/pgsql/<major>/data` as `postgres`;
- avoid ext4 `lost+found` inside actual PGDATA.

External WAL root produces `<root>/wal`; external log root produces `<root>/logs`.

### MySQL

Historical source intended external `database-data` root `<root>/data`, owned by `mysql`, with SELinux equivalence to `/var/lib/mysql`, and explicit initialization with:

`mysqld --initialize-insecure --user=mysql --datadir=<root>/data`

Firewall-before-first-network-start and immediate secure local/admin bootstrap are invariants to preserve. External `database-logs` produces `<root>/logs` with the correct SELinux type.

### MariaDB

Historical source intended explicit initialization with:

`mariadb-install-db --user=mysql --datadir=<root>/data --auth-root-authentication-method=socket --skip-test-db`

### Redis / Valkey

Historical source intended external `<root>/data`, provider ownership, persistent SELinux mapping, and a vendor-compatible RDB location. Durable configuration stores only password verifier material; plaintext password remains in the secret boundary/in memory.

### Nginx / Apache HTTPD

External `application-data` root produces `<root>/www`, with `httpd_sys_content_t` and only LayerSentry-managed root/DocumentRoot mutation.

### Tomcat

External `application-data` root produces `<root>/webapps`; the managed Host `appBase` is changed to that absolute directory and restored on uninstall.

### Node.js / Python / Podman

These remain package/runtime providers rather than arbitrary application-data owners. Their runtime packages stay package-managed on the OS.

The Ansible migration should preserve these product semantics using dedicated modules/templates/handlers rather than maintaining parallel imperative Go execution.

## 7. VIP semantics to preserve during migration

VIP remains optional under `network.vip`.

### Secondary/manual VIP

Historical model:

- customer supplies VIP address/prefix/interface;
- service listen address may equal the secondary VIP;
- persist through the active NetworkManager connection;
- add/remove converges;
- refuse unsafe coexistence with active `nm-cloud-setup.service` when metadata reconciliation may remove the manual address;
- no Keepalived package required.

### VRRP VIP

Historical model requires:

- floating VIP and prefix;
- interface;
- local node `source_address` for unicast VRRP;
- MASTER/BACKUP state;
- virtual_router_id;
- priority;
- unicast peers.

Safety semantics to preserve:

- VRRP requires cluster topology;
- service must accept the floating IP after role changes;
- source_address is a real local IPv4 on the selected interface;
- VRRP peers are declared cluster peers;
- Keepalived exact package/repository provenance is bound to the reviewed plan;
- firewalld admits VRRP only from declared peer addresses;
- one LayerSentry VRRP owner per guest in the V1 design;
- ownership/state is durable before mutation so partial failure remains recoverable.

Actual failover/takeover remains `NOT_TESTED` until real multi-node evidence exists.

## 8. Historical config-file workflow

The historical implementation added:

`/usr/bin/layersentry-configure-from-file`

with validate/plan/apply semantics and secret references rather than plaintext secrets.

Under the current execution contract, shell is not the product lifecycle engine. Do not extend this wrapper into a provider/LVM/VIP installer. Migrate runtime guest mutation to the Go→Ansible contract; a small wrapper may remain only as a non-authoritative developer/operator transport if it does not perform product installation logic itself.

## 9. Historical documentation review

The historical implementation was designed around first-party PostgreSQL, MySQL, MariaDB, Redis/Valkey, Apache HTTPD, Tomcat and RHEL/Rocky Linux behavior. Those decisions remain useful migration input, but current provider support must be revalidated at the migrated Ansible vertical-slice evidence gate rather than inherited from this handoff.

## 10. Current next gates

The older instruction to jump directly to RPM/Hyper-V qualification is superseded by the Go→Ansible migration contract.

Current sequence:

1. fetch current branch and inspect existing Go source;
2. implement the bounded Go→Ansible Runner foundation under the approved `tools/layersentry/ansible/` target;
3. migrate PostgreSQL standalone first, including external data/WAL/log, ownership, SELinux/firewalld, exact package/version policy and health;
4. add Ansible idempotency/negative tests and Go integration tests;
5. deprecate/remove duplicate imperative Go/shell runtime execution only after equivalent coverage exists;
6. run a fresh reproducible source-validation pass and commit exact evidence;
7. only then qualify the exact migrated artifact on Rocky Linux 9;
8. expand to MySQL/MariaDB, Redis/Valkey and APaaS/runtime providers after the PostgreSQL vertical slice passes;
9. retain real VRRP failover and real database HA/replication as `NOT_TESTED` until a real multi-node environment is authorized and exercised.

Never weaken SELinux/firewalld, use the OS disk for destructive storage tests, or claim production readiness from source presence alone.
