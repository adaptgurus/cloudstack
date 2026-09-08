# LayerSentry Execution Model Optimization — 2026-09-07

## Decision

The project execution model is changed to reduce repeated context work, unnecessary custom code and Codex credit consumption while increasing end-to-end completion.

## Selected routing

- Kubernetes/RKE2/Kubernetes DBaaS/APaaS/Streaming: **Codex**.
- VM-native Single-OS DBaaS/APaaS: **ChatGPT**.
- DC/DR/DRaaS native baseline/troubleshooting: **ChatGPT**.
- broad UI feature development: **frozen**; ChatGPT handles defects/integration/browser acceptance.
- documentation/architecture maintenance: **ChatGPT**.

## VM-native architecture decision

Retain the existing Go orchestration/control-plane investment for API/auth, schema, planning, operation state, idempotency, locking, secret references, evidence and rollback/recovery state.

Move guest installation/configuration to **Ansible Runner/ansible-core with versioned roles/playbooks**.

Shell scripts are no longer an approved product installation/configuration boundary. Existing runtime installation/configuration scripts are deprecated and must not be extended; migrate their behavior to Ansible. Small build-only wrappers may remain temporarily where they are not the runtime/customer installation path.

## DC/DR decision

Do not expand heavy custom DR source while native CloudStack recovery is still unproven.

Priority is to resolve the actual lab/environment blockers and prove native CloudStack 4.22.1.1 Backup & Recovery with two real recovery points and isolated cross-Zone `createVMFromBackup` guest-data validation.

After native recovery works, add thin LayerSentry orchestration/UI and one provider-native low-RPO path when required. Planned failover/failback precedes witness/fencing/automatic failover.

## Kubernetes decision

Do not add broad new horizontal scaffolding. Codex must convert existing E0/E1 source into one working RKE2 vertical slice with immutable artifacts, deployed controller stack, automatic join, 6443/9345, one CNI, CCM, one safe CSI path, Flux, status/scale/replacement/delete and failure/reconciliation evidence.

Kubernetes PostgreSQL DBaaS begins only after the base cluster/storage safety gates pass.

The existing approved native CloudStack + QCOW2/cloud-init + Ansible Runner + RKE2 fallback remains available only after exact evidence and a release decision show that the CAPI/CAPC/CAPRKE2 path cannot meet a required V1 gate without disproportionate downstream maintenance. One release uses one lifecycle owner.

## UI decision

Treat existing broad LayerSentry UI source as feature-frozen for this phase. Only defects, integration, RBAC/status/error wiring, browser E2E, responsive/accessibility/security corrections and vertical-slice-specific UI changes are in scope.

## Context optimization

Normal startup now loads only:

1. `AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. one specialist context/workstream;
5. actual source/workflow/live evidence.

Historical handoffs/re-audits are opened only to resolve a concrete conflict.

## Files establishing the decision

- `/AGENTS.md`
- `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md` schema 4.0
- `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`
- `docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` schema 2.0
- `docs/layersentry/codex/WORKSTREAM_D_DR_HA_UPGRADE.md`
- `docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`
- `docs/layersentry/codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`
- `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md`
- `docs/layersentry/codex/README.md`

## Evidence status

This record changes project execution/architecture policy only. It does not promote any runtime module to `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED`.
