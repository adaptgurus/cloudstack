# LayerSentry V1 — Control-Plane HA, XaaS and Future-Upgrade Policy

## Purpose

Stable architecture policy for three related decisions that must remain explicit as LayerSentry matures:

1. how the LayerSentry/CloudStack control plane is virtualized and survives failures without dedicated physical Management/DB servers;
2. when Apache CloudStack XaaS/Extensions should and should not be used;
3. how the LayerSentry overlay remains practical to carry from the current CloudStack 4.22.1.1 LTS baseline to future upstream releases.

This file contains design/acceptance policy only. Current deployment state and certification evidence remain in `LAYERSENTRY_PROGRESS_LEDGER.md`.

---

## 1. Core decision

The LayerSentry primary architecture remains:

```text
LayerSentry UI/product profile
        -> LayerSentry services/controllers only where needed
        -> supported CloudStack APIs/contracts
        -> native CloudStack KVM/network/storage/RBAC/async-job semantics
        -> KVM/libvirt
```

Do not replace native CloudStack KVM orchestration with XaaS merely to move LayerSentry code outside CloudStack.

Use XaaS selectively for genuinely external systems or lifecycle extension points after verifying that native CloudStack APIs/plugins do not already provide the required semantics.

This decision minimizes lost functionality, fork debt and future upgrade risk.

---

## 2. XaaS decision rule

CloudStack XaaS/Extensions is useful when CloudStack must delegate work to an external executable/orchestrator, external network system or other service that is not natively managed by the selected CloudStack KVM path.

### Good XaaS candidates

Examples, subject to release-specific capability validation:

- external hypervisor/orchestrator integrations;
- external SDN/network lifecycle integrations where the upstream framework supports the required hooks;
- narrowly scoped custom actions that truly require CloudStack lifecycle invocation;
- external systems whose resource lifecycle lives outside native CloudStack.

### Do not use XaaS for the LayerSentry native-KVM core

Do not implement the main LayerSentry KVM VM lifecycle through XaaS when native CloudStack already supplies:

- KVM scheduling and capacity;
- VM deploy/start/stop/reboot/delete;
- native volumes/storage lifecycle;
- native network/NIC semantics;
- affinity/placement behavior;
- migration/live migration;
- user-data/metadata;
- RBAC/account/domain semantics;
- asynchronous jobs and resource state;
- native CKS/Object Storage/B&R APIs where selected.

The 4.22.1 Extensions Framework has framework-level limitations for important VM/cloud semantics, and extension executables must be present consistently across Management Servers. Built-in extension compatibility may also evolve across releases. Therefore XaaS is an extension boundary, not the foundation of LayerSentry's native KVM control plane.

### XaaS packaging rule

Any LayerSentry XaaS extension that is eventually certified must:

- be a versioned signed LayerSentry artifact;
- be installed identically on every Management Server that can execute it;
- carry an explicit input/output schema version;
- have timeout, idempotency and error semantics;
- redact secrets from payload/log output;
- fail closed on integrity/compatibility mismatch;
- expose readiness/health truthfully;
- be included in N-1 -> N upgrade/regression testing;
- have a removal/replacement plan if upstream later makes it unnecessary.

---

## 3. Virtualized control-plane decision

LayerSentry does **not** require dedicated physical servers solely for the Management Server or database roles.

The target may use virtual machines for:

- 3 LayerSentry/CloudStack Management Servers;
- 3 database nodes in the selected LayerSentry-certified topology;
- 2 load-balancer/VIP nodes when an external ADC is not used.

Virtualization does not remove failure-domain requirements. `3 Management VMs + 3 DB VMs` is not itself an HA guarantee.

### Minimum production placement contract

For a three-failure-domain local HA profile, place roles so loss of any one physical compute host/failure domain still leaves:

- at least 2 Management Servers;
- at least 2 members/quorum participants of a 3-node DB topology;
- at least 1 load-balancer/VIP node;
- sufficient CPU/RAM/storage/network capacity to keep the remaining control plane operational.

A preferred three-host placement pattern when all roles are virtualized is conceptually:

```text
Failure Domain A       Failure Domain B       Failure Domain C
----------------       ----------------       ----------------
MGMT-1                 MGMT-2                 MGMT-3
DB-1                   DB-2                   DB-3
LB-1                   LB-2                   reserved capacity
```

The exact physical placement may differ, but equivalent anti-affinity/failure-domain properties are mandatory.

Do not place two DB quorum members in the same failure domain if that makes a single host/rack/storage failure remove DB quorum.

Do not place both LB nodes in one failure domain.

Reserve enough control-plane capacity that tenant workload pressure cannot starve Management/DB/LB VMs.

