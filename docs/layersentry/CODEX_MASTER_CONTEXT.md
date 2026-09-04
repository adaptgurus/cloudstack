# LayerSentry V1 — Codex Master Context

## Purpose

This is the concise Codex execution context for LayerSentry. It is intentionally shorter than the Super Master Context and is designed to get coding agents productive quickly without losing the anti-hallucination, upgradeability, safety, and evidence rules.

`AGENTS.md` is mandatory and applies to the repository. This file does not replace the authoritative LayerSentry documents; it tells Codex how to use them.

## Repositories

Primary product source:

- Repository: `adaptgurus/cloudstack`
- Integration branch: `layersentry/4.22.1.1-ui`
- Immutable upstream validation base: Apache CloudStack 4.22.1.1 commit `71af23d73741cfeae854d2f1a6d36324307c32c4`
- Draft PR: #1

Runner / Hyper-V / live-lab automation:

- Repository: `adaptgurus/cozystack`
- Integration branch: `ops/layersentry-hyperv-inventory`

Never trust a historical HEAD written in documentation. Fetch the real branch HEAD at the start of each session.

## Read order

Every Codex workstream must read:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_MASTER_CONTEXT_REAUDIT_2026-09-04.md`
4. `docs/layersentry/LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`
5. `docs/layersentry/LAYERSENTRY_UPSTREAM_DIFF.md`
6. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
7. this file
8. its assigned workstream file under `docs/layersentry/codex/`

The progress ledger contains the freshest completion state. Repository/workflow/live evidence overrides historical docs.

## Product goal in one paragraph

LayerSentry V1 is a simple commercial on-prem KVM private-cloud appliance built on Apache CloudStack 4.22.1.1. Keep CloudStack's mature APIs, DB schema, RBAC, VM lifecycle, scheduler, storage/network semantics, KVM agent, plugins, and upgrade model intact. LayerSentry adds an opinionated KVM-only customer experience, role-aware self service, simplified workflows, automated installation, appliance hardening, controlled updates, backup/DR productization, release engineering, and support/validation tooling.

## Customer experience target

Platform Administrator:

- Dashboard
- Compute
- Storage
- Network
- Images
- Infrastructure
- Backup & DR
- Activity
- Administration

Department Administrator:

- Dashboard
- Compute: VMs, conditional Kubernetes
- Storage: disks, snapshots, conditional buckets
- Network: VM networks, public IP/firewall where applicable
- Images
- Backup & DR when configured/authorized
- Department: users/accounts/resource limits
- Activity

Normal User:

- Dashboard
- Virtual Machines
- conditional Kubernetes
- Storage/Snapshots
- conditional Buckets
- Networks
- Images
- conditional Backup & DR
- Activity

Do not expose physical CloudStack internals or non-KVM hypervisors in normal customer modes.

## Core-preservation rule

Default decision: do not modify CloudStack Java backend, DB schema, API contracts, KVM agent/core orchestration, async jobs, or internal resource model. Solve requirements with UI, config, supported APIs, LayerSentry-only services, installers, CI, tests, and wrappers.

Any proposed core change requires an explicit written proof that no supported LayerSentry overlay/API approach can satisfy the requirement.

## Current proven state

`LIVE_VERIFIED` on lab VM `sen`:

- LayerSentry served branding/terminology baseline.
- DBaaS/APaaS V1 placeholders removed.
- Exact successful placeholder-removal deployment evidence:
  - UI source: `6ce76d6c241629086ffcad794093dbdd5f2dd5ba`
  - served repair: `85031bd2e394c16c631b6e493ced1af87c19fbd3`
  - workflow run: `33879178031`
  - job: `101043343720`
  - artifact: `9939463820`
  - artifact digest: `sha256:1a308fdcfff5a87348a4dad3783afc4bf24ea4b5efa6a583a6203064b8599813`
  - assertions: HTTP 200, `V1_PLACEHOLDERS=ABSENT`, onboarding/logo/runtime-config/terminology pass.

This evidence does not prove the remaining V1 capabilities below.

## Remaining major scope

Still `PENDING`, `PARTIAL`, or `NOT_TESTED` unless newer evidence says otherwise:

- CI-built immutable production UI artifact; no production-side npm build
- production source-map suppression/support-build strategy
- release manifest, digest/signature verification, SBOM
- KVM-only LayerSentry product-profile visibility matrix
- Platform Admin dashboard redesign
- Department Admin self-service dashboard
- normal User dashboard
- simplified VM wizard
- simplified CKS wizard
- simplified Bucket UX
- Site/Infrastructure onboarding simplification
- prerequisite/provider-aware feature gating
- RBAC/direct-URL negative testing
- KVM snapshot conflict safety guard
- CKS metadata isolation NetworkPolicy
- CKS CSI integration validation
- Rocky 9 SELinux enforcing policy and validation
- firewalld-enabled LayerSentry KVM validation
- package/repository lockdown
- controlled signed update channel
- full air-gap CKS
- live object-store validation
- native NAS B&R proof
- two-Zone DR proof and measured RPO/RTO
- DR mapping/test recovery/failover/failback
- 3-management/2-LB/3-DB HA certification
- physical OOBM/fencing certification
- N-1 -> N upgrade and rollback/resume evidence
- production release certification

## Important technical corrections

- Version-specific CloudStack 4.22.1.x documentation is authoritative; do not rely on `/latest/` alone.
- Product DB compatibility baseline is MySQL 8.4/equivalent for the 4.22.1 target; actual HA topology remains uncertified until tested.
- Department with delegated sub-account administration should normally map to a CloudStack Domain; teams/workloads to Accounts; users in one Account are not isolated.
- Feature visibility requires permission plus real prerequisites/provider/configuration state.
- VM-create `Backup Policy` is post-deploy B&R orchestration, not a native `deployVirtualMachine` parameter.
- CKS CSI integration synchronizes CloudStack Disk Offerings to Kubernetes Storage Classes; do not invent unsupported CKS parameters.
- Block pod access to CloudStack VM metadata/user-data by default for production CKS unless explicitly required.
- Full offline CKS is not natively complete in CloudStack 4.22.1; internal registry/bootstrap work remains separate.
- NAS B&R should not be used as the primary protection mechanism for CKS nodes.
- DR recovery depends on backup repository reachability and source instance DB-record retention; account for purge/expunge behavior.
- KVM Instance snapshots and Volume snapshots have a documented coexistence risk; LayerSentry must guard unsafe workflows.
- A two-VM nested lab proves functional cross-Zone recovery only, not physical site independence or real BMC fencing.

## Production and upgrade principles

- Keep the upstream delta minimal.
- Build production UI in controlled CI, not on management nodes.
- Pin toolchains and dependencies.
- Disable production source maps by default; create explicit support builds when needed.
- Produce immutable artifacts, digests, signatures, release manifests, and SBOMs.
- Installer verifies exact artifact provenance before deploying.
- Keep proprietary LayerSentry orchestration server-side when practical; never rely on browser obfuscation as security.
- Do not promise impossible non-reverse-engineerability.
- Test fresh install and supported N-1 -> N upgrades on staging before certification.
- Respect CloudStack schema-upgrade sequencing; do not promise zero management-plane downtime when upstream requires all other management nodes stopped during DB upgrade.

## Parallel Codex execution model

Run four isolated agents/worktrees. They may work concurrently because their file ownership is intentionally separated.

### Workstream A — UI / Self-service

Branch suggestion: `codex/layersentry-ui-self-service`

Primary ownership:

- `ui/src/config/**`
- `ui/src/views/**`
- `ui/src/components/**` where directly required by customer UX
- `ui/src/locales/**`
- LayerSentry UI tests

Do not own installer/release pipeline or DR/Hyper-V runner automation.

Read `docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`.

### Workstream B — Release / Installer / Build

Branch suggestion: `codex/layersentry-release-installer`

Primary ownership:

- `install-layersentry*.sh`
- `ui/vue.config.js` and build-only settings
- release-manifest/SBOM/signature/digest tooling
- immutable UI artifact build/deploy pipeline
- installer idempotency/resume/rollback structure

Do not redesign dashboards/wizards.

Read `docs/layersentry/codex/WORKSTREAM_B_RELEASE_INSTALLER.md`.

### Workstream C — Security / Validation

Branch suggestion: `codex/layersentry-security-validation`

Primary ownership:

- LayerSentry validation/test tooling
- RBAC/direct-URL negative tests
- SELinux/firewalld validation assets
- package-lock/update validation
- snapshot-conflict test/guard specification
- CKS metadata-isolation and CSI validation
- support/evidence collection tooling

Avoid broad production UI redesign and avoid DR infrastructure mutation.

Read `docs/layersentry/codex/WORKSTREAM_C_SECURITY_VALIDATION.md`.

### Workstream D — DR / HA / Upgrade

CloudStack branch only when needed: `codex/layersentry-dr-ha-upgrade`

Runner repository branch suggestion: `codex/layersentry-dr-ha-upgrade` from `adaptgurus/cozystack:ops/layersentry-hyperv-inventory`.

Primary ownership:

- Hyper-V/runner automation
- second-VM/two-Zone DR proof harness
- NAS B&R validation orchestration
- HA failure-test workflows
- upgrade/resume/rollback test harness
- evidence artifacts

Do not alter CloudStack core to make tests pass.

Read `docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`.

## Parallel merge discipline

No workstream merges directly to the integration branch without review.

Each agent:

1. starts from the fetched current integration HEAD;
2. uses an isolated worktree/branch;
3. commits only its owned scope;
4. runs relevant tests;
5. writes a concise workstream handoff/report under `docs/layersentry/codex/reports/` if requested;
6. reports exact commit and validation results.

Integration order normally:

1. B release/build foundation first if A needs the new artifact pipeline;
2. A UI product profile/self-service;
3. C security/negative-test guards against the merged A/B state;
4. D live DR/HA/upgrade workflows after source and deployment pipeline are stable.

Independent changes may be reviewed/merged earlier when there is no file overlap.

Only the integration/lead session updates the shared progress ledger after verifying merge/build/live evidence. This prevents four agents from racing on the same status file.

## What a Codex agent must do when stuck

Do not guess. Inspect source/tests/logs. If runtime evidence is needed but unavailable, mark the state `UNKNOWN` or `BLOCKED` and state the exact evidence required. If another workstream owns the required file, stop and record a cross-workstream dependency rather than editing outside ownership.

## Standard handoff format

At task completion report exactly:

- Workstream
- Branch/worktree
- Base commit
- Final commit
- Files changed
- Behavior changed
- Core CloudStack impact: YES/NO
- Checks/tests run
- Checks/tests not run
- Runtime mutation: YES/NO
- Known limitations
- Cross-workstream dependencies
- Recommended integration order
- Next evidence gate

Never report unexecuted tests as passing.
