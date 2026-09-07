# LayerSentry V1 — Execution Contract

**Contract schema:** 1.0  
**Effective date:** 2026-09-07  
**Applies to:** ChatGPT, Codex, repository work, live validation and handoffs  
**Baseline:** Apache CloudStack 4.22.1.1, KVM-first LayerSentry

This contract defines **how work is executed now**. It intentionally reduces duplicate architecture work, repeated context loading and unnecessary custom code.

## 1. Execution routing

Use the following default owner/model routing unless the product owner explicitly changes it.

| Surface | Default execution owner | Primary objective |
| --- | --- | --- |
| LayerSentry-managed RKE2/Kubernetes | **Codex** | finish source + immutable artifacts + real E2E qualification |
| Kubernetes DBaaS/APaaS/Streaming | **Codex** | implement only after the base RKE2 vertical slice passes |
| VM-native Single-OS DBaaS/APaaS | **ChatGPT** | retain Go orchestration, migrate installation/configuration to Ansible, test provider vertical slices |
| DC/DR/DRaaS baseline | **ChatGPT** | use and troubleshoot native CloudStack APIs first; make native recovery work before custom DR code |
| LayerSentry UI/self-service | **ChatGPT, defect/integration only** | feature-freeze broad redesign; finish wiring, regression and browser acceptance |
| General architecture/document cleanup | **ChatGPT** | keep context concise and current; do not consume Codex for documentation churn |

Codex credits are therefore reserved primarily for the Kubernetes/RKE2/Data Services path and its end-to-end tests.

## 2. Context-loading rule

Every new session reads the minimum necessary context only:

1. `/AGENTS.md`;
2. this execution contract;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. one applicable specialist context/workstream when the task requires it;
5. fetch the actual branch/workflow/live state.

Do not automatically reread historical handoffs, dated audits, the knowledge graph, every specialist context or every workstream. Open them only to resolve a concrete dependency or conflict.

Repository source, workflow evidence and live evidence override stale text. When stable context is stale, fix it once rather than making every later session rediscover the discrepancy.

## 3. Global architecture boundary

Apache CloudStack remains authoritative for:

- KVM VM lifecycle;
- Zones/Sites, Pods/Infrastructure Groups, Clusters and Hosts;
- networks, public IPs, firewall, supported native LB resources and ACLs;
- primary/secondary/object storage contracts exposed by CloudStack;
- volumes, templates, ISOs, snapshots and native Backup & Recovery;
- account/domain/project/RBAC/quota authority;
- async jobs and CloudStack resource state.

LayerSentry must not create a second VM scheduler, second RBAC/tenancy database, second quota authority or conflicting copy of CloudStack resource state.

Do not modify CloudStack Java/backend/schema/KVM-agent/core orchestration merely to simplify LayerSentry. Use native CloudStack 4.22.1.1 APIs first, then supported provider/plugin contracts, then a thin LayerSentry orchestration layer only where a composite workflow genuinely requires it.

## 4. VM-native DBaaS/APaaS: Go + Ansible

The selected VM-native architecture is:

```text
LayerSentry UI/API
      |
      v
LayerSentry Go orchestration/control service
  - authorization/project binding
  - strict schema validation
  - immutable plan and confirmation digest
  - operation UUID/idempotency
  - lifecycle lock
  - durable journal/state
  - secret references
  - evidence/status
      |
      v
Ansible Runner / ansible-core
      |
      v
Versioned LayerSentry roles/playbooks
      |
      v
Rocky Linux 9 guest
```

### 4.1 Go owns orchestration, not package-by-package imperative configuration

Retain and improve the existing Go engine for:

- API/authentication/authorization integration;
- plan generation and exact version resolution policy;
- idempotency and operation locking;
- durable state/journal;
- secret-reference handling;
- safe target/inventory selection;
- Ansible Runner invocation and result parsing;
- health/evidence aggregation;
- rollback/recovery decision state.

Do not keep expanding Go with large amounts of hand-written package installation, config-file mutation, SELinux, firewalld, LVM, mount and service imperative logic when an Ansible role/module is the clearer execution boundary.