---

## 4. Availability claim envelope

Never claim "all worst-case scenarios" without defining the failure set.

A production profile must publish and test a failure envelope.

### Expected single-failure goals for the 3-MGMT / 3-DB / 2-LB profile

Subject to exact release/topology certification:

- loss/reboot of one Management VM: management endpoint remains available through surviving Management Servers;
- loss of one LB VM: VIP/service remains available through the surviving LB/ADC path;
- loss of one DB VM: DB service remains available if the selected 3-node topology retains quorum/primary service;
- loss of one physical KVM host/failure domain: control plane remains available if role anti-affinity and N+1 capacity requirements are satisfied;
- loss of one NIC/path/switch/controller: service remains available only if that layer has independently tested redundancy.

### Failures that a 3-node DB topology cannot automatically guarantee

A 3-member quorum topology normally tolerates one member/failure-domain loss. It must not be advertised as tolerating arbitrary simultaneous loss of two DB failure domains.

If the contractual requirement is to retain DB quorum after any two independent DB/failure-domain losses, evaluate a larger quorum design (for example five data-bearing members) and certify the resulting latency/operational behavior. Do not pretend three nodes can mathematically provide two-failure quorum tolerance.

### Site/common-mode failures

Local HA does not by itself survive:

- complete site/power loss;
- loss of a single non-redundant storage array holding all control-plane disks;
- loss of a single non-redundant management network/fabric;
- logical DB corruption replicated to all DB nodes;
- operator/security compromise affecting all replicas;
- simultaneous loss exceeding the certified quorum/capacity envelope.

Those require separate controls such as redundant fabrics/storage, backups/PITR, security isolation and a DR site.

---

## 5. Physical failure-domain contract

"No dedicated physical Management/DB server" is acceptable only when the underlying platform supplies real redundancy.

Production certification must describe at least:

- physical KVM host count;
- rack/power failure domains where applicable;
- NIC bonding and redundant switch/fabric design;
- management network failure domains;
- storage controller/path/fabric redundancy;
- whether control-plane VM disks rely on one shared storage system;
- N+1 compute capacity after one host/failure-domain loss;
- anti-affinity/placement enforcement for MGMT/DB/LB roles;
- OOBM/recovery access to physical hosts.

A collection of VMs on one physical host, one storage array or one switch is not highly available merely because the VM count is greater than one.

---

## 6. Self-hosted control-plane recovery contract

If Management/DB/LB VMs run on the same physical KVM estate that LayerSentry manages, avoid a circular-recovery dependency.

The product must have a recovery path that does not require a healthy CloudStack API merely to bring the CloudStack control plane back.

At minimum design and test:

- deterministic VM definitions/inventory for control-plane VMs;
- host boot/autostart behavior appropriate to the selected design;
- service dependency/start order (DB endpoint/quorum -> Management Servers -> LB/VIP admission);
- out-of-band physical-host access;
- a rescue/bootstrap workflow that can inspect/start/recover control-plane VMs without depending on the normal LayerSentry UI/API;
- backup/recovery of DB, configuration, release manifest and certificates/keys;
- behavior when all Management Servers are unavailable while guest workloads continue running;
- recovery after one host containing a control-plane VM is permanently lost.

Do not rely solely on CloudStack guest-VM HA to resurrect the CloudStack Management plane if the Management plane required to coordinate that HA is itself unavailable.

---

## 7. Database topology certification gate

CloudStack documentation exposes DB HA/replica connector options, but historical validation/operational limitations mean LayerSentry must certify the exact modern topology rather than merely copy an old example.

For the three DB VMs, evaluate a modern MySQL 8.4-compatible single-writer/quorum design and a stable connection endpoint. Candidate designs may include a three-node MySQL single-primary Group Replication/InnoDB Cluster style topology with redundant/local routing, but this is a candidate until tested against the exact CloudStack release.

Before selecting the certified DB topology, test at minimum:

- CloudStack schema creation/upgrade;
- transaction behavior and connection pooling;
- source/primary failure during reads and writes;
- management-server reconnect behavior;
- failover and failback;
- split-brain/quorum loss behavior;
- network partition;
- one DB VM reboot;
- full cluster restart;
- backup and point-in-time recovery;
- binlog/redo/storage capacity management;
- monitoring and alerting;
- upgrade sequencing with all Management Servers;
- latency under expected load.

Use single-writer semantics unless a multi-writer design is explicitly proven safe for the exact CloudStack workload. DB HA replicates availability; it does not replace backup or protect against logical corruption.

---

## 8. Load-balancer/VIP contract

When no external enterprise ADC is available, the LayerSentry-certified virtual LB design must remove a single LB VM as a single point of failure.

