# LayerSentry Single-OS DBaaS/APaaS Super Master Context

Status: `DESIGN_DEFINED`

## 1. Authority and architecture isolation

This document is authoritative for the **LayerSentry VM-native Single-OS DBaaS/APaaS appliance path**.

It is intentionally separate from the existing Kubernetes-managed data-services architecture governed by:

`docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`

The two paths are alternative LayerSentry deployment/lifecycle models. They MUST NOT be merged into one controller, one lifecycle state machine, or one package/orchestration plane merely because both expose DBaaS/APaaS experiences.

### Existing Kubernetes-managed path

Uses CAPI/RKE2/Kubernetes/operator/package-plane constructs and is appropriate when the service lifecycle is Kubernetes-native.

### This Single-OS path

Uses a hardened Rocky Linux 9 guest appliance and a LayerSentry guest lifecycle engine to install, configure, upgrade, repair and uninstall supported database/application software directly inside CloudStack-provisioned VMs.

This path MUST NOT require Kubernetes, RKE2, CAPI, CRDs or Kubernetes operators.

## 2. Product objective

Provide one reusable hardened Rocky Linux 9 operating-system image rather than maintaining a separate VM image for each database/application/version.

Customer workflow is GUI-driven:

1. select software/product;
2. select release line/version policy;
3. select standalone or supported cluster topology;
4. provide storage/mount requirements;
5. provide network/role/topology inputs;
6. review the generated plan;
7. confirm installation;
8. LayerSentry generates a versioned declarative guest configuration and executes the lifecycle transaction;
9. LayerSentry reports exact resolved version, health, evidence and rollback/recovery state.

CloudStack remains authoritative for VM, network, storage, tenancy, quota and RBAC state. This guest engine MUST NOT become a second VM scheduler or competing cloud-control plane.

## 3. Single base OS invariant

LayerSentry V1 Single-OS DBaaS/APaaS uses **Rocky Linux 9 minimal** as the primary appliance base.

The base image SHOULD contain only:

- required OS/runtime prerequisites;
- hardened system configuration;
- LayerSentry guest lifecycle engine and its narrowly required dependencies;
- approved repository/trust metadata/bootstrap capability;
- observability/audit primitives required by the product.

Do NOT pre-install every supported database/application package into the base image. Product packages are resolved and installed only after the customer selects a supported product/version/topology.

A new image is required only when the OS/platform baseline itself changes materially, not for every product patch release.

## 4. Guest engine contract

Working service name: `layersentryd`.

Current status until source exists and is tested: `PENDING`.

The engine SHALL be manifest/provider driven. Product-specific logic belongs in versioned providers/manifests, not in an unbounded shell-script monolith.

The engine SHALL expose deterministic lifecycle operations such as:

- preflight;
- plan;
- install;
- configure;
- join/initialize where supported;
- health/status;
- patch/upgrade;
- repair/reconcile;
- uninstall;
- rollback/recover.

Every mutating operation requires an operation UUID/idempotency key and an exclusive lifecycle lock.

## 5. Declarative configuration and durable state

The generated guest configuration SHALL be schema-versioned and contain only non-secret configuration plus secret references.

Minimum logical fields:

- schema version;
- operation UUID;
- product/provider identifier;
- selected release line;
- exact resolved package/software version;
- topology mode;
- node/role identity when applicable;
- peer endpoints when applicable;
- requested storage devices/mount points and intended use;
- network/listener requirements;
- feature flags;
- secret references;
- rollback policy;
- maintenance/upgrade policy;
- expected health assertions.

Secrets MUST NOT be stored in plaintext inside the durable configuration, Git, browser code, logs or generated evidence bundles.

Durable state SHALL record at least:

- config digest;
- plan digest;
- exact resolved version/package NEVRA where relevant;
- repository/source identity;
- before/after package inventory;
- operation status and timestamps;
- health assertions/results;
- rollback/checkpoint state;
- redacted error evidence.

## 6. Transaction lifecycle

A mutating lifecycle action SHALL follow this order unless a provider documents a stricter sequence:

```text
Schema validation
 -> authorization/operation validation
 -> exclusive operation lock
 -> OS/resource/storage/network preflight
 -> peer connectivity preflight when applicable
 -> exact version resolution
 -> package/repository signature + TLS validation
 -> immutable execution plan
 -> checkpoint/snapshot when supported and appropriate
 -> package download/cache
 -> installation/configuration
 -> service enable/start
 -> product-specific health tests
 -> post-install hardening validation
 -> commit durable state/evidence
 -> cleanup obsolete caches/residue
```

On failure, the engine SHALL stop further mutation, preserve bounded diagnostic evidence, attempt only the provider-defined safe rollback/recovery sequence, and report the truthful resulting state.

Do not blindly retry an operation whose previous mutation state is unknown.

## 7. Version resolution and package hygiene

When a customer chooses a release line such as a supported major/minor family, LayerSentry SHALL resolve an exact approved patch version at execution time, then pin that exact version for the transaction and evidence record.

Requirements:

