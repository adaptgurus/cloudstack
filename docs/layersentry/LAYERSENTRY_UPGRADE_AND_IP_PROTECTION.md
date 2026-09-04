# LayerSentry V1 — Upgradeability, Supply-Chain, IP Protection and Production-Stability Guardrails

## Authority and scope

This is a **stable specialist policy**. Current implementation/completion state belongs in `LAYERSENTRY_PROGRESS_LEDGER.md`, not here.

Read this document for release engineering, installer/update work, upstream upgrades, rollback/recovery, artifact signing, SBOM/provenance, IP-protection decisions and production-stability controls.

The canonical product/evidence contract is `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`. Exact fork deltas are tracked in `LAYERSENTRY_UPSTREAM_DIFF.md`.

---

## 1. Upgrade principle

LayerSentry remains an overlay/product layer over Apache CloudStack rather than a deep fork.

Target lifecycle:

```text
new upstream CloudStack release
        -> compatibility/source audit
        -> upstream-delta review
        -> reapply minimum LayerSentry overlay
        -> deterministic build
        -> regression/security tests
        -> supported N-1 -> N upgrade tests
        -> staging/canary
        -> production promotion
```

Never make the normal upgrade process depend on manually re-porting hundreds of backend changes.

Therefore:

- avoid LayerSentry-only CloudStack DB-schema changes;
- do not rename/change upstream API contracts;
- do not duplicate scheduler/network/storage/VM orchestration;
- do not remove upstream hypervisor implementations from core;
- keep KVM-only behavior in the product profile/UI/configuration;
- keep additional LayerSentry orchestration in separate services/adapters where practical;
- prefer new LayerSentry files/components over large upstream edits;
- document every necessary upstream-file modification.

---

## 2. Upstream-delta control

`LAYERSENTRY_UPSTREAM_DIFF.md` is the delta register.

Every modified upstream file should record:

- upstream path/reference;
- LayerSentry reason;
- behavior changed;
- presentation-only vs functional impact;
- upgrade/rebase risk;
- tests covering the change;
- replacement/removal plan if upstream later provides the capability.

At each CloudStack target change, regenerate the actual changed-file comparison and classify every delta as:

- reusable with review;
- requires rebase/adaptation;
- obsolete because upstream now provides it;
- unsafe and must be redesigned.

Never copy an old modified file wholesale over a new upstream release.

Any future Java/backend/database/KVM-agent/core change requires the core-change exception gate from the canonical Super Master Context.

---

## 3. Immutable release manifest

Every production/candidate LayerSentry release must have one versioned immutable manifest containing, as applicable:

- LayerSentry version/channel;
- exact CloudStack upstream release/reference;
- exact LayerSentry source commit;
- management/KVM package versions;
- Java version;
- supported Rocky Linux range;
- supported DB version/topology identifier;
- UI artifact name/digest/signature;
- bootstrap/installer artifact name/digest/signature;
- product/config schema versions;
- optional Kubernetes ISO/template/CNI/CSI versions when certified;
- object-store provider/version when certified;
- B&R/DR provider/version when certified;
- SELinux/firewall/update-policy versions;
- SBOM reference/digest;
- provenance reference;
- supported upgrade-from releases;
- known release limitations/exceptions.

Never identify a production release only by `main`, `latest` or another moving branch/tag.

---

## 4. Controlled CI build

Production management nodes must not compile the LayerSentry Vue UI.

CI/build environment must:

1. start from an exact source commit;
2. use a pinned build image/toolchain and lockfile;
3. verify dependency resolution/policy;
4. run lint/static/unit/component checks appropriate to the change;
5. run secret/dependency/vulnerability checks required by release policy;
6. build production assets;
7. enforce V1 placeholder/terminology/branding policy;
8. ensure production source maps are absent unless producing an explicitly controlled support build;
9. package one immutable deployment artifact;
10. generate SBOM and provenance;
11. compute cryptographic digest;
12. sign release metadata/artifacts according to the trust model;
13. publish immutable artifact identifiers.

The target appliance receives verified artifacts, not npm dependencies/build tools.

Do not claim reproducible-build or SLSA compliance unless the exact requirements for that claim have been implemented and evidenced.

---

## 5. Signing and trust model

Private signing/license keys never belong in Git, browser JavaScript, customer artifacts or plaintext workflow logs.

The final production design must define:

- trust root/public verification material;
- signer/key custody;
- rotation/revocation procedure;
- CI authorization to sign;
- verification behavior on the appliance;
- expired/revoked/unknown-key behavior;
- emergency key-compromise procedure.

Prefer managed KMS/HSM or short-lived workload identity/signing mechanisms where practical rather than long-lived exportable CI private keys.

Artifact/manifest verification failure is fail-closed.

---

## 6. SBOM, provenance and dependency governance

