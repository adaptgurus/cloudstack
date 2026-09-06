# LayerSentry Single-OS — LVM / Provider Data Roots / VIP / File Workflow Handoff

**Date:** 2026-09-07  
**Repository:** `adaptgurus/cloudstack`  
**Required shared branch:** `layersentry/4.22.1.1-ui`  
**Workstream:** F — VM-native Single-OS DBaaS/APaaS  
**CloudStack baseline:** Apache CloudStack 4.22.1.1  
**Guest baseline:** Rocky Linux 9  
**CloudStack Java/backend/schema/KVM-core impact:** **NO**  
**Kubernetes/RKE2/CAPI dependency:** **NO**

> Fetch the actual current branch HEAD before changing anything. Other agents may advance the same shared branch after this handoff. Never reset the branch to a SHA copied from documentation and never force-push.

## 1. Evidence status

For the source scope covered by this handoff:

- engine/security/LVM/provider-data/VIP/file-workflow source: `SOURCE_COMPLETE`;
- Go unit/security tests: passed in the source-validation run;
- `go vet ./...`: passed;
- `go build ./cmd/layersentryd ./cmd/layersentryctl`: passed;
- shell syntax for the changed provisioning/image/package scripts: passed;
- exact source-validation evidence: `docs/layersentry/evidence/single-os/2026-09-07-single-os-lvm-vip-provider-storage-source-validation.md`;
- Rocky Linux 9 Hyper-V live qualification: `NOT_TESTED` for this new scope;
- real PostgreSQL multi-node replication/failover: `NOT_TESTED` and provider-native standby join remains fail-closed;
- real Keepalived MASTER/BACKUP takeover: `NOT_TESTED` under the one-VM Workstream-F acceptance envelope;
- production certification: `NOT_TESTED`.

Do not translate source/CI evidence into live or production evidence.

## 2. Mandatory startup sequence for the next session

Read, in order:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. `docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`
5. `docs/layersentry/LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`
6. `docs/layersentry/codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`
7. `docs/layersentry/evidence/single-os/2026-09-07-single-os-lvm-vip-provider-storage-source-validation.md`
8. this handoff
9. fetch the actual current shared branch and inspect concurrent work;
10. continue the existing implementation, never rewrite it from an older chat summary.

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

## 4. Reusable-image contract

The reusable Rocky 9 image contains only the hardened OS, LayerSentry binaries/services and orchestration prerequisites including LVM2, NetworkManager/nmcli, SELinux management tooling, firewalld and filesystem utilities.

It deliberately does **not** contain PostgreSQL, MySQL, MariaDB, Redis, Valkey, Nginx, HTTPD, Tomcat, Node.js, Python 3.12, Podman or Keepalived. Provider packages and Keepalived are resolved/pinned/installed only after the customer selects the service and confirms the immutable plan.

`image/validate-image.sh` fails a sealed image if a provider package or Keepalived was accidentally left installed.

## 5. LVM and OS-disk safety

The service intent supports LayerSentry-owned LVM with:

- `lvm[].name` — must use `ls_` prefix;
- `lvm[].devices[]` — stable `/dev/disk/by-*` only;
- `initialize_pvs` plus independent `confirm_pv_initialize`;
- logical volumes with `ls_` names;
- explicit sizes (`10G`, `100G`, etc.) or one final `100%FREE`;
- XFS/ext4;
- independent `format` and `confirm_format`;
- provider storage purposes and approved mount roots.

The OS/root disk is protected twice:

1. ordinary preflight resolves `/` ancestry using `findmnt`/`lsblk` and rejects root/root-parent devices;
2. the isolated root `lvmexec` helper repeats the same live root-ancestry check before PV/VG mutation.

A compromised API daemon therefore still cannot request PV creation on the OS/root disk through the LVM helper.

LVM creation is only allowed in the original confirmed install transaction. Repair/recovery uses observation-only `EnsureMounted`: it proves LayerSentry ownership and existing PV/VG/LV/filesystem state and never replays PV initialization or filesystem creation from historical confirmations.

## 6. Provider external-data semantics

### PostgreSQL

Customer may supply external roots for `database-data`, `database-wal` and `database-logs` through direct filesystems or LVs.

For a friendly external data root such as `/data/postgresql`:

- LayerSentry creates `/data/postgresql/data` owned by `postgres`, mode 0700;
- external root receives persistent SELinux equivalence to `/var/lib/pgsql`;
- the child `data` directory is persistently bind-mounted to `/var/lib/pgsql/<major>/data`;
- PGDG systemd/service semantics therefore remain standard;
- the existing provider runs `initdb -D /var/lib/pgsql/<major>/data` as `postgres`;
- this avoids ext4 `lost+found` inside actual PGDATA.

External WAL root produces `<root>/wal` and is passed to `initdb --waldir`. External log root produces `<root>/logs` and is written into `postgresql.conf` as `log_directory`.

### MySQL

External `database-data` root produces `<root>/data`, owned by `mysql`, with persistent SELinux equivalence to `/var/lib/mysql`.

LayerSentry explicitly initializes an empty custom MySQL datadir using:

`mysqld --initialize-insecure --user=mysql --datadir=<root>/data`

The network firewall is applied before first service start. The existing local bootstrap immediately provisions the LayerSentry administrator from a secret reference. MySQL root localhost authentication is converted to the `auth_socket` plugin so local administrative tooling/backups do not require a stored root password.

External `database-logs` root produces `<root>/logs` with persistent `mysqld_log_t` labeling and is configured as the error-log location.

### MariaDB

External `database-data` root produces `<root>/data`, owned by `mysql`, and is explicitly initialized with:

`mariadb-install-db --user=mysql --datadir=<root>/data --auth-root-authentication-method=socket --skip-test-db`

The existing encrypted backup/TLS/admin lifecycle remains intact.

### Redis / Valkey

External `database-data` root produces `<root>/data`, owned by the provider account and persistently SELinux-labeled equivalent to `/var/lib/redis` or `/var/lib/valkey`.

The external child is bind-mounted into the provider-owned RDB directory so existing encrypted backup/restore and typed privileged operations remain narrow. Durable service config stores only the SHA-256 password verifier; plaintext password remains in the encrypted secret store/in memory.

### Nginx / Apache HTTPD

External `application-data` root produces `<root>/www`.

LayerSentry persists `httpd_sys_content_t`, rewrites only the LayerSentry-managed Nginx `root` or Apache `DocumentRoot`, and writes the deterministic health object into the external content root. Customer content is preserved by normal uninstall.

### Tomcat

External `application-data` root produces `<root>/webapps`, gets persistent provider-appropriate SELinux equivalence, and the exactly-one managed Tomcat `Host` `appBase` is rewritten to that absolute directory. The prior appBase is durably recorded and restored on uninstall.

### Node.js / Python / Podman

These remain package/runtime providers rather than application-data owners. Their runtime packages stay RPM-managed on the OS. Customer workspaces can be mounted independently, but the package-only provider does not pretend to own arbitrary application data, backup semantics or VIPs.

## 7. VIP semantics

VIP is optional and lives under `network.vip`.

### Secondary/manual VIP

`mode: "secondary"`

- customer supplies VIP address/prefix/interface;
- service listen address equals the secondary VIP;
- LayerSentry persists the address through the active NetworkManager connection;
- add/remove is convergent;
- if `nm-cloud-setup.service` is active, LayerSentry refuses the manual persistent VIP because metadata reconciliation could remove it;
- no additional package is installed.

### VRRP VIP

`mode: "vrrp"`

Required fields include:

- floating VIP and prefix;
- interface;
- **local node `source_address`** used for unicast VRRP;
- MASTER/BACKUP state;
- virtual_router_id;
- priority;
- unicast peers.

Rules:

- VRRP requires cluster topology;
- service binds `0.0.0.0` so it can accept the floating IP after role changes;
- source_address must be an actual local IPv4 address on the selected interface;
- VRRP peer IPs must also appear in the declared cluster peers;
- Keepalived is resolved from approved AppStream, exact NEVRA and repo digest are recorded in the immutable plan as a platform package pin;
- install refuses repository drift after plan confirmation;
- Keepalived config is generated from the reviewed values;
- firewalld permits VRRP only from declared peer /32 addresses;
- one LayerSentry VRRP service owns Keepalived on a guest in V1;
- ownership is journaled before mutation so a partial Keepalived/firewall failure remains recoverable.

Actual failover/takeover has not been live tested because Workstream F currently permits only one VM.

## 8. Immutable config-file workflow

Installed wrapper:

`/usr/bin/layersentry-configure-from-file`

Commands:

```text
layersentry-configure-from-file validate INTENT.json
layersentry-configure-from-file plan INTENT.json
layersentry-configure-from-file apply INTENT.json CONFIRMED_PLAN_SHA256
```

The file must contain the same strict schema used by the API. It contains secret references, never plaintext passwords/tokens.

`plan` performs validation/preflight/version/repository resolution and emits the immutable plan plus `confirmation_digest`; it does not start provider mutation.

`apply` requires the same intent file and exact reviewed 64-hex digest. It performs the confirmed transaction including LVM/filesystem, provider install/init, firewall, optional VIP, service start and health.

When the wrapper is invoked by root, it stages a private copy under `/run/layersentryd` and executes the file modes as the dedicated `layersentry` account, preventing root-owned journal/state artifacts.

Example intents live under:

`tools/layersentry/single-os/examples/`

## 9. Official-documentation design validation

Implementation was checked against first-party PostgreSQL, MySQL, MariaDB, Redis/Valkey, Apache HTTPD, Tomcat and Red Hat Enterprise Linux 9 documentation before source freeze.

Key decisions retained from that review:

- PostgreSQL initialization uses the official `initdb -D` model and postgres-owned target;
- MySQL custom data initialization uses the official initialize path and is followed immediately by secure local/root/admin bootstrap;
- MariaDB uses `mariadb-install-db` for an explicitly chosen datadir;
- MySQL `auth_socket` is used only for local root peer authentication;
- Redis/Valkey durable ACL password material is a SHA-256 verifier rather than the plaintext password;
- Nginx/Apache custom web roots receive the correct persistent SELinux HTTP-content label;
- Tomcat uses an absolute `Host appBase` for an external webapps directory;
- Node.js 20 remains the selected supported RHEL 9 module path rather than the Technology Preview Node.js 22 path;
- LVM uses PV -> VG -> LV and filesystem/mount layering;
- NetworkManager is the persistent secondary-IP authority;
- Keepalived VRRP uses a real local unicast source address plus declared peers, not the wildcard service bind address.

## 10. Next evidence gates

Do not add new architecture before the current source is live-qualified unless a concrete defect requires it.

Next sequence:

1. build the exact current RPM from the current shared branch;
2. install it on the one allowed Rocky 9 Hyper-V VM (2 vCPU / 2048 MiB static / Dynamic Memory off);
3. prove SELinux Enforcing and firewalld before/after;
4. attach approved non-OS data disks through the infrastructure path;
5. test root-disk rejection and LVM confirmed creation on those attached disks;
6. validate PostgreSQL standalone external data/WAL/log roots, reboot recovery, backup/restore, same-line patch and uninstall;
7. validate one representative MySQL-family external datadir and one Redis/Valkey external data root if they fit the resource envelope;
8. validate static secondary VIP on the one VM if the lab network permits it;
9. validate Nginx/Apache/Tomcat external application roots as resource permits;
10. retain VRRP real failover and PostgreSQL real standby replication as `NOT_TESTED` until a separately authorized multi-VM acceptance environment exists;
11. persist exact artifact/VM/test evidence and only then advance live status.

Never weaken SELinux/firewalld, use the OS disk for LVM tests, create a second Workstream-F VM without authorization, or claim production readiness from source tests alone.