### 4.2 Ansible is the product installation/configuration boundary

Use Ansible roles/playbooks for:

- Rocky Linux baseline/hardening application;
- repository configuration and package installation/removal;
- service users/directories/permissions;
- SELinux labels/policy application;
- firewalld rules;
- LVM/filesystems/mounts;
- NetworkManager/VIP configuration;
- PostgreSQL/MySQL/MariaDB/Redis/Valkey;
- Nginx/Apache/Tomcat;
- Node.js/Python/Podman and future supported runtime providers;
- provider-specific cluster bootstrap/join/upgrade/repair/uninstall where Ansible is appropriate.

Roles must be versioned, idempotent, testable and receive schema-validated variables only. Secrets are passed by approved runtime secret references and must not be committed or emitted into normal logs/evidence.

### 4.3 Shell-script prohibition for installation

**Shell scripts are not an approved product installation/configuration engine.**

Do not implement provider installation, database/application configuration, cluster join, upgrade, repair, uninstall, LVM/storage setup, firewall/SELinux setup or RKE2 installation as a Bash/sh script lifecycle.

Existing shell installation/configuration assets are **deprecated** and must not be extended. Migrate their product behavior to Ansible before the affected path is considered current implementation.

Small build/packaging developer wrappers may temporarily remain when they are not a customer/runtime installation boundary. They must contain no customer-controlled shell interpolation and should be replaced by structured tooling when practical.

Inside Ansible, prefer dedicated modules. `ansible.builtin.shell`/`raw` are not normal provider mechanisms. If a vendor exposes only a CLI, use argv-safe `command` semantics or a purpose-built module and document the exception.

### 4.4 Ansible repository shape

Target source layout:

```text
tools/layersentry/ansible/
  ansible.cfg
  collections/requirements.yml
  playbooks/
    single_os_apply.yml
    single_os_upgrade.yml
    single_os_repair.yml
    single_os_uninstall.yml
    rke2_fallback.yml
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

Exact roles may be combined when ownership remains clean; avoid a monolithic playbook.

## 5. DC/DR/DRaaS: native CloudStack first

The DR critical path is **not** a large custom replication/orchestration codebase.

### 5.1 V1 order

```text
Make the DC and DR CloudStack infrastructure healthy
 -> enable/configure supported native Backup & Recovery
 -> prove selected recovery point creation/listing
 -> prove cross-Zone createVMFromBackup/recovery on isolated networking
 -> prove old and latest recovery points by guest data
 -> expose the working native workflow through a thin LayerSentry UI/orchestration layer
 -> only then add one advanced provider-native low-RPO path
 -> planned failover/failback
 -> witness/fencing/automatic failover last
```

### 5.2 Current troubleshooting priority

Resolve the observed environment blockers before writing more advanced DR code, including as applicable:

- functional primary storage and image/secondary storage;
- SystemVM template readiness;
- enabled and correctly configured CloudStack Backup & Recovery framework/provider;
- correct API/RBAC behavior and async-job observation;
- KVM agent/libvirt/qemu-kvm readiness on the intended DR compute host;
- an Advanced destination Zone/network path compatible with `createVMFromBackup`;
- a disposable source VM with root + data-disk markers;
- two distinct recovery points;
- isolated destination network and exact content verification.

### 5.3 Custom DR code ceiling

The existing provider-neutral DR state-machine source is **not the critical path** and must not be expanded merely because interfaces exist.

Until native recovery is live-proven:

- do not build another VM replication engine;
- do not implement custom block copying where CloudStack/provider-native functionality exists;
- do not implement witness/fencing/auto-failover runtime merely to increase source percentage;
- do not duplicate `createVMFromBackup` behind another scheduler.

After native recovery passes, use thin adapters over certified provider-native replication, beginning with the selected LayerSentry HCI provider when required. Ceph/SAN/libvirt adapters remain optional certification targets, not simultaneous V1 blockers.

## 6. UI policy: feature freeze

The LayerSentry UI has substantial source implementation. Treat the broad UI build as **feature-frozen** for this phase.

Allowed UI work:

- defects;
- missing API/BFF wiring;
- RBAC/direct-route defects;
- status/progress/error integration;
- browser E2E and responsive regressions;
- exact K8s/DR/Single-OS integration required by a vertical slice;
- accessibility/security corrections.

Do not spend a separate Codex workstream redesigning navigation, dashboards, terminology or provisioning UX unless a concrete acceptance defect requires it.

UI source completeness is not production certification; exact-artifact browser acceptance remains required.

## 7. Kubernetes/RKE2: Codex vertical-slice rule

Codex is reserved for the Kubernetes/Data Services path.

The current preferred architecture remains:

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> central Flux
 -> certified CNI/CCM/CSI/operators
```