Use a standard machine-readable SBOM format such as SPDX or CycloneDX according to the release toolchain.

Provenance should allow an operator to determine at minimum:

- source repository and exact commit;
- build workflow/builder identity;
- toolchain/build-image identity;
- dependency-lock state;
- artifact digest;
- release manifest identity.

Dependency/security policy should include:

- dependency pin/lock review;
- license review appropriate to distribution obligations;
- vulnerability scanning;
- explicit risk acceptance for unresolved release findings, with owner/reason/expiry where exceptions are allowed;
- secret scanning;
- update/refresh process for third-party components.

Do not silently upgrade dependencies during customer installation.

---

## 7. Installer artifact-consumption model

Fresh install, resume install, repair/redeploy and upgrade paths must consume the **same release artifact contract**.

Expected flow:

```text
read release manifest
    -> verify compatibility
    -> verify signature/trust
    -> verify digest
    -> stage artifact
    -> preflight target
    -> create rollback checkpoint
    -> atomic/proven deployment
    -> health/policy checks
    -> commit release state
```

Do not maintain independent UI build/pinning logic in fresh/resume/repair paths.

An installer must not overwrite a known-good runtime after pre-deployment integrity/policy failure.

All mutating stages must be idempotent, deduplicated by state, or explicitly non-idempotent with a recovery procedure.

---

## 8. Upgrade preflight

Before mutation validate, as applicable:

- current LayerSentry release is a supported source version;
- target CloudStack upgrade path is documented/supported;
- exact current management-server inventory is known;
- DB/config backup is possible;
- DB health/topology meets the certified precondition;
- disk capacity is sufficient;
- target Java/package/artifact versions are available;
- signatures/digests validate;
- upstream-delta audit passed;
- plugins/providers are compatible;
- KVM hosts meet target requirements;
- System VM template requirements are met;
- async jobs/maintenance state are safe;
- no unsupported mixed-version state will be created.

Fail closed on unmet safety/compatibility prerequisites.

---

## 9. Durable pre-upgrade checkpoint

Before an upgrade preserve, at minimum:

- CloudStack/usage DB backups as required;
- relevant configuration/key files according to secure backup policy;
- current LayerSentry release manifest;
- served UI/runtime config backup where applicable;
- package inventory;
- management/KVM inventory/state;
- known-good health/evidence report;
- exact intended source/target releases;
- rollback/recovery class and procedure.

The checkpoint must be durable outside the transient AI/chat session.

---

## 10. CloudStack schema-aware management upgrade

Respect the exact 4.22.1.x upgrade guidance for the source/target path.

When DB/schema upgrade sequencing requires other Management Servers stopped:

1. preflight and back up;
2. stop/drain management services according to documented requirements;
3. upgrade the first management server;
4. allow/verify DB upgrade;
5. start/validate the first server;
6. upgrade remaining management servers using the supported sequence;
7. restore LB membership only after health checks.

For paths with no DB/schema migration, use the least-disruptive supported sequence after validation.

Never advertise zero management-plane downtime for a path that upstream requires to stop management services.

---

## 11. KVM rolling update

Where supported, process KVM hosts serially/with safe concurrency:

- validate remaining cluster capacity;
- enter maintenance/drain workflow;
- migrate/stop workloads according to policy;
- apply only approved signed update transactions;
- reboot if required;
- verify agent/libvirt/network/storage/migration/security state;
- return host to service;
- proceed to the next host.

Never update an entire production Compute Cluster simultaneously unless an explicitly approved outage procedure requires it.

---

## 12. Post-upgrade validation

Validate applicable certified features, including:

- UI/API authentication;
- role/RBAC/direct-URL behavior;
- representative VM lifecycle and console;
- KVM agent connectivity;
- live migration/HA where certified;
- network and volume operations;
- primary/image-store state;
- System VMs/Virtual Routers as applicable;
- CKS/CSI/CNI when enabled;
- object storage when enabled;
- B&R and cross-zone recovery prerequisites when enabled;
- LayerSentry branding/terminology/V1 scope;
- SELinux/firewall/package-lock controls;
- support/evidence generation.

A management service starting successfully is not sufficient post-upgrade validation.

---

## 13. Required release upgrade tests

Before `PRODUCTION_CERTIFIED` for an applicable release, preserve evidence for:

- fresh target install;
- supported N-1 -> N upgrade;
- interrupted upgrade/resume;
- first-management-node failure handling;
- DB/schema upgrade recovery behavior;
- management restarts;
- mixed-version window only where upstream supports it;
- KVM-agent rolling update where applicable;
- installer idempotency;
- UI artifact replacement/rollback;
- configuration-schema migration;
- package/security controls preserved;
- backup/recovery after upgrade when certified;
- role-aware UI/RBAC after upgrade;
- DR recovery after upgrade when DR is certified.

Do not infer rollback from a successful forward upgrade.

---

