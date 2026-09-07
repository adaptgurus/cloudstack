# LayerSentry V1 — Execution Contract

**Contract schema:** 1.1  
**Effective date:** 2026-09-07  
**Applies to:** ChatGPT, Codex, repository work, live validation and handoffs  
**Baseline:** Apache CloudStack 4.22.1.1, KVM-first LayerSentry

This contract defines how work is executed now. It intentionally minimizes duplicate architecture work and custom source by reusing CloudStack and mature Kubernetes ecosystem components.

## 1. Execution routing

| Surface | Default execution owner | Primary objective |
| --- | --- | --- |
| LayerSentry UI/self-service | **Codex** | finish/optimize existing UI, integration, RBAC, browser E2E; no broad redesign |
| LayerSentry-managed RKE2/Kubernetes | **Codex** | close existing E0/E1 live gates and complete one reusable cluster lifecycle |
| Kubernetes DBaaS/APaaS/Streaming | **Codex** | install/qualify pinned upstream products through the same RKE2 + Flux package plane; do not rebuild them |
| VM-native Single-OS DBaaS/APaaS | **ChatGPT** | retain Go orchestration, migrate/finish Ansible execution and provider vertical slices |
| Hypervisor/bootstrap/control-plane HA | **ChatGPT** | Ansible/native tooling, one-time bootstrap and HA validation |
| DC/DR/DRaaS | **ChatGPT** | native CloudStack recovery and provider-native replication first |
| General architecture/document cleanup | **ChatGPT** | keep authority concise/current; no repeated design churn |

Codex capacity is concentrated on **UI completion plus Kubernetes/RKE2 E2E**, with Kubernetes remaining the primary technical risk.

## 2. Context-loading rule

Every new engineering session reads only:

1. `/AGENTS.md`;
2. this contract;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. one applicable specialist context/workstream;
5. actual repository/workflow/live state.

Do not automatically reread historical handoffs, dated audits, every specialist context or every workstream. Repository, workflow and live evidence override stale text.

## 3. Global CloudStack boundary

Apache CloudStack remains authoritative for:

- KVM VM lifecycle;
- Zones/Sites, Pods/Infrastructure Groups, Clusters and Hosts;
- networks/VPCs, IPs, firewall/ACL and supported native LB;
- storage, volumes, templates, ISOs, snapshots and native Backup & Recovery;
- account/domain/project/RBAC/quota;
- async jobs and CloudStack resource state.

LayerSentry must not create a second VM scheduler, tenancy/RBAC database, quota authority or conflicting copy of CloudStack-owned resource state.

Implementation preference:

```text
native CloudStack 4.22.1.1 API
 -> supported CloudStack provider/plugin/configuration
 -> Kubernetes ecosystem controller where Kubernetes owns lifecycle
 -> thin LayerSentry orchestration/policy/evidence
 -> narrow core exception only when explicitly approved
```

## 4. UI policy — Codex owned, feature-frozen

The existing LayerSentry UI is substantial. Codex owns its remaining optimization and integration work.

Allowed:

- broken/missing routes or actions;
- API/BFF wiring;
- RBAC/direct-route corrections;
- KVM-only presentation;
- status/progress/error/empty states;
- exact K8s/DR/Single-OS integration;
- browser E2E/responsive/accessibility/security fixes.

Do not redesign navigation, dashboards, terminology or provisioning from scratch without a concrete acceptance defect. UI source completeness is not browser/live certification.

## 5. One reusable RKE2 lifecycle

User Kubernetes, DBaaS, APaaS and Streaming use the **same underlying LayerSentry RKE2 lifecycle**.

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> CNI/CCM/CSI
 -> central Flux
 -> profile-selected packages/operators
```

Different service profiles may choose different worker pools, StorageClasses, network exposure and package sets, but they do not receive separate cluster lifecycle engines.

Do not create a second DBaaS/APaaS/Kafka cluster provisioner.

## 6. Current RKE2 implementation strategy

The branch already contains substantial source for BFF/auth/RBAC, saga/journal/reconciliation, CloudStack preflight/client, CAPI/CAPC/CAPRKE2 resources, lifecycle executor, CAPC endpoint/volume ownership work, CCM/CSI downstream fixes, NodeDiskSet, Flux resources and runtime wiring.

Therefore the next Codex work is live vertical-slice closure, not broad scaffolding.

Required sequence:

```text
immutable artifacts
 -> deploy exact controller stack
 -> GUI/API create
 -> CAPC creates CloudStack resources
 -> CAPRKE2 automatic join
 -> 6443 + 9345
 -> primary CNI Ready
 -> CCM L4 lifecycle
 -> one safe CSI path
 -> Flux remote reconciliation
 -> status/scale
 -> node replacement + PVC/data survival
 -> delete/cleanup
 -> restart/UNKNOWN reconciliation
 -> supported upgrade
 -> deny-all-egress air-gap proof where claimed
```

A source change is valuable only when it closes a concrete release gate or observed E2E defect.

## 7. CAPC/CAPRKE2 stop-loss

CAPI/CAPC/CAPRKE2 remains the preferred path because significant LayerSentry source already exists.

Do not abandon it for normal integration defects, but do not maintain a permanent downstream fork merely to preserve sunk cost.

If a bounded qualification campaign repeatedly fails to reach the minimum base proof — CloudStack VM creation, automatic RKE2 join, reachable 6443/9345 and cluster `Ready` — and evidence shows the provider maintenance is disproportionate, select the already-approved release fallback:

```text
LayerSentry durable workflow
 -> native CloudStack APIs
 -> hardened QCOW2/cloud-init
 -> Ansible Runner
 -> RKE2
 -> Flux
