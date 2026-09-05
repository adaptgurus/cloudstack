# LayerSentry V1 UI Experience Specification

**Status:** `DESIGN_DEFINED`  
**Baseline:** Apache CloudStack 4.22.1.1, KVM-only customer profile  
**Scope:** every authenticated customer page, generated action, detail view and authentication state

## Product direction

LayerSentry is a task-oriented private-cloud product, not a renamed CloudStack menu. CloudStack remains authoritative for CloudStack APIs, permissions, resources and asynchronous jobs. The UI changes information architecture, terminology, presentation, progressive disclosure and workflow composition only.

LayerSentry-managed Kubernetes, DBaaS, APaaS and Streaming are valid product modules. Their lifecycle/storage/network/package semantics are governed by `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`; this UI specification governs their customer-facing quality and consistency without moving their control logic into browser code.

The experience uses one visual system: navy application chrome, teal interaction color, neutral operational surfaces, readable semantic status colors, 6/10px radii and visible keyboard focus. All pages share the same anatomy:

1. page identity and contextual scope;
2. primary task and permission-safe secondary actions;
3. persistent loading, empty, unavailable, error or partial state;
4. filters and inventory or guided form;
5. detail tabs with state, relationships and activity;
6. asynchronous/controller operation feedback with reconciliation and retry guidance.

No page may label a resource healthy, protected, encrypted, HA-capable, CSI-ready, WAF-protected or DR-ready without a real supporting signal.

## Functional-preservation invariant

LayerSentry branding must not remove, disable, rename at the API boundary or
change the payload of an existing authorized CloudStack operation. UI work may
change layout, grouping, customer-facing wording, iconography and progressive
disclosure while preserving:

- every API-backed action available to the current role and resource state;
- the original action object, API name, parameters and asynchronous-job flow;
- authorized list, detail and deep-link routes;
- configured storage, network, backup, Kubernetes and extension integrations;
- advanced native workflows required by Platform/Support roles.

Controls may be absent from the current rendered context only when CloudStack
authorization denies the API, the existing resource-state predicate makes the
action invalid, an optional feature/provider is not configured and usable, or
the KVM-only customer profile excludes a non-KVM choice. These conditions are
presentation gates, not permission to delete or degrade the existing GUI route,
component, action definition or integration. If the upstream GUI implements the
workflow, it must remain functional when its original supported eligibility
conditions are satisfied (including outside the KVM-focused customer profile).
Presentation hiding is never authorization, and LayerSentry must not introduce a
new denial where CloudStack authorizes an otherwise valid operation.

LayerSentry-specific K8s/DBaaS/APaaS/Streaming actions additionally require the dedicated server-side module authorization and capability checks. Browser visibility never substitutes for those checks.

Shared action icons are derived from the existing API verb without mutating or
filtering the action: create/add/deploy, start, stop, restart, edit, migrate,
attach, detach, restore and delete actions use consistent semantic icons.
Destructive styling is based on the destructive API verb and does not alter the
underlying confirmation or execution behavior.

Every UI slice must test action-count/identity preservation, emitted action/API
identity, authorized deep links and representative integration workflows in
addition to visual and accessibility assertions.

## Persona navigation

| Persona | Primary navigation | Advanced access |
|---|---|---|
| Platform Administrator | Dashboard, Quick Provision, Compute, Storage, Network, Images, Kubernetes, Data Services, APaaS/Streaming, Object Storage, Infrastructure, Backup & DR, Activity, Administration, Support when modules are enabled | Physical infrastructure, providers, offerings and configuration remain permission-gated |
| Department Administrator | Dashboard, Quick Provision, Virtual Machines, Volumes, Networks & VPCs, Images, Kubernetes, permitted DBaaS/APaaS/Streaming, Buckets, Backup & Recovery, Activity, Department | No physical infrastructure internals |
| Operator / User | Dashboard, Quick Provision, Virtual Machines, Volumes, Networks, Kubernetes, permitted managed services, Buckets, Recovery Points, Activity | Only owned/delegated actions and resources |
| Read-only / Auditor | Dashboard, Inventory, Protection, Activity and authorized managed-service inventory | No mutation controls; authorized deep links remain readable |

Navigation grouping never grants permission. CloudStack API authorization remains the security boundary for CloudStack resources, LayerSentry service authorization applies to module-specific actions, and every hidden mutation requires direct-route and direct-API negative tests.

## Page and section contract

### Entry and common shell

- `/user/login`, password recovery/reset, 2FA and OAuth verification: LayerSentry identity, clear server/domain context, accessible validation, no upstream promotional content.
- `/dashboard`: persona-specific operational summary, exceptions first, truthful capacity/protection state, recent failed jobs and next actions.
- `/quick-provision`: one-page VM Ownership & Site, Compute, Storage, Network, Availability & Protection, Review/Preflight and Deploy workflow.
- `/403`, `/404`, `/500` and `/exception/*`: LayerSentry language, safe recovery action, correlation information where available and no sensitive diagnostics.
- optional `/plugins/*` and `/apidocs`: Platform/Support-only placement when configured and authorized.

