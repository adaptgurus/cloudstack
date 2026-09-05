# LayerSentry V1 — Unified Provisioning, UI, Runner Validation and DR Policy

## Purpose

This policy defines the validated LayerSentry direction for four connected product requirements:

1. a fully KVM-only customer-facing product experience;
2. a polished role-aware LayerSentry UI including a fast one-page VM provisioning experience;
3. mandatory `adaptgurus/cozystack` runner validation for every merge-candidate UI/feature change and every completed development module;
4. provider-neutral DR provisioning with automatic Site/network/VLAN/IP/storage mapping while preserving Apache CloudStack 4.22.1.1 as the infrastructure authority.

This is a stable architecture and acceptance contract. It does not by itself promote any runtime capability above its evidence-backed status in `LAYERSENTRY_PROGRESS_LEDGER.md`.

LayerSentry-managed RKE2/Kubernetes, DBaaS, APaaS, Streaming and their Kubernetes-specific package/storage/VIP/Gateway/WAF workflows are valid product modules and are governed in detail by `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`. This policy continues to govern the shared UI quality, KVM-only profile, VM Quick Provision and DR concepts; it does not override the specialist Kubernetes/Data Services lifecycle contract.

## Validated architecture decision

LayerSentry remains an overlay around Apache CloudStack 4.22.1.1 rather than a replacement scheduler or a large CloudStack-core fork.

```text
LayerSentry role-aware UI / Quick Provision SPA
                    |
                    v
       LayerSentry thin orchestration services
       only for multi-step/external operations
                    |
          supported CloudStack APIs
                    |
                    v
          Apache CloudStack 4.22.1.1
                    |
                    v
             native KVM/libvirt
                    |
         certified network/storage paths
```

CloudStack remains authoritative for VM lifecycle, async jobs, scheduling, accounts/domains/projects, KVM hosts, volumes, storage pools, networks, VPCs, VLAN allocation, IP allocation, HA semantics and native B&R operations.

LayerSentry may add an idempotent thin controller when a customer workflow spans multiple native API calls or an external system such as enterprise DNS/IPAM, storage-native replication or DR fencing. That controller must not become a second VM scheduler, quota system, RBAC database or storage allocator.

For LayerSentry-managed RKE2, the specialist context selects CAPI/CAPC/CAPRKE2 after exact qualification rather than extending this VM orchestrator into a second Kubernetes lifecycle engine.

## KVM-only customer contract

All normal LayerSentry customer-facing surfaces use KVM only.

This applies to:

- login/onboarding;
- Platform Administrator UI;
- Department Administrator UI;
- Department Operator/User UI;
- read-only/auditor UI;
- VM/image/ISO/host/cluster/storage/network wizards;
- Kubernetes/Data Services workflows;
- filters, search facets and selectors;
- help text, tooltips, empty/error states and validation messages;
- dashboards, cards and reports intended for customers;
- Quick Provision and recovery workflows.

Do not show VMware, XenServer/XCP-ng, Hyper-V, Proxmox, MaaS or other upstream hypervisor names as choices or normal product terminology in the LayerSentry customer profile.

Do not delete those upstream implementations from CloudStack source. They remain upstream compatibility code so future CloudStack upgrades/rebases stay bounded. Explicit low-level Support/engineering diagnostics may expose raw upstream data only when necessary for troubleshooting and clearly outside normal customer navigation.

Every customer-facing UI release must include a rendered-DOM/navigation regression audit for non-KVM hypervisor leakage. Do not fail merely because preserved upstream source bundles contain non-KVM strings that are never rendered to LayerSentry users.

## Role-aware polished UI contract

LayerSentry is a product experience, not a reskinned CloudStack menu tree.

### Platform Administrator

Primary areas may include when enabled/certified:

- Dashboard;
- Quick Provision;
- Compute;
- Storage;
- Network;
- Images;
- Kubernetes;
- Data Services / DBaaS;
- APaaS / Streaming;
- Object Storage;
- Infrastructure;
- Backup & DR;
- Activity/Alerts;
- Administration/Support.

Dashboard content must prioritize actionable KVM host health, VM state, capacity, storage/network/provider state, protection state, alerts and failed jobs rather than generic internal counters.