```

The release must select one lifecycle owner. CAPI and fallback must never simultaneously own the same cluster lifecycle.

## 8. Kubernetes services: upstream-first, no replacement products

Once base RKE2/CSI/CCM/Flux is live-proven, use mature upstream packages.

Current V1 execution assumption:

- OpenEverest stable v1 line supplies supported PostgreSQL/PXC-MySQL/MongoDB lifecycle through its existing operators/control plane;
- OpenBao is installed from its supported Helm content;
- Harbor is installed from its supported Helm content;
- Strimzi owns Kafka lifecycle;
- other services are added through mature existing operators/providers when justified.

Codex must **not** build replacement database operators, DB backup/PITR engines, DB failover engines, Kafka operators, Harbor controllers or OpenBao controllers.

For current V1, upstream application UI rebranding is **not a Codex requirement** unless the product owner explicitly assigns that task. LayerSentry owns catalog/navigation/access/policy/compatibility/status integration and preserves required legal attribution.

Application-specific certification still tests the upstream lifecycle (for example backup/PITR, HA/failover, upgrade and data integrity), but that is validation/integration rather than a reason to recreate upstream code.

## 9. One V1 signed release carrier

For current V1 execution, use one logical signed platform carrier:

```text
layersentry-platform-<release>.iso
```

It may contain:

- RKE2/CAPI/CAPC/CAPRKE2;
- QCOW2 images;
- CNI/CCM/CSI;
- Flux;
- OpenEverest and required database operators/images;
- OpenBao;
- Harbor;
- Strimzi/Kafka;
- approved security/observability/backup packages;
- RPM/DEB/local registry content;
- compatibility metadata, checksums, signatures, SBOM and provenance.

Bundled artifacts are `AVAILABLE`, not automatically installed. Flux installs only selected packages. No ISO or cluster reinstall is required to add an already-bundled package unless host/kernel capability must change.

This V1 packaging decision supersedes the earlier conceptual two-carrier split in the Kubernetes specialist context for current execution. Logical platform and Data Services catalog sections may remain separate inside the same signed carrier.

## 10. VM-native DBaaS/APaaS: Go + Ansible

Architecture:

```text
LayerSentry UI/API
 -> Go orchestration/control
 -> Ansible Runner / ansible-core
 -> versioned roles/playbooks
 -> Rocky Linux 9 guest
```

Go owns authorization, validation, immutable planning, idempotency/locking, durable state/journal, secret references, Ansible invocation/result handling, evidence and recovery state.

Ansible owns repositories/packages, services, users/files, SELinux, firewalld, LVM/filesystems/mounts, networking/VIP and provider configuration.

Shell scripts are not an approved product installation/configuration lifecycle. Existing shell lifecycle assets are deprecated and must not be extended. In Ansible, use dedicated modules; `shell`/`raw` are exceptional.

## 11. Hypervisor/bootstrap/control-plane HA

ChatGPT owns the one-time bootstrap and Ansible-driven hypervisor/control-plane lifecycle unless explicitly reassigned.

The bootstrap server is temporary. Production must operate after it is removed. The target HA profile uses 3 Management VMs, 3 DB VMs and redundant LB/VIP nodes or a certified external ADC, distributed across real failure domains and tested independently of the bootstrap server.

## 12. DC/DR/DRaaS: native first

Current V1 order:

```text
healthy DC/DR CloudStack
 -> supported native Backup & Recovery
 -> two real recovery points
 -> selected old/latest createVMFromBackup recovery
 -> isolated destination network
 -> exact root/data guest validation
 -> thin LayerSentry recovery UI/orchestration
 -> one provider-native low-RPO path if needed
 -> planned failover/failback
 -> witness/fencing/automatic failover last
```

Do not build a generic LayerSentry block-copy/replication data plane where CloudStack or the storage provider already exposes the required mechanism.

## 13. Research and change-control rule

Research deeply when an exact version/provider decision is open, a hard blocker appears, or security/data safety may invalidate the design. Do not repeatedly research frozen decisions before every implementation step.

For each E2E failure:

1. capture exact evidence;
2. identify owner layer;
3. fix the smallest correct owner;
4. add regression coverage;
5. build/redeploy the exact affected artifact;
6. rerun the same step.

Do not redesign architecture because of a fixable integration bug.

## 14. Evidence rules

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

Source is not deployment proof. Build success is not runtime proof. Documentation support is not exact combination proof. Live claims require exact source/artifact, target and assertions.

## 15. Credit/token optimization

- Codex: UI completion + Kubernetes/RKE2 E2E only;
- ChatGPT: Single-OS/Ansible, bootstrap/HA, native DR and context maintenance;
- one UI Codex stream and one K8s Codex stream may run only with clean file ownership;
- do not run multiple overlapping K8s Codex agents;
- do not rebuild upstream applications that already supply the required lifecycle;
- do not create separate cluster engines for DBaaS/APaaS/Streaming;
- do not create repetitive large handoffs;
- spend Codex effort on the first failing live gate.

## 16. Conflict rule

This contract supersedes older **execution-routing, V1 package-carrier and implementation-sequencing** instructions where they conflict.

In particular:

- UI is now Codex-owned for finishing/optimization;
- current V1 uses one unified signed platform release carrier;
- OpenEverest/OpenBao/Harbor/Strimzi are upstream integration/qualification targets, not LayerSentry rewrite projects;
- the same RKE2 lifecycle serves user K8s and service profiles.

Detailed specialist storage/network/security/data-safety architecture remains valid unless explicitly changed here.