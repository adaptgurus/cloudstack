# LayerSentry V1 — Current Status

**Role:** compact startup status index.  
**Baseline:** Apache CloudStack 4.22.1.1 + KVM + Rocky Linux 9.  
**Rule:** actual current source/workflow/live evidence overrides this file if newer. Never reset to a SHA copied from here.

## 1. Execution / module state

| Module | Owner / activation | Current state | First unmet gate |
| --- | --- | --- | --- |
| RKE2/K8s/Data Services | **Codex / ACTIVE PRIMARY** | substantial source; source/path gate `CI_VERIFIED`; release candidate `PENDING` | immutable CCM/CSI/Flux artifacts -> deploy controller -> one real cluster -> auto join -> 6443/9345 -> `Ready` |
| Healthy second RKE2 | test-only parallel lane | package qualification only | Flux/OpenEverest/OpenBao/Harbor/Strimzi/offline tests; no lifecycle-source commits |
| VM-native Single-OS | ChatGPT by default | source + exact RPM `CI_VERIFIED`; live provider `NOT_TESTED` | clean Rocky 9 + non-OS disk -> install exact RPM -> PostgreSQL live acceptance |
| DC/DR | ChatGPT by default | `PARTIAL`; state/recovery source exists | healthy CloudStack/B&R -> OLD/NEW recovery points -> isolated recovery -> exact guest-data verify |
| Bootstrap/Hypervisor | ChatGPT by default | H0-H2 + B0/B1 source slices exist; live `NOT_TESTED` | three real KVM failure domains -> live B0/B1 -> DB/control-plane progression |
| UI/Self-Service | Codex / **DEFERRED** | substantial existing UI | one final backend integration/RBAC/build/Chrome+Firefox pass after contracts stabilize |
| Release/Security | milestone-gated | source foundations; production trust/certification pending | exact artifact promotion/signing/security/upgrade gates when activated |

One source writer per module. Foreign-module defects are handed to their owner.

## 2. RKE2 / Kubernetes / services

Current machine-readable authority:

`tools/layersentry/k8s/release-candidate-lane-b.json`

Candidate tuple: CloudStack `4.22.1.1`, CAPI `1.13.5`, CAPC `0.6.1` + pinned downstream overlay, CAPRKE2 `0.25.2`, RKE2 `1.36.4+rke2r1`, Kubernetes `1.36.x`, CloudStack CSI `3.0.2` downstream candidate, CloudStack CCM `1.2.0` downstream candidate, Flux package plane.

Implemented source includes BFF/auth/RBAC, durable saga/journal/reconciliation, CloudStack preflight/client, CAPI/CAPC/CAPRKE2 resources, create/status/scale/delete, 6443/9345 endpoint work, CAPC volume ownership work, CCM/CSI downstream source, NodeDiskSet, Flux and runtime wiring.

The module-specific `LayerSentry K8s Source Validation` gate is `CI_VERIFIED` at `6f8e81001feefce50cfeea2ca3b3df907af2f09a`, run `34165534684`. It mechanically validates K8s source/unit/manifests and commit-aware K8s path ownership; local staged-path enforcement is also available through `module-writer-guard.sh precommit k8s`. This proof does not promote any live E0/E1 gate.

The current release manifest still has all hard live gates false, including endpoints, Flux reconcile, CAPC/NodeDisk ownership, CSI project/resize, stateful replacement, air-gap, backup/restore and PITR. Do not broaden source while the current gate fails.

Services reuse the same RKE2 + Flux substrate:

- OpenEverest stable v1 -> supported PostgreSQL/PXC-MySQL/MongoDB;
- OpenBao -> supported Helm/OCI;
- Harbor -> supported Helm/OCI;
- Strimzi -> Kafka.

Do not build replacement DB/Kafka/application operators/controllers or upstream UIs.

**Current scope boundary:** cross-site RKE2 application DR, Kubernetes-backed DBaaS/APaaS DC->DR replication/promotion/failback, RKE2 RPO/RTO and RKE2 DR UI are not current Workstream-E gates. Independent DC/DR remains separate. CSI/PVC data safety and DB backup/restore/PITR where advertised remain in scope.

The separate healthy RKE2 cluster is test-only; success there does not by itself make the LayerSentry-created cluster `LIVE_VERIFIED`.

## 3. VM-native Single-OS

Authoritative module status:

