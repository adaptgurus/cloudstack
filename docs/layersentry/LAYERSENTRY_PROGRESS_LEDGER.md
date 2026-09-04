# LayerSentry V1 — Durable Progress Ledger

## Purpose

This file is the **volatile, frequently updated, Git-backed operational checkpoint** for LayerSentry work. Current HEADs, workflow/job/artifact IDs, live target observations, completion state, blockers and next execution gates belong here rather than in the canonical Super Master Context.

Stable architecture, safety, evidence/status governance and production-certification rules are authoritative in:

`docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`

Specialist stable policy:

- upgrade/supply-chain/IP protection: `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`
- upstream/fork deltas: `LAYERSENTRY_UPSTREAM_DIFF.md`

Historical re-audits/handoffs are audit history after their findings are incorporated and are not normal startup authority.

## Mandatory checkpoint rule

After every meaningful atomic task, and before starting a risky/long/destructive task, persist progress to GitHub/evidence where practical:

1. Commit source/config/document changes in a small atomic commit.
2. Record the task status and exact commit SHA here when shared project state changed.
3. Record workflow run/job/artifact IDs when CI or live deployment was used.
4. Record live assertions actually executed.
5. Record unresolved limitations and the exact next action.
6. If runtime changed without a source change, persist evidence/status in this ledger, workflow evidence or another versioned evidence artifact.
7. Never rely on chat text, hidden scratchpad, browser state or model memory as the only record of completion.

A page refresh or new chat recovers from Git/repository/workflow/live evidence rather than restarting work from memory.

## Recovery after refresh/reconnect/new chat

Before changing anything:

1. Read `/AGENTS.md`.
2. Read `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`.
3. Read this progress ledger.
4. Read the assigned workstream file when applicable.
5. Fetch the actual current HEAD of `adaptgurus/cloudstack` branch `layersentry/4.22.1.1-ui`.
6. Fetch the `adaptgurus/cozystack` runner integration branch when relevant.
7. Inspect the latest relevant workflow/run/artifact.
8. If the previous action may still be running, inspect its exact state before retrying.
9. Read specialist upgrade/delta/runbook documents only if the current task needs them.
10. Resume from the first unmet evidence gate.

## Current checkpoint

### SOURCE_COMPLETE — canonical context governance v2 / context-cleanliness re-audit

The LayerSentry AI/Codex context stack was re-audited and normalized so stable policy and volatile execution state no longer compete with one another.

Source commits in this documentation-only context-governance update:

- canonical stable Super Master Context v2: `74658e14e887a9fde2687d947e63e477cd4d485e`;
- simplified root `AGENTS.md` authority/read order: `ea9d4fbf9e67f92fe1a4ffd686bdf0c4f2549417`;
- old master-context re-audit converted to archival pointer: `f3ad1588ee54c5f74644c171f9a571c7ccce61ed`;
- `CODEX_MASTER_CONTEXT.md` converted to concise execution index: `3e2a787908aa1cf4bbe99e45aab11180fc9078c1`;
- multi-agent master deduplicated: `63d2f4230e365c6bc4e09325523481b87d9fdb9f`;
- four-agent runbook authority/startup flow simplified: `0af02405d8094ca3353407877d9b462a3e706406`;
- upgrade/supply-chain/IP policy converted to stable-only production policy: `6fa3ff7aa24ed84584325e311a8d38a5cc9ecec1`.

Key governance changes:

- volatile HEADs/run IDs/artifact IDs/live IPs/current statuses removed from the Super Master Context;
- current execution state now lives only in this progress ledger plus underlying evidence;
- historical re-audit is no longer mandatory startup context;
- mandatory Codex startup reduced to `AGENTS.md` + canonical Super Master Context + progress ledger + assigned workstream;
- specialist documents are loaded on demand;
- explicit instruction-injection isolation added for logs/issues/web/customer-controlled content;
- R0-R4 change-risk classification added;
- production certification gates expanded to cover supply chain, installation/recovery, RBAC, appliance security, optional integrations, HA, upgrade and reliability/performance evidence;
- release policy now explicitly covers trust/signing, SBOM/provenance, dependency/secret scanning, key rotation/revocation and rollback classes;
- effort arithmetic corrected: historical component ranges sum to **20–29 engineering man-days**, not 20–27.

Scope limit: this is `SOURCE_COMPLETE` documentation/governance work only. It changes no CloudStack Java/API/DB/KVM-agent/orchestration code and performs no live runtime mutation. It does not promote any product capability to a stronger runtime status.

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

### PARTIAL

- customer terminology: substantial work exists and current onboarding terminology passed live verification, but full role/context wrong-label audit remains pending;
- installer: current V1 UI/resume/served-repair pins are aligned for the placeholder-removal scope, but CI-built UI artifact deployment, SELinux final state/policy, firewall-policy validation, appliance lockdown and signed update controls remain incomplete;
- self-service foundation: upstream CloudStack components exist, but final LayerSentry Department Admin/User UX is not yet implemented/live-proven;
- IP protection: stable architecture/policy is defined, but production artifact/source-map/signing/appliance controls remain dependent on implementation/evidence;
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