### Department Administrator

Primary areas may include when delegated/enabled:

- Dashboard;
- Quick Provision;
- Virtual Machines;
- Volumes;
- Networks/VPCs delegated to the department;
- Kubernetes;
- DBaaS/APaaS/Streaming services permitted to the department;
- Buckets;
- Backup/Recovery;
- Activity.

### User / Operator

Expose only owned/delegated actions and resources. Optimize for deploy, operate, attach, protect, recover and view activity rather than infrastructure internals.

### Read-only / Auditor

Provide safe inventory, state, capacity where authorized, activity, protection/recovery status and diagnostics without mutation controls.

### Visual quality

Every major entity/action uses a relevant consistent icon from the selected UI icon system. Do not mix arbitrary icon styles or use decorative icons that obscure meaning.

Required quality gates:

- coherent spacing, typography and design tokens;
- responsive desktop/tablet behavior for supported browser widths;
- accessible contrast, labels, focus states and keyboard navigation;
- loading/skeleton states;
- informative empty states;
- actionable validation/error states;
- confirmation for destructive/high-impact actions;
- progress/result presentation for CloudStack async jobs and LayerSentry controller workflows;
- consistent terminology and status badges;
- no fabricated `Healthy`, `Protected`, `HA`, `DR Ready`, `Encrypted`, `CSI Ready` or `WAF Protected` state.

## Quick Provision — one-page SPA

LayerSentry adds one fast **VM provisioning** surface, tentatively named **Quick Provision**. It is a single-page application view with progressive sections and a live plan summary. Advanced native CloudStack forms remain available to privileged roles where required.

The SPA must not invent unsupported CloudStack API fields. It composes supported APIs and LayerSentry post-deploy operations.

LayerSentry K8s/DBaaS/APaaS/Streaming use separate service-oriented GUI wizards defined by the specialist module context; do not force those lifecycles into the VM Quick Provision form.

### One-page sections

1. **Ownership and Site**
   - Department/Account/Project where role permits;
   - Site;
   - optional application/environment tag/profile.

2. **Compute**
   - OS Image;
   - Compute Profile;
   - optional permitted CPU/RAM customization;
   - architecture only when the selected Site genuinely requires a choice;
   - KVM is implicit and not presented as a multi-hypervisor selector.

3. **Storage**
   - root Storage Profile/size;
   - zero or more data-volume profiles/sizes;
   - optional pre-existing attachable volumes where CloudStack permits;
   - storage capability indicators only when backed by real provider data.

4. **Network**
   - Network Blueprint or explicit permitted network/VPC selection;
   - VPC/tier where applicable;
   - primary and additional VM networks;
   - private IP strategy when supported;
   - public IP/firewall/LB controls only when the selected Network Offering supplies those services;
   - DNS mode/suffix and optional enterprise DNS registration when a configured connector exists.

5. **Availability and Protection**
   - VM HA only when prerequisites are satisfied;
   - Backup Offering/Protection Plan only when a provider is configured and authorized;
   - optional DR Protection Plan with target Site and recovery-network summary;
   - no impossible RPO/RTO selection.

6. **Review / Preflight / Deploy**
   - resolved Site, compute, storage, network, IP/DNS, protection and estimated capability summary;
   - blocking prerequisite/conflict checks before mutation;
   - one idempotent submit action;
   - async progress with exact partial-failure reporting.

### Safe automatic defaults

The SPA may automatically choose sensible defaults but must never blindly enable every feature.

Automatic selection is allowed only after all relevant gates pass:

- role/RBAC;
- LayerSentry product policy;
- Site configuration;
- provider/backend availability;
- capacity/offerings/images;
- network/VPC prerequisites;
- storage compatibility;
- protection/DR capability;
- reliable health/readiness signal when available.

Examples of safe automation:

- select the department's default Site when only one eligible Site exists;
- select the default Network Blueprint for that department/application;
- resolve the appropriate VLAN/network through CloudStack/network policy rather than asking a normal user for a raw VLAN ID;
- allocate an IP from the permitted CloudStack/DR pool;
- select a compatible Storage Profile for the chosen workload class;
- automatically attach the selected Backup/Protection Plan after VM deployment succeeds.

