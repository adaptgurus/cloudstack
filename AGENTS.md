# LayerSentry AI Operating Rules

This repository is Apache CloudStack 4.22.1.1 with a LayerSentry KVM-first product layer. These rules apply to ChatGPT, Codex and other AI-assisted engineering performed in the LayerSentry context.

The objective is to ship working vertical slices with minimal custom infrastructure code, not to maximize files, commits, abstractions or documentation.

## 1. Minimal mandatory startup

Before changing source or runtime, read only:

1. `AGENTS.md`;
2. `docs/layersentry/LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`;
4. the single specialist context/workstream required by the assigned task;
5. fetch the actual current repository/workflow/live state.

Specialist context:

- Kubernetes/RKE2/Kubernetes DBaaS/APaaS/Streaming: `LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` + `codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`;
- VM-native Single-OS DBaaS/APaaS: `LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` + `codex/WORKSTREAM_F_SINGLE_OS_DBAAS_APAAS.md`;
- DC/DR/DRaaS: `LAYERSENTRY_DRAAS_ARCHITECTURE.md` + `codex/WORKSTREAM_D_DR_HA_UPGRADE.md` when needed;
- secure-engineering details: `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`;
- debugging/root cause: `LAYERSENTRY_DEBUGGING_RUNBOOK.md`.

Do not load historical handoffs/re-audits or every specialist document by default. Use them only to resolve a concrete conflict or missing fact.

Always inspect actual refs before editing:

```bash
git status --short --branch
git remote -v
git branch --show-current
git fetch --all --tags --prune
git rev-parse HEAD
git log -5 --oneline --decorate
```

Never reset a shared branch to a SHA copied from documentation and never force-push unless the owner explicitly authorizes a known recovery action.

## 2. Current execution routing

The authoritative routing is in `LAYERSENTRY_EXECUTION_CONTRACT.md`.

Default:

- **Codex:** LayerSentry-managed RKE2/Kubernetes and Kubernetes DBaaS/APaaS/Streaming, including end-to-end testing;
- **ChatGPT:** VM-native Single-OS DBaaS/APaaS, Ansible migration, DC/DR native-API troubleshooting/integration, UI defect/integration work, architecture/context maintenance;
- **UI:** broad feature work is frozen for this phase; fix defects and integration gaps only;
- **DR:** native CloudStack recovery first; custom advanced DR code is not the critical path;
- **Single-OS:** Go orchestration + Ansible execution; shell scripts are not the product installation boundary.

Older runbooks that route UI/DR/Single-OS to Codex are superseded on execution ownership by the current execution contract.

## 3. Non-negotiable CloudStack boundary

Default decision: **do not rewrite CloudStack core**.

CloudStack remains authoritative for VM, KVM, Zone/Pod/Cluster/Host, network, IP, firewall, supported native LB, storage, volume, template/ISO, snapshot, Backup & Recovery, account/domain/project/RBAC/quota and async-job lifecycle.

Prefer, in order:

1. native CloudStack 4.22.1.1 APIs;
2. supported CloudStack configuration/plugin/provider contracts;
3. the selected Kubernetes ecosystem controller where Kubernetes owns the lifecycle;
4. a thin LayerSentry BFF/controller for composite workflow, policy, evidence and external integration;
5. a narrow upstream/core change only when the above cannot satisfy the requirement and an explicit exception is approved.

Never create a second VM scheduler, second tenancy/RBAC authority, second quota authority or conflicting copy of CloudStack resource state.

## 4. VM-native Single-OS installation rule

Selected architecture:

```text
LayerSentry UI/API
 -> Go orchestration/control service
 -> Ansible Runner / ansible-core
 -> versioned LayerSentry roles/playbooks
 -> Rocky Linux 9 guest
```

Go owns validation, authorization binding, immutable planning, idempotency, locking, state/journal, secret references, Ansible invocation, health/evidence and rollback/recovery state.

Ansible owns guest installation/configuration such as packages, repositories, services, SELinux, firewalld, LVM/filesystems/mounts, VIP/network configuration and database/application provider configuration.

### Shell prohibition

Do **not** implement product installation/configuration, database/application lifecycle, cluster join, upgrade, repair, uninstall, LVM/storage setup, firewall/SELinux setup or RKE2 installation as Bash/sh lifecycle scripts.

Existing shell-based product installation/configuration assets are deprecated and must not be extended. Migrate them to versioned Ansible roles/playbooks.

Small developer/build/packaging wrappers may temporarily remain when they are not a runtime/customer installation boundary. They must not interpolate untrusted values into shell strings.

Inside Ansible, prefer dedicated modules. `shell`/`raw` are exceptional, not normal provider mechanisms. Where only a vendor CLI exists, use argv-safe command/module semantics.

## 5. DC/DR/DRaaS rule

Do not build heavy custom DR orchestration while the native CloudStack recovery baseline is unhealthy or unproven.

Current order:

```text
healthy DC/DR CloudStack infrastructure
 -> native Backup & Recovery enabled/configured
 -> two real recovery points
 -> selected old/latest createVMFromBackup recovery
 -> isolated destination networking
 -> guest data validation
 -> thin LayerSentry UI/orchestration
 -> one certified provider-native low-RPO path
 -> planned failover/failback
 -> witness/fencing/automatic failover last
```

