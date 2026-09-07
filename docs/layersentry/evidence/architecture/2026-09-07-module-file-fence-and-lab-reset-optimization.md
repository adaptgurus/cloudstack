# LayerSentry module isolation and lab-reset optimization — 2026-09-07

## Purpose

Reduce Codex/ChatGPT context cost, duplicate source work and concurrent-edit risk without weakening product safety or production evidence requirements.

## Decisions

1. `AGENTS.md` now defines hard writable-path fences for UI, RKE2/K8s, Single-OS, DR, bootstrap/hypervisor and governance work.
2. A module session may inspect foreign source when needed to understand a native contract, but it does not edit outside its assigned fence.
3. Foreign-module defects are handed to the owning workstream with exact path/API/failure evidence.
4. One source writer is allowed per module. In particular, there is one primary K8s source writer.
5. UI is deferred as a continuously active Codex stream. Run one bounded final UI integration/browser pass after backend contracts stabilize.
6. Release/signing/security work is milestone-gated rather than a permanent parallel agent.
7. A separately provided healthy RKE2 cluster is a test-only/read-mostly package qualification lane for Flux, OpenEverest, OpenBao, Harbor, Strimzi, backup/restore and offline package tests. It does not create a second CAPI/CAPC/CAPRKE2 implementation.
8. For disposable VM-native and DR acceptance labs, the owner may manually reinstall/recreate Rocky Linux 9 test VMs. When a dirty/ambiguous guest blocks further testing, the agent records evidence, reports `LAB_RESET_REQUIRED`, stops mutating the guest and resumes after a fresh VM is provided.
9. Agents do not build automatic test-VM snapshot/reimage/reset machinery solely to clean disposable labs. This does not remove product requirements for safe install, idempotency, repair, upgrade, uninstall, backup/restore, rollback/recovery or production DR.
10. `LAYERSENTRY_SUPER_MASTER_CONTEXT.md` was de-duplicated so it contains stable architecture rather than repeating execution routing/file fences already present in always-read files.

## Current source observations used in the optimization

- K8s already contains substantial BFF/auth/RBAC, CloudStack client/preflight, CAPI/CAPC/CAPRKE2 resources, lifecycle executor, CCM/CSI downstream work, NodeDiskSet, Flux resources and runtime wiring. Current priority remains live E0/E1 gate closure, not more scaffolding.
- `release-candidate-lane-b.json` still has unresolved final CCM/CSI images/Flux catalog and live hard gates, so K8s remains source-heavy but live-light.
- Single-OS currently contains substantial Go + Ansible provider source plus RPM/Rocky acceptance tooling, including verified local PGDG asset handling, two-phase PostgreSQL acceptance and root-disk destructive-plan rejection tests. Live provider qualification remains outstanding.
- DR already has native CloudStack recovery foundation plus provider-neutral operation/journal source. Current priority remains CloudStack/Zone/storage/B&R/KVM lab health and OLD/NEW recovery proof, not a generic replication framework.
- UI is already substantially implemented and should be final-integrated against stable backend contracts rather than repeatedly modified during backend development.

## Authority files updated

- `/AGENTS.md`
- `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`
- `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
- `docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`
- `docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`
- `docs/layersentry/codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`
- `docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`
- `docs/layersentry/codex/README.md`
- `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md`
- `docs/layersentry/evidence/single-os/CURRENT_STATUS.md`

## Status

This is an execution/governance optimization only. It does not promote runtime readiness or production-certification status.