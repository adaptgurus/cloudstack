# LayerSentry V1 — Durable Progress Ledger

## Purpose

This file is the frequently updated, Git-backed operational checkpoint for LayerSentry work. It exists so that browser refreshes, reconnects, tab closes, ChatGPT/Codex session loss, context exhaustion, model retries, or transient tool failures do **not** erase already completed work or cause verified work to be repeated.

The architecture, rules, evidence hierarchy, status governance, and anti-hallucination policy remain authoritative in `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`. The version-specific corrections in `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md` are an authoritative companion and override conflicting or less-specific wording until folded directly into the master context. This ledger records the latest execution state.

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
3. Read this progress ledger.
4. Fetch the actual current HEAD of `adaptgurus/cloudstack` branch `layersentry/4.22.1.1-ui`.
5. Fetch the runner branch HEAD when relevant.
6. Inspect the latest relevant workflow/run/artifact.
7. If the previous action may still be running, check its actual state before retrying.
8. Do not repeat destructive or non-idempotent actions merely because the prior assistant message disappeared.
9. Resume from the first unmet evidence gate.

## Current checkpoint

### LIVE_VERIFIED — served LayerSentry branding/customer terminology baseline on `sen`

Evidence:

- workflow run: `33856746145`
- job: `100971705863`
- conclusion: `success`
- artifact: `9930784385`
- artifact digest: `sha256:6a6751c9c07723f73df36e02b9f66ee3a41cb3098ac2f2834945af4759e9a50b`
- HTTP 200
- served config: `/etc/cloudstack/management/config.json`

Scope is only what that workflow asserted. It does not prove the pending V1 redesign, KVM profile, Kubernetes, object storage, appliance lockdown, HA topology, backup, or DR.

### SOURCE_COMPLETE — continuity/anti-hallucination documentation

- `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md` exists in the LayerSentry branch.
- This progress ledger is the refresh-safe operational checkpoint.
- `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md` records the deep 4.22.1 re-audit corrections.
- Current re-audit source commit: `16ea815745fddcdc3241332da6ef0997a0fd6e07`.
- No production/runtime capability was promoted by this documentation-only audit.

### RE-AUDIT FINDINGS — SOURCE_COMPLETE, RUNTIME UNCHANGED

The master architecture remains valid, but these corrections/guardrails are now authoritative:

- use version-pinned CloudStack 4.22.1.x docs; do not rely on `/latest/` alone;
- standardize the 4.22.1 database compatibility baseline on MySQL 8.4/equivalent;
- account for the EL `ipmitool` OOBM caveat before certifying KVM Host HA/fencing;
- use the full current KVM/libvirt security guidance, not insecure old quick-install TCP examples;
- treat SELinux enforcing as policy engineering/testing, not a mode toggle;
- `firewalld enabled` is a LayerSentry hardening deviation from the reference KVM guide and requires its own traffic/forwarding/migration/storage/B&R/CKS validation matrix;
- when delegated Department Admin manages subordinate teams/accounts, map Department to Domain and teams/workloads to Accounts; Users in one Account are not isolated;
- feature visibility requires permission plus real provider/prerequisite/configuration state, not API presence alone;
- a Create-VM Backup Policy selector must orchestrate supported B&R APIs after VM deployment rather than pretending it is a native deploy field;
- native CKS CSI integration is enabled during cluster creation and Disk Offerings sync to Kubernetes Storage Classes; do not invent an unsupported native storage-class parameter;
- block CKS pod access to underlying VM metadata/user-data by default unless explicitly required and tested;
- account for the B&R dependency on retaining the original/unmanaged/expunged instance DB entry;
- guard the known KVM VM-snapshot/Volume-snapshot coexistence issue;
- a two-VM DR POC on one Hyper-V host proves functional cross-zone recovery only, not physical site independence.

### PARTIAL

- customer terminology: substantial work exists, but full role/context wrong-label audit remains pending.
- installer: working historical paths exist, but fresh/resume parity, CI-built UI artifact, SELinux final state/policy, firewall-policy validation, lockdown, and signed update controls remain incomplete.
- self-service foundation: upstream CloudStack components exist, but final LayerSentry Department Admin/User UX is not yet implemented/live-proven.

### PENDING / NOT_TESTED

- remove DBaaS/APaaS placeholder routes/checks
- KVM-only `layersentry-kvm` product profile
- Platform Admin dashboard redesign
- Department Admin self-service dashboard
- normal User self-service dashboard
- simplified VM wizard
- simplified Kubernetes wizard
- simplified Bucket UX
- final Site/Infrastructure onboarding simplification
- fresh/resume installer parity
- CI-built immutable UI artifact deployment
- SELinux-enforcing appliance policy/modules and live validation
- firewalld-enabled LayerSentry KVM traffic/security validation
- package/repository lockdown
- controlled signed update mechanism
- full air-gap CKS
- CKS metadata-isolation NetworkPolicy live validation
- CKS CSI integration live validation for the selected Kubernetes ISO/profile
- live Kubernetes validation
- live object-store/Bucket validation
- KVM snapshot-conflict guard implementation/test
- native NAS B&R proof
- DR source-record retention/purge negative test
- two-zone cross-zone DR proof
- RPO/RTO measurement
- automated DR mapping
- Test Recovery
- planned/emergency failover
- failback
- 3-Management/2-LB/3-DB HA deployment and certification
- physical OOBM/fencing certification on actual supported hardware
- rolling upgrade certification
- production release certification

## Exact next execution sequence

1. Re-read current repository HEADs, the re-audit companion, and latest workflow evidence.
2. Remove DBaaS/APaaS V1 placeholders and installer checks.
3. Fix fresh/resume installer parity.
4. Move UI compilation away from production management nodes to a CI-built immutable artifact.
5. Implement the KVM-only product-profile visibility matrix with prerequisite/provider-aware feature gating.
6. Implement role-aware dashboards and simplified VM/Kubernetes/Bucket UX using the corrected Department/Account model.
7. Add the KVM snapshot-safety guard and CKS metadata-isolation/CSI requirements to the relevant product/security tests.
8. Build/deploy/role-test on `sen`.
9. Add the second Rocky Linux 9 nested-KVM VM.
10. Prove native two-zone NAS B&R cross-zone recovery, including source-record retention behavior, before advanced DR automation.

## Refresh-safe invariant

**If the user refreshes the page in the middle of work, already committed/evidenced completed tasks remain completed. The next session must discover and preserve them from GitHub/workflow/live evidence. It must not restart from the beginning or mark them lost merely because the chat UI no longer contains the previous assistant output.**