The UI must show the resolved plan before deployment and allow only authorized overrides.

For K8s/Data Services wizards the same UX rule applies, but eligibility additionally includes exact CAPI/RKE2/CNI/CSI/package/VIP/Gateway/WAF compatibility and offline artifact presence from the specialist context.

## Network Blueprint model

Do not make ordinary users design physical networking in the VM wizard.

A LayerSentry **Network Blueprint** is a presentation/orchestration abstraction over existing CloudStack resources and policies. It may reference:

- Site/Zone;
- network type and Network Offering;
- existing isolated/shared/L2 network;
- VPC and tier where applicable;
- permitted guest VLAN range/policy;
- CIDR/gateway/IP pool;
- DNS suffix/resolvers where supported;
- public-network/NAT/LB/firewall capabilities;
- DR counterpart mapping.

CloudStack remains authoritative for the actual network/VPC/VLAN/IP resource lifecycle.

For VPC tiers and isolated networks, prefer configured VLAN ranges and CloudStack allocation rather than asking users to enter arbitrary physical VLAN IDs. Platform Administrators may receive a validated override when needed.

Kubernetes Frontend/VIP/Gateway/WAF presentation may reuse Network Blueprint data, but its provider/lifecycle semantics come from the specialist K8s/Data Services context.

## DNS contract

CloudStack-provided DHCP/DNS behavior and network DNS suffixes remain native where applicable.

Enterprise authoritative DNS record management is a separate optional LayerSentry connector. If implemented, it must:

- use least-privilege credentials;
- support idempotent create/update/delete/reconcile;
- validate zones/names/IPs;
- avoid SSRF and arbitrary endpoint access;
- report partial failure separately from VM/service deployment;
- never expose provider credentials to browser clients.

Failure to register an optional DNS record after a VM/service deploy must not falsely report that the underlying VM/application itself failed to deploy. The workflow must show the exact partial state and retry path.

## Storage Profile and SAN contract

Ordinary VM users choose a **Storage Profile**, not storage-array credentials, target IQNs or raw LUNs.

Platform Administrators configure/certify the underlying CloudStack storage pools and map them to LayerSentry VM Storage Profiles.

For the CloudStack 4.22.1.1 KVM baseline, supported/certified paths may include, subject to exact deployment validation:

- NFS / SharedMountPoint;
- iSCSI-backed shared storage presented through the CloudStack 4.22 KVM shared-mount/storage-pool model;
- Fibre Channel-backed shared storage through the same supported KVM shared-mount pattern where applicable;
- Ceph/RBD;
- LINSTOR;
- supported vendor storage plugins such as the exact certified SAN platform;
- local storage only for explicitly compatible non-shared use cases.

Do not make LayerSentry 4.22.1.1 depend on CloudStack 4.23-only CLVM/CLVM_NG behavior. Re-evaluate that capability when a future LayerSentry release certifies CloudStack 4.23+ or its successor.

Volume creation/placement/attachment remains through CloudStack native APIs. A VM Storage Profile can express validated policy/capabilities but is not a second storage scheduler.

Kubernetes StorageProfiles are a different abstraction and may map to CloudStack CSI, SharedFS/NFS CSI or OEM CSI according to the specialist context. Do not reuse this VM section to infer Kubernetes multi-attach or CSI semantics.

## Thin Provisioning Orchestrator / transaction model

Quick Provision may use a small LayerSentry orchestration service because one customer action can span multiple systems.

Use a durable idempotent state machine/saga such as:

```text
PRECHECK
 -> RESOLVE_BLUEPRINTS
 -> RESERVE_OPTIONAL_EXTERNAL_RESOURCES
 -> DEPLOY_VM (CloudStack async job)
 -> CREATE_ATTACH_DATA_VOLUMES when required
 -> APPLY_POST_DEPLOY_SETTINGS
 -> ASSIGN_BACKUP_PROTECTION
 -> ASSIGN_DR_PROTECTION
 -> REGISTER_OPTIONAL_DNS
 -> VERIFY
 -> COMPLETE | PARTIAL | FAILED
```

