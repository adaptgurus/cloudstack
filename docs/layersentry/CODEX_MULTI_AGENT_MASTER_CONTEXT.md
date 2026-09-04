# LayerSentry V1 — Codex Multi-Agent Master Context

## Purpose

This is the mandatory startup/execution context for running multiple Codex sessions against the LayerSentry V1 project. It exists to make parallel development faster **without losing correctness, duplicating work, corrupting branches, or allowing AI hallucination to become project state**.

This file does not replace the project source of truth. Every Codex session must read the following files before changing code:

1. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
2. `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md`
3. `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`
4. `docs/layersentry/LAYERSENTRY_UPSTREAM_DIFF.md`
5. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
6. this file

Repository/workflow/live-runtime evidence overrides historical SHAs or text in all documents.

---

## 1. Product objective

LayerSentry V1 is a production-oriented, KVM-first, on-prem private-cloud product based on Apache CloudStack 4.22.1.1.

The product goal is:

> Give customers a simple self-service private cloud for VMs, Kubernetes, storage, networking, buckets, backup and DR while preserving CloudStack's mature backend/API/RBAC/KVM orchestration.

Do **not** build a new hypervisor, scheduler, quota engine, RBAC engine, VM lifecycle engine, storage engine, network engine or Kubernetes engine when CloudStack already provides the required behavior.

The correct architecture is:

`LayerSentry UI + LayerSentry automation/hardening/orchestration -> supported CloudStack APIs/RBAC -> KVM/libvirt -> Rocky Linux 9`

---

## 2. Non-negotiable no-core-change rule

Unless a verified upstream defect requires an isolated fix, do not modify:

- CloudStack backend API contracts/names;
- CloudStack DB schema;
- async-job semantics;
- VM lifecycle semantics;
- KVM agent protocol;
- upstream RBAC enforcement;
- Zone/Pod/Cluster/Host internal model;
- storage/network orchestration semantics;
- upstream hypervisor implementations;
- upgrade model.

Prefer LayerSentry-specific wrappers/components/configuration over invasive edits to upstream files.

UI hiding is UX only. CloudStack RBAC remains the server-side security boundary.

---

## 3. Authoritative repositories

### Product source

Repository: `adaptgurus/cloudstack`

Integration branch: `layersentry/4.22.1.1-ui`

Immutable upstream validation base: `71af23d73741cfeae854d2f1a6d36324307c32c4`

Historical HEAD when this Codex context was created: `1fb7c0b2e6f69ecd7fe0c87b13ba410093c9a0d8`

**Never assume this historical HEAD is current. Run `git fetch origin` and read `origin/layersentry/4.22.1.1-ui` before work. Never force-push or reset the integration branch backward.**

### Runner/live-test automation

Repository: `adaptgurus/cozystack`

Branch: `ops/layersentry-hyperv-inventory`

The self-hosted Windows runner is on the Hyper-V test host. The current CloudStack test VM is historically named `sen` at `10.10.10.14`, but live state must be re-read before mutation.

---

## 4. Current proved state — do not redo

From the durable progress ledger, the DBaaS/APaaS V1 placeholder removal is `LIVE_VERIFIED` on the current `sen` test target for the exact tested scope.

Authoritative evidence currently recorded:

- cleaned UI source: `6ce76d6c241629086ffcad794093dbdd5f2dd5ba`;
- served repair: `85031bd2e394c16c631b6e493ced1af87c19fbd3`;
- successful workflow run: `33879178031`;
- job: `101043343720`;
- artifact: `9939463820`;
- artifact digest: `sha256:1a308fdcfff5a87348a4dad3783afc4bf24ea4b5efa6a583a6203064b8599813`;
- `HTTP=200`;
- `V1_PLACEHOLDERS=ABSENT`;
- `ONBOARDING=PASS`;
- `LOGO_ASSETS=PASS`;
- `RUNTIME_CONFIG=PASS`;
- `TERMINOLOGY=PASS`.

Do not reimplement/remove DBaaS/APaaS again unless newer source/runtime evidence proves regression.

---

## 5. Main remaining work

The durable ledger currently identifies these major unfinished areas:

