# LayerSentry — Codex Execution Runbook

**Historical filename retained:** `CODEX_4_AGENT_RUNBOOK.md`  
**Current model:** one standing Codex source writer — RKE2/Kubernetes; UI is deferred finalization

`LAYERSENTRY_EXECUTION_CONTRACT.md` is authoritative.

## 1. Why this model

Parallel Codex writers previously increased context loading, overlapping architecture, duplicate edits and source growth without proportional E2E progress.

Current policy:

- one active K8s source writer;
- optional read/test-only package lane on a second working RKE2 cluster;
- no continuous UI Codex stream;
- no standing Codex DR/Single-OS/bootstrap/release streams by default.

## 2. Primary Codex session — Workstream E

Read only:

```text
AGENTS.md
 -> LAYERSENTRY_EXECUTION_CONTRACT.md
 -> LAYERSENTRY_PROGRESS_LEDGER.md
 -> LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md
 -> WORKSTREAM_E_K8S_DBAAS_APAAS.md
 -> current branch/release-candidate/workflow/live target
```

Then close the first failing gate:

```text
immutable artifacts
 -> controller deployment
 -> cluster create
 -> automatic join
 -> 6443/9345
 -> CNI
 -> CCM
 -> CSI/PVC safety
 -> Flux
 -> scale/replacement/delete
 -> restart/UNKNOWN recovery
 -> upgrade
 -> air-gap
```

Do not add service breadth while a substrate gate fails.

## 3. Package qualification lane

If the owner supplies an already-working RKE2 cluster, use it to test:

- Flux;
- OpenEverest and one supported DB lifecycle;
- OpenBao;
- Harbor;
- Strimzi/Kafka;
- package update/remove/recovery;
- backup/restore/offline package behavior where available.

This lane is test-only/read-mostly. It must not create a second CAPI/CAPC/CAPRKE2 implementation or edit lifecycle source. Report manifest/package defects to the primary K8s writer.

## 4. Upstream-first rule

Use pinned/qualified OpenEverest, OpenBao, Harbor and Strimzi. Do not spend Codex on replacement DB/Kafka/application operators, backup/PITR engines or upstream UI rewrites.

## 5. CAPC stop-loss

If a bounded qualification campaign cannot produce CloudStack VM creation + automatic RKE2 join + 6443/9345 + `Ready`, and evidence shows provider maintenance is disproportionate, record the release decision and activate the approved native CloudStack API + QCOW2/cloud-init + Ansible Runner + RKE2 + Flux fallback as a separate assigned scope.

Do not quietly start a second lifecycle owner.

## 6. UI finalization

Workstream A is dormant until backend contracts stabilize. Then run one short Codex pass limited to `ui/**` for integration, RBAC/routes/progress/errors, build and browser acceptance.

Do not keep paying for UI edits after every backend change.

## 7. File/concurrency discipline

Obey the hard file fences in `AGENTS.md`.

- one K8s writer;
- no cross-module edits;
- foreign defects are handed off;
- serialize destructive operations on the same lab;
- never reset/force-push the shared branch;
- fetch/reconcile before every meaningful batch.

## 8. Copy/paste primary K8s prompt

```text
You are the primary LayerSentry RKE2/Kubernetes Codex writer. Read only AGENTS.md, LAYERSENTRY_EXECUTION_CONTRACT.md, LAYERSENTRY_PROGRESS_LEDGER.md, LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md and WORKSTREAM_E_K8S_DBAAS_APAAS.md, then fetch the actual branch/release candidate/live state.

Obey the Workstream-E hard file fence. Do not edit UI, Single-OS, Ansible, DR or global authority files. Close the first failing E0/E1 gate using existing source. Do not add horizontal frameworks or service breadth while the current gate fails. After the base RKE2/CSI/CCM/Flux path works, integrate OpenEverest/OpenBao/Harbor/Strimzi as pinned upstream packages rather than rewriting them.

Commit coherent milestones and report only exact artifacts/tests/live evidence and the next failing gate.
```

## 9. Copy/paste final UI prompt

```text
You are the LayerSentry final UI Codex engineer. Start only after the backend contracts are stable enough for final integration. Read AGENTS.md, LAYERSENTRY_EXECUTION_CONTRACT.md, LAYERSENTRY_PROGRESS_LEDGER.md and WORKSTREAM_A_UI_SELF_SERVICE.md, then fetch the current branch.

Edit only ui/** and UI-specific tests/evidence. Do not modify backend modules. Finish wiring, RBAC/routes/status/errors and exact-artifact browser acceptance without redesigning the product. Hand backend defects to their owning workstream.
```

## 10. Handoff

Keep handoffs concise: exact commit/artifact, tests/live actions, gate reached, failure/root cause and next gate. Do not generate another large master context from normal implementation work.