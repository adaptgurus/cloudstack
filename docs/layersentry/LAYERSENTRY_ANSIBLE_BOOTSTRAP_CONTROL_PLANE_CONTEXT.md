# LayerSentry V1 — One-Time Ansible Bootstrap and DC Control-Plane HA Context

**Context schema:** 1.0  
**Effective date:** 2026-09-07  
**Baseline:** Apache CloudStack 4.22.1.1, Rocky Linux 9, KVM-first LayerSentry  
**Execution owner:** ChatGPT by default  
**Production configuration engine:** Ansible Runner / ansible-core  

This context defines the initial LayerSentry DC bootstrap and steady-state control-plane architecture. It extends `AGENTS.md`, `LAYERSENTRY_EXECUTION_CONTRACT.md` and `LAYERSENTRY_CONTROL_PLANE_XAAS_AND_FUTURE_UPGRADE_POLICY.md`. Repository/live evidence overrides stale examples.

## 1. Product objective

LayerSentry shall use **one temporary bootstrap server only during initial site installation/recovery bootstrap**. The bootstrap server is not part of steady-state availability and LayerSentry must remain fully operational after it is shut down or removed.

The bootstrap workflow creates and configures a self-hosted HA control plane on three distinct physical KVM failure domains in the DC:

- 3 LayerSentry/Apache CloudStack Management VMs, one per KVM host;
- 3 database VMs, one per KVM host, in one certified 3-node HA database topology;
- 2 load-balancer/VIP VMs, on separate KVM hosts, unless an existing certified external ADC is supplied;
- no single bootstrap, Management, database or LB VM is required for steady-state service.

A single LB VM is not a production HA topology. When LayerSentry owns the LB tier, use two LB/VIP VMs or a certified external ADC.

## 2. Physical placement contract

Minimum production candidate with three KVM failure domains:

```text
Temporary Bootstrap Server
  - used for bootstrap only
  - Ansible Runner / signed execution environment
  - no steady-state dependency
  - powered off/removed after acceptance

KVM HOST A                 KVM HOST B                 KVM HOST C
----------                 ----------                 ----------
LS-MGMT-01                 LS-MGMT-02                 LS-MGMT-03
LS-DB-01                   LS-DB-02                   LS-DB-03
LS-LB-01                   LS-LB-02                   reserved HA capacity
```

Equivalent placement is allowed only when loss of any one physical host still leaves:

- 2 Management Servers;
- 2 of 3 database quorum members;
- 1 LB/VIP node when LayerSentry owns the LB tier;
- sufficient CPU/RAM/storage/network capacity for the surviving control plane.

Do not place two DB quorum members in one failure domain. Do not place both LB nodes on one host. Reserve/control control-plane capacity so tenant workloads cannot starve these VMs.

## 3. Bootstrap server lifecycle

The bootstrap server is a **temporary control-plane seed**, not a permanent management dependency.

It may be a temporary physical server or VM reachable to all three KVM hosts and required management/storage networks. It contains the signed LayerSentry bootstrap release, Ansible execution environment, pinned collections and ephemeral runtime credentials.

### Bootstrap lifecycle

```text
Boot bootstrap server
 -> verify signed LayerSentry release
 -> discover/validate three KVM hosts
 -> configure minimum host prerequisites through Ansible
 -> create control-plane VMs directly on the intended hosts
 -> establish DB HA
 -> establish three CloudStack Management Servers
 -> establish management UI/API LB/VIP
 -> register/reconcile KVM hosts with CloudStack
 -> execute full HA/failure validation
 -> persist signed topology/recovery manifest and backups
 -> revoke bootstrap credentials
 -> purge temporary Ansible/runtime secrets
 -> power off/remove bootstrap server
```

After completion, normal CloudStack/LayerSentry operations must not contact the bootstrap server.

The bootstrap workflow remains reproducible from signed offline release media for total-control-plane disaster recovery, but there is no continuously running bootstrap service.

## 4. Narrow exception for self-hosted control-plane VMs

Normal customer/tenant VM lifecycle remains owned by CloudStack.

The initial CloudStack Management/DB/LB VMs are a narrow bootstrap exception because CloudStack cannot be required to create the Management plane that must exist before its API is available.

The bootstrap server therefore creates only the signed, allowlisted control-plane VM definitions directly through libvirt/Ansible. It must never expose a general second VM scheduler.

