# LayerSentry — Codex Execution Runbook

**Historical filename retained:** `CODEX_4_AGENT_RUNBOOK.md`  
**Current model:** one primary Codex stream, Kubernetes/RKE2/Data Services

The previous multi-agent A/B/C/D/E model is no longer the default execution strategy. `LAYERSENTRY_EXECUTION_CONTRACT.md` supersedes the old routing.

## 1. Why the model changed

Parallel Codex streams created useful source, but also increased:

- repeated context loading;
- overlapping architecture work;
- integration/handoff overhead;
- source progress without proportional E2E progress;
- Codex credit consumption outside the highest-value blocker.

Current strategy reserves Codex for the Kubernetes/RKE2/Data Services vertical slice and uses ChatGPT for VM-native providers, native DR troubleshooting and UI integration/defects.

## 2. Active Codex scope

### Active — Workstream E

`docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`

Owns:

- CAPI/CAPC/CAPRKE2/RKE2;
- K8s controller/BFF integration;
- CNI/CCM/CSI;
- Flux package plane;
- Kubernetes DBaaS/APaaS/Streaming;
- K8s-specific UI wiring only as required by the vertical slice;
- immutable K8s component artifact integration;
- K8s E2E/failure/upgrade/air-gap validation.

Primary goal: **one complete RKE2 cluster lifecycle before expanding provider breadth**.

## 3. Non-Codex default scopes

### UI / Self-service

ChatGPT defect/integration work only. Broad UI feature development is frozen.

### Release / Installer

ChatGPT by default, except exact Kubernetes artifact work needed to unblock Workstream E may be performed in the same coordinated Codex stream when it is inseparable from the K8s release candidate.

### Security / Validation

ChatGPT by default for shared controls. Workstream E owns the K8s-specific negative/destructive cases required to prove its vertical slice.

### DR / HA / Upgrade

ChatGPT-led, native CloudStack API and lab troubleshooting first. Do not use a separate Codex stream to expand custom DR code before native recovery works.

### VM-native Single-OS DBaaS/APaaS

ChatGPT-led. Selected architecture is Go orchestration + Ansible Runner. No shell-script product installation lifecycle.

## 4. Minimal Codex startup

In the K8s worktree/session:

```text
Read AGENTS.md
 -> read LAYERSENTRY_EXECUTION_CONTRACT.md
 -> read LAYERSENTRY_PROGRESS_LEDGER.md
 -> read LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md
 -> read WORKSTREAM_E_K8S_DBAAS_APAAS.md
 -> fetch actual integration ref
 -> inspect actual first unmet E2E gate
 -> continue existing source
```

Do not start by reading every dated audit/handoff.

## 5. Repository/worktree discipline

Use one isolated K8s Codex worktree/branch at a time unless the owner explicitly authorizes another independent non-overlapping K8s substream.

Recommended layout:

```text
~/layersentry/
  cloudstack-base/
  k8s-codex/
  cozystack-base/
  k8s-runner/        # only when runner workflow changes are required
```

Before creation/reuse:

```bash
cd ~/layersentry/cloudstack-base
git fetch --all --tags --prune
git status --short --branch
git worktree list
git branch --list 'codex/layersentry-*'
```

Never delete/reset an existing worktree/branch merely because a runbook example differs from current state.

## 6. Copy/paste Codex prompt

```text
You are the primary LayerSentry Kubernetes/RKE2/Data Services Codex engineer.

Read AGENTS.md, docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md, docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md, docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md and docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md. Fetch and inspect the actual current integration ref and current live/workflow evidence before editing.

Your job is not to create more horizontal scaffolding. Continue the existing CAPI/CAPC/CAPRKE2/RKE2 source and close the first failing E0/E1 end-to-end gate. Produce immutable component artifacts, deploy the exact controller stack, create one real RKE2 cluster from the LayerSentry workflow, prove 6443/9345, one CNI, CCM, one safe CSI/storage path and Flux, then prove status/scale/replacement/delete/reconciliation. Fix the smallest correct owner for each observed failure and rerun the same E2E step.

Do not do broad UI redesign, VM-native Single-OS provider work or custom DR development. Stateful Kubernetes DBaaS remains blocked until cluster/storage safety gates pass. PostgreSQL is the first DBaaS vertical slice after the base cluster lifecycle works. Use the approved native CloudStack + Ansible RKE2 fallback only after exact evidence and a recorded release decision show the CAPI path cannot satisfy a required V1 gate without disproportionate downstream maintenance.

Commit coherent milestones and report exact source/artifact/workflow/target evidence plus the next failing vertical gate.
```

## 7. E2E execution discipline

At each step:

1. reproduce the exact live failure;
2. preserve logs/resource/job IDs;
3. classify owner layer;
4. implement the smallest fix;
5. add regression coverage;
6. build immutable affected artifact;
7. redeploy exact artifact;
8. rerun the same step;
9. proceed only when it passes.

Do not solve an E2E failure by adding a parallel controller or bypassing ownership boundaries.

## 8. Resource/concurrency

Serialize operations that contend for the same runner/lab resources:

- Kubernetes cluster create/delete;
- VM mutation;
- storage/CSI tests;
- VIP/LB tests;
- upgrade/replacement;
- destructive data-safety tests.

Source analysis can run locally in parallel only when it does not create conflicting edits.

## 9. Recovery after session loss

```bash
git status --short --branch
git rev-parse HEAD
git log -5 --oneline --decorate
git fetch --all --tags --prune
```

Then inspect the exact last workflow/live operation before retrying. Resume from the first unmet gate; do not reconstruct work from chat memory.

## 10. Handoff size

Keep handoffs concise:

- source commit;
- exact component/release tuple;
- artifact digests;
- vertical-slice step reached;
- workflow/job/target;
- failure/root cause if blocked;
- exact next E2E gate.

Do not generate another large master context unless architecture materially changes.
