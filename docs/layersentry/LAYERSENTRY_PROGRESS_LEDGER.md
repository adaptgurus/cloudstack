# LayerSentry V1 — Durable Progress Ledger

## Purpose

This file is the frequently updated, Git-backed operational checkpoint for LayerSentry work. It exists so that browser refreshes, reconnects, tab closes, ChatGPT/Codex session loss, context exhaustion, model retries, or transient tool failures do **not** erase already completed work or cause verified work to be repeated.

The architecture, rules, evidence hierarchy, status governance, and anti-hallucination policy remain authoritative in `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`. The version-specific corrections in `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md` are an authoritative companion and override conflicting or less-specific wording until folded directly into the master context. Upgrade/IP-protection/stability requirements are defined in `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`. Fork/upgrade deltas are tracked in `docs/layersentry/LAYERSENTRY_UPSTREAM_DIFF.md`. This ledger records the latest execution state.

## Mandatory checkpoint rule

After every meaningful atomic task, and before starting a risky/long/destructive task, the active AI session must persist progress to GitHub where practical:

1. Commit source/config/document changes in a small atomic commit.
2. Record the task status and exact commit SHA here.
3. Record workflow run/job/artifact IDs when CI or live deployment was used.
4. Record live assertions actually executed.
5. Record unresolved limitations and the exact next action.
6. If runtime changed without a source change, commit an evidence/status update to this ledger or another repository evidence file.
7. Never rely on chat text, hidden scratchpad, browser state, or model memory as the only record of completion.

A page refresh or new chat must recover from Git/repository/workflow/live evidence, not restart the task from memory.

## Recovery after refresh/reconnect/new chat

Before changing anything:

1. Read `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`.
2. Read `LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md`.
3. Read `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`.
4. Read `LAYERSENTRY_UPSTREAM_DIFF.md`.
5. Read this progress ledger.
6. Fetch the actual current HEAD of `adaptgurus/cloudstack` branch `layersentry/4.22.1.1-ui`.
7. Fetch the runner branch HEAD when relevant.
8. Inspect the latest relevant workflow/run/artifact.
9. If the previous action may still be running, check its actual state before retrying.
10. Do not repeat destructive or non-idempotent actions merely because the prior assistant message disappeared.
11. Resume from the first unmet evidence gate.

## Current checkpoint

### LIVE_VERIFIED — LayerSentry V1 DBaaS/APaaS placeholder removal on `sen`

Customer-facing DBaaS/APaaS placeholder routes, placeholder section files, the LayerSentry ServiceCatalog placeholder, and the remaining onboarding text reference have been removed from the V1 UI and the exact cleaned build has been deployed to the current `sen` test target.

Exact UI commit deployed:

`6ce76d6c241629086ffcad794093dbdd5f2dd5ba`

Key source changes leading to this UI:

- `ui/src/config/router.js`: DBaaS/APaaS imports and route registration removed;
- `ui/src/config/section/dbaas.js`: removed;
- `ui/src/config/section/apaas.js`: removed;
- `ui/src/views/layersentry/ServiceCatalog.vue`: removed;
- `ui/src/views/dashboard/OnboardingDashboard.vue`: obsolete DBaaS/APaaS service-catalog wording removed and replaced with truthful Kubernetes/object-storage/backup wording conditional on provider configuration.

No CloudStack Java backend, API, database schema, KVM-agent or orchestration-core functionality was changed by this task.

Served-UI repair commit:

`85031bd2e394c16c631b6e493ced1af87c19fbd3`

It pins UI `6ce76d...`, fails if `DBaaS` or `APaaS` remains in built/served JavaScript, and emits diagnostic file names if a placeholder marker is found.

Resume path commit:

`8ccb2e7af9b3109e8d39c76d64e8943766158310`

Main installer pin-alignment commit:

`6cc23984c253a7ea9618b9c7553d12a495dcc971`

Runner workflow/request:

- workflow pin update commit: `675f6e433feb85ce9320a1b8a6d073e8f758fd0d`;
- request commit: `af484d1b6e063c4929634ed045560f95f3891d7d`;
- workflow run: `33879178031`;
- job: `101043343720`;
- conclusion: `success`;
- evidence artifact ID: `9939463820`;
- artifact name: `layersentry-customer-ui-deploy-33879178031`;
- artifact digest: `sha256:1a308fdcfff5a87348a4dad3783afc4bf24ea4b5efa6a583a6203064b8599813`.

Live assertions proven by this exact run:

- build passed from immutable UI source `6ce76d...`;
- `BUILD_CONFIG_CHECKS` passed;
- build contained no `DBaaS`/`APaaS` placeholder markers under the enforced V1 check;
- runtime backup created at `/var/backups/layersentry/20260904-191720/served-ui-before-branding` before deployment;
- management service restarted and returned HTTP 200 after its normal startup window;
- `RUNTIME_CONFIG_CHECKS` passed;
- `HTTP=200`;
- served config `/etc/cloudstack/management/config.json`;
- `V1_PLACEHOLDERS=ABSENT`;
- `ONBOARDING=PASS`;
- `LOGO_ASSETS=PASS`;
- `RUNTIME_CONFIG=PASS`;
- `TERMINOLOGY=PASS`;
- independent `--verify-only` verification repeated the same assertions successfully;
- Hyper-V console capture succeeded and VM `sen` remained Running.

Scope limit: this `LIVE_VERIFIED` status proves the current V1 placeholder removal and the assertions above only. It does not certify the future KVM-only profile, self-service dashboards, Kubernetes, object storage, HA architecture, appliance lockdown, upgrade path, backup or DR.

### Historical diagnostic run — FAILED BEFORE DEPLOY, superseded by the successful run above

First removal attempt:

- run `33877641094`;
- job `101038334940`;
- artifact `9938829995`;
- digest `sha256:c10be571cefc3896602107b7c3ef2611ee28fbde0410cf53be113360d0e95b1d`.

The build completed but pre-deployment validation correctly blocked deployment because `OnboardingDashboard.vue` still contained DBaaS/APaaS wording. Because failure occurred in build validation before runtime backup/deploy, that run did not replace the live UI. The source was corrected and the later run `33879178031` is authoritative for the completed removal.

### LIVE_VERIFIED — historical served LayerSentry branding/customer terminology baseline on `sen`

Earlier evidence remains useful for provenance:

- workflow run: `33856746145`;
- job: `100971705863`;
- conclusion: `success`;
- artifact: `9930784385`;
- artifact digest: `sha256:6a6751c9c07723f73df36e02b9f66ee3a41cb3098ac2f2834945af4759e9a50b`.

This historical run has been superseded for the DBaaS/APaaS-removal scope by run `33879178031` but remains evidence for the earlier branding lineage.

### SOURCE_COMPLETE — continuity / re-audit / upgradeability guardrails

- `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md` exists.
- `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md` exists.
- `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md` exists.
- `docs/layersentry/LAYERSENTRY_UPSTREAM_DIFF.md` exists.
- This progress ledger is the refresh-safe operational checkpoint.

Upgrade/IP protection policy explicitly requires minimal upstream diff, versioned release manifests, deterministic signed CI artifacts, upgrade compatibility gates, schema-aware CloudStack upgrade sequencing, staged/canary testing, rollback classification, SBOM/support bundles, server-side placement of proprietary logic, and no production source maps by default when implemented.

Important IP statement: it is **not technically possible to guarantee that customer-delivered software cannot be reverse engineered**, particularly open-source CloudStack core and browser JavaScript. The product objective is to minimize exposed LayerSentry-specific logic, keep proprietary orchestration server-side, raise the cost of analysis, sign artifacts, reduce shell/source exposure, and never rely on obscurity for security.

The upstream-delta register records the current architectural goal and upgrade procedure. The last audited compare showed LayerSentry changes confined to docs/installers/UI presentation with no CloudStack Java backend/API/database/KVM-agent source changes. Recalculate this at every future upgrade/release; historical file counts are not permanent truth.

### PARTIAL

- customer terminology: substantial work exists and current onboarding terminology passed live verification, but full role/context wrong-label audit remains pending;
- installer: current V1 UI/resume/served-repair pins are aligned for the placeholder-removal scope, but CI-built UI artifact deployment, SELinux final state/policy, firewall-policy validation, appliance lockdown and signed update controls remain incomplete;
- self-service foundation: upstream CloudStack components exist, but final LayerSentry Department Admin/User UX is not yet implemented/live-proven;
- IP protection: architecture/policy is defined, but production source-map policy, compiled proprietary components if ever required, signed release channel and appliance-access controls are not yet implemented/certified;
- upgrade engineering: architecture is defined, but supported N-1 -> N upgrade automation and release-specific evidence are pending.

### PENDING / NOT_TESTED

- KVM-only `layersentry-kvm` product profile;
- Platform Admin dashboard redesign;
- Department Admin self-service dashboard;
- normal User self-service dashboard;
- simplified VM wizard;
- simplified Kubernetes wizard;
- simplified Bucket UX;
- final Site/Infrastructure onboarding simplification;
- CI-built immutable UI artifact deployment;
- production source-map suppression/support-build strategy implementation;
- signed release manifest/artifact/update channel;
- N-1 -> N LayerSentry upgrade test automation;
- CloudStack schema-aware upgrade orchestration/rollback evidence;
- SELinux-enforcing appliance policy/modules and live validation;
- firewalld-enabled LayerSentry KVM traffic/security validation;
- package/repository lockdown;
- controlled signed update mechanism;
- full air-gap CKS;
- CKS metadata-isolation NetworkPolicy live validation;
- CKS CSI integration live validation for the selected Kubernetes ISO/profile;
- live Kubernetes validation;
- live object-store/Bucket validation;
- KVM snapshot-conflict guard implementation/test;
- native NAS B&R proof;
- DR source-record retention/purge negative test;
- two-zone cross-zone DR proof;
- RPO/RTO measurement;
- automated DR mapping;
- Test Recovery;
- planned/emergency failover;
- failback;
- 3-Management/2-LB/3-DB HA deployment and certification;
- physical OOBM/fencing certification on actual supported hardware;
- rolling upgrade certification;
- production release certification.

## Exact next execution sequence

1. Move UI compilation away from production management nodes to a CI-built immutable artifact with digest/signature verification and production source maps disabled by default.
2. Implement the KVM-only product-profile visibility matrix with prerequisite/provider-aware feature gating.
3. Implement role-aware Platform Admin / Department Admin / User dashboards using native CloudStack API/RBAC semantics.
4. Simplify VM/Kubernetes/Bucket workflows without inventing unsupported CloudStack API parameters.
5. Add the KVM snapshot-safety guard and CKS metadata-isolation/CSI requirements to relevant product/security tests.
6. Build/deploy/role-test on `sen` and update this ledger per atomic gate.
7. Add the second Rocky Linux 9 nested-KVM VM.
8. Prove native two-zone NAS B&R cross-zone recovery, including source-record retention behavior, before advanced DR automation.
9. Build the appliance package-lock/update/SELinux/security profile.
10. Later certify the 3-Management/2-LB/3-DB production HA profile and supported upgrade path on sufficient infrastructure.

## Refresh-safe invariant

**If the user refreshes the page in the middle of work, already committed/evidenced completed tasks remain completed. The next session must discover and preserve them from GitHub/workflow/live evidence. It must not restart from the beginning or mark them lost merely because the chat UI no longer contains the previous assistant output.**