Requirements:

- client-generated/idempotency key;
- persisted operation ID and step state;
- bounded retries with async-job reconciliation;
- never repeat VM/volume/network creation blindly after timeout;
- compensation only where technically safe;
- exact partial-failure presentation;
- server-side authorization for every privileged step;
- audit trail with secret redaction.

The Kubernetes/Data Services module has its own durable CAPI/controller state-machine contract. Do not copy the VM saga blindly into that lifecycle.

## Smart DR provisioning and replica model

The LayerSentry DR UI should feel automatic, but automation must be provider-aware and evidence-backed.

### Foundation

For Backup DR, prove and reuse native CloudStack 4.22 cross-Zone creation from NAS Backup & Recovery first. Where appropriate, use Zone-local backup repositories with background synchronization so recovery reads from the closest DR-side copy.

For low-RPO Hot Replica tiers, prefer storage-native replication:

- LINSTOR/DRBD for the preferred LayerSentry HCI profile when certified;
- Ceph RBD mirroring for certified Ceph deployments;
- enterprise SAN array-native consistency-group replication for certified arrays;
- generic file-backed/NFS path using libvirt backup/checkpoint mechanisms plus CloudStack NAS B&R for baseline/retention/reseed.

Do not use `rsync` as the primary running-VM block replication engine.

### Site Pair

A Site Pair records validated source-to-recovery relationships without replacing CloudStack Sites/Zones.

It may include:

- source Site and recovery Site;
- supported storage-provider pair/capabilities;
- Recovery Repository mapping;
- network/VPC mapping set;
- IP recovery strategy/pools;
- DNS policy;
- witness/fencing capability;
- measured/certified protection tiers.

### DR Network Mapping

Maintain an explicit mapping object for each protected network class:

```text
Source Site + source Network/VPC tier
        -> Recovery Site + recovery Network/VPC tier
        -> VLAN/network policy
        -> recovery CIDR/IP pool
        -> gateway/DNS policy
```

During initial VM provisioning the Quick Provision page shows the resolved DR target for every protected NIC. Normal users see friendly network names; Platform Administrators can inspect/override validated mappings when authorized.

Do not assume that a source VLAN ID must equal the recovery VLAN ID.

### Recovery IP strategy

Support explicit policies rather than one hard-coded behavior:

1. **AUTO_FROM_DR_POOL** — preferred default; allocate a valid address from the mapped recovery network/IP pool.
2. **RESERVED_MAPPED_IP** — reserve a deterministic preselected recovery address for the protected VM.
3. **PRESERVE_SOURCE_IP** — allowed only when network architecture, routing/L2 extension and collision/fencing controls make reuse safe.
4. **ADMIN_OVERRIDE** — authorized administrator chooses an available recovery IP/network after conflict validation.

Before failover, run IP uniqueness, network reachability and mapping preflight. Never create dual writers or duplicate active IP ownership merely to preserve an address.

### Replica and Recovery Point listing

The LayerSentry UI provides one provider-neutral protected-workload inventory containing at least:

- VM;
- source Site/network/storage profile;
- Protection Plan;
- recovery Site;
- replica/provider state;
- latest durable recovery point;
- older retained points;
- last successful sync/backup time;
- measured/observed lag when the provider exposes it reliably;
- recovery network/IP resolution state;
- readiness blockers;
- Test Recovery state;
- failover/failback state.

`Hot Replica`, `Recovery Point`, `Backed up`, `Protected`, `Ready` and `DR Ready` are separate states and must not be conflated.

### Failover order

Production automation must progress in this order:

```text
native backup/recovery proof
 -> Site Pair/network mapping
 -> provider replication
 -> old-point recovery
 -> isolated Test Recovery
 -> Planned Failover
 -> reverse replication
 -> Failback
 -> witness/exclusive recovery lease/fencing
 -> emergency automatic failover
```

Automatic failover is prohibited until witness/quorum and safe source fencing/exclusivity are implemented and repeatedly tested.

Kubernetes/Data Services application/cluster DR, when implemented, integrates with the same provider-neutral DR/fencing authority and its workload-native backup/storage mechanisms; it must not create a second conflicting DR control plane.

