# LayerSentry V1 — Bootstrap / Control-Plane HA Context

**Role:** stable bootstrap/control-plane architecture and production contract  
**Baseline:** Apache CloudStack 4.22.1.1 + Rocky Linux 9 + KVM  
**Execution owner:** ChatGPT by default  
**Production configuration engine:** Ansible Runner / ansible-core

Current B0/B1/H0-H2 implementation state belongs in `LAYERSENTRY_CURRENT_STATUS.md` and focused bootstrap/hypervisor evidence. Historical expanded research/detail remains available in Git history and is not normal startup context.

## 1. Objective and topology

LayerSentry uses one temporary bootstrap server only for initial site installation or catastrophic control-plane reseed. It is not part of steady-state availability.

Target production candidate across three real KVM failure domains:

```text
HOST A              HOST B              HOST C
------              ------              ------
MGMT-01             MGMT-02             MGMT-03
DB-01               DB-02               DB-03
LB-01               LB-02               reserve/N+1 capacity
```

A certified external ADC may replace the two LayerSentry LB VMs.

Loss of any one physical failure domain must still leave:

- at least 2 Management Servers;
- DB quorum/service for the selected 3-node topology;
- at least one LB/VIP path when LayerSentry owns the LB tier;
- sufficient surviving compute/storage/network capacity.

Do not place two DB quorum members or both LB nodes in one failure domain.

## 2. Bootstrap lifecycle

```text
verify signed LayerSentry release
 -> preflight exactly three KVM hosts
 -> configure minimum host prerequisites through Ansible
 -> create allowlisted control-plane VMs directly through libvirt/Ansible
 -> establish DB HA
 -> establish 3 CloudStack Management Servers
 -> establish UI/API LB/VIP
 -> register/reconcile KVM hosts with CloudStack
 -> execute HA/failure/recovery acceptance
 -> persist signed topology/recovery state and backups
 -> revoke bootstrap credentials / purge temporary secrets
 -> power off/remove bootstrap server
```

Normal CloudStack/LayerSentry operation after acceptance must not contact the bootstrap server.

## 3. Narrow pre-CloudStack VM-creation exception

CloudStack owns normal customer/tenant VM lifecycle.

Before the CloudStack API exists, the bootstrap server may create only signed, allowlisted LayerSentry control-plane VMs (Management, DB, LB) directly on the intended KVM hosts. This must never become a second general VM scheduler.

Required VM-create properties:

- deterministic allowlisted name/UUID ownership;
- exact target host/failure domain;
- immutable source image/digest;
- CPU/RAM/storage intent;
- deterministic disk ownership;
- NIC/bridge/VLAN/MTU intent;
- firmware/UEFI profile;
- autostart/recovery policy;
- observation before retry after timeout/ambiguity;
- cleanup only for proven bootstrap-owned incomplete resources.

After CloudStack host registration, bootstrap-owned domains must not be accidentally adopted/deleted/migrated by CloudStack unless a separately certified ownership transition exists. Coexistence with the CloudStack agent is a mandatory live qualification gate.

## 4. Ansible-only execution

Selected path:

```text
signed LayerSentry bootstrap release
 -> bounded bootstrap controller
 -> Ansible Runner / ansible-core
 -> pinned collections + LayerSentry roles/modules
 -> KVM hosts/control-plane VMs
```

Prefer declarative Ansible/libvirt modules and templates. Shell/raw is exceptional. Never use `curl | bash`, `wget | sh`, `eval`, arbitrary URLs, arbitrary playbook names or customer-controlled commands.

Customer installation must not depend on live Ansible Galaxy or runtime `pip install`. Carry exact certified ansible-core/Runner, collections, Python dependencies, package repositories/artifacts, checksums/signatures/SBOM/provenance in the signed offline release.

## 5. Required dependency order

### B0 — three-host preflight

Validate, for each intended KVM host:

- Rocky Linux 9/approved patch baseline;
- virtualization and `/dev/kvm`;
- libvirt/QEMU and required pinned runtime dependencies;
- time/DNS;
- unique host/failure-domain identity;
- management bridge/VLAN/MTU;
- required storage paths/providers;
- SELinux Enforcing;
- firewalld active;
- N+1 capacity.

### B1 — create DB VMs

Create exactly one DB VM per qualified KVM host using deterministic ownership and authoritative post-create observation.

### B2 — establish DB HA

