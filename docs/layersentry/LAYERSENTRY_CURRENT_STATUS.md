# LayerSentry V1 — Current Status

**Role:** compact startup status index.  
**Baseline:** Apache CloudStack 4.22.1.1 + KVM + Rocky Linux 9.  
**Authority rule:** actual current source/workflow/live evidence overrides this file if newer.

This file exists so a new ChatGPT/Codex session can understand what has already been achieved and what the first unmet gate is **without reading the full historical Progress Ledger**.

Do not treat any recorded commit here as a reset target. Always fetch the actual shared branch first.

## 1. Current execution model

| Module | Default owner | Activation | Current high-level state |
| --- | --- | --- | --- |
| RKE2/Kubernetes/Data Services | Codex | **ACTIVE PRIMARY** | substantial source exists; live E0/E1 gates remain `PENDING` |
| Healthy second RKE2 cluster | test-only lane | parallel when supplied | package/Flux qualification only; no lifecycle-source writing |
| VM-native Single-OS | ChatGPT by default | active when clean Rocky lab is available | source + exact RPM are `CI_VERIFIED`; live provider qualification is next |
| DC/DR | ChatGPT by default | active native-API/lab stream | source foundation exists; native two-point recovery remains unproven |
| Bootstrap/Hypervisor/Control Plane | ChatGPT by default | active when 3-host lab is available | B0/B1 and H0-H2 source slices exist; live qualification remains |
| UI/Self-Service | Codex | **DEFERRED FINAL PASS** | substantial UI exists; run one final integration/browser pass after backend contracts stabilize |
| Release/signing/security | milestone-gated | only when artifact/trust gate requires it | source foundations exist; final production trust/certification remains pending |

One source writer per module. Foreign-module defects are handed to the owning module rather than fixed cross-scope.

## 2. RKE2 / Kubernetes / Data Services

**Status:** `PENDING` for the current release candidate; source implementation is substantial but live qualification is low.

Current release tuple is recorded in:

`tools/layersentry/k8s/release-candidate-lane-b.json`

Selected candidate:

- CloudStack `4.22.1.1`;
- CAPI `1.13.5`;
- CAPC `0.6.1` plus pinned LayerSentry downstream overlay;
- CAPRKE2 `0.25.2`;
- RKE2 `1.36.4+rke2r1` / Kubernetes `1.36.x`;
- CloudStack CSI `3.0.2` plus downstream project/idempotency work;
- CloudStack CCM `1.2.0` plus Kubernetes 1.36 downstream work;
- Flux as central package reconciler.

Already implemented in source includes BFF/auth/RBAC, durable saga/journal/reconciliation, CloudStack preflight/client, CAPI/CAPC/CAPRKE2 resources, create/status/scale/delete executor, dual 6443/9345 endpoint work, CAPC volume-ownership work, CCM/CSI downstream source, NodeDiskSet and Flux/runtime wiring.

Current hard gates remain false in the release candidate, including:

- tuple reconciliation;
- 6443;
- 9345;
- Flux remote reconcile;
- CAPC volume ownership safety;
- NodeDiskSet ownership;
- CSI project scope;
- CSI resize idempotency;
- air-gap create/scale/repair;
- stateful Machine replacement;
- backup/restore;
- PITR restore.

Current first unmet gate:

```text
immutable final artifacts (especially CCM / CSI / Flux catalog)
 -> deploy exact controller stack
 -> create one real cluster
 -> automatic CAPRKE2 join
 -> 6443 + 9345
 -> Ready
```

Do not add service breadth before the current substrate gate passes.

The separately supplied healthy RKE2 cluster is **test-only** for Flux/OpenEverest/OpenBao/Harbor/Strimzi/package/offline tests. Success there does not by itself promote the full LayerSentry K8s path to `LIVE_VERIFIED`.

## 3. Kubernetes DBaaS / APaaS / Streaming

**Architecture:** one shared RKE2 + Flux substrate; upstream-first.

V1 integration targets:

- OpenEverest stable v1 line for supported PostgreSQL/PXC-MySQL/MongoDB lifecycle;
- OpenBao from supported Helm/OCI content;
- Harbor from supported Helm/OCI content;
- Strimzi for Kafka.

LayerSentry does not build replacement DB operators, DB backup/PITR/failover engines, Kafka operators, Harbor/OpenBao controllers or replacement upstream UIs.

First meaningful service qualification begins only after the shared RKE2/CSI/CCM/Flux substrate is proven, although package behavior may be tested earlier on the separate healthy RKE2 lane.

## 4. VM-native Single-OS

**Status:** source and exact RPM are `CI_VERIFIED`; live Rocky provider qualification is `NOT_TESTED`.

Current implementation includes:

- substantial Go API/auth/plan/idempotency/journal/secrets/reconciliation/provider control plane;
- Go -> Ansible execution boundary;
- Rocky baseline, LVM/storage, network/VIP and provider roles/playbooks;
- PostgreSQL, MySQL/MariaDB, Redis/Valkey, Nginx, HTTPD, Tomcat and runtime provider source;
- exact install/signature/SHA acceptance tooling;
- root/OS-disk destructive-plan rejection;
- two-phase PostgreSQL live acceptance covering install/read-write/idempotent replay/backup-restore/reboot/repair/upgrade/uninstall/data preservation.

Latest durable source gate:

- implementation/evidence commit: `f2aee691867d974c2eb0b28184d92b4567100ce8`;
- source-validation run `34126279393`, job `101755596059`;
- exact RPM build run `34126279307`;
- artifact `10020266864`;
- RPM `layersentry-single-os-0.2.0-1.el9.x86_64.rpm`;
- RPM SHA-256 `5ddfa332d222a616f9d9749282540ab3a4acaad64b4b4cba767236a0d4b58fe1`.