- use official/vendor-supported packages or LayerSentry-approved mirrored equivalents;
- verify repository/package signatures;
- verify TLS for online repositories;
- air-gap mirrors MUST preserve provenance, signatures/digests and release metadata;
- never use `curl | bash`, unverified remote scripts, arbitrary URLs or `eval` as the product installation boundary;
- successful upgrade SHOULD remove obsolete package caches/version residue unless a provider explicitly requires side-by-side content;
- uninstall removes LayerSentry-managed packages, repository entries, units, transient files and bounded caches while preserving customer data by default unless an explicit destructive data-removal operation was separately requested;
- residue audit covers RPM/DNF state, repo files, systemd units, processes, listeners, temporary/cache locations, service accounts and managed configuration.

## 8. Hardening baseline

The Single-OS appliance SHALL be hardened before any provider is considered production capable.

Minimum baseline:

- Rocky Linux 9 minimal and fully supported security update baseline;
- SELinux `Enforcing`; disabling SELinux or using permissive mode as a workaround is prohibited;
- firewalld active with default-deny posture and only explicitly required product/management ports opened;
- no unnecessary listening services;
- SSH restricted to the approved management path; prefer key-based authentication; root password login is disabled for production appliances;
- controlled disposable-lab exceptions must remain lab-only and MUST NOT become image defaults;
- root-owned engine configuration/state; sensitive files mode `0600` or stricter as applicable;
- safe canonical path validation and symlink-resistant file handling;
- argv-based subprocess execution, strict allowlists and no shell interpolation of untrusted values;
- least privilege: daemon runs without broad root privilege where practical; any privileged helper has a narrow command contract;
- systemd sandboxing applied as compatibility permits, including `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectSystem=strict` or strongest compatible setting, `ProtectHome=true`, `LockPersonality=true`, capability bounding and restricted address families;
- bounded timeouts, retries, concurrency, file sizes and log retention;
- no reusable credentials in command-line arguments or logs;
- structured redaction of tokens/passwords/private keys;
- audit trail for configuration digest, resolved version, plan digest and before/after package/service exposure;
- rollback MUST NOT silently disable security controls to make a service start.

Provider-specific firewall/SELinux policy is explicit, versioned and testable. Broad `setenforce 0`, firewall disablement, wildcard ports or blanket SELinux allow rules are release blockers.

## 9. Cluster-mode contract

Cluster support is provider-specific; generic words such as `master`/`replica` are not sufficient to implement every database/application safely.

Before mutation, cluster workflow SHALL validate:

- node role/topology schema;
- peer address format and uniqueness;
- required TCP connectivity;
- DNS/time assumptions where required;
- storage/mount readiness;
- version compatibility;
- provider-specific quorum/bootstrap prerequisites.

Passwords/keys are supplied by runtime secret reference, not persisted plaintext.

Cluster join/bootstrap SHALL be idempotent and provider-aware. It MUST NOT create a second LayerSentry topology authority conflicting with the product's own consensus/cluster state.

## 10. Exact Hyper-V acceptance envelope for this workstream

Until explicitly changed by the owner, live validation for this architecture is constrained to exactly:

- **1 Hyper-V Generation 2 VM**;
- **2 vCPU**;
- **2048 MB RAM**;
- **Dynamic Memory OFF**;
- **Rocky Linux 9**;
- one disposable LayerSentry test VM only.

No second VM may be created for this acceptance cycle.

Local processes, loopback endpoints, network namespaces or provider mocks may be used inside the single VM to validate parser/state-machine/connectivity/error-handling logic, but they are NOT evidence of real multi-node HA, quorum, replication or failover.

Resource-efficiency is part of acceptance. The guest engine must remain usable under this 2-vCPU/2-GB envelope when no heavy database workload is running. A database product whose vendor minimum exceeds this VM size may be plan/provider tested but MUST NOT be falsely marked live-certified on this envelope.

## 11. Mandatory single-VM test matrix

Where implementation exists, collect durable runner evidence for:

1. VM inventory proves exactly 1 test VM, 2 vCPU, 2048 MB static RAM, Dynamic Memory OFF;
2. Rocky Linux 9 identity/version;
3. SELinux enforcing before and after lifecycle operations;
4. firewalld active and expected zone/default posture;
5. baseline listener/process inventory has no unexplained service;
6. valid configuration accepted;
7. malformed/unknown-schema configuration rejected without mutation;
8. unsupported product/version rejected without mutation;
9. path traversal/symlink/unsafe-file attempts rejected;
10. shell/meta-character injection inputs cannot escape the provider contract;
11. exact release-line-to-patch resolution and version pinning;
12. representative standalone install where the selected product fits the lab resource envelope;
13. idempotent install/reconcile rerun;
14. service restart and VM reboot recovery;
15. same-line patch upgrade where safe and resource-compatible;
16. injected installation/upgrade failure and safe rollback/recovery;
17. duplicate/concurrent operation lock behavior;
18. uninstall plus residue audit;
19. secret/log redaction;
20. CPU/RAM/disk/cache growth observations for the idle engine and test operation;
21. cluster configuration/plan/connectivity negative tests using mocks/local isolation only;
22. final hardening revalidation after install/upgrade/uninstall.