The exact DB technology/version is a release qualification decision, not a permanent assumption. Prefer a quorum-aware single-writer design for the first candidate and test it against CloudStack 4.22.1.1.

Required evidence includes:

- schema creation/upgrade;
- CloudStack connection/transaction behavior;
- writer/one-member failure;
- network partition and quorum-loss fail-closed behavior;
- full cluster restart;
- backup/restore/PITR where supported;
- rolling maintenance;
- management reconnect;
- latency/load;
- logical-corruption recovery separate from HA.

Do not select multi-writer merely because a DB supports it, and do not use an unverified schema-initialization shortcut.

### B3/B4 — create and admit 3 Management VMs

Create one Management VM per host. Initialize the CloudStack schema exactly once; additional Management Servers join the existing DB with matching required key material and unique node identity.

Before LB admission prove each node healthy, on the expected schema, directly API-reachable, capable of async work, security controls enabled and free of secret leakage.

### B5 — UI/API LB/VIP

Prefer an existing certified external ADC when available. Otherwise use two LayerSentry LB/VIP VMs on separate failure domains with tested health checks, required persistence/stickiness and TLS behavior.

For KVM/System-VM agent traffic, prefer the exact CloudStack-supported Management-address distribution mechanism where qualified; do not add an unnecessary TCP proxy simply for architectural symmetry.

### B6 — register/reconcile KVM hosts

Only after DB/Management/LB health is established, register the KVM hosts through supported CloudStack APIs/configuration and verify safe coexistence with the bootstrap-owned control-plane domains.

### B7 — HA acceptance

At minimum prove:

- all 3 Management nodes direct health and UI/API through the LB/ADC;
- each Management VM loss;
- one LB loss/VIP failover when LayerSentry owns LB;
- one DB member loss and writer transition where applicable;
- one physical KVM failure-domain loss/reboot at a time;
- KVM/System-VM agent reconnection/distribution;
- restart order after clean total shutdown;
- bootstrap server powered off during steady-state tests.

A test with bootstrap still online does not prove bootstrap independence.

## 6. Steady-state and recovery

After bootstrap removal:

```text
Users/API -> LB/ADC -> MGMT-01/02/03 -> stable DB endpoint -> DB-01/02/03
KVM/System-VM agents -> qualified CloudStack Management distribution
```

No steady-state dependency points to bootstrap.

Persist outside the temporary bootstrap server:

- signed topology/control-plane recovery manifest;
- exact release/artifact digests;
- VM definitions and host/failure-domain mapping;
- non-secret config fingerprints;
- encrypted/safe DB backup/PITR material;
- certificates/public trust material;
- logical secret references, not plaintext secrets;
- LB/VIP intent;
- recovery procedure/evidence.

A new temporary bootstrap instance may be recreated from signed recovery media for catastrophic reseed.

## 7. Updates/upgrades

Do not reactivate bootstrap for ordinary updates. Use the persistent LayerSentry Management plane and the same signed Ansible execution model.

For Management/LB/DB upgrades:

- preserve quorum/service capacity;
- drain/upgrade one Management/LB node at a time;
- preserve DB quorum and certified writer routing;
- back up DB before schema-changing CloudStack upgrades;
- follow the exact supported N-1 -> N sequence;
- verify service before advancing;
- support interruption/resume from authoritative state;
- define rollback/rebuild boundaries explicitly.

Bootstrap is reused only when the persistent control plane cannot perform recovery/reseed.

## 8. Security / IP protection

- keep runtime credentials ephemeral and revoke them after bootstrap;
- do not ship private keys, Git history, development source trees or unnecessary test fixtures to customer hosts;
- clean temporary Ansible/module payloads where practical;
- use signed artifacts/manifests and config/binary fingerprints for integrity/drift evidence;
- do not claim absolute non-reverse-engineerability on customer-owned hardware.

## 9. Research and evidence discipline

Re-open external research only for a concrete blocker, version change, failure or materially better alternative. Do not repeatedly rescan forums/docs when a decision is already frozen.

Before a significant architecture/version change, validate exact CloudStack 4.22.1.1 source/docs, selected Ansible collection/module contracts and selected DB/LB vendor behavior.

This document is architecture/execution policy, not runtime proof. The 3-MGMT/3-DB/2-LB profile remains below `LIVE_VERIFIED` until the exact Rocky/CloudStack/DB/LB/Ansible release passes the full failure, restart, upgrade, backup/recovery and bootstrap-removal matrix.