# LayerSentry AI Operating Rules

This repository is Apache CloudStack 4.22.1.1 with a LayerSentry KVM-first product layer. These rules apply to ChatGPT, Codex and other AI-assisted engineering in the LayerSentry context.

The objective is to finish customer-operable vertical slices with the **smallest supportable LayerSentry overlay**. Reuse CloudStack and mature Kubernetes ecosystem products instead of rebuilding functionality they already provide.

## 1. Minimal mandatory startup

Before changing source or runtime, read only:

1. `AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. the one specialist context/workstream required by the task;
5. fetch the actual current repository/workflow/live state.

Specialist context:

- UI/self-service: `codex/WORKSTREAM_A_UI_SELF_SERVICE.md`;
- Kubernetes/RKE2/Data Services/APaaS/Streaming: `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` + `codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`;
- VM-native Single-OS: `LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` + `codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`;
- DC/DR/DRaaS: `LAYERSENTRY_DRAAS_ARCHITECTURE.md` + `codex/WORKSTREAM_D_DR_HA_UPGRADE.md` when needed;
- secure-engineering details: `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`;
- debugging/root cause: `LAYERSENTRY_DEBUGGING_RUNBOOK.md`.

Do not load historical handoffs/re-audits or every specialist document by default. Open them only to resolve a concrete conflict or missing fact.

Always inspect actual refs before editing:

```bash
git status --short --branch
git remote -v
git branch --show-current
git fetch --all --tags --prune
git rev-parse HEAD
git log -5 --oneline --decorate
```

Never reset a shared branch to a SHA copied from documentation. Never force-push unless the owner explicitly authorizes a known recovery action.

## 2. Current execution routing

The authoritative routing is `LAYERSENTRY_EXECUTION_CONTRACT.md`.

Default:

- **Codex — UI finishing:** optimize/integrate/test the already-built LayerSentry UI; no broad redesign.
- **Codex — RKE2/Kubernetes:** finish the existing CAPI/CAPC/CAPRKE2/RKE2 source, immutable artifacts and real E2E qualification.
- **Codex — Kubernetes services:** after the base RKE2 lifecycle works, install and qualify upstream OpenEverest/OpenBao/Harbor/Strimzi through the same Flux/package plane. Do not rebuild those products.
- **ChatGPT — VM-native Single-OS:** Go orchestration + Ansible execution.
- **ChatGPT — bootstrap/hypervisor/control-plane HA:** Ansible/native tooling.
- **ChatGPT — DC/DR/DRaaS:** native CloudStack recovery and provider-native replication first.
- **ChatGPT — architecture/context cleanup:** concise authority maintenance only.

Codex is therefore concentrated on two bounded scopes: **UI completion** and **Kubernetes/RKE2 E2E**. The Kubernetes stream remains the dominant engineering effort.

## 3. Non-negotiable CloudStack boundary

Default decision: **do not rewrite CloudStack core**.

CloudStack remains authoritative for VM/KVM lifecycle, Zone/Pod/Cluster/Host, networks/VPCs, IPs, firewall/ACL/native LB, storage, volumes, templates/ISOs, snapshots, Backup & Recovery, account/domain/project/RBAC/quota and async-job/resource state.

Prefer, in order:

1. native CloudStack 4.22.1.1 APIs;
2. supported CloudStack provider/plugin/configuration contracts;
3. the selected Kubernetes ecosystem controller when Kubernetes owns the lifecycle;
4. thin LayerSentry BFF/orchestration for composite workflow, policy and evidence;
5. narrow upstream/core change only by explicit exception.

Never create a second VM scheduler, tenancy/RBAC authority, quota authority or conflicting copy of CloudStack-owned state.

## 4. UI rule — Codex owned, optimization only

The broad LayerSentry UI is **feature-frozen**. Codex owns the remaining UI work, but this means finishing the existing product, not redesigning it.

Allowed:

- defects and broken routes/buttons;
- API/BFF wiring;
- RBAC/direct-route corrections;
- status/progress/error/empty states;
- KVM-only customer presentation;
- exact K8s/DR/Single-OS integration required by working backends;
- browser E2E, responsive, accessibility and security regressions.

Do not start another dashboard/navigation/terminology redesign without a concrete acceptance defect. UI hiding never replaces server-side authorization.

## 5. One LayerSentry RKE2 lifecycle

LayerSentry does **not** need separate Kubernetes provisioning engines for user clusters, DBaaS, APaaS or Streaming.

Use one lifecycle:

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> central Flux
 -> selected packages/operators
```

