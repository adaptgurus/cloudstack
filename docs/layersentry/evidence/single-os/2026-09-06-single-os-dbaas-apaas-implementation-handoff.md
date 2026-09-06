# LayerSentry Single-OS DBaaS/APaaS — Implementation Handoff / Master Continuation

**Generated:** 2026-09-06 22:22 IST  
**Repository:** `adaptgurus/cloudstack`  
**Required shared branch:** `layersentry/4.22.1.1-ui`  
**Workstream:** F — VM-native Single-OS DBaaS/APaaS  
**CloudStack baseline:** Apache CloudStack 4.22.1.1  
**Primary guest:** Rocky Linux 9  
**Primary agent:** Go `layersentryd`  
**Starting HEAD for this implementation continuation:** `7a00a03ddaee0234b5c9a88a1c71d60a97c04ad0`  
**Implementation HEAD immediately before this handoff document:** `886ec0befa9ad4b2a1589dd997dd24e7b5732a11`  
**CloudStack Java/backend/schema/KVM-core impact:** **NO**  
**Kubernetes/RKE2/CAPI dependency:** **NO**

---

## 0. Read this first — owner instruction and evidence ceiling

The owner explicitly required the implementation to be written first and tested only after the source is complete enough for the intended code scope.

Therefore, in this continuation:

- substantial source code **was written and committed**;
- unit/security tests **were written but NOT executed**;
- `go test`, `go build`, `go vet`, `gofmt`, `go mod tidy`, RPM build, Rocky VM validation and browser validation **were NOT run in this continuation**;
- no source status in this document means `CI_VERIFIED`, `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED`;
- all runtime claims remain `NOT_TESTED` until the exact artifact is exercised under the Workstream-F acceptance rules.

Do not reinterpret source completeness as runtime proof.

---

## 1. Mandatory next-session startup — follow `AGENTS.md` strictly

A new ChatGPT/Codex session must not start from chat memory. Perform this exact startup sequence:

1. Read `/AGENTS.md`.
2. Read `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`.
3. Read `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`.
4. Read `docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`.
5. Read `docs/layersentry/LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`.
6. Read `docs/layersentry/codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`.
7. Read this file.
8. Fetch the actual current shared branch and inspect concurrent changes:

```bash
git status --short --branch
git remote -v
git branch --show-current
git fetch --all --tags --prune
git rev-parse HEAD
git log -10 --oneline --decorate
```

9. Verify the current branch is exactly:

```text
layersentry/4.22.1.1-ui
```

10. Inspect `tools/layersentry/single-os/` and continue the current implementation rather than rewriting it.
11. If another agent has advanced the same files, reconcile the newer source; never reset to a historical SHA or overwrite another agent's newer work.
12. Respect the owner's code-first instruction: finish the selected source scope before beginning the deferred test phase.

Never force-push, reset the shared branch to a documentation SHA, rewrite another agent's history, or merge this VM-native lifecycle into Workstream E/Kubernetes.

---

## 2. Authoritative architecture invariant

This workstream implements the following boundary:

```text
CloudStack creates/manages the VM, network, attached storage, tenancy, RBAC,
quota, template and power/infrastructure lifecycle.

The hardened Rocky Linux 9 guest runs layersentryd.

layersentryd creates/manages software inside that guest:
  catalog
  exact package/version resolution
  storage/mount preparation
  software install/configure/init
  service lifecycle
  firewall delta owned by LayerSentry
  health
  patch/upgrade
  repair
  backup/restore
  uninstall/residue audit
  maintenance policy
  evidence
```

Do not move this lifecycle into Kubernetes, RKE2, CAPI, CAPC, CAPRKE2, Flux, CloudStack Java APIs, CloudStack DB schema, the KVM agent, or another external DBaaS controller.

---

## 3. Current code-completion estimate

Percentages below measure **source written against the current design checklist**, not successful compilation, CI, live behavior or production certification.

