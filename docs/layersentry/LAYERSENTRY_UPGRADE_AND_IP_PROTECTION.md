# LayerSentry V1 — Upgradeability, IP Protection and Production-Stability Guardrails

## Authority

This document is an authoritative companion to:

- `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
- `LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md`
- `LAYERSENTRY_PROGRESS_LEDGER.md`

It defines how LayerSentry must be engineered so future Apache CloudStack upgrades remain practical, production incidents are minimized, and LayerSentry-specific intellectual property is protected as far as realistically possible without compromising security, supportability, license obligations, or upgradeability.

Repository/runtime evidence and version-pinned CloudStack documentation remain authoritative over historical wording.

---

## 1. Non-negotiable upgrade principle

LayerSentry must remain an **overlay/product layer over CloudStack**, not a deep fork.

The upgrade-cost target is:

`new upstream CloudStack tag -> compatibility audit -> rebuild LayerSentry overlay -> automated regression -> canary -> production rollout`

not:

`manually re-port hundreds of backend changes after every upstream release`.

Therefore:

- do not change CloudStack database schema for LayerSentry-only metadata unless no supported alternative exists;
- do not rename or change upstream API contracts;
- do not duplicate upstream orchestration logic;
- do not remove upstream hypervisor implementations from the core;
- keep KVM-only behavior in LayerSentry product-profile/UI/configuration layers;
- keep additional LayerSentry orchestration in separate services/adapters where practical;
- prefer new LayerSentry files/components over editing large upstream files;
- when an upstream file must be modified, keep the diff small and document it.

---

## 2. Upstream-delta budget

Maintain `LAYERSENTRY_UPSTREAM_DIFF.md` or equivalent with one record per modified upstream file:

- upstream path;
- upstream version/tag;
- LayerSentry reason;
- exact behavior changed;
- whether the change is presentation-only or functional;
- upgrade/rebase risk;
- tests covering the change;
- upstream replacement/removal plan if the same capability later becomes native.

At every upstream upgrade, compare the current LayerSentry branch against the exact new upstream tag and classify each delta:

- cleanly reusable;
- needs rebase/review;
- obsolete because upstream now supports it;
- unsafe and must be redesigned.

Do not copy an old modified file wholesale over a new upstream version.

---

## 3. Versioned release manifest

Every LayerSentry release must have one immutable release manifest containing at least:

- LayerSentry version;
- exact CloudStack upstream version/tag/commit;
- exact LayerSentry source commit;
- management RPM versions;
- KVM agent RPM versions;
- Java version;
- supported Rocky Linux minor-version range;
- supported MySQL/equivalent DB version;
- UI artifact digest;
- installer/bootstrap artifact digest;
- optional Kubernetes ISO/template versions;
- CNI/CSI versions when enabled;
- object-store integration/provider versions when certified;
- backup/DR plugin/provider versions when certified;
- SELinux policy version;
- package/repository-lock policy version;
- SBOM digest/location;
- upgrade paths supported from previous LayerSentry releases.

Never identify a production release only by a branch name such as `latest` or `main`.

---

## 4. Deterministic CI-built artifacts

Production management nodes must not compile the LayerSentry Vue UI.

Target model:

1. build in a controlled CI builder;
2. use a pinned Node/npm/toolchain container or image;
3. run lint/static checks/tests;
4. build production UI;
5. verify no obsolete/customer-hidden placeholders are bundled;
6. verify branding/terminology contract;
7. disable production source maps unless explicitly required for a support build;
8. create an immutable archive/RPM;
9. generate SHA-256 or stronger digest;
10. sign release metadata/artifacts;
11. installer verifies signature/digest before deployment.

The target server should receive the built artifact, not `npm install` dependencies.

This reduces dependency drift, install-time failures, attack surface and upgrade complexity.

---

## 5. Upgrade pipeline

For each supported LayerSentry upgrade, automate these phases.

### Phase A — compatibility preflight

Validate before mutation:

- current LayerSentry release is a supported source version;
- target CloudStack upgrade path is supported by version-pinned documentation;
- all Management Servers are known;
- current DB backup is possible;
- DB replication/HA state is acceptable for the LayerSentry-certified topology;
- enough disk space exists;
- Java target is available;
- target RPMs/artifacts signatures/digests are valid;
- custom LayerSentry diff audit passed;
- plugins/providers are compatible;
- KVM hosts satisfy target compatibility requirements;
- System VM template requirements are satisfied;
- pending async jobs/maintenance states are safe;
- no unsupported mixed-version state would be created.

Fail closed when prerequisites are not satisfied.

### Phase B — durable pre-upgrade checkpoint

Before upgrade:

- DB backup with routines/procedures preserved as required by CloudStack documentation;
- configuration backup;
- LayerSentry release manifest backup;
- served UI/runtime config backup;
- current package inventory;
- current management-server inventory/state;
- known-good health report;
- exact rollback/recovery procedure recorded in the progress/evidence ledger.

### Phase C — database/schema-aware management upgrade

CloudStack 4.22.1 upgrade guidance requires all other Management Servers to be stopped when the first upgraded Management Server needs to perform the DB upgrade. LayerSentry automation must respect this behavior rather than claiming an always-zero-downtime schema upgrade.

Target sequence when a DB/schema upgrade is required:

1. preflight and backup;
2. stop/drain all management servers according to documented requirements;
3. upgrade the first management server;
4. allow/verify the database upgrade;
5. start and validate the first management server;
6. upgrade the remaining management servers one at a time;
7. restore the HA/LB pool only after each node passes health checks.

For upgrades where no DB/schema migration is required, use the least-disruptive supported rolling sequence after validation.

Never advertise zero management-plane downtime for an upgrade path whose upstream DB migration requires all management nodes to be stopped.

### Phase D — KVM host upgrade

Use CloudStack maintenance/rolling-maintenance functions where supported.

For each host:

- validate cluster capacity before evacuation;
- place host into maintenance/drain workflow;
- migrate or stop workloads according to policy;
- apply signed approved update;
- reboot if required;
- verify KVM/libvirt/agent/network/storage/migration health;
- return host to service;
- continue to the next host.

Never upgrade an entire production cluster simultaneously unless an explicit outage is approved.

### Phase E — post-upgrade validation

Verify at minimum:

- UI/API authentication;
- role/RBAC behavior;
- VM create/start/stop/console;
- KVM agent connectivity;
- live migration where certified;
- network creation/attachment;
- volume attach/detach;
- primary/image-store health;
- System VMs/Virtual Routers where applicable;
- Kubernetes when enabled;
- CSI/CNI when enabled;
- buckets/object store when enabled;
- backup/recovery when enabled;
- DR prerequisites/mappings when enabled;
- LayerSentry branding and terminology;
- no DBaaS/APaaS placeholders in V1;
- SELinux/firewall policy health;
- no regression in package lockdown.

---

## 6. Upgrade test matrix before release

A LayerSentry release cannot be `PRODUCTION_CERTIFIED` until applicable upgrade tests pass against disposable/staging infrastructure.

Required tests include:

- fresh install target release;
- supported N-1 -> N upgrade;
- interrupted upgrade/resume;
- first-management-node upgrade failure handling;
- management restart after schema upgrade;
- mixed-version window only where upstream supports it;
- KVM agent rolling upgrade;
- installer idempotency;
- UI replacement/rollback;
- configuration migration;
- package lock preserved after upgrade;
- SELinux enforcing after upgrade;
- backup/recovery after upgrade;
- role-aware UI/RBAC after upgrade;
- DR recovery after upgrade where DR is certified.

Keep evidence artifacts for each release.

---

## 7. Rollback reality

Do not promise an automatic package downgrade after a CloudStack database schema migration unless that exact downgrade path is documented and tested.

Rollback must be classified as one of:

- UI-only rollback: safe atomic artifact switch after validation;
- LayerSentry service/config rollback: supported if state schema is backward-compatible;
- management package rollback without DB change: only if validated;
- database/schema rollback: restore the pre-upgrade database/config backup and matching software release in a controlled recovery procedure.

The update UI must communicate the rollback class before the customer starts the upgrade.

---

## 8. Production issue reduction principles

To minimize production issues:

- release only immutable signed artifacts;
- pin dependencies/toolchains;
- generate SBOMs;
- run dependency/CVE scanning;
- run static analysis and linting;
- run unit/component tests for LayerSentry UI logic;
- run API contract tests against the exact CloudStack target;
- run role/RBAC tests;
- run installation/resume tests;
- run HA/failure tests;
- run upgrade tests;
- use feature flags for optional integrations;
- hide features until prerequisites/provider health are confirmed;
- prefer fail-closed behavior for dangerous operations;
- use explicit validation and dry-run/preflight where possible;
- create support bundles automatically on failure;
- preserve logs/evidence with correlation IDs;
- keep configuration schema versioned and migratable;
- avoid manual edits on production nodes;
- avoid compiling/building on production nodes;
- use canary/staging validation before broad rollout;
- maintain a tested rollback/recovery path.

---

## 9. Supportability and observability

LayerSentry should generate a support bundle without requiring package installation on the appliance.

Include, with secret redaction:

- LayerSentry release manifest;
- package inventory;
- service status;
- CloudStack management/agent logs;
- selected journal entries;
- KVM/libvirt diagnostics;
- network/bridge/VLAN/route state;
- storage/mount/multipath/Ceph state according to profile;
- SELinux AVC summary;
- firewalld/nftables state;
- DB connectivity/replication summary from reliable probes;
- Kubernetes/CSI/CNI summary when enabled;
- object-store summary when enabled;
- backup/DR provider summary when enabled;
- recent async-job failures;
- sanitized configuration.

No support bundle may contain plaintext secrets by default.

---

## 10. IP protection — realistic security rule

**It is impossible to guarantee that no one can reverse engineer software delivered to a customer.**

This is especially true for:

- Apache CloudStack core, whose upstream source is public;
- browser-delivered JavaScript, which must be sent to the user to execute;
- any local binaries or packages to which a sufficiently privileged customer has physical/root access.

Therefore LayerSentry must not use "impossible to reverse engineer" as a security or contractual technical claim.

The correct objective is:

**minimize exposed LayerSentry-specific implementation details, keep sensitive logic server-side, raise the cost of reverse engineering, preserve legal obligations, and never rely on obscurity for security.**

---

## 11. IP protection architecture

### Keep proprietary logic out of browser JavaScript

The browser UI should contain presentation, validation and calls to supported APIs only.

Do not place proprietary algorithms, licensing secrets, signing keys, DR decision logic, sensitive credentials, or unique automation logic in client-side JavaScript.

Any genuinely proprietary orchestration should execute server-side in a LayerSentry service/controller.

### Production UI build

For customer builds:

- minify JavaScript/CSS normally;
- do not publish production source maps by default;
- remove development/debug-only routes;
- remove placeholder/dead modules;
- avoid embedding internal repository URLs or credentials;
- do not ship build toolchains/npm cache/node_modules to appliances.

Aggressive JavaScript obfuscation should **not** be a default because it can make debugging, browser compatibility and future upgrades materially worse while providing limited protection. If evaluated, it requires performance/error/upgrade tests and must never alter legal notices that must be preserved.

### Proprietary server-side components

For LayerSentry-specific components where IP protection is commercially important, prefer a clear process boundary from CloudStack core.

Possible implementation model:

- Go or Rust compiled service for proprietary orchestration/state logic;
- stripped production symbols where operationally acceptable;
- separate debug-symbol/support build retained internally;
- signed binaries/packages;
- no embedded private keys or reusable credentials;
- stable versioned local API contract between LayerSentry service and UI/bootstrap.

Python/Ansible remains useful for transparent deployment automation, but it should not contain the only copy of commercially sensitive algorithms if IP secrecy is a major requirement.

### Appliance access

Normal customers should not receive routine root shell access.

Use:

- least-privilege support/admin roles;
- controlled support access when required;
- audit logging;
- signed update channel;
- repository/package lockdown;
- secure boot/measured boot only if later implemented and certified.

Do not claim that root/physical access can be made unable to inspect a normal Rocky Linux appliance.

---

## 12. License and attribution rule

IP-protection work must not remove or alter Apache LICENSE/NOTICE/source headers or other legally required attribution.

LayerSentry can hide irrelevant upstream branding from the normal customer portal while still preserving required legal notices in the distribution/source/package documentation.

Do not attempt to make Apache CloudStack itself secret. Protect LayerSentry's differentiated product layer and operations instead.

---

## 13. Secrets are not IP protection

Never hard-code or embed:

- package-signing private keys;
- update-signing private keys;
- database credentials;
- API secret keys;
- support backdoor credentials;
- license signing keys;
- customer credentials.

Use external secret stores, deployment-time secret generation, short-lived credentials and key rotation.

A binary that contains a secret should be assumed extractable by a determined local attacker.

---

## 14. Versioned internal contracts

To keep future upgrades smooth, every LayerSentry-specific service/API/config file must have explicit versioning.

Examples:

- `layersentryProductProfileVersion`
- bootstrap inventory schema version;
- LayerSentry health-service API version;
- DR mapping schema version;
- update manifest schema version;
- support-bundle schema version.

Provide forward migrations and reject unsupported schema versions clearly.

Avoid using internal CloudStack database tables as an undocumented LayerSentry API.

---

## 15. Release channels

Recommended channels:

- `dev` — development only;
- `candidate` — integrated QA/POC;
- `stable` — production-certified release;
- optional `lts` — long-lived production branch after the product matures.

Customers should never receive a moving branch as an update source.

Each stable release maps to immutable signed artifacts and a release manifest.

---

## 16. Current status

At creation of this document:

- upgradeability/IP-protection architecture: `DESIGN_DEFINED`;
- production CI-built UI artifact: `PENDING`;
- production source-map policy: `PENDING`;
- signed LayerSentry package/update channel: `PENDING`;
- compiled proprietary orchestration service: not yet required/implemented;
- CloudStack backend remains intentionally unmodified for the current DBaaS/APaaS-removal task.

Do not promote any of these to `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED` without the evidence gates above.