- CI-built immutable UI artifact deployment instead of production-side npm builds;
- production source-map suppression/support-build policy;
- signed release manifest/artifact/update channel;
- KVM-only `layersentry-kvm` product profile;
- role-aware Platform Admin / Department Admin / normal User dashboards;
- simplified VM, Kubernetes and Bucket UX;
- final Site/Infrastructure onboarding simplification;
- KVM snapshot safety guard;
- CKS metadata-isolation and CSI validation;
- SELinux-enforcing appliance policy and tests;
- firewalld-enabled LayerSentry KVM traffic/security validation;
- package/repository lockdown and controlled signed updates;
- native NAS B&R proof and two-zone DR proof;
- source-record retention/purge negative test for DR;
- RPO/RTO measurement;
- upgrade N-1 -> N automation and rollback evidence;
- later 3-Management / 2-LB / 3-DB HA certification.

Do not promote any of these to complete without the evidence gates in the project documents.

---

## 6. Mandatory evidence/status model

Use only the project's governed status labels:

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

Never use unqualified `DONE`, `COMPLETE`, `WORKING`, `HEALTHY`, `HA`, `DR READY`, `AIR-GAPPED`, `IMMUTABLE`, or `PRODUCTION READY` unless the corresponding evidence gate has passed.

A commit is not a live deployment. A build is not a runtime test. HTTP 200 is not whole-cloud health. Documentation support is not proof that the current environment is configured or healthy.

---

## 7. Anti-hallucination rules

Never invent or silently assume:

- current branch HEADs;
- workflow/run/job/artifact IDs;
- IPs/VLANs/gateways/DNS;
- current KVM/agent/storage/network/System-VM state;
- CKS/Object Store/B&R provider state;
- backup or recovery success;
- RPO/RTO;
- DB/LB/HA state;
- role permissions;
- installer/upgrader success.

If not verified, say `UNKNOWN`, `NOT_TESTED`, or `BLOCKED` and identify the evidence required.

For CloudStack capability/requirement questions, prefer version-pinned 4.22.1.x documentation and current source. Do not rely on `/latest/` as the only authority.

---

## 8. Mandatory refresh/reconnect behavior

Chat/Codex state is not the persistence layer.

Persistence is Git commits, the progress ledger, workflow logs/artifacts and verified live runtime evidence.

After every meaningful atomic task:

1. commit coherent source changes;
2. record exact checks/test results;
3. preserve run/job/artifact IDs if remote automation was used;
4. state next unmet gate;
5. never leave the only evidence in an AI response.

After a refresh/new Codex window, read the authoritative docs and resume from the first unmet gate instead of starting over.

---

## 9. Multi-agent Git safety model

**Never run four Codex agents in the same checkout.**

Use one Git worktree per agent and one branch per worktree.

Recommended branches/worktrees:

- Agent A: `codex/ui-selfservice` -> `~/layersentry/work-ui`
- Agent B: `codex/release-installer` -> `~/layersentry/work-release`
- Agent C: `codex/security-quality` -> `~/layersentry/work-security`
- Agent D: `codex/dr-ha-upgrade` -> `~/layersentry/work-dr`

Each branch starts from the exact fetched current `origin/layersentry/4.22.1.1-ui` HEAD.

Agents must not merge into the integration branch themselves unless the user explicitly changes this policy.

Agents must not force-push.

Agents must not rewrite another agent's branch.

Keep commits small and task-focused.

The integration/review step should merge/cherry-pick one verified branch at a time, rerun combined tests, then update the durable progress ledger.

---

## 10. Agent A — UI / self-service product profile

Scope:

- implement `layersentry-kvm` customer product profile;
- hide non-KVM customer choices without deleting upstream support;
- role-aware Platform Admin / Department Admin / normal User navigation;
- dashboard redesign using existing CloudStack APIs/UsageDashboard data model;
- simplify existing VM wizard rather than replacing backend provisioning;
- simplify CKS wizard using actual native API semantics;
- simplify Bucket UX using native Object Storage APIs;
- simplify Site/Infrastructure onboarding;
- feature-gate K8s/Buckets/Backup/DR using permission + configuration + provider/prerequisites, not route/API presence alone;
- preserve correct terminology mapping and run wrong-label audit.

