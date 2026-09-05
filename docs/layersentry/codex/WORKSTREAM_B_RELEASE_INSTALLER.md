# Codex Workstream B — Release / Installer / Build

## Mission

Make LayerSentry installation, release, rollback/recovery and future upgrades deterministic, integrity-verifiable, supportable and low-risk. Production management nodes consume verified LayerSentry artifacts; they do not compile the Vue UI.

## Startup

Read:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`
5. `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` when building/releasing LayerSentry K8s/Data Services/APaaS/Streaming artifacts
6. this workstream file.

Fetch/inspect the actual integration HEAD before editing. Use an isolated worktree/branch such as `codex/layersentry-release-installer`.

Read `LAYERSENTRY_UPSTREAM_DIFF.md` when the change touches upstream files or upgrade/rebase behavior. Historical handoffs/re-audits are not normal startup context.

## File ownership

Primary ownership:

- `install-layersentry*.sh`
- LayerSentry build/release scripts
- `ui/vue.config.js` and build-only production settings
- release manifest/SBOM/provenance/digest/signature tooling
- installer/resume/repair/rollback logic
- LayerSentry product-artifact CI configuration
- release-carrier/bundle mechanics shared by the K8s/Data Services module when coordinated with Workstream E

Avoid dashboard/wizard implementation, Kubernetes lifecycle logic and CloudStack Java/backend changes unless the integration lead explicitly reassigns scope.

## Required outcomes

1. Move production UI compilation off CloudStack management nodes.
2. Define a pinned deterministic builder/toolchain compatible with the target CloudStack UI.
3. Build one immutable LayerSentry UI artifact/package from an exact source commit.
4. Disable production source maps by default; explicit controlled support builds may differ.
5. Produce a versioned release manifest, cryptographic digest, SBOM and provenance.
6. Implement the production signing/verification trust model without committing private keys.
7. Make fresh install, resume, repair/redeploy and upgrade consume one artifact contract.
8. Verify manifest compatibility, trust/signature and digest before target mutation; fail closed on mismatch.
9. Make stages idempotent/deduplicated or explicitly non-idempotent with recovery procedure.
10. Provide safe staging/atomic deployment or a proven equivalent and deterministic rollback/recovery classification.
11. Preserve CloudStack runtime/backend directories/configuration that must not be replaced by UI deployment.
12. Remove production dependence on Node/npm/compiler dependencies.
13. Preserve future CloudStack upgradeability and minimal upstream delta.
14. Generate enough evidence that a released artifact can be tied to source, builder, dependency state and release policy.
15. When Workstream E is enabled for a release, provide the signed two-bundle/offline catalog mechanics and incremental-update transport required by the dedicated Kubernetes/Data Services master context without taking ownership of CAPI/RKE2/operator lifecycle.

## Stable compatibility baseline

For LayerSentry V1, use the target baseline in the canonical context: CloudStack 4.22.1.1, Rocky Linux 9 product profile, Java 17 and the exact validated management-database topology/version selected by release evidence. Do not hard-code an unresolved MySQL version choice into release tooling merely because historical documentation mentioned one.

Kubernetes/Data Services versions are not inferred from CloudStack version. When that module is enabled, the release manifest pins the exact CAPI/CAPC/CAPRKE2/RKE2, QCOW2, CNI/CCM/CSI/Gateway/operator/application tuple defined and qualified by Workstream E.

Do not encode historical branch HEADs or current completion state in this workstream file; read the progress ledger/current source.

## Supply-chain/security requirements

- Never commit signing/license private keys or reusable secrets.
- Define signer/trust-root/key-rotation/revocation behavior as required by the specialist policy.
- Production source maps off by default.
- Pin/validate build image/toolchain and dependency lock state.
- Run secret/dependency/vulnerability/license checks required by the release policy.
- Use a standard machine-readable SBOM format and provenance adequate to identify source/builder/artifact.
- Do not claim SLSA/reproducible-build compliance unless the exact standard requirements are actually implemented and evidenced.
- Signed artifacts provide authenticity/integrity; they do not make software impossible to reverse engineer.
- Keep proprietary decision logic server-side when practical.
- Do not redistribute commercial OEM/NVIDIA/vendor artifacts unless the exact license/redistribution terms permit it; support a verified customer/OEM import path where required.

## Upgrade requirements

Follow `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`:

- versioned immutable release manifest;
- compatibility preflight;
- durable DB/config/release checkpoint;
- CloudStack schema-aware management-server sequencing;
- supported N-1 -> N test before certification;
- interruption/resume and rollback/recovery tests;
- rolling KVM-host update only with capacity/maintenance validation;
- post-upgrade functional/security regression;
- no unsupported automatic downgrade promise after DB/schema migration.

For the K8s/Data Services module, also preserve the specialist separation among package-only updates, QCOW2/RKE2 node-image updates, CNI/CSI migrations, operator updates and database-engine updates. Do not collapse them into one opaque release transaction.

## Risk classification

Normal source/build work is R1. A controlled UI deployment may be R2. Package/repository changes, service topology/reboot, CloudStack/Kubernetes platform upgrade or DB/schema-affecting work is R3/R4 and follows the canonical disposable-test/target-boundary/checkpoint/recovery rules.

Do not run destructive package/platform upgrade work on an unconfirmed production/customer target merely because a test would be useful.

## Testing

At minimum, as applicable to the implemented batch:

- clean-checkout build using pinned toolchain;
- dependency/lock/toolchain policy checks;
- production source maps absent;
- LayerSentry branding/config/terminology gates preserved;
- K8s/DBaaS/APaaS/Streaming artifacts/routes are included only when the release intentionally implements and capability-gates them; unfinished modules are hidden/unavailable rather than falsely advertised, and no stale global exclusion text rejects a valid enabled module;
- release manifest schema validation;
- SBOM/provenance generation;
- digest verification positive/negative tests;
- signature/trust positive and tamper/unknown-key/revocation behavior when implemented;
- installer syntax/static tests;
- fresh/resume/repair parity;
- idempotent retry/deduplication behavior;
- pre-deploy fail-closed behavior;
- atomic/proven UI deployment and rollback/recovery tests;
- CloudStack backend/runtime-config preservation;
- when K8s/Data Services release media is enabled: exact bundle manifest/digest/signature verification, OCI/chart/RPM/DEB/QCOW2 inventory validation, licensing/NOTICE checks, compatibility-range checks, offline import and incremental-update positive/negative tests.

Do not describe a deterministic/reproducible property based only on one successful build; define and test the exact property being claimed.

## Handoff

Report exact branch/base/final commit, changed files, artifact/provenance behavior, core impact YES/NO, checks actually run/not run, runtime mutation/risk class, rollback/retry behavior, security assumptions/limitations and dependencies on A/C/D/E. Do not edit the shared progress ledger or self-merge unless explicitly assigned.
