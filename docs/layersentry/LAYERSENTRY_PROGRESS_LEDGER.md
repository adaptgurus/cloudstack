# LayerSentry V1 — Durable Progress Ledger

## Purpose

This file is the frequently updated, Git-backed operational checkpoint for LayerSentry work. It exists so that browser refreshes, reconnects, tab closes, ChatGPT/Codex session loss, context exhaustion, model retries, or transient tool failures do **not** erase already completed work or cause verified work to be repeated.

The architecture, rules, evidence hierarchy, status governance, and anti-hallucination policy remain authoritative in `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`. The version-specific corrections in `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md` are an authoritative companion and override conflicting or less-specific wording until folded directly into the master context. Upgrade/IP-protection/stability requirements are defined in `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`. This ledger records the latest execution state.

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
4. Read this progress ledger.
5. Fetch the actual current HEAD of `adaptgurus/cloudstack` branch `layersentry/4.22.1.1-ui`.
6. Fetch the runner branch HEAD when relevant.
7. Inspect the latest relevant workflow/run/artifact.
8. If the previous action may still be running, check its actual state before retrying.
9. Do not repeat destructive or non-idempotent actions merely because the prior assistant message disappeared.
10. Resume from the first unmet evidence gate.

## Current checkpoint

### LIVE_VERIFIED — historical served LayerSentry branding/customer terminology baseline on `sen`

Evidence:

- workflow run: `33856746145`
- job: `100971705863`
- conclusion: `success`
- artifact: `9930784385`
- artifact digest: `sha256:6a6751c9c07723f73df36e02b9f66ee3a41cb3098ac2f2834945af4759e9a50b`
- HTTP 200
- served config: `/etc/cloudstack/management/config.json`

Scope is only what that historical workflow asserted. It does not prove the pending V1 KVM profile, self-service redesign, Kubernetes, object storage, appliance lockdown, HA topology, backup, or DR.

### SOURCE_COMPLETE — continuity / re-audit / upgradeability guardrails

- `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md` exists.
- `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md` exists.
- `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md` exists; creation commit `aa3163d108b1b602b18fe8409c77da35bffa96e4`.
- This progress ledger is the refresh-safe operational checkpoint.

Upgrade/IP protection policy now explicitly requires minimal upstream diff, versioned release manifests, deterministic signed CI artifacts, upgrade compatibility gates, schema-aware CloudStack upgrade sequencing, staged/canary testing, rollback classification, SBOM/support bundles, server-side placement of proprietary logic, and no production source maps by default when implemented.

Important anti-hallucination/IP statement: it is **not technically possible to guarantee that customer-delivered software cannot be reverse engineered**, particularly open-source CloudStack core and browser JavaScript. The product objective is to minimize exposed LayerSentry-specific logic, keep proprietary orchestration server-side, raise the cost of analysis, sign artifacts, reduce shell/source exposure, and never rely on obscurity for security.

### SOURCE_COMPLETE — DBaaS/APaaS placeholder removal

Customer-facing V1 DBaaS/APaaS placeholder implementation has been removed from the LayerSentry UI source.

Exact reviewed UI commit:

`9ad724eb76843d40d6a883c0a0ab47a75ceed449`

Compared with the prior audited branch point `44b93e1bf6bc742c1c1a0c66e6319d25a6c47dda`, the exact UI delta is:

- `ui/src/config/router.js`: only 4 deletions — DBaaS/APaaS imports and route registration;
- `ui/src/config/section/dbaas.js`: removed;
- `ui/src/config/section/apaas.js`: removed;
- `ui/src/views/layersentry/ServiceCatalog.vue`: removed.

No CloudStack backend/API/database/core functionality was changed for this task.

### SOURCE_COMPLETE — V1 served-UI verification and installer pin alignment

- served-UI repair commit: `49dbbeafe6e02c0797dac8d675e89ec440e44437`
  - pins UI commit `9ad724...`;
  - fails if DBaaS/APaaS strings are present in the built/served JavaScript;
  - emits `V1_PLACEHOLDERS=ABSENT` on success.
- resume path commit: `8b9999a98af0d410d051e851578d31008cb5383f`
  - pins the same V1 UI and served-UI repair.
- main installer alignment commit: `c8ee0cc76d1646810c1e4fb597af9fbdf1d96cb4`
  - UI pin: `9ad724...`;
  - resume pin: `8b9999...`;
  - served repair pin: `49dbbe...`.

This is **source-level pin parity for the current V1 placeholder-removal change**. It does not mean the overall production installer is complete; CI-built artifact deployment, SELinux enforcing policy, package lockdown and signed updates remain pending.

### CI/LIVE IN PROGRESS — DBaaS/APaaS removal deployment

Runner repository: `adaptgurus/cozystack`

- workflow updated for exact new UI/repair pins: commit `eea046ae31669d56d4c86738950227c214a99510`;
- deployment request commit: `32b7dfdb43061457d322410a31697bd0a0cce313`;
- workflow run: `33877641094`;
- job: `101038334940`;
- last observed state at this checkpoint: `Deploy customer-friendly Layersentry UI` **in progress**.

The next session/action must inspect run `33877641094` first. Do **not** submit a duplicate deployment request while this run is still active or before reading its final result.

### PARTIAL

- customer terminology: substantial work exists, but full role/context wrong-label audit remains pending.
- installer: current V1 UI/resume/served-repair pins are aligned, but CI-built UI artifact, SELinux final state/policy, firewall-policy validation, appliance lockdown and signed update controls remain incomplete.
- self-service foundation: upstream CloudStack components exist, but final LayerSentry Department Admin/User UX is not yet implemented/live-proven.
- IP protection: architecture/policy is defined, but production source-map policy, compiled proprietary components (if needed), signed release channel and appliance-access controls are not yet implemented/certified.

### PENDING / NOT_TESTED

- live verification of DBaaS/APaaS placeholder removal — workflow `33877641094` currently in progress at checkpoint time;
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

1. Inspect workflow `33877641094` and job `101038334940`; capture logs/artifact/final live assertions.
2. If the run passes, promote DBaaS/APaaS placeholder removal to `LIVE_VERIFIED` for the exact assertions and update this ledger.
3. If it fails, diagnose from the exact logs; do not submit a duplicate run blindly.
4. Move UI compilation away from production management nodes to a CI-built immutable artifact.
5. Implement the KVM-only product-profile visibility matrix with prerequisite/provider-aware feature gating.
6. Implement role-aware dashboards and simplified VM/Kubernetes/Bucket UX using the corrected Department/Account model.
7. Add the KVM snapshot-safety guard and CKS metadata-isolation/CSI requirements to the relevant product/security tests.
8. Build/deploy/role-test on `sen`.
9. Add the second Rocky Linux 9 nested-KVM VM.
10. Prove native two-zone NAS B&R cross-zone recovery, including source-record retention behavior, before advanced DR automation.

## Refresh-safe invariant

**If the user refreshes the page in the middle of work, already committed/evidenced completed tasks remain completed. The next session must discover and preserve them from GitHub/workflow/live evidence. It must not restart from the beginning or mark them lost merely because the chat UI no longer contains the previous assistant output.**
