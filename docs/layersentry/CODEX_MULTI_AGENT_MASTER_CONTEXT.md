# LayerSentry V1 — Multi-Agent Context

> **Purpose:** concise policy for parallel Codex execution. Detailed base operator commands/prompts live in `docs/layersentry/CODEX_4_AGENT_RUNBOOK.md`. Stable product/security/evidence rules live in `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`. Current completion state lives only in `LAYERSENTRY_PROGRESS_LEDGER.md`.

This file deliberately contains no current HEADs, run IDs, artifact IDs, live IPs or task-status duplication.

## Mandatory authority

Each agent must read:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. its assigned workstream file under `docs/layersentry/codex/`.

Workstream E also reads `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`. Any A/B/C/D task touching that module reads the same specialist file before editing.

Use `CODEX_4_AGENT_RUNBOOK.md` for the established base worktree setup pattern. Workstream E uses the same one-agent/one-worktree isolation rule and may be launched as an additional isolated workstream; the historical “4-agent” filename does not exclude E from the product scope.

## Workstream ownership

- **A — UI / Self-service:** customer product profile, role-aware navigation/dashboards, terminology, VM/CKS/Bucket/Site UX and shared UI components. K8s/Data Services lifecycle logic remains E-owned.
- **B — Release / Installer / Build:** CI artifacts, build settings, installer/resume/rollback, manifest/SBOM/provenance/digest/signature, coordinating with E for K8s/Data Services bundles.
- **C — Security / Validation:** RBAC/negative tests, SELinux/firewall/package/update/snapshot/Kubernetes security and evidence tooling.
- **D — DR / HA / Upgrade:** runner/Hyper-V discovery, DR/HA/upgrade proof automation and evidence, including global framework used by E workload-specific tests.
- **E — K8s / DBaaS / APaaS / Streaming:** CAPI/CAPC/CAPRKE2/RKE2, central Flux, module storage/network/VIP/WAF, DBaaS/OpenEverest/Redis, APaaS/OpenBao/Harbor, Strimzi/Kafka and GPU worker-pool integration.

Do not modify another workstream's primary files without coordination. If cross-workstream work is required, document the dependency rather than silently creating overlapping edits.

## Git isolation

- one writable Git worktree per agent;
- one branch per worktree;
- all branches start from the actual fetched integration HEAD;
- never force-push or rewrite another agent's branch;
- agents do not self-merge into the shared integration branch unless explicitly assigned;
- only the integration/lead path updates the shared progress ledger by default.

## Live-environment isolation

Parallel reasoning/editing is allowed. Conflicting live mutations are not.

Serialize:

- deployments to the same target;
- VM/network/storage operations;
- Kubernetes cluster/worker/storage/VIP operations on the same target;
- backup/recovery/DR operations;
- upgrades/reboots;
- heavy builds that would contend for the same runner capacity.

Every R3/R4 operation follows the canonical change-risk and standing disposable-test rules: current-state inspection, exact-target verification, in-flight operation check, appropriate checkpoint/rebuild strategy and immediate evidence capture.

## Integration order

For the established base product, preserve the proven B -> A -> C -> D dependency logic when those workstreams overlap.

For the Kubernetes/Data Services module, E is integrated in dependency-aware slices:

1. B provides/validates release-artifact mechanics needed by E;
2. E implements one vertical module slice;
3. A integrates shared/customer-facing UI where needed;
4. C adds/revalidates security/RBAC/negative gates;
5. D adds/revalidates global upgrade/HA/DR evidence where applicable.

Independent, non-overlapping changes may be reviewed in another order when the integration lead documents why.

## Agent handoff

Every agent reports exact base/final commits, files changed, core impact, checks actually executed, runtime mutations, evidence, known limitations, retry/rollback state and next evidence gate.

No agent may promote status from model confidence, documentation support or another agent's unreviewed claim.