| Area | Approx. source written | Truthful current status |
| --- | ---: | --- |
| F0 engine/security foundation | **94%** | source in progress; tests written, NOT_RUN |
| PostgreSQL standalone reference DB provider | **92%** | source in progress; NOT_TESTED |
| Nginx VM-native APaaS reference provider | **92%** | source in progress; NOT_TESTED |
| Storage/network/mount/firewall lifecycle | **92%** | source in progress; NOT_TESTED |
| HTTPS API/auth/embedded GUI | **90%** | source in progress; browser/runtime NOT_TESTED |
| Privilege separation/root helper | **92%** | source in progress; NOT_TESTED |
| Image/RPM/systemd/firstboot/seal | **92%** | source in progress; RPM/Rocky NOT_TESTED |
| Backup/restore/retention | **88%** | verified logical catalog source exists; encryption/live restore pending |
| Maintenance/auto-patch policy | **90%** | source in progress; NOT_TESTED |
| Cluster schema/planning/enrollment boundary | **50%** | planning schema exists; richer enrollment pending; real HA NOT_TESTED |
| Source test suite | **~50% written** | **0% executed** in this continuation |
| Additional provider matrix | **~20%** | PostgreSQL + Nginx implemented; remaining providers pending |

### Overall percentage

Two percentages must be kept separate:

1. **First production-oriented milestone defined by the Single-OS continuation context:** approximately **94% source-written**.
2. **Broader intended product including the expanded provider matrix:** approximately **60–65% source-written**.

Validation/certification percentage is intentionally much lower because tests have not yet been executed.

---

## 4. Source implemented in this continuation

### 4.1 Guest lifecycle engine

Implemented under `tools/layersentry/single-os/agent/internal/lifecycle/`:

- immutable plan generation;
- canonical request digest;
- canonical plan integrity digest;
- operation UUID + idempotency collision handling;
- global mutation lock;
- plan review/confirmation boundary;
- install transaction stages;
- lifecycle actions: start, stop, restart, upgrade, repair, backup, restore, uninstall;
- `UNKNOWN` state on ambiguous timeout/cancellation;
- observation-only `UNKNOWN` reconciliation;
- uninstall residue handling;
- state transitions persisted to the durable JSON journal.

Recent integrity work additionally ensures:

- repeated plan calls reuse the already pinned plan rather than re-resolving repository/package state;
- installation re-hashes the stored immutable plan before mutation;
- stored plan request digest must match the operation request digest;
- provider/service/operation identity must match across request, plan and operation;
- the operation state is re-read under the global mutation lock before first mutation;
- failed/in-flight lifecycle action UUIDs are not blindly replayed.

### 4.2 Durable journal

Implemented under `internal/journal/`:

- atomic JSON writes;
- fsync/rename durability pattern;
- non-symlink/private directory checks;
- bounded object size;
- UUID-only operation/service/plan/backup catalog paths;
- idempotent `Begin` behavior;
- operation listing;
- service listing;
- verified backup catalog;
- backup retention pruning with path/symlink confinement.

This is intentionally an embedded single-appliance state model; it does not introduce an external database.

### 4.3 Secret storage

Implemented under `internal/secrets/`:

- `secret://<32-hex>` references;
- AES-GCM encrypted local secret objects;
- per-node random encryption key generated after deployment;
- atomic ciphertext writes;
- non-symlink key/object checks;
- private directory checks;
- key creation with exclusive create + fsync;
- bounded secret size;
- malformed/traversal reference rejection.

Durable service/plan state stores secret references, not plaintext passwords.

### 4.4 Authentication/session security

Implemented under `internal/auth/`:

- unique first-boot bootstrap token;
- one-time local administrator creation;
- bcrypt password verifier;
- bootstrap token invalidation;
- secure HttpOnly session cookie;
- SameSite Strict cookies;
- CSRF double-submit token/header proof;
- bounded in-memory session set;
- expired-session cleanup;
- symlink-resistant administrator record handling.

### 4.5 Privilege separation

Implemented under `internal/privileged/` and systemd packaging:

```text
layersentryd serve
  -> dedicated non-login `layersentry` account
  -> authenticated API/planning/UI/state
  -> Unix socket
  -> layersentryd privileged-helper
  -> root
  -> typed allowlisted privileged operations only
```

There is no generic `run_command(string)` helper and no shell execution API.

The root helper currently constrains:

- DNF to approved provider packages and explicit approved repositories;
- `appstream` -> Nginx;
- `pgdg16` -> PostgreSQL 16 server;
- `pgdg17` -> PostgreSQL 17 server;
- systemd units to Nginx/PostgreSQL provider units;
- firewalld mutation to deterministic LayerSentry-owned zones;
- filesystem formatting to stable `/dev/disk/by-*` identities;
- formatting additionally performs its own root/root-parent ancestry rejection;
- mount targets to approved service data roots;
- PostgreSQL `runuser`/binary commands to exact init/health/backup/restore grammar;
- arbitrary SQL and arbitrary shell execution are rejected.

The helper's systemd service deliberately does not use an incompatible read-only `/usr` sandbox because DNF/RPM provider installation requires legitimate package-manager writes. The typed root protocol is the primary privileged boundary; the unprivileged API process retains stronger filesystem sandboxing.

### 4.6 Security preflight

Lifecycle planning and install revalidation check:

- Rocky Linux 9;
- SELinux `Enforcing`;
- firewalld active and enabled;
- CPU/RAM observation;
- listener IP belongs to the guest;
- requested listener port availability;
- stable disk identity;
- block-device root ancestry to reject root/root-parent disks.

### 4.7 Repository/package trust

Implemented under `internal/packageutil/` and provider plans:

- repository must be enabled;
- package GPG verification must be enabled;
- TLS verification may not be disabled;
- insecure HTTP repo URLs are rejected;
- GPG key reference must be configured;
- repository config is normalized and SHA-256 fingerprinted;
- exact package resolution is scoped to the approved repository;
- exact NEVRA is pinned;
- install disables unrelated repositories and enables only the approved repo;
- immutable plan records repository ID and repository digest;
- install re-fingerprints repository config and refuses drift after customer plan confirmation.

No `curl | bash`, arbitrary repo URL or `--nogpgcheck` path was added.

### 4.8 PostgreSQL reference DB provider

Implemented provider: `providers/postgresql/`.

Current source supports:

- release lines 16 and 17;
- approved `pgdg16`/`pgdg17` repository selection;
- exact NEVRA resolution/pinning;
- standalone admin password from secret reference;
- SCRAM host authentication;
- `initdb --pwfile` so password is not placed in process argv;
- data mount alignment to vendor PGDATA path;
- optional WAL and log mounts;
- generated `postgresql.conf` and `pg_hba.conf`;
- provider-owned firewall rule;
- start/stop/restart;
- `pg_isready` plus SQL/version health assertion;
- same-release-line package patch upgrade path;
- repair/restart;
- logical `pg_dumpall` backup;
- backup file regular-file/header/size/SHA-256 verification;
- durable verified backup catalog;
- explicit restore by exact backup UUID + caller-confirmed SHA-256;
- restore re-hashes the file before `psql` consumes it;
- normal uninstall preserves customer data;
- residue audit.

Cluster role schema accepts provider-specific `primary`/`standby`, but real multi-node join remains deliberately blocked under the one-VM acceptance envelope.

### 4.9 Nginx reference APaaS provider

Implemented provider: `providers/nginx/`.

Current source supports:

- Rocky `appstream` repository provenance;
- exact package resolution/pinning;
- provider-generated per-service config;
- service-specific document root;
- listener validation;
- restricted firewall rules;
- config syntax test;
- local HTTP health endpoint;
- start/stop/restart;
- same-line package upgrade;
- repair;
- uninstall/residue audit;
- customer application data preserved by default.

Nginx does not currently claim application-data backup semantics.

### 4.10 Storage, network and firewall

Implemented:

- attached storage inventory with stable IDs;
- actual guest interface/address discovery;
- multiple disk assignment in the embedded GUI;
- per-disk purpose, filesystem, mount point and format choice;
- explicit second confirmation for formatting;
- root/root-parent disk rejection;
- XFS/ext4;
- `/etc/fstab` by filesystem UUID;
- symlink-resistant atomic fstab updates;
- provider-owned deterministic firewalld zones;
- allowed CIDR scoping;
- firewall removal on uninstall.

### 4.11 Embedded HTTPS API/GUI

The Go binary embeds the management UI. Current UI/API includes:

- first-boot bootstrap/login;
- catalog;
- storage discovery;
- network discovery;
- product/release/topology selection;
- transient database password -> secret reference;
- multi-disk mapping;
- maintenance/backup policy;
- immutable plan review;
- explicit install confirmation by plan digest;
- installed services;
- start/stop/restart/upgrade/repair/backup/restore/uninstall;
- verified backup catalog selection;
- operation inventory;
- observation-only UNKNOWN reconciliation;
- basic evidence endpoint.