Do not create more horizontal scaffolding until the existing E0/E1 source is turned into a working vertical slice.

### 7.1 First Kubernetes definition of done

Codex must drive one exact release through:

```text
immutable component build/publication
 -> management-cluster/controller deployment
 -> GUI/API create
 -> CloudStack VM/network/IP creation through the selected ownership path
 -> automatic RKE2 join
 -> 6443 + 9345 endpoint proof
 -> primary CNI Ready
 -> CCM/L4 lifecycle proof
 -> one safe CSI/storage path
 -> central Flux reconciliation
 -> status
 -> scale up
 -> safe node replacement/volume-survival checks where applicable
 -> delete/cleanup
 -> restart/reconciliation negatives
 -> Rocky Linux 9 evidence
```

Do not start broad Kubernetes DBaaS/APaaS/Streaming implementation before this base vertical slice passes the release-defined gates.

### 7.2 Approved fallback

If exact evidence shows CAPC/CAPRKE2 cannot satisfy a required V1 gate without disproportionate downstream maintenance, the already-approved fallback may be selected by a documented decision:

```text
LayerSentry durable workflow
 -> native CloudStack APIs
 -> hardened QCOW2/cloud-init
 -> Ansible Runner
 -> RKE2
 -> Flux
```

Do not maintain CAPI and fallback as two active owners for the same release.

## 8. Vertical-slice completion model

Progress is measured by customer-operable vertical slices, not file count, line count or commit count.

Priority proofs are:

1. **VM-native appliance proof:** UI/API -> VM -> Go plan -> Ansible -> PostgreSQL -> health -> reboot -> backup/restore -> uninstall.
2. **RKE2 proof:** UI/API -> cluster -> Ready -> scale -> delete with storage/network correctness.
3. **Kubernetes DBaaS proof:** PostgreSQL first, including storage, backup/PITR, maintenance and recovery.
4. **APaaS proof:** one complete OpenBao or Harbor lifecycle before expanding the catalog.
5. **Native DR proof:** two recovery points -> isolated recovery -> exact old/latest guest data validation.

Only after a vertical slice works should the provider/catalog matrix expand.

## 9. Evidence rules

Use only:

- `DESIGN_DEFINED`
- `SOURCE_COMPLETE`
- `CI_VERIFIED`
- `LIVE_VERIFIED`
- `PRODUCTION_CERTIFIED`
- `PARTIAL`
- `PENDING`
- `BLOCKED`
- `UNKNOWN`
- `NOT_TESTED`

Source code is not deployment proof. HTTP success is not service proof. Documentation is not compatibility proof. Live claims require exact source/artifact, target and assertions.

## 10. Credit/token optimization rules

- reserve Codex for K8s/RKE2/Data Services implementation and E2E;
- use ChatGPT for VM-native providers, Ansible migration, native CloudStack DR troubleshooting, UI defect work and context maintenance;
- do not start multiple Codex agents on overlapping architecture;
- do not repeatedly research a frozen decision unless a blocker/version change requires it;
- do not generate a new large handoff after every small commit; update concise durable status after meaningful vertical milestones;
- prefer execution/testing over additional design documents once the architecture is settled.

## 11. Conflict rule

This execution contract supersedes older runbook/workstream **execution-routing** instructions where they conflict. Detailed specialist architecture remains valid unless this contract explicitly changes it.

If a historical document says to use Codex for UI, DR or Single-OS work, follow this contract instead.