## Cozystack runner validation contract

`adaptgurus/cozystack` is the mandatory durable live-validation path for LayerSentry runtime-affecting work unless an explicitly approved replacement is recorded.

The current historical UI deploy/audit workflows prove the runner can deploy/audit the lab, but hard-coded commit/target workflows are not a sufficient universal release gate. New validation automation must accept an exact authorized CloudStack source/artifact identity rather than silently testing an old pinned UI.

### Gate 1 — every merge-candidate UI/feature change

Before integration of a runtime-affecting UI/feature change, run the relevant fast validation set. At minimum where applicable:

- clean/pinned source build or exact immutable release artifact verification;
- lint/static/unit tests;
- feature-policy/prerequisite tests;
- KVM-only rendered navigation/selector audit;
- terminology/wrong-label audit;
- K8s/DBaaS/APaaS/Streaming visibility and wording match the current specialist module scope; no stale exclusion or fake-ready placeholder;
- affected role/RBAC/direct-route negatives;
- error/empty/loading state tests;
- changed API contract tests;
- security negatives for changed trust boundaries.

A developer may iterate locally between pushes, but a merge candidate cannot bypass this gate.

### Gate 2 — completed portion/module

When a coherent UI feature, product portion or module is declared complete, deploy the **exact commit/release artifact being claimed** through the Cozystack runner to the authorized Rocky Linux 9 acceptance target and execute end-to-end validation.

For UI modules include, as applicable:

- current Chrome and Firefox;
- Platform Administrator;
- Department Administrator;
- User/Operator;
- Read-only/Auditor;
- allowed workflows;
- forbidden/direct-URL/direct-API workflows;
- responsive/accessibility checks;
- KVM-only rendered UI audit;
- existing-functionality regression;
- browser refresh/deep-link/cache behavior;
- failure/partial-state behavior.

For storage/network/DR/backend/Kubernetes modules include the exact provider/API/controller path, idempotency/retry/negative tests and rollback/recovery evidence.

A module must not be labeled complete, `LIVE_VERIFIED` or stronger solely from source review, screenshots, HTTP 200 or one happy-path execution.

### Evidence identity

Every runner acceptance record captures:

- CloudStack source commit;
- release artifact digest when applicable;
- Cozystack runner commit;
- workflow run/job IDs;
- evidence artifact ID/digest;
- target identity/scope;
- personas/tests executed;
- mutation class;
- results and failed assertions;
- rollback/cleanup state;
- known limitations and next gate.

Do not test an artifact and then claim a later untested commit inherits the result.

## Definition of done for the base unified experience

The unified provisioning/UI/DR work is not complete until all of the following applicable gates are met:

- no customer-facing non-KVM hypervisor leakage;
- polished role-aware screens and icons for all supported personas;
- Quick Provision one-page VM flow implemented with supported CloudStack semantics;
- capability-gated safe automatic defaults;
- VM Storage Profiles backed by certified storage pools/providers including the intended SAN path;
- Network Blueprints with VPC/VLAN/IP/DNS behavior live-tested;
- multi-step VM provisioning idempotency and partial-failure handling proven;
- Protection Plan integration proven;
- native cross-Zone B&R proven before advanced DR claims;
- DR Site Pair/network/IP mapping proven;
- at least one production-intended low-RPO storage replication provider certified before offering that tier;
- old recovery point and isolated Test Recovery proven;
- Planned Failover/Failback proven before automatic failover;
- Cozystack runner gates integrated and producing durable evidence for exact commits/artifacts;
- security/RBAC/browser/upgrade/regression tests passed for the certified release;
- production release gates in the Super Master Context satisfied.

K8s/DBaaS/APaaS/Streaming have additional independent definition-of-done gates in `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`; success of this base VM/DR UI policy does not certify those modules, and their addition does not invalidate these existing gates.

## Production-readiness rule

Adding this policy or the Kubernetes/Data Services specialist context is architecture/source-governance progress only. None of the new Quick Provision, DR mapping, provider replication, universal runner gate, polished-role experience, K8s/DBaaS/APaaS/Streaming capability may be called implemented or production-ready until the corresponding code and evidence exist.