After bootstrap:

- control-plane VM identities/definitions are stored in the signed LayerSentry control-plane recovery manifest;
- their placement is pinned to the intended failure domains unless a controlled recovery operation moves/recreates them;
- customer/tenant VM lifecycle is performed through CloudStack;
- out-of-band control-plane recovery remains available without requiring a healthy CloudStack API.

Before certifying this topology, validate exact CloudStack/KVM behavior with these bootstrap-owned libvirt domains present on CloudStack-managed hosts. Do not assume unmanaged domain coexistence from design alone.

## 5. Ansible-only bootstrap execution

No Bash/sh installation lifecycle is allowed.

Selected path:

```text
Signed LayerSentry bootstrap release
 -> compiled/bootstrap controller
 -> Ansible Runner / ansible-core
 -> version-pinned collections and LayerSentry roles
 -> KVM hosts / control-plane VMs
```

Prefer dedicated Ansible modules and templates. Avoid `ansible.builtin.shell` and `raw`. For an unavoidable external CLI, use argv-safe command/module semantics with strict allowlists.

Never use `curl | bash`, `wget | sh`, `eval`, arbitrary URLs, arbitrary playbook names or customer-controlled commands.

## 6. Declarative VM creation

For direct bootstrap-time KVM VM creation, prefer supported Ansible/libvirt modules rather than shelling out to `virt-install`.

Current Ansible `community.libvirt` provides declarative VM/network/storage primitives including `community.libvirt.virt_install`, `virt_net`, `virt_pool`, `virt_volume` and libvirt inventory support. Pin the exact certified collection version in the LayerSentry release.

The bootstrap VM-create contract must include:

- deterministic VM name/UUID ownership;
- target physical host/failure-domain identity;
- CPU/RAM sizing;
- immutable source image/digest;
- disk/storage placement;
- NIC/bridge/VLAN mapping;
- firmware/UEFI profile;
- autostart/recovery policy;
- no duplicate creation after timeout;
- authoritative observation before retry;
- safe cleanup only for bootstrap-owned incomplete resources.

Do not give customers a generic `virt_install` interface.

## 7. Required bootstrap order

Use dependency order rather than creating all VMs and hoping services converge.

### B0 — physical host preflight

Validate all three KVM hosts:

- Rocky Linux 9 and approved patch baseline;
- CPU virtualization and `/dev/kvm`;
- libvirt/QEMU;
- time/DNS;
- management NIC/bridge/VLAN;
- storage paths;
- NFS/iSCSI/multipath/NVMe profile as applicable;
- MTU;
- SELinux Enforcing;
- firewalld active;
- unique host identity;
- sufficient N+1 capacity;
- failure-domain placement.

### B1 — create 3 DB VMs

Create exactly one DB VM per KVM host and validate their network/storage identity before database installation.

### B2 — establish 3-node DB HA

The exact database HA implementation is a release qualification decision, not an assumption.

Preferred first candidate is a MySQL 8.4-compatible, 3-node, quorum-aware, **single-writer** design such as MySQL InnoDB Cluster / Group Replication, with a stable routing endpoint. CloudStack 4.20.3 introduced MySQL 8.4 support carried into later releases, but the exact LayerSentry 4.22.1.1 topology must still be tested.

Do not select multi-writer merely because a technology supports it.

Alternative candidates such as Percona XtraDB Cluster or MariaDB Galera may be researched/qualified, but are not automatically selected. CloudStack community deployments exist with 3 Management Servers + 3-node Galera + HAProxy, and recent 4.22.1 community reports also describe Management crashes in such a topology. Treat this as operational evidence requiring exact reproduction/qualification, not proof that Galera is either broken or certified.

Required DB tests include:

- schema creation and upgrade;
- DB credentials/authentication compatibility;
- CloudStack transaction/connection-pool behavior;
- primary/writer failure;
- one DB VM loss;
- network partition;
- quorum loss;
- full DB cluster restart;
- backup/PITR/restore;
- rolling DB maintenance;
- management reconnect;
- latency/load;
- logical corruption recovery separate from HA.

Do not use an unverified `--schema-only` shortcut to initialize production CloudStack databases. A 2026 CloudStack 4.22.1 community report describes a schema-only initialization ending at an old schema level. Use the exact supported setup path and verify the final schema/version before bringing all Management Servers online.