Profiles may differ in node pools, storage, networking, security and packages, but cluster create/status/scale/replace/delete/upgrade uses the same owner path.

Do not create separate DBaaS/APaaS/Kafka cluster provisioners.

## 6. RKE2 Codex priority — E2E before more source

The branch already contains substantial E0/E1 source including BFF/auth/RBAC, durable saga/journal/reconciliation, CloudStack client/preflight, CAPI/CAPC/CAPRKE2 resources, lifecycle executor, CAPC endpoint/volume-ownership work, CCM/CSI downstream work, NodeDiskSet, Flux resources and runtime wiring.

Therefore Codex must prioritize the **first failing live gate**, not more horizontal scaffolding.

Required base proof:

```text
immutable artifacts
 -> controller deployment
 -> GUI/API create
 -> CAPC CloudStack VMs/resources
 -> CAPRKE2 automatic join
 -> 6443
 -> 9345
 -> primary CNI Ready
 -> CCM/L4 lifecycle
 -> one safe CSI path
 -> Flux remote reconciliation
 -> status/scale
 -> node replacement + PVC/data safety
 -> delete/cleanup
 -> restart/unknown-state recovery
 -> supported upgrade
 -> air-gap proof for the claimed profile
```

For every failure: capture evidence, identify the owning layer, fix the smallest correct owner, add regression coverage, rebuild the affected immutable artifact and rerun the same step.

## 7. CAPC stop-loss and approved fallback

CAPI/CAPC/CAPRKE2 remains the preferred V1 path because substantial source already exists. Do not abandon it for a fixable integration defect.

But do not patch CAPC indefinitely.

If one bounded qualification campaign repeatedly fails to achieve the minimum base cluster proof — CloudStack VM creation, automatic RKE2 join, reachable 6443/9345 and cluster `Ready` — and evidence shows the remaining provider maintenance is disproportionate, record a release decision and switch to the approved fallback:

```text
LayerSentry durable workflow
 -> native CloudStack APIs
 -> hardened QCOW2/cloud-init
 -> Ansible Runner
 -> RKE2
 -> Flux
```

One release has one lifecycle owner. Never run CAPI and fallback as competing owners for the same cluster lifecycle.

## 8. Upstream services are packages, not LayerSentry rewrite projects

After the base RKE2/CSI/CCM/Flux path works, reuse mature upstream products through pinned Helm/OCI/Flux content.

V1 default:

- **OpenEverest stable v1 line** for supported PostgreSQL/PXC-MySQL/MongoDB lifecycle;
- **OpenBao** from its supported Helm deployment;
- **Harbor** from its supported Helm deployment;
- **Strimzi** for Kafka lifecycle.

Do not implement replacement PostgreSQL/MySQL/MongoDB operators, backup/PITR engines, DB failover engines, Kafka operators, Harbor controllers or OpenBao controllers.

For V1, do not spend engineering effort rebranding upstream application UIs unless the owner explicitly asks for that exact branding task. LayerSentry owns the service catalog, access point, policy, compatibility, storage/network selection and status integration; upstream products may retain their own UI/identity where appropriate and legally required attribution remains intact.

Redis/Valkey, additional engines and additional APaaS products use an existing mature operator/provider if added; do not write a new operator merely to fill catalog breadth.

## 9. One signed platform release carrier

For V1, use one logical signed release carrier, conceptually:

```text
layersentry-platform-<release>.iso
```

It may contain both platform and optional service artifacts:

- QCOW2 node images;
- RKE2/CAPI/CAPC/CAPRKE2;
- CNI/CCM/CSI;
- Flux;
- OpenEverest and required database operators/images;
- OpenBao;
- Harbor;
- Strimzi/Kafka;
- approved security/observability/backup packages;
- RPM/DEB content where required;
- compatibility metadata, checksums, signatures, SBOM and provenance.

