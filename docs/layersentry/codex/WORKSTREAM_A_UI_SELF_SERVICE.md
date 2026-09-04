# Codex Workstream A — UI / Self-Service

## Mission

Turn the existing CloudStack 4.22.1.1 UI into the LayerSentry KVM-first self-service experience without changing CloudStack core APIs, DB schema, scheduler, KVM agent, RBAC semantics, or resource model.

## Startup

Read `/AGENTS.md` and `docs/layersentry/CODEX_MASTER_CONTEXT.md` plus all mandatory documents they reference. Fetch the actual integration branch HEAD. Create/use an isolated worktree/branch such as `codex/layersentry-ui-self-service`.

## File ownership

Primary ownership:

- `ui/src/config/**`
- `ui/src/views/**`
- `ui/src/components/**` only where needed for UX
- `ui/src/locales/**`
- UI-specific tests

Do not modify installer/release scripts, `ui/vue.config.js`, runner/Hyper-V workflows, or CloudStack Java/backend files unless the lead explicitly reassigns scope.

## Required outcomes

1. Implement a KVM-only LayerSentry customer product profile without deleting non-KVM upstream implementations.
2. Make navigation role/task focused for Platform Admin, Department Admin, Department Operator/User, and Read-only where appropriate.
3. Redesign Platform Admin dashboard around real actionable VM/KVM host/capacity/alerts/service status, not generic CloudStack internal counters.
4. Redesign Department Admin and normal User dashboards using existing CloudStack API/RBAC/UsageDashboard data rather than a new backend.
5. Simplify Create VM UX while preserving native deploy semantics.
6. Simplify CKS UX while using actual native parameters; KVM is implicit.
7. Simplify Bucket UX only when a usable Object Store/provider is configured and authorized.
8. Simplify Site/Infrastructure onboarding without changing Zone/Pod/Cluster/Host backend meaning.
9. Feature-gate K8s/Buckets/Backup/DR based on permission plus real prerequisites/provider/config state.
10. Preserve LayerSentry branding and correct customer terminology.

## Customer terminology contract

Presentation only:

- Zone -> Site
- Pod -> Infrastructure Group
- Cluster -> Compute Cluster
- Host -> KVM Host / Compute Host
- Service Offering -> Compute Profile
- Disk Offering -> Storage Profile where it is actually a Disk Offering
- Template -> OS Image
- Guest Network -> VM/Workload Network

Do not rename backend fields or globally replace words where context changes meaning.

## Department model

When delegated departmental administration is needed, design for Department = CloudStack Domain, teams/workloads = Accounts, users = Users in Accounts. Users in one Account are not isolated; do not design the UI as if they are.

## Important workflow semantics

- A Create-VM `Backup Policy` is post-deploy B&R orchestration, not a native deploy field. If surfaced, design the UX/state/error behavior without inventing an API parameter.
- CKS native CSI enablement is real; Storage Classes derive from CloudStack Disk Offerings. Do not invent an unsupported cluster-create Storage Class field.
- Public IP/firewall/LB controls appear only where the chosen network offering provides them.
- `Healthy`, `Protected`, `HA`, `Backed up`, `DR ready`, etc. require real signals.

## V1 exclusions

Do not reintroduce DBaaS/APaaS placeholders. They are already live-verified as removed.

## Wrong-label audit

Before handoff inspect normal customer UI for stale/incorrect occurrences of:

- Pod
- wrong Zone/Site context
- VMware/XenServer/Hyper-V/Proxmox/MaaS
- DBaaS/APaaS
- wrong Storage/Storage Profile context
- unsupported provider/feature labels
- state labels not backed by real data

Legal/source text and explicit Platform/Support diagnostics are not customer-label failures.

## Validation

Run the narrowest relevant UI/static tests available in the repository. Build/test against the exact toolchain currently proven by the project; do not weaken tests. If the release/build workstream has not yet produced the new CI artifact pipeline, do not redesign that pipeline here.

## Handoff

Provide exact branch/base/final commit, changed files, screenshots or test evidence where available, core impact YES/NO, tests run/not run, known limitations, and any dependency on Workstream B/C/D. Do not edit the shared progress ledger unless explicitly assigned.