### Compute

- `/vm`: Virtual Machines inventory with state, Site, owner, Compute Profile, primary address and protection summary; fast operate/protect/recover tasks.
- VM detail: overview, compute, volumes, networks, metrics, snapshots, backups, activity and advanced diagnostics as supported.
- `/vmsnapshot`, `/vmgroup`, `/affinitygroup`, `/ssh`, `/userdata`: task-focused supporting resources with snapshot-conflict warnings and explicit ownership.
- `/autoscalevmgroup`: capacity-policy language and async activity; provider prerequisites shown before mutation.
- `/kubernetes`: Kubernetes product area. Native CKS remains distinguishable from LayerSentry-managed RKE2; KVM is implicit and each lifecycle path keeps its own backend semantics.
- `/cniconfiguration`: Platform Administrator-only native Kubernetes networking configuration where applicable.

All VM lifecycle `/action/*` routes use the same guided action shell, impact summary, validation and async progress. Quick Provision is the default customer VM deployment path; the advanced native deployment route remains available to privileged operators.

### LayerSentry K8s / Data Services / APaaS / Streaming

These are service-oriented UI modules rather than additions to the raw VM form.

Normal design requirements:

- LayerSentry K8s cluster create/scale/storage/package/network/upgrade workflows are GUI-only and backed by the CAPI/RKE2 specialist architecture;
- DBaaS engine selection, HA, compute, storage, backup/PITR, maintenance and connectivity are expressed as managed-service intent, not Helm/CRD/YAML fields;
- APaaS exposes certified OpenBao/Harbor-style services only when their package/provider dependencies are real;
- Streaming exposes Strimzi/Kafka intent with protocol-correct endpoint/VIP requirements;
- storage selectors distinguish node disks, Kubernetes block CSI, shared NFS/RWX and OEM profiles;
- exposure selectors distinguish private endpoint, L4 NLB, L7 ALB/Gateway and L7+WAF/hardware ADC profiles;
- package catalogs distinguish `AVAILABLE`, `ENABLED` and `READY` and allow later installation without reinstalling the base ISO;
- every page shows compatibility/preflight blockers before mutation and controller reconciliation after submit.

Do not invent a route or mark a module visible simply because the design exists. Exact routes are implementation details and appear only when backend feature policy, RBAC and prerequisites are implemented.

### Storage and protection

- `/volume`: Volumes inventory using Storage Profile terminology with attachment, Site and state context.
- `/snapshot`, `/snapshotpolicy`: Recovery Points and schedules where the underlying resource semantics permit; do not conflate volume snapshots with VM backups.
- `/backup`, `/backupschedule`, `/backupoffering`: Backup & Recovery inventory, schedules and administrator offerings. Provider unavailable and not-configured are distinct states.
- `/sharedfs`: Shared File Systems with Site, capacity, access and attachment context.
- `/buckets`: Object Storage / Buckets only when permission, provider and usable configuration gates pass.
- `/storagepool`, `/imagestore`, `/backuprepository`, `/objectstore`: Platform infrastructure/provider pages; never expose raw provider credentials.
- `/diskoffering`: VM Storage Profiles, retaining CloudStack Disk Offering semantics underneath.

Kubernetes StorageProfiles/StorageClasses are distinct from CloudStack Disk Offerings and use the dedicated module semantics. Do not globally reuse VM labels in a way that implies unsupported Kubernetes behavior.

### Network

- `/guestnetwork`: Workload Networks with Network Blueprint, Site, CIDR and service capability summaries.
- `/vpc`, `/acllist`, `/privategw`, `/ilb`: application-network groupings and tier relationships.
- `/publicip`, firewall, port-forwarding and load-balancing tabs/actions: visible only when the selected offering supplies the service.
- `/securitygroups`: workload security rules with readable direction/source/protocol summaries.
- `/s2svpn`, `/s2svpnconn`, `/vpnuser`, `/vpncustomergateway`: Connectivity section with endpoint and tunnel state.
- `/asnumbers`, `/ipv4subnets`, `/guestvlans`, `/physicalnetwork`, `/nsp`: Platform Administrator datacenter-network pages with prerequisite-aware empty states.
- `/vnfapp`, `/tungstenfabric`, `/tungstenpolicy*`: optional provider pages shown only with real configuration and permission.
- `/networkoffering`, `/vpcoffering`: Network Blueprints/advanced offerings presentation while preserving backend names in diagnostics.

Kubernetes Frontend/VIP/Gateway/WAF views may reuse network/IP presentation components but follow the dedicated module ownership model: CloudStack L4/IPAM where selected, Gateway API for L7, vendor controller for hardware WAF/ADC.

### Images and profiles