## 14. Rollback/recovery classification

Before an update, identify its rollback class:

- **UI-only rollback:** atomic switch to a prior verified artifact when supported;
- **LayerSentry service/config rollback:** only when state/config schema is backward-compatible or migration is reversible;
- **package rollback without DB change:** only when tested for that release pair;
- **DB/schema recovery:** restore matching pre-upgrade DB/config/software state when downgrade is not supported.

The product must communicate the class/limitations before executing a high-consequence upgrade.

Never promise an automatic package downgrade after a DB/schema migration unless that exact path has been tested and supported.

---

## 15. Production-stability principles

- immutable signed release artifacts;
- pinned toolchains/dependencies;
- explicit config/schema versioning;
- fail-closed integrity/policy checks;
- staging/canary before broad rollout;
- feature flags/gating for optional integrations;
- support bundles and correlation-friendly logs;
- idempotent/resumable automation;
- deterministic rollback/recovery classification;
- negative/failure tests, not only happy-path tests;
- no ad-hoc manual edits/builds on production nodes;
- no security control weakening merely to pass a lab test.

Where feasible, automate preflight/dry-run output before R3/R4 operations.

---

## 16. Supportability

Support bundle collection should be preinstalled and secret-redacted. Depending on profile it may include:

- release manifest/package inventory;
- service status/logs/journal;
- KVM/libvirt diagnostics;
- network/bridge/VLAN/route state;
- storage/multipath/Ceph/NFS/CIFS state;
- SELinux AVC/firewall state;
- reliable DB health/replication summary;
- CKS/CSI/CNI summary;
- object-store summary;
- B&R/DR summary;
- recent async-job failures;
- sanitized configuration.

Do not require arbitrary package installation during an incident just to gather baseline support evidence.

---

## 17. IP-protection reality

It is not technically possible to guarantee that customer-delivered software cannot be reverse engineered.

- Apache CloudStack upstream source is public;
- browser JavaScript must be delivered to the browser;
- local binaries/packages can be inspected by sufficiently privileged customers.

The product objective is to minimize unnecessary exposure of LayerSentry-specific implementation details, keep sensitive logic server-side, raise analysis cost where reasonable, preserve legal obligations and never rely on obscurity as security.

---

## 18. Browser vs server-side IP boundary

Browser code may contain presentation, validation and supported API calls. It must not contain:

- private signing/license keys;
- reusable credentials;
- proprietary DR/upgrade decision algorithms that can live server-side;
- sensitive infrastructure automation;
- secrets used to authorize server operations.

Customer production builds:

- minify normally;
- no production source maps by default;
- no development/debug-only routes/modules;
- no `node_modules`/build cache/toolchain on appliances;
- no internal credentials/repository secrets.

Aggressive JavaScript obfuscation is not a default security control because it adds operational/debug/upgrade cost for limited protection. Evaluate only with explicit benefit and regression testing.

---

## 19. Proprietary service boundary

When LayerSentry later has commercially sensitive orchestration logic, prefer a clear versioned service boundary from CloudStack core.

Compiled Go/Rust components may be appropriate for selected proprietary logic, with:

- signed packages/binaries;
- no embedded secrets;
- internal debug symbols/support builds retained securely where needed;
- stable local API contract;
- explicit schema/API versioning and migration.

Python/Ansible remains appropriate for deployment automation, but should not become the only copy of highly sensitive proprietary algorithms if that matters commercially.

---

## 20. Appliance access and legal attribution

Normal customers should not require routine root shell access. Use least-privilege product/support roles, controlled audited support access and signed updates.

Do not claim root/physical access can be made unable to inspect a normal Rocky Linux appliance.

IP-protection work must preserve Apache LICENSE/NOTICE/source headers and other required attribution. Upstream branding can be removed from irrelevant normal customer UI while legal obligations remain intact in distribution/source/package documentation.

---

## 21. Versioned internal contracts

Version all LayerSentry-specific persistent/interfaces that can outlive a release, such as:

- product-profile schema;
- bootstrap inventory schema;
- health/support API;
- DR mapping schema;
- update/release manifest schema;
- support-bundle schema.

Provide migrations or clear incompatibility errors. Do not use undocumented CloudStack DB tables as a LayerSentry internal API.

---

## 22. Release channels

Recommended logical channels:

- `dev` — engineering only;
- `candidate` — integrated QA/staging;
- `stable` — production-certified exact releases;
- optional `lts` only after a long-term support policy exists.

Customers never consume a moving Git branch as a production update source. Every stable release maps to immutable signed artifacts and a release manifest.

---

## 23. Status rule

This file contains **no current implementation status** by design.

For what is currently `PENDING`, `SOURCE_COMPLETE`, `CI_VERIFIED`, `LIVE_VERIFIED` or otherwise, read:

`docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`

This prevents release-policy documentation from becoming stale execution state.
