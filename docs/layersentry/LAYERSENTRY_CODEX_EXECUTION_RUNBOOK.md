# LayerSentry — Codex Execution Runbook

**Current launcher.** Historical filenames such as `CODEX_4_AGENT_RUNBOOK.md` are compatibility stubs only.

Execution authority:

- `/AGENTS.md` — hard file/safety/concurrency rules;
- `LAYERSENTRY_EXECUTION_CONTRACT.md` — scheduling/activation;
- `LAYERSENTRY_CURRENT_STATUS.md` — compact current progress/orientation;
- assigned workstream — exact module sequence.

## 1. Primary Codex model

Default standing Codex source writer:

**Workstream E — RKE2/Kubernetes/Data Services**

UI is a deferred bounded finalization pass. DR, Single-OS, bootstrap/hypervisor and release/security are not standing Codex streams unless the owner explicitly reassigns them.

Only one K8s source writer is permitted.

## 2. Primary K8s startup

Read only:

```text
AGENTS.md
 -> LAYERSENTRY_EXECUTION_CONTRACT.md
 -> LAYERSENTRY_CURRENT_STATUS.md
 -> WORKSTREAM_E_K8S_DBAAS_APAAS.md
 -> tools/layersentry/k8s/release-candidate-lane-b.json
 -> actual current Git/workflow/live state
```

Open the large K8s Super Master/addendum only when the current failing gate requires detailed provider/storage/network/version architecture.

Before source mutation, use the writer guard when working from a normal Git worktree:

```bash
tools/layersentry/governance/module-writer-guard.sh start k8s
# before each meaningful batch
tools/layersentry/governance/module-writer-guard.sh check k8s
# after fetching/reconciling the new shared state
tools/layersentry/governance/module-writer-guard.sh advance k8s
```

The guard detects same-module remote changes; it is not a distributed lock and does not replace manual review/reconciliation.

## 3. K8s gate order

```text
immutable artifacts
 -> controller deployment
 -> one real cluster
 -> automatic CAPRKE2 join
 -> 6443 + 9345
 -> cluster Ready
 -> one CNI
 -> CCM
 -> one safe CSI/PVC path
 -> Flux remote reconcile
 -> status/scale
 -> replacement + PVC survival
 -> delete
 -> restart/UNKNOWN reconciliation
 -> supported upgrade
 -> air-gap proof where claimed
```

Do not move to service breadth while the current substrate gate fails.

At each failure: capture exact evidence, identify the owning layer, fix the smallest correct owner inside the K8s file fence, add regression coverage, rebuild/redeploy the affected immutable artifact and rerun the same step.

## 4. Package qualification lane

A separately supplied healthy RKE2 cluster may test:

- Flux;
- OpenEverest and supported DB lifecycle;
- OpenBao;
- Harbor;
- Strimzi/Kafka;
- package update/remove/recovery;
- backup/restore where available;
- offline/local-registry behavior.

This lane is test-only/read-mostly. It must not create another CAPI/CAPC/CAPRKE2 implementation. Its evidence is scoped to that cluster and does not by itself certify the LayerSentry-created RKE2 path.

## 5. Upstream-first rule

Use pinned/qualified OpenEverest, OpenBao, Harbor and Strimzi. Do not build replacement DB/Kafka/application operators, backup/PITR engines or upstream application UIs.

## 6. CAPC stop-loss

If a bounded campaign repeatedly cannot produce CloudStack VM creation + automatic RKE2 join + 6443/9345 + `Ready`, and evidence shows continued CAPC maintenance is disproportionate, record the release decision and assign the approved fallback as a separate scope:

```text
native CloudStack APIs
 -> QCOW2/cloud-init
 -> Ansible Runner
 -> RKE2
 -> Flux
```

One release has one lifecycle owner.

## 7. Final UI Codex pass

Activate Workstream A only after backend contracts are stable enough for final integration.

Startup:

```text
AGENTS.md
 -> LAYERSENTRY_EXECUTION_CONTRACT.md
 -> LAYERSENTRY_CURRENT_STATUS.md
 -> WORKSTREAM_A_UI_SELF_SERVICE.md
 -> actual current UI/backend state
```

Edit only `ui/**` and UI-specific tests/evidence. Finish wiring, RBAC/routes/status/errors/build/browser acceptance without redesigning the product. Hand backend defects to their owners.

## 8. Status and handoff

Do not update the full historical Progress Ledger during ordinary module work.

At meaningful evidence milestones:

1. update the module-specific status/release manifest/evidence pointer;
2. report exact commit/artifact/workflow/live result and first unmet gate;
3. allow an integration/status reconciliation pass to refresh `LAYERSENTRY_CURRENT_STATUS.md` when the global summary materially changes.

Handoff is concise: exact commit/artifact, tests/live actions, current gate, observed blocker/root cause and next exact action. Do not create another master context during normal implementation.