Do not touch installer/release pipeline unless absolutely required and coordinated.

Do not invent CloudStack API fields. Backup Policy during VM create, if exposed, is post-deploy supported B&R orchestration, not a native `deployVirtualMachine` field.

CKS Storage Classes are tied to CSI/Disk Offerings; do not invent a native storage-class parameter.

Deliverables:

- source commits;
- build/static checks;
- exact files changed;
- role/URL/API test plan;
- handoff note for integration.

---

## 11. Agent B — release artifact / installer / upgradeability foundation

Scope:

- move UI compilation away from production management nodes;
- create deterministic CI-built UI artifact/RPM/archive;
- pin build toolchain;
- production source maps disabled by default; optional controlled support build if required;
- artifact digest/signature verification design/implementation;
- versioned release manifest;
- SBOM generation/integration where practical;
- align fresh/resume/UI-only installer paths to one release artifact;
- idempotency/resume/rollback handling;
- minimize upstream fork debt;
- preserve exact CloudStack version/update sequencing;
- never claim zero-downtime DB-schema upgrades where upstream requires management downtime.

Do not redesign customer dashboards.

Deliverables:

- source commits;
- reproducible build instructions;
- artifact provenance checks;
- installer/static tests;
- upgrade compatibility notes;
- handoff note for integration.

---

## 12. Agent C — appliance security / quality / negative tests

Scope:

- SELinux enforcing policy engineering/test plan;
- firewalld-enabled LayerSentry KVM traffic validation matrix;
- package/repository lockdown design/implementation;
- controlled signed-update security controls;
- CKS pod metadata/user-data isolation NetworkPolicy requirement/tests;
- KVM VM-snapshot/Volume-snapshot conflict guard/test;
- role/API negative tests and direct-URL tests;
- security regression checks;
- support/debug tooling baseline;
- avoid broad or unsafe `audit2allow` policy generation.

Do not claim physical fencing certification from nested Hyper-V. Real OOBM/BMC/IPMI/Redfish requires actual physical hardware testing.

Deliverables:

- source/test commits;
- negative test matrix;
- remaining hardware-dependent gates;
- handoff note for integration.

---

## 13. Agent D — DR / HA / upgrade test automation

Scope:

- audit exact 4.22.1 NAS B&R cross-zone behavior against source/docs;
- prepare two-Zone functional DR automation for the future second Rocky/KVM VM;
- preserve source-record retention/purge limitation and negative test;
- repository mapping/network/storage/compute-profile mapping validation;
- RPO/RTO measurement harness;
- management-HA test plan for later 3-manager/2-LB/3-DB topology;
- N-1 -> N upgrade test orchestration and rollback evidence framework;
- keep advanced DR controller/failover/failback out of CloudStack core;
- do not build sophisticated DR orchestration before native cross-zone recovery is proven.

A two-VM POC on the same Hyper-V host is a functional recovery proof only, not physical-site certification.

Deliverables:

- scripts/workflows/tests/docs commits;
- exact prerequisites for second VM;
- safe/destructive action classification;
- evidence collection format;
- handoff note for integration.

---

## 14. Shared-agent conflict rules

To avoid agents fighting over files:

- Agent A owns normal UI UX/product-profile files.
- Agent B owns build/release/installer packaging files.
- Agent C owns security policy/test files.
- Agent D owns DR/HA/upgrade test automation.

If an agent needs to modify a file primarily owned by another agent, stop and document the requested change instead of making an overlapping edit unless the user/integration coordinator explicitly approves it.

Only the integration/coordinator session updates `LAYERSENTRY_PROGRESS_LEDGER.md` after reviewing merged evidence, unless an agent is explicitly assigned to do so.

---

## 15. Live environment mutation policy

Codex agents should default to source/build/test work.

Before touching `sen` or any future DR VM:

1. inspect live state;
2. classify action as read-only/reversible/destructive;
3. create a durable checkpoint;
4. verify the workflow/request targets exact intended VM/IP/FQDN;
5. preserve rollback method;
6. execute only when authorized by the user's existing project instructions;
7. record evidence immediately after action.

Never duplicate a still-running workflow after refresh. Inspect the exact run first.