- `/template`: OS Images; rendered normal-customer selectors and filters are KVM-only.
- `/iso`: Installation Media; `None` remains valid where CloudStack uses it for ISO compatibility, without presenting another hypervisor choice.
- `/kubernetesiso`: native Kubernetes Node Images where the upstream CloudStack route applies.
- LayerSentry-managed RKE2 uses versioned QCOW2 node templates plus signed offline release/catalog artifacts according to the specialist context; do not conflate that with native CKS binaries ISO semantics.
- `/computeoffering`: Compute Profiles.
- `/systemoffering`: System VM Profiles, Platform Administrator-only.

Registration and copy actions must validate KVM compatibility and must not leak non-KVM selectors in the LayerSentry customer profile.

### Infrastructure

- `/infrasummary`: Platform Operations dashboard with Sites, KVM hosts, management nodes, storage/network providers, alerts and capacity.
- `/zone`, `/pod`, `/cluster`, `/host`: Sites, Infrastructure Groups, Compute Clusters and KVM Hosts. Backend names remain unchanged.
- `/systemvm`, `/router`, `/ilbvm`: Platform Services inventory with role, state, Site/host and recovery actions.
- `/managementserver`: Management Nodes with heartbeat/version/state; topology alone never implies HA.
- `/metric`, `/alert`, `/cpusocket`, `/gpudevices`: operational diagnostics and capacity/licensing views.
- `/zones`: tenant-visible eligible Sites, distinct from Platform infrastructure administration.

Onboarding follows Site → Infrastructure Group → Compute Cluster → KVM Host → storage/network readiness, with a persistent readiness checklist and supported API semantics.

### Identity, collaboration and administration

- `/domain`: Departments; `/account`: Teams/Accounts; `/accountuser`: users. Help text explains that users inside one Account are not isolated resource owners.
- `/project`: Projects and membership with scoped resource usage.
- `/role`: roles and API rules; UI visibility is never described as authorization.
- `/event`, `/alert`, `/webhookdeliveries`: Activity & Alerts with severity, actor, target, time and correlation/job context.
- `/usage`, `/quotasummary`, `/quotatariff`, `/quotaemailtemplate`: Consumption & Quota, shown only where the plugin/APIs are configured.
- `/globalsetting`, `/ldapsetting`, `/oauthsetting`: Platform configuration with change impact and sensitive-value handling.
- `/guestoscategory`, `/guestos`, `/guestoshypervisormapping`, `/hypervisorcapability`, `/gpucard`, `/vgpuprofile`: advanced Support/Platform configuration; non-KVM data is excluded from normal customer presentation but preserved in CloudStack.
- `/extension`, `/customaction`, `/comment`, `/webhook`: integrations and automation with explicit trust boundaries.
- `/manageinstances`, `/managevolumes`: advanced import/unmanage tools, never normal self-service navigation.
- `/cloudian`: optional provider entry only when configured and usable.

## Shared state patterns

Every list, card, form and detail page distinguishes:

- `loading`: skeleton/progress with an accessible label;
- `empty`: explains what belongs here and offers an authorized next action;
- `unavailable`: missing provider, configuration, compatibility or prerequisite;
- `forbidden`: permission boundary without revealing foreign objects;
- `error`: persistent inline summary, safe detail and retry;
- `partial`: completed infrastructure/controller step plus failed post-step and reconciliation path;
- `complete`: confirmed API/job/controller result, never inferred from a click or HTTP shell response.

All rendered state and exclusion surfaces—including forbidden routes, invalid
resource-state actions, missing or unusable providers, unsupported profile
choices, validation failures and global exception pages—use the LayerSentry
name, visual system and customer terminology. They must retain safe upstream
CloudStack/provider error codes/messages, request or job identifiers and diagnostic
detail needed for troubleshooting; no exclusion may fall back to customer-
visible Apache CloudStack/upstream-product branding or conceal the actual failure cause.

## Responsive and accessibility contract

- Current Chrome and Firefox, desktop and tablet widths; mobile supports urgent operational tasks while wide tables scroll within their region.
- Keyboard navigation, visible focus with at least 3:1 non-text contrast, explicit accessible names on icon buttons, associated form errors and logical headings.
- Status never relies on color alone. Reduced-motion preferences are honored. Dialogs/drawers trap focus, close with Escape where safe and restore focus.
- Long resource names, IDs, translated strings and 200% zoom must not hide primary actions or status.

## Delivery slices and acceptance

1. Foundation: unified tokens, shell, page/action/status/state primitives and pinned CI builder.
2. Core self-service: dashboards, VM list/detail and corrected Quick Provision.
3. Storage, network, images and native Kubernetes surfaces.
4. Platform infrastructure, identity, administration and support.
5. Real provider-gated Object Storage and Backup & DR experiences.
6. LayerSentry-managed K8s/Data Services/APaaS/Streaming surfaces coordinated with Workstream E and its specialist architecture.
7. Four-persona direct-route/API tests, rendered KVM/terminology audit, Chrome/Firefox Rocky deployment and regression.

Each slice is `SOURCE_COMPLETE` only after source tests/build pass and `LIVE_VERIFIED` only after the exact artifact is deployed and exercised through the governed Rocky Linux 9 runner path. This document does not itself promote any runtime capability.