`docs/layersentry/evidence/single-os/CURRENT_STATUS.md`

Current durable proof:

- source validation: `CI_VERIFIED` at `f2aee691867d974c2eb0b28184d92b4567100ce8`, run `34126279393`, job `101755596059`;
- exact Rocky RPM build: run `34126279307`, artifact `10020266864`;
- RPM `layersentry-single-os-0.2.0-1.el9.x86_64.rpm`;
- RPM SHA-256 `5ddfa332d222a616f9d9749282540ab3a4acaad64b4b4cba767236a0d4b58fe1`.

Source already includes Go control/lifecycle + Ansible boundary, Rocky/LVM/VIP roles, PostgreSQL/MySQL-family/Redis-Valkey/Nginx/HTTPD/Tomcat/runtime providers and two-phase PostgreSQL acceptance tooling.

Next: clean disposable Rocky 9 VM with separate data disk -> exact RPM install -> live root-disk exclusion -> PostgreSQL phase 1 -> reboot -> phase 2/repair/upgrade/uninstall/data preservation.

If the disposable guest becomes dirty/ambiguous, record `LAB_RESET_REQUIRED`; the owner may manually reinstall the VM rather than building lab-reset automation.

## 4. Hypervisor / bootstrap

Current source evidence pointers:

- `evidence/hypervisor/2026-09-07-h2-network-security-source.md`;
- `evidence/bootstrap/2026-09-07-b0-physical-host-preflight-source.md`;
- `evidence/bootstrap/2026-09-07-b1-db-vm-provisioning-source.md`;
- `evidence/bootstrap/2026-09-07-b1-runtime-dependency-closure.md`.

Implemented: Rocky/KVM/security/network preflight, H2 SELinux/NetworkManager/firewalld boundary, exactly-three-failure-domain B0 checks, allowlisted deterministic B1 DB-VM libvirt provisioning and runtime dependency guards.

Nothing above is live-certified yet. First live gate is three real KVM failure domains with signed package intent/storage/base image/UEFI/bridge/MTU/cloud-init/SSH, then CloudStack-agent coexistence and later DB/MGMT/LB HA.

## 5. DC / DR

Current execution pointer:

`docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`

Source foundations include provider-neutral DR objects/state/journal/lease/idempotency and the bounded native selected-recovery-point `createVMFromBackup` adapter. Native recovery is not yet `LIVE_VERIFIED`.

First gate remains environment/native recovery, not more framework source:

```text
healthy DC/DR CloudStack -> B&R -> OLD -> mutate -> NEW
 -> recover OLD + NEW to isolated destination -> exact root/data verification
```

Only after that qualify one required provider-native low-RPO path, then Planned Failover/Failback, then witness/fencing/Auto Failover last.

This is the independent CloudStack/VM/provider-native DR workstream; it does not currently add RKE2 application DR requirements to Workstream E.

## 6. UI / release / production

UI is substantial but intentionally dormant until backend contracts are stable enough for one final `ui/**` integration/browser pass. Do not redesign the portal or rebuild upstream service UIs.

For K8s/DBaaS/APaaS, final production audit should trace each advertised action through UI/API/authorization/backend/reconciler-or-operator/K8s-or-storage/persistence/failure-path/test/live evidence rather than rely on one overall UI percentage.

Release/security is milestone-only. One logical V1 carrier remains `layersentry-platform-<release>.iso`; bundled packages are `AVAILABLE`, not installed.

**Overall production certification remains `PENDING`.** Governance/source/CI progress is not runtime certification.

## 7. Status maintenance

Keep this file small (target roughly 5-8 KB) and current.

- Module writers update their module-specific status/release manifest/focused evidence only at meaningful evidence milestones.
- An integration/status/governance pass updates this file when a module status, first unmet gate or authoritative pointer materially changes.
- Do not paste logs/history here. The compacted `LAYERSENTRY_PROGRESS_LEDGER.md` and Git/evidence history are read on demand only.
- Every new session still fetches actual Git/workflow/live state; newer evidence wins if this summary is stale.

New-session resume path:

```text
AGENTS.md
 -> LAYERSENTRY_EXECUTION_CONTRACT.md
 -> LAYERSENTRY_CURRENT_STATUS.md
 -> assigned workstream/module status
 -> actual current Git/workflow/live state
 -> first unmet gate
```

Do not restart completed work because a prior chat is unavailable.