Bundled means **AVAILABLE**, not installed. Flux installs only the packages selected for a cluster/profile. Adding an available package does not require reinstalling the ISO or rebuilding the cluster unless host/kernel capability actually changes.

This V1 packaging decision supersedes the earlier conceptual split into separate K8s and Data Services ISO carriers for current execution. Logical catalog sections may remain separate inside the same signed release.

## 10. VM-native Single-OS installation rule

Selected architecture:

```text
LayerSentry UI/API
 -> Go orchestration/control
 -> Ansible Runner / ansible-core
 -> versioned roles/playbooks
 -> Rocky Linux 9 guest
```

Go owns validation, authorization binding, planning, idempotency, locking, durable state/journal, secret references, Ansible invocation, health/evidence and rollback/recovery state.

Ansible owns guest packages, repositories, services, SELinux, firewalld, LVM/filesystems/mounts, VIP/network configuration and database/application provider configuration.

Do **not** implement product installation/configuration, cluster join, upgrade, repair, uninstall, storage or RKE2 installation as Bash/sh lifecycle scripts. Existing shell-based product installation/configuration assets are deprecated and must not be extended.

Inside Ansible prefer dedicated modules. `shell`/`raw` are exceptional; when only a vendor CLI exists use argv-safe command/module semantics.

## 11. DC/DR/DRaaS rule

Do not build heavy custom DR code while native CloudStack recovery is unproven.

Current order:

```text
healthy DC/DR CloudStack
 -> native Backup & Recovery
 -> two real recovery points
 -> selected old/latest createVMFromBackup recovery
 -> isolated destination networking
 -> exact guest data validation
 -> thin LayerSentry UI/orchestration
 -> one provider-native low-RPO path if required
 -> planned failover/failback
 -> witness/fencing/automatic failover last
```

Use native CloudStack APIs and storage-native replication. Do not create a generic LayerSentry block replication engine when the provider already supplies the data plane.

## 12. Research rule

Research deeply only when a material version/provider decision is open or a real blocker requires it.

Do not repeatedly re-audit frozen architecture. For major unresolved decisions verify exact CloudStack 4.22.1.1 source/docs, exact upstream versions and relevant issue/PR history. Record the decision once and execute until evidence invalidates it.

## 13. Engineering and evidence lifecycle

For meaningful changes:

```text
current-state check
 -> focused decision only if needed
 -> implementation/integration
 -> tests
 -> live/E2E validation where applicable
 -> concise evidence/status update
 -> commit
```

Use only:

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

A commit is not deployment proof. A build is not runtime proof. HTTP 200 is not whole-service proof. Documentation is not exact-combination proof.

## 14. Security baseline

Treat customer/operator/external values as untrusted. Preserve server-side authorization, strict validation, safe argv/typed API/module invocation, parameterized SQL, path/archive/symlink safety, TLS verification, SSRF controls, finite timeouts/retries, mutation idempotency and secret redaction.

Secrets never enter Git, browser code, normal logs or evidence. Keep SELinux Enforcing and firewalld active for production Rocky profiles; do not disable security controls to make tests pass.

## 15. Continuity and concurrency

Repository/workflow/live evidence overrides chat memory and stale handoffs.

Before mutation inspect actual current refs and in-flight operations. After timeout/refresh, observe authoritative state before retrying.

UI and K8s Codex source work may run separately only when file ownership is non-overlapping. Coordinate any shared router/config/API contract changes. Serialize cluster create/delete, storage/CSI, VIP/LB, upgrade/replacement and destructive data-safety operations on the same lab.

## 16. Progress model

Measure progress by customer-operable vertical slices, not line/file/commit count.

Priority proofs:

1. one complete LayerSentry RKE2 lifecycle;
2. UI acceptance against the working RKE2/backend contracts;
3. OpenEverest installed through Flux and one supported DB lifecycle proved using upstream semantics;
4. OpenBao/Harbor/Strimzi installed through the same package plane and qualified as required;
5. VM-native Go+Ansible vertical slices;
6. two-point native CloudStack DR recovery with exact guest-data verification.

Do not expand provider/catalog breadth before the shared substrate and package plane work.