Before advanced DR code, resolve real blockers such as storage/image-store/SystemVM readiness, B&R provider configuration, API/RBAC/async-job observation, DR KVM/libvirt readiness and destination Zone/network compatibility.

Do not implement a custom block-copy/replication engine where CloudStack or the storage provider already exposes the required supported primitive.

The existing provider-neutral DR state-machine source may be retained, but do not expand it merely to increase source percentage before native recovery works end to end.

## 6. Kubernetes/RKE2 Codex rule

Codex effort is concentrated here.

Current preferred architecture remains:

```text
LayerSentry UI/BFF
 -> CAPI
    -> CAPC -> CloudStack/KVM
    -> CAPRKE2 -> RKE2
 -> Flux
 -> certified CNI/CCM/CSI/operators
```

Do not add broad new scaffolding before turning existing E0/E1 source into a live vertical slice.

First complete:

1. immutable component artifacts;
2. controller deployment;
3. GUI/API cluster create;
4. automatic RKE2 join;
5. 6443 and 9345 endpoint proof;
6. one primary CNI;
7. CCM/L4 lifecycle;
8. one safe storage/CSI path;
9. Flux reconciliation;
10. status, scale, replacement/data-safety where applicable, delete/cleanup;
11. restart/reconciliation negatives;
12. Rocky Linux 9 evidence.

Only then expand Kubernetes DBaaS/APaaS/Streaming. PostgreSQL is the first DBaaS vertical slice.

If exact evidence shows CAPC/CAPRKE2 cannot satisfy a required V1 gate without disproportionate downstream maintenance, use the already-approved native CloudStack API + hardened QCOW2/cloud-init + Ansible Runner + RKE2 fallback after recording the decision. Never run both as active owners for the same release.

## 7. UI rule

Treat the broad LayerSentry UI as **feature-frozen** for this phase.

Allowed work:

- defects;
- missing API/BFF wiring;
- RBAC/direct-route corrections;
- status/progress/error integration;
- browser E2E/responsive/accessibility/security regressions;
- integration required by K8s, DR or Single-OS vertical slices.

Do not start another broad dashboard/navigation/terminology redesign without a concrete acceptance defect.

## 8. Research rule

Research deeply when a material architecture/version/provider decision is still open or a real blocker requires it.

Do **not** repeatedly re-audit frozen decisions before every implementation step.

For major unresolved decisions, verify exact CloudStack 4.22.1.1 source/docs, relevant upstream issues/PRs and exact provider/version behavior. Record the decision once, then execute it until new evidence materially invalidates it.

## 9. Engineering lifecycle

For meaningful changes:

```text
Current-state check
 -> focused design/decision only if needed
 -> implementation
 -> tests
 -> failure/edge-case validation
 -> live/E2E validation where applicable
 -> concise evidence/status update
 -> commit
```

Do not create a new large design or handoff document after every small commit. Persist durable evidence after meaningful milestones/vertical slices.

## 10. Evidence/status rules

Use only:

- `DESIGN_DEFINED`
- `SOURCE_COMPLETE`
- `CI_VERIFIED`
- `LIVE_VERIFIED`
- `PRODUCTION_CERTIFIED`
- `PARTIAL`
- `PENDING`
- `BLOCKED`
- `UNKNOWN`
- `NOT_TESTED`

A commit is not deployment proof. A build is not runtime proof. HTTP 200 is not whole-service proof. Documentation is not compatibility proof.

When evidence is missing, report the lower truthful status and the first unmet gate.

## 11. Security baseline

Treat customer/operator/external values as untrusted.

At minimum:

- preserve server-side authorization;
- no caller-controlled shell interpolation/eval;
- parameterized SQL and safe argv-based subprocess/command execution;
- validate files, paths, archives and symlinks;
- consider SSRF for fetch/integration features;
- verify TLS by default;
- finite timeouts/retries/concurrency;
- idempotency/deduplication for mutations;
- no invented cryptography;
- do not expose secrets to untrusted PR/fork code;
- secret values never enter Git, browser code, normal logs or evidence.

For detailed trust-boundary work, read `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`.

## 12. Live validation

Rocky Linux 9 remains the primary runtime acceptance target for LayerSentry V1.

Source/CI validation is necessary but insufficient for runtime-affecting work. Use the authorized runner/lab path and preserve exact source commit, artifact/workflow identifiers, target scope and assertions.

For Backup/DR/storage, validate exact storage/provider behavior and real restored data. For Kubernetes/Data Services, include destructive data-safety, node replacement, storage, networking, upgrade/rollback and air-gap tests where the release claims them.

If live validation is unavailable, keep the status below `LIVE_VERIFIED`.

## 13. Continuity and concurrency

Repository/workflow/live evidence overrides chat memory and stale handoffs.

Before mutation, inspect in-flight operations when duplicate execution could corrupt results. After a timeout/refresh, observe the exact operation before retrying.

Parallel source work is allowed only with clean ownership. Serialize conflicting deployments, storage/network/DR mutations and operations on the same target.

## 14. Progress model

Measure progress by customer-operable vertical slices, not commit count or line count.

Priority proofs:

1. VM-native PostgreSQL through Go + Ansible;
2. one complete RKE2 cluster lifecycle;
3. Kubernetes PostgreSQL DBaaS with backup/PITR;
4. one complete APaaS lifecycle;
5. two-point native CloudStack DR recovery with exact guest-data verification.

Expand provider/catalog breadth only after the corresponding vertical slice works.