Authoritative module pointer:

`docs/layersentry/evidence/single-os/CURRENT_STATUS.md`

First unmet gate: clean disposable Rocky Linux 9 VM + separate non-OS disk, exact RPM installation, live root-disk safety proof, then PostgreSQL standalone phase 1/reboot/phase 2.

If the disposable VM becomes dirty or ambiguous, capture evidence and report `LAB_RESET_REQUIRED`; the owner may manually reinstall Rocky rather than building lab-reset automation.

## 5. Hypervisor / Bootstrap / Control Plane

**Status:** multiple source slices are `SOURCE_COMPLETE`; live qualification is still `NOT_TESTED`.

Implemented source includes:

- H0/H1 Ansible hypervisor entrypoints;
- H2 network/security boundary with SELinux enforcing, NetworkManager bridge handling and firewalld agent rules;
- B0 exactly-three-host physical preflight with distinct failure domains, Rocky/KVM/time/network/storage/security checks;
- B1 allowlisted provisioning for `LS-DB-01..03` using pinned `community.libvirt`, deterministic UUID/MAC/storage/CIDATA, authoritative observation after ambiguous create and no force recreate;
- B1 runtime dependency fail-closed checks for `virt-install`, `python3-libvirt`, `python3-lxml` and `python3-pycdlib`.

Evidence pointers:

- `docs/layersentry/evidence/hypervisor/2026-09-07-h2-network-security-source.md`;
- `docs/layersentry/evidence/bootstrap/2026-09-07-b0-physical-host-preflight-source.md`;
- `docs/layersentry/evidence/bootstrap/2026-09-07-b1-db-vm-provisioning-source.md`;
- `docs/layersentry/evidence/bootstrap/2026-09-07-b1-runtime-dependency-closure.md`.

First unmet gate: live B0/B1 qualification on three real KVM failure domains with signed package intent, storage/base image, UEFI, bridge/MTU, three DB VM identities, cloud-init/SSH and later CloudStack-agent coexistence proof.

## 6. DC / DR

**Status:** `PARTIAL`; source foundations exist, but native recovery is not `LIVE_VERIFIED`.

Already implemented:

- provider-neutral DR objects/state/journal/lease/idempotency foundation;
- explicit Test Recovery/Recovery/Planned Failover/Failback/Auto-Failover safety gates;
- native CloudStack `createVMFromBackup` adapter for selected recovery points with bounded offline tests;
- storage-native-first architecture for advanced low-RPO tiers.

Latest known live baseline still shows the native path blocked by environment readiness such as source/destination Zone/storage/image-store/SystemVM/B&R configuration/API/RBAC/DR KVM readiness. Historical same-host nested Hyper-V evidence is functional only and cannot certify independent-site DR.

First unmet gate:

```text
healthy DC/DR CloudStack
 -> native B&R enabled
 -> disposable source VM + data disk
 -> Recovery Point OLD
 -> mutate data
 -> Recovery Point NEW
 -> recover OLD and NEW into isolated destination
 -> verify exact root/data contents
```

Do not expand advanced provider code until native recovery passes.

## 7. UI / Self-Service

**Status:** `PARTIAL` / substantial existing source; final product acceptance is deferred.

Existing work includes LayerSentry/KVM presentation, Quick Provision and broad self-service foundations. Historical exact-artifact evidence exists for selected UI scopes, but final backend-integrated role/RBAC/browser acceptance remains.

Activation rule: keep UI dormant while K8s/DR/Single-OS contracts move; then run one bounded final pass over `ui/**` only for VM/bucket/backup, RKE2, service catalog/status, DR integration, RBAC/routes/progress/errors, production build and Chrome/Firefox acceptance.

## 8. Release / Security / Production Certification

Release/security work is milestone-gated. Do not run permanent release/security streams.

One logical V1 release carrier remains:

`layersentry-platform-<release>.iso`

Final production gates still include immutable/signature/trust/SBOM/provenance, offline artifact closure, exact installer/upgrade/rollback evidence, security negatives, HA/DR, performance/scale/soak and release-specific regression.

**Overall production certification remains `PENDING`.** Source/CI progress must not be promoted to runtime certification.

## 9. Status maintenance contract

This file is intentionally compact and should remain **under roughly 8 KB whenever practical**.

Maintenance rules:

1. Module writers update their module-specific machine-readable/status/evidence pointer after a meaningful evidence milestone, not after every commit.
2. The global `LAYERSENTRY_CURRENT_STATUS.md` is reconciled by an integration/status/governance pass when a module's status, first unmet gate or authoritative pointer materially changes.
3. Do not copy long logs, old checkpoint narratives or full test output into this file; link/pointer to durable evidence instead.
4. The historical `LAYERSENTRY_PROGRESS_LEDGER.md` is not startup context. Use it only when older evidence/history is actually needed.
5. A new session always fetches current Git/workflow/live state; this status file is an orientation index, not a substitute for observation.
6. If this file is stale, newer current source, module CURRENT_STATUS/release manifest, workflow evidence and live evidence win.

## 10. New-session resume rule

A new session should be able to start from:

```text
AGENTS.md
 -> LAYERSENTRY_EXECUTION_CONTRACT.md
 -> LAYERSENTRY_CURRENT_STATUS.md
 -> assigned workstream/module status
 -> actual current Git/workflow/live state
 -> first unmet gate
```

Do not restart completed work merely because the previous chat is unavailable.