Browser code does not use localStorage for service credentials.

HTTP hardening source includes TLS 1.2+ minimum, bounded timeouts/header sizes, CSP without inline-script allowances, frame denial, no-store, no-referrer and restricted Permissions-Policy.

### 4.12 Maintenance

Implemented:

- systemd maintenance timer;
- manual/daily/weekly/monthly/notify-only policies;
- maintenance window parsing;
- same-line auto-patch gate;
- automatic database patch requires backup policy;
- fresh verified backup before automatic database upgrade;
- scheduled daily/weekly/monthly backups;
- backup retention pruning;
- global lifecycle lock still governs mutations.

### 4.13 RPM/image lifecycle

Implemented:

- RPM spec/build script;
- dedicated sysusers/tmpfiles definitions;
- `layersentry-privileged.service`;
- unprivileged `layersentryd.service`;
- firstboot service;
- maintenance service/timer;
- Rocky 9 image preparation;
- reuse of existing `rocky9-hardening` baseline;
- prebuilt signed LayerSentry RPM requirement;
- optional signed local PGDG repository-definition RPM;
- no provider packages baked into the reusable base image;
- clone-safe image validation;
- image seal removing node/bootstrap/TLS/secret identities;
- seal refuses initialized admin/service/backup/app/customer state;
- SSH host keys/machine-id/cloud-init/transient caches cleaned by seal script.

---

## 5. Tests written but NOT executed

Test source now includes coverage for several core boundaries:

- `internal/config/config_test.go`
  - schema rejection;
  - unknown fields;
  - UUID validation;
  - plaintext secret rejection;
  - duplicate disks;
  - unsafe mounts;
  - destructive format confirmation;
  - invalid CIDR;
  - standalone/cluster field separation;
  - duplicate peers;
  - secret-reference digest binding.

- `internal/journal/journal_test.go`
  - idempotent begin;
  - changed-digest collision;
  - symlink target rejection;
  - path traversal rejection;
  - unsafe journal root;
  - service state round trip;
  - verified backup catalog gate.

- `internal/privileged/privileged_test.go`
  - no-GPG/remote-repo rejection;
  - explicit repository requirement;
  - package/repository mismatch;
  - systemd unit allowlist;
  - firewalld argument validation;
  - unstable mkfs target rejection;
  - unsafe mount rejection;
  - arbitrary `runuser` executable rejection;
  - arbitrary SQL rejection;
  - restore path confinement;
  - shell rejection.

- `internal/auth/auth_test.go`
  - one-time bootstrap;
  - login/logout;
  - invalid password.

- `internal/secrets/store_test.go`
  - encrypted round trip;
  - plaintext absence from ciphertext;
  - malformed reference;
  - symlink key rejection;
  - secret-size limits.

- `internal/bootstrap/bootstrap_test.go`
  - per-clone identity uniqueness;
  - firstboot idempotency;
  - symlink identity rejection;
  - seal refusal when customer state exists;
  - clean seal identity removal.

- `internal/filesystem/safe_test.go`
  - traversal;
  - atomic write;
  - symlink target/parent;
  - outside-root rejection.

- `internal/lifecycle/integrity_test.go`
  - canonical plan acceptance;
  - resolved-version tamper;
  - repository-provenance tamper;
  - request tamper;
  - operation/plan digest mismatch.

- `internal/packageutil/dnf_test.go`
  - signed HTTPS repo config;
  - gpgcheck/HTTP rejection;
  - stable repo normalization;
  - exact repoquery argv;
  - exact repo-scoped install argv;
  - unsafe NEVRA rejection.

Again: these tests are **WRITTEN / NOT_RUN**.

---

## 6. Explicit remaining source work before the broader code scope is complete

Do not hide these gaps.

### 6.1 Additional provider matrix — PENDING

The following providers from the intended expansion matrix are not yet implemented and must not appear as fake selectable catalog items:

- MySQL;
- MariaDB;
- Valkey;
- Redis where licensing/package provenance is acceptable for the selected release;
- Apache HTTPD;
- Tomcat;
- Node.js runtime;
- Python runtime;
- controlled Podman OCI application provider.

For each provider, follow the same rules as PostgreSQL/Nginx:

1. research/qualify the official Rocky/vendor package source;
2. add exact repository/package allowlists to the privileged helper;
3. implement validation/version resolve/immutable plan;
4. install/configure/init/health;
5. start/stop/restart;
6. same-line upgrade policy;
7. repair;
8. backup/restore where the provider owns meaningful data;
9. uninstall/data-preservation/residue audit;
10. tests for exact argv and negative inputs;
11. only then add to the visible catalog/UI.

Do not add DB2/proprietary installation media to the product without a valid licensed distribution model.

### 6.2 Cluster enrollment/planning — PARTIAL

Current source has provider-specific role/peer schema and safe validation, but still needs a richer enrollment boundary:

- one-time short-lived join token generation;
- peer LayerSentry agent reachability;
- peer TLS identity validation;
- provider/release compatibility proof;
- time sync check;
- required-port checks;
- role uniqueness/topology conflict detection;
- durable token expiry/use-once semantics;
- provider-native topology observation before reconfiguration.

Real PostgreSQL multi-node replication/quorum/failover/fencing remains `NOT_TESTED` and must not be claimed under the current one-VM acceptance restriction.

### 6.3 Backup-at-rest encryption — PENDING

The PostgreSQL logical backup is verified and cataloged but not yet encrypted at rest. Implement an authenticated-encryption streaming format using a standard reviewed primitive/library and a separate backup key lifecycle before claiming encrypted local backups.

Do not invent a custom cipher.

### 6.4 Nginx backup policy guard — SMALL GAP

Nginx intentionally does not own application-data backups, but a direct API caller can still request a backup policy in generic schema. Tighten the provider validator/UI so unsupported backup semantics are rejected before plan generation.

### 6.5 Orphan secret garbage collection — SMALL GAP

The browser creates a PostgreSQL secret reference before submitting the plan. If plan generation fails or the user abandons an unconfirmed plan, that encrypted secret may remain unreferenced. Add safe server-side reference-aware deletion/GC; never let the browser delete a secret that is referenced by a plan/service.

### 6.6 Support/evidence bundle depth — PARTIAL

The API exposes service/operation/backup evidence without secrets. Expand it to a bounded support bundle containing safe host diagnostics such as:

- agent version;
- Rocky/kernel;
- SELinux state;
- firewalld summary;
- relevant package inventory;
- service/provider health;
- operation metadata;
- bounded redacted logs/resource usage.

Never include secret store, TLS private key, bootstrap token, admin hash file or raw authorization/session material.

### 6.7 Further tests to WRITE before test execution

Still add tests for:

- full PostgreSQL provider plan/argv/config/backup/restore behavior using fakes;
- Nginx provider plan/config/repo-drift behavior;
- lifecycle global mutation lock concurrency;
- complete `UNKNOWN` reconciliation matrix;
- maintenance backup/retention/pre-upgrade checkpoint behavior;
- API authentication/CSRF/origin/security headers/body limits;
- mounts/firewall/storage/network negative behavior;
- backup retention symlink/tamper cases;
- helper root-device ancestry with an injectable observer if needed.

---

## 7. Exact next implementation order

Unless a newer concurrent commit changes the source, continue in this order:

1. Re-fetch/reconcile `layersentry/4.22.1.1-ui`.
2. Re-read the required authoritative documents listed in Section 1.
3. Inspect the latest lifecycle/config/provider/helper files; do not assume this documented HEAD is still current.
4. Close Nginx backup-policy fail-closed validation.
5. Implement reference-aware orphan-secret deletion/GC.
6. Implement bounded support/evidence bundle diagnostics.
7. Implement backup-at-rest authenticated encryption and its key lifecycle.
8. Complete cluster enrollment/planning boundary without claiming real HA.
9. Qualify and implement the additional provider matrix one provider at a time; do not add fake catalog entries.
10. Complete the remaining unit/security tests.
11. Re-fetch/reconcile concurrent branch commits.
12. **Only after the code-first scope is complete**, begin the deferred source-test phase:
    - `gofmt`;
    - `go mod tidy` / generate `go.sum`;
    - `go vet` where applicable;
    - `go build ./...`;
    - `go test ./...`;
    - fix all failures;
    - re-run until clean.
