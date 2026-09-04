# Codex Workstream D — DR / HA / Upgrade

## Mission

Prove LayerSentry's real operational behavior under recovery, failure, and upgrade conditions using supported CloudStack 4.22.1.1 capabilities and the existing Hyper-V/self-hosted-runner lab. Do not build a custom DR controller before native recovery is proven.

## Startup

Read `/AGENTS.md`, `docs/layersentry/CODEX_MASTER_CONTEXT.md`, and all mandatory LayerSentry documents. For live-lab work also inspect `adaptgurus/cozystack` branch `ops/layersentry-hyperv-inventory`, latest relevant workflows, and the actual Hyper-V/CloudStack runtime state.

Use isolated branches/worktrees. Suggested runner-repo branch: `codex/layersentry-dr-ha-upgrade`. CloudStack source branch only when a LayerSentry source change is genuinely needed.

## Primary ownership

Primarily in `adaptgurus/cozystack`:

- Hyper-V inventory/VM automation
- deployment/test workflows
- second-VM/two-Zone DR harness
- NAS B&R proof workflows
- HA failure/reboot tests
- upgrade/resume/rollback test harness
- evidence capture/artifacts

In `adaptgurus/cloudstack`, limit work to DR/HA/upgrade-specific LayerSentry scripts/docs that do not overlap A/B/C ownership.

## Phase 1 — read-only discovery

Before mutation establish current authoritative state:

- runner host and Hyper-V VM inventory
- CloudStack `sen` service state
- current Zone/Site/Pod/Cluster/Host inventory
- primary/secondary/backup storage
- guest/public networks
- System VMs
- agent state
- current B&R provider/repository state
- current CKS/object-store state if relevant

Persist discovery evidence. Do not infer missing state from old handoffs.

## Phase 2 — second-VM / two-Zone functional DR proof

When the user provides the second Rocky Linux 9 nested-KVM VM:

1. validate nested virtualization/network reachability;
2. create/configure the DR Zone/Site using supported CloudStack operations;
3. configure DR compute/network/storage prerequisites;
4. configure NAS B&R cross-Zone requirements;
5. create a small source test VM with identifiable data;
6. take and verify backup;
7. replicate/make repository data available at the DR Site using the chosen lab model;
8. recover the VM into the DR Site;
9. verify boot, network, data, and workload health;
10. measure backup/replication/recovery/boot timings and effective RPO/RTO;
11. repeat from an independent recovery point;
12. run safe negative tests for missing repository/storage and verify idempotent retry.

Account for CloudStack's dependency on retaining the original/unmanaged/expunged source instance DB record. Add a controlled purge/retention negative test only on disposable lab data.

If both VMs share one Hyper-V host/vSwitch/storage/failure domain, label the result `FUNCTIONAL_POC`/`LIVE_VERIFIED` only for the exact tested assertions. Do not call it independent-site certification.

## Phase 3 — HA proof

When sufficient lab resources exist, validate:

- multi-management-server availability behind LB/VIP
- one-management-node reboot/failure behavior
- agent multi-manager connectivity/distribution
- DB failover behavior for the exact certified MySQL 8.4/equivalent topology
- KVM host maintenance/HA behavior
- physical OOBM/fencing only on real supported hardware, not nested Hyper-V

Do not claim 3-management/2-LB/3-DB certification from a two-VM lab.

## Phase 4 — upgrade proof

Follow `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`:

- fresh target release install
- supported N-1 -> N path
- durable pre-upgrade checkpoint and DB/config backup
- CloudStack schema-aware management sequencing
- interrupted upgrade/resume
- UI artifact rollback
- KVM host rolling upgrade where supported
- post-upgrade VM/network/storage/RBAC/K8s/bucket/B&R/DR regression

Never promise zero management-plane downtime when upstream schema upgrade requires other management servers to be stopped.

## Safety rules

- Every destructive or connectivity-affecting action gets a durable pre-action checkpoint and rollback method.
- Never submit a duplicate workflow/recovery/VM create if an earlier one may still be running.
- Use only disposable test workloads for destroy/recovery/purge tests.
- Never expose passwords or long-lived private keys in GitHub artifacts/logs.
- Prefer ephemeral SSH credentials as current runner workflows do.
- Do not weaken CloudStack/KVM security to make a test pass.

## Handoff

Report exact repository/branch/commit, workflow run/job/artifact IDs, live target, mutations performed, test results, measured timings, failures, rollback state, scope limitations, and exact next gate. Do not edit the shared progress ledger unless explicitly assigned by the integration/lead session.