A typical candidate is two LB VMs using an HA VIP/failover mechanism and health-checked backends. Exact software is an implementation choice, not a claim in this policy.

Validate:

- API/UI traffic;
- required Management Server agent/System-VM connectivity ports;
- persistence/stickiness where CloudStack requires it;
- LB node failure/reboot;
- backend Management Server failure;
- certificate lifecycle;
- VIP failover timing;
- split-brain prevention;
- restart/upgrade behavior.

The two LB VMs must occupy separate physical failure domains for the certified HA profile.

---

## 9. CloudStack future-version policy

Current product baseline remains the current LTS `4.22.1.1` until LayerSentry deliberately certifies another upstream release.

Do not move production baseline merely because a newer regular release exists.

### Version-numbering compatibility

Apache CloudStack has announced that the release that would historically have been called `4.24` will instead use the new version line `24`, with full version `24.0.0`. LayerSentry must therefore not assume all future CloudStack versions begin with `4.` or contain four numeric components.

Version handling in installers, manifests, CI, package selection, compatibility checks, monitoring and upgrade tooling must:

- treat the upstream version as a validated semantic/version string rather than a fixed `4.x.x.x` regex;
- support the current four-component legacy form such as `4.22.1.1` and the announced three-component form such as `24.0.0`;
- never infer release support solely from numeric comparison;
- consult an explicit LayerSentry compatibility matrix/manifest;
- use exact upstream tags/branches/package metadata appropriate to the target release.

### Upgrade-path rule

Do not assume a direct `4.22.1.1 -> 24.0.0` production upgrade is supported until the official 24 release documentation and LayerSentry staging tests establish the supported path.

For every future target:

1. read the exact upstream release notes/upgrade documentation;
2. compare API/schema/plugin/extension changes;
3. regenerate the upstream delta;
4. reapply only the minimum LayerSentry overlay;
5. remove LayerSentry code made obsolete by new upstream features;
6. rebuild signed artifacts/SBOM/provenance;
7. run fresh-install and supported N-1 -> N/interruption/rollback-recovery tests;
8. run role/KVM/network/storage/CKS/B&R/DR/security regression appropriate to the certified profile;
9. promote only after release-specific evidence.

---

## 10. Upstream-first adoption rule

At every CloudStack feature/LTS upgrade, explicitly inspect new upstream capabilities before carrying forward LayerSentry-specific implementation.

Examples of features that may reduce future LayerSentry custom work include new native KVM storage/data-protection, network-extension, KMS/security and backup capabilities.

Decision for each LayerSentry delta:

- keep because upstream still lacks the requirement;
- simplify because upstream now supplies part of it;
- replace with supported upstream behavior;
- remove because upstream made it unnecessary.

The objective is for the LayerSentry delta to shrink or remain bounded over time, not accumulate indefinitely.

---

## 11. Certification evidence for control-plane HA

Before claiming the VM-based production control plane `PRODUCTION_CERTIFIED`, execute and retain evidence for the exact topology at minimum:

- one Management VM stop/reboot/failure;
- one DB VM stop/reboot/failure;
- one LB VM stop/reboot/failure;
- one physical KVM host/failure-domain loss;
- management/backend network path failure where redundancy is claimed;
- one storage path/controller failure where redundancy is claimed;
- DB primary/single-writer loss and automatic recovery;
- DB quorum-loss behavior (must fail safely, not split brain);
- Management Server reconnect to DB after failover;
- all-Management-Server outage and independent control-plane recovery procedure;
- full control-plane cold restart in documented order;
- control-plane VM placement verification;
- capacity verification after a failure domain is removed;
- backup/restore/PITR proof for the DB;
- upgrade and rollback/recovery sequence on the VM-based control plane;
- meaningful soak and concurrent API/async-job testing.

State the exact failure envelope in customer documentation. Do not use "always available" or "survives all worst cases" as an unqualified technical claim.

---

## 12. Current architecture recommendation

For LayerSentry V1:

1. keep native CloudStack KVM as the primary orchestration engine;
2. keep the LayerSentry product/UI/controller overlay small and API-driven;
3. use XaaS selectively, not as a replacement for native KVM;
4. virtualize Management, DB and LB roles if desired, but spread them across independent physical failure domains with reserved capacity;
5. certify a modern three-node DB topology before shipping it;
6. build a control-plane recovery path independent of the normal CloudStack API;
7. remain on the current LTS baseline until a newer target is deliberately certified;
8. make all version tooling compatible with the announced `24.0.0` naming scheme;
9. define exact failure tolerance instead of promising arbitrary worst-case survival;
10. use a second site/DR design for site-level failures rather than expecting local HA to solve them.