### B3 — create 3 Management VMs

Create one Management VM on each host.

All three use the same CloudStack databases and the same required encryption/database key material, delivered from the runtime secret boundary.

Initialize the CloudStack schema exactly once. Additional Management Servers must join the existing DB rather than recreate it.

Community guidance for CloudStack 4.22 multiple Management Servers confirms the second/additional Management nodes still need DB configuration against the existing database without redeploying/recreating it, or equivalent validated `db.properties`/key provisioning with each node's `cluster.node.IP` set correctly. Automate this through Ansible and test it; do not hand-copy secrets as an operational procedure.

### B4 — Management readiness before LB admission

For each Management node prove:

- service healthy;
- expected DB/schema version;
- cluster node identity unique;
- API works directly;
- no 503;
- async job execution;
- agent/system-VM control path prerequisites;
- SELinux/firewalld remain enabled;
- no secret leakage.

Do not add an unhealthy Management Server to the LB pool.

### B5 — create HA LB/VIP tier

If a certified external ADC exists, use it rather than deploying LayerSentry LB VMs.

Otherwise create:

- LS-LB-01 on Host A;
- LS-LB-02 on Host B;
- HAProxy (or another release-certified proxy);
- a tested VIP-owner mechanism such as Keepalived/VRRP where the network supports it;
- health checks against all 3 Management Servers;
- persistence/stickiness required by the exact CloudStack Management LB contract;
- TLS termination/pass-through according to the release certificate design.

Use the LB/VIP primarily for UI/API traffic.

For KVM/System-VM agent traffic, prefer CloudStack's native management-address CSV plus `indirect.agent.lb.algorithm=roundrobin` where the exact 4.22.1.1 contract supports it. Do not add an unnecessary TCP proxy for 8250 unless the release explicitly requires and certifies it.

### B6 — register/reconcile the three KVM hosts

Only after Management and DB HA are healthy, register the KVM hosts through supported CloudStack APIs/configuration.

Validate that the bootstrap-created control-plane domains coexist safely with CloudStack agent operation. Do not allow CloudStack to accidentally adopt/delete/migrate LayerSentry bootstrap-owned control-plane VMs unless a separately certified ownership transition exists.

### B7 — control-plane HA acceptance

Prove, at minimum:

- direct health of all 3 Management nodes;
- UI/API through LB VIP;
- one Management VM loss;
- each Management VM loss in turn;
- one LB VM loss;
- VIP failover;
- one DB VM loss;
- DB writer/primary transition where applicable;
- one physical KVM host loss/reboot at a time;
- KVM agent reconnection/distribution;
- System VM behavior;
- restart order after total clean shutdown;
- bootstrap server powered off during all steady-state tests.

A passing test while bootstrap remains online is not proof of bootstrap independence.

## 8. Steady-state dependency graph

After bootstrap removal:

```text
Users/API
   |
   v
LB VIP (2-node HA or external ADC)
   |
   +------> MGMT-01
   +------> MGMT-02
   +------> MGMT-03
                |
                v
       stable DB routing/endpoint
                |
      +---------+---------+
      |         |         |
    DB-01     DB-02     DB-03

KVM/System VM agents
   -> native CloudStack Management Server distribution where certified
```

No arrow points to the bootstrap server.

## 9. Total control-plane recovery

Although the bootstrap server is removed after install, LayerSentry must preserve enough signed recovery state to reconstruct the control plane after catastrophic loss.

Persist outside the ephemeral bootstrap server:

- signed topology manifest;
- exact release/artifact digests;
- control-plane VM definitions;
- host/failure-domain mapping;
- generated non-secret configuration digests;
- encrypted/safe DB backups and PITR material;
- certificates/public trust material;
- logical secret references, not plaintext secrets;
- LB/VIP configuration intent;
- recovery procedure and evidence.

A new temporary bootstrap server may be instantiated from the signed LayerSentry recovery media for disaster recovery. The old bootstrap instance is never a required recovery dependency.

## 10. Ansible supply-chain/offline rules

LayerSentry customer installation must not depend on live Ansible Galaxy access.

The signed offline release must carry the exact certified:

- ansible-core/Runner execution environment;
- `community.libvirt` and other required collections;
- Python dependencies;
- LayerSentry collections/roles/playbooks;
- package repositories/artifacts;
- checksums/signatures/SBOM/provenance.

Pin exact collection versions and verify compatibility with the selected ansible-core/Python execution environment before release.

Ansible community discussions show real collection-version compatibility and Galaxy availability failures. Therefore do not resolve `latest` collections during customer bootstrap and do not use Galaxy as a production runtime dependency.

## 11. Mandatory research/forum gate

Before any **significant** change to bootstrap, KVM, CloudStack Management HA, database topology, load balancing, Ansible execution, upgrade or recovery:

1. inspect exact Apache CloudStack 4.22.1.1 source and version-pinned official docs;
2. inspect relevant CloudStack release notes/issues/PRs;
3. search materially relevant Apache CloudStack GitHub Discussions and community/mail-list/operator evidence;
4. inspect exact Ansible module/collection documentation;
5. search relevant Ansible Forum issues for module/version/offline/Runner/AWX/collection problems;
6. inspect database/LB vendor documentation and known issues for the exact selected version;
7. compare alternatives;
8. retain the current architecture unless evidence demonstrates a better/simpler/safer path;
9. record only high-signal findings that change implementation or tests.

Do not turn the research gate into repeated broad documentation churn. Once a decision is frozen, re-open research only for a concrete blocker, version change, failure or materially better alternative.

## 12. Research findings incorporated into this context

High-signal findings reviewed on 2026-09-07 include:

- Apache CloudStack installation documentation supports multiple Management Servers using an external/separate MySQL database and requires a load balancer for multiple Management Servers.
- A 2026 CloudStack GitHub Discussion on adding multiple Management Servers explains that additional nodes must configure the existing DB without redeploying it, with matching DB/key material and correct per-node cluster IP.
- CloudStack community operators report using HAProxy for three Management nodes and SSL offload; this is useful operational evidence but not release certification.
- A recent CloudStack discussion reports crashes in a 3-Management + 3-Galera + HAProxy environment after upgrading to 4.22.1, so the DB topology must be stress/failure-qualified rather than copied blindly.
- Current `community.libvirt` documentation provides declarative `virt_install`, network, storage-pool and volume modules; use these rather than shell `virt-install` for bootstrap VM creation.
- Ansible Forum discussions reinforce pinning collection versions and carrying local collection artifacts for disconnected operation; Galaxy outages/dependency issues are real operational failure modes.
- MariaDB documentation states Galera normally uses an odd node count such as three and recommends a production load balancer/proxy, but LayerSentry still requires CloudStack-specific validation before selecting it.

## 13. IP protection

Keep proprietary Ansible control content on the temporary bootstrap/management execution plane rather than persistently copying the complete repository to KVM hosts or control-plane guests.

After execution:

- clean temporary module/playbook payloads;
- revoke temporary bootstrap credentials;
- leave only required signed binaries/packages and generated configuration;
- ship no development source tree, Git history, test fixtures or unnecessary architecture documents to customer hosts;
- use signed manifests and configuration/binary fingerprints for tamper/drift evidence.

Do not claim absolute non-reverse-engineerability on customer-owned hardware. The product goal is practical IP protection, minimum source exposure and tamper evidence.

## 14. Update/upgrade behavior

The bootstrap server is not reactivated for ordinary updates.

Normal updates are orchestrated from the persistent LayerSentry Management plane using the same signed Ansible execution model and rolling HA rules.

For Management/LB/DB upgrades:

- preserve quorum/service capacity;
- drain one Management/LB node at a time;
- maintain DB quorum and certified writer routing;
- back up DB before CloudStack schema-changing upgrades;
- follow exact CloudStack N-1 -> N management-server sequencing;
- verify service before moving to the next node;
- support interruption/resume from authoritative state;
- keep rollback/rebuild paths defined.

The bootstrap workflow is used again only for total-control-plane recovery/reseed where the normal Management plane is unavailable.

## 15. Evidence/status ceiling

This document is architecture/execution policy, not runtime proof.

Do not claim the 3-MGMT / 3-DB / 2-LB profile `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED` until the exact Rocky Linux 9 / CloudStack 4.22.1.1 / DB / LB / Ansible release has passed the complete failure, restart, upgrade, backup/recovery and bootstrap-removal matrix.