13. Build the RPM from the exact tested source.
14. Perform source/security review focused on helper allowlist, API/session/CSRF, path/symlink, secrets, repository provenance, backup/restore and image seal.
15. Reconcile/fix findings.
16. Only then use the authorized single Rocky Linux 9 Hyper-V acceptance VM for Workstream-F live validation.
17. Do not create a second VM for real cluster testing under the current acceptance envelope.
18. Persist actual test/run/artifact evidence and update status truthfully.

---

## 8. Deferred test/live acceptance sequence

When the owner/code-first gate permits testing, the minimum sequence is:

```text
gofmt / static source cleanup
 -> go mod tidy
 -> go build ./...
 -> go test ./...
 -> negative/security tests
 -> RPM build
 -> RPM signature/provenance check
 -> Rocky 9 single-VM image prep
 -> prove 2 vCPU / 2048 MB / static memory
 -> prove SELinux Enforcing/firewalld
 -> firstboot uniqueness/bootstrap/TLS
 -> API/auth/CSRF/browser path
 -> Nginx standalone install/health/restart/upgrade/uninstall/residue
 -> PostgreSQL standalone install/SQL health/restart
 -> backup verification/catalog/retention
 -> explicit restore with data assertion
 -> same-line patch + pre-upgrade backup
 -> failure/UNKNOWN observation
 -> uninstall/data preservation/residue
 -> image seal validation
 -> final hardening/resource audit
```

A successful build/test is not `LIVE_VERIFIED`.

---

## 9. Current truthful status

```text
Single-OS architecture:                 DESIGN_DEFINED
Engine/reference-provider source:       PARTIAL / source implementation advanced
First-milestone source written:         ~94%
Broader provider-matrix source written: ~60-65%
PostgreSQL standalone source:           ~92% written, NOT_TESTED
Nginx APaaS source:                     ~92% written, NOT_TESTED
Privilege separation source:            ~92% written, NOT_TESTED
Tests written:                          PARTIAL
Tests executed in this continuation:    NOT_TESTED
Rocky live acceptance:                  NOT_TESTED
Real multi-node PostgreSQL HA:          NOT_TESTED
Production certification:               NOT_TESTED
CloudStack core impact:                 NO
```

Do not promote any of these to `SOURCE_COMPLETE`, `CI_VERIFIED`, `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED` without satisfying the corresponding evidence gate.

---

## 10. Coordination note: accidental temporary branch

During connector use, a temporary branch named:

```text
tmp-ignore
```

was accidentally created from historical commit:

```text
7a00a03ddaee0234b5c9a88a1c71d60a97c04ad0
```

No implementation work was intentionally placed on it. The required implementation remains on:

```text
layersentry/4.22.1.1-ui
```

The available connector in this session did not expose a branch-delete action. Delete `tmp-ignore` when a permitted Git/GitHub branch-delete path is available. Do not merge it and do not use it as continuation source.

---

## 11. Non-negotiable invariants for the next agent

Never:

- turn Single-OS DBaaS/APaaS into Kubernetes;
- add RKE2/CAPI/CAPRKE2/Flux to this guest architecture;
- modify CloudStack Java/backend/schema/KVM core merely for guest software lifecycle;
- hardcode passwords/tokens/private keys;
- store service passwords in durable service JSON;
- use shell interpolation for customer input;
- expose a generic root command executor;
- use `curl | bash`, arbitrary repositories, `--nogpgcheck` or TLS verification disablement;
- disable SELinux or firewalld;
- format a disk without explicit confirmation;
- permit the privileged helper to format the root/root-parent device;
- treat `/dev/sdb` as durable disk identity when a stable ID exists;
- silently retry `UNKNOWN` mutation state;
- restore a database from an implicit/latest file without exact verified backup identity;
- perform PostgreSQL 17 -> 18 as a normal patch;
- erase customer database/application data during normal uninstall;
- claim real cluster HA/failover from one VM;
- claim live or production status from source code/tests alone.

---

## 12. Simplest continuation statement

```text
CloudStack creates the computer.
LayerSentry inside that computer creates and manages the database/application service.
```

Continue the existing Go guest engine on the same shared branch. Finish the remaining source scope first, then execute the deferred test/security/Rocky acceptance gates and report only evidence-backed status.