If a particular product cannot run within 2 GB RAM according to its supported requirements, do not force it to run by disabling safeguards. Mark the product live-install test `BLOCKED` or `NOT_TESTED` for this envelope while still testing the engine/provider planning path.

## 12. Evidence and certification ceiling

A source commit or successful CI job is not live proof.

Use the repository-wide evidence labels from `AGENTS.md`.

For this workstream:

- architecture can be `DESIGN_DEFINED` after review/documentation;
- engine/provider source can be `SOURCE_COMPLETE` only when implementation and required source tests are complete;
- test automation can become `CI_VERIFIED` from reproducible CI evidence;
- standalone/hardening behavior becomes `LIVE_VERIFIED` only after the exact artifact is exercised on the authorized Rocky Linux 9 Hyper-V VM with durable evidence;
- real multi-node cluster bootstrap, replication, quorum, failover and fencing remain `NOT_TESTED`/`PARTIAL` while the one-VM restriction is in force;
- do not use `PRODUCTION_CERTIFIED` until the product/provider-specific security, upgrade, rollback, backup/recovery, load and supported topology gates are actually satisfied.

## 13. Separation from Kubernetes DBaaS/APaaS

The following MUST remain separate between the Kubernetes-managed path and this Single-OS path:

- lifecycle controller/state machine;
- guest engine/agent;
- provider/package state;
- topology/job state;
- API namespace/routes where lifecycle semantics differ;
- Kubernetes CRDs/operators/CAPI/RKE2 objects;
- installation/upgrade evidence whose runtime target differs.

The following MAY be shared when contracts remain clean:

- CloudStack native VM/network/storage APIs;
- CloudStack RBAC/tenancy/quota authority;
- common LayerSentry UI shell/design system;
- secure-engineering policy;
- evidence status vocabulary;
- audit/event primitives;
- approved secrets infrastructure;
- common observability presentation where underlying evidence remains distinguishable.

Never silently route a Single-OS service request into the Kubernetes module or vice versa.

## 14. Recommended UI/API boundary

The UI SHOULD present this as an explicit VM-native deployment mode/profile rather than hiding the architecture choice after submission.

The UI/API submits declarative intent to LayerSentry orchestration; orchestration uses supported CloudStack APIs to create/attach required VM/network/storage resources and passes only the guest lifecycle configuration/secret references to the target appliance.

CloudStack remains authoritative for infrastructure lifecycle. `layersentryd` is authoritative only for software lifecycle inside its assigned guest.

## 15. Codex execution order

For this workstream Codex/agents SHALL:

```text
Read AGENTS.md + this context
 -> inspect current branch/runtime evidence
 -> audit single-OS design against secure-engineering policy
 -> implement schema/state/locking core
 -> implement hardened systemd/service packaging
 -> implement provider interface + representative provider
 -> implement unit/negative/idempotency tests
 -> build/provision the one allowed Rocky Linux 9 Hyper-V VM
 -> verify 2 vCPU/2 GB/static-memory constraint
 -> apply and verify OS hardening
 -> execute install/restart/upgrade/failure/uninstall tests that fit the envelope
 -> perform residue/resource/security audit
 -> store durable evidence
 -> update progress ledger/knowledge graph
 -> report truthful evidence status and blockers
```

Do not weaken security controls or create a second VM merely to make a test pass.

## 16. Current design audit

### Selected approach

One hardened Rocky Linux 9 base image + a small declarative, provider-driven guest lifecycle engine.

### Why this is preferred

Compared with one image per product/version, this reduces image sprawl and patch lag while preserving a stable OS baseline. Compared with a generic unrestricted bootstrap script, a schema/provider/state-machine design gives stronger idempotency, auditability, security controls and rollback semantics. Compared with forcing the existing Kubernetes DBaaS/APaaS plane onto VM-native workloads, it preserves clean lifecycle boundaries and avoids unnecessary Kubernetes dependency.

### Primary risks and required mitigations

- **privileged guest engine compromise** -> least privilege, strict schema, safe subprocess/file boundaries, SELinux/systemd hardening;
- **supply-chain compromise** -> signed packages, pinned exact versions, provenance/digest evidence, controlled mirrors;
- **partial installation state** -> operation journal, lock, immutable plan, checkpoints and provider-defined rollback;
- **version drift/residue** -> exact version evidence, cleanup and residue audit;
- **cluster split-brain/mis-bootstrap** -> provider-specific quorum/bootstrap contracts and real multi-node certification before production claims;
- **architecture overlap** -> explicit separate lifecycle/API/state boundaries from the Kubernetes module;
- **2-GB lab pressure** -> lightweight engine, bounded caches and truthful per-product resource eligibility.

### Audit conclusion

Architecture: `DESIGN_DEFINED`.

Guest engine implementation: `PENDING` until source exists on the applicable implementation branch and passes source tests.

Hyper-V standalone hardening/runtime acceptance: `NOT_TESTED` until a runner execution proves the exact one-VM envelope and guest assertions.

Real cluster HA/failover: `NOT_TESTED` by design under the current one-VM restriction.