Never expose or commit passwords, tokens, API keys or private SSH keys.

---

## 16. Required startup command sequence for every Codex agent

From its own worktree:

```bash
pwd
git status --short --branch
git fetch origin
git rev-parse HEAD
git rev-parse origin/layersentry/4.22.1.1-ui
sed -n '1,220p' docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md
sed -n '1,220p' docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md
sed -n '1,220p' docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md
sed -n '1,220p' docs/layersentry/LAYERSENTRY_UPSTREAM_DIFF.md
sed -n '1,260p' docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md
sed -n '1,260p' docs/layersentry/CODEX_MULTI_AGENT_MASTER_CONTEXT.md
```

If the worktree HEAD is not the expected branch or has unexpected local modifications, stop and diagnose before editing.

---

## 17. Standard Codex startup prompt

Paste this into every Codex window, followed by that agent's role block:

> Continue LayerSentry V1 from the repository evidence, not model memory. Read `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`, `LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md`, `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`, `LAYERSENTRY_UPSTREAM_DIFF.md`, `LAYERSENTRY_PROGRESS_LEDGER.md`, and `CODEX_MULTI_AGENT_MASTER_CONTEXT.md` before editing. Fetch current refs and verify this worktree/branch. Repository/workflow/live evidence overrides historical SHAs. Preserve CloudStack 4.22.1.1 backend/API/RBAC/KVM semantics; avoid CloudStack-core changes. Do not redo LIVE_VERIFIED work. Do not mark anything complete without the required evidence gate. Use small commits, run relevant tests, and finish with exact commit SHA, files changed, tests executed, known limitations and next gate. Do not merge into `layersentry/4.22.1.1-ui`; stop at a reviewable agent branch.

Then append one of:

- `You are Agent A. Execute only Section 10 UI/self-service scope.`
- `You are Agent B. Execute only Section 11 release/installer scope.`
- `You are Agent C. Execute only Section 12 security/quality scope.`
- `You are Agent D. Execute only Section 13 DR/HA/upgrade scope.`

---

## 18. Integration protocol

After an agent finishes a coherent task:

1. agent commits and reports SHA;
2. inspect diff against the exact integration base;
3. verify no unexpected backend/core changes;
4. run relevant build/static/unit checks;
5. cherry-pick/merge into an integration branch/worktree;
6. run combined checks because independently passing branches can conflict when combined;
7. deploy only after source/CI gates pass;
8. update durable progress ledger with exact evidence;
9. only then promote status.

Do not merge all four branches blindly at the end.

Integrate continuously in small verified batches.

---

## 19. Production engineering principles

- Future CloudStack upgrades must remain practical.
- Minimize upstream diff.
- Build once in controlled CI; production host deploys signed immutable artifact.
- No production source maps by default.
- Keep proprietary LayerSentry orchestration server-side where practical.
- Never rely on obscurity as a security control.
- Preinstall required debugging tools before appliance package lockdown.
- Users/admins must not install arbitrary packages; approved LayerSentry update transactions may change package sets.
- SELinux enforcing and firewalld are production goals only after actual compatibility testing.
- CloudStack documentation support is not runtime certification.
- Preserve legal Apache license/notice requirements.

---

## 20. Stop conditions

Stop and ask for review/decision rather than guessing when:

- source contradicts version-pinned CloudStack documentation;
- a proposed change requires CloudStack backend/API/schema modification;
- a task crosses another agent's ownership materially;
- a destructive live action lacks a verified rollback path;
- live state is different from the ledger;
- credentials or secrets appear in source/logs;
- the requested capability is unsupported in 4.22.1.1 and would need a new architecture;
- tests show a regression in LIVE_VERIFIED functionality.

---

## 21. Definition of success for the multi-agent phase

Success is not "four agents produced lots of code".

Success means:

- each agent works in an isolated branch/worktree;
- CloudStack core remains essentially untouched;
- changes are small, reviewable and upgrade-friendly;
- existing LIVE_VERIFIED behavior does not regress;
- build/test/runtime evidence is durable;
- combined integration passes relevant gates;
- every remaining capability retains an honest status;
- the project can resume after a refresh/new session without lost progress.
