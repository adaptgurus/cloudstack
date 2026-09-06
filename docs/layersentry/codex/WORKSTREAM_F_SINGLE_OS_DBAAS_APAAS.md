# Codex Workstream F — Single-OS DBaaS / APaaS

## Mission

Implement and validate the **VM-native Single-OS LayerSentry DBaaS/APaaS path** governed by:

`docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`

This workstream is deliberately separate from Workstream E's Kubernetes/CAPI/RKE2 DBaaS/APaaS/Streaming architecture.

It owns software lifecycle **inside CloudStack-provisioned Rocky Linux 9 guests**. It does not own Kubernetes, CAPI, CAPC, CAPRKE2, RKE2, Kubernetes operators, Flux package reconciliation or the Kubernetes DBaaS/APaaS lifecycle.

## Startup

Read, in order:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. `docs/layersentry/LAYERSENTRY_SINGLE_OS_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`
5. `docs/layersentry/LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`
6. this file
7. release/debugging/upgrade specialist documents only when needed.

Fetch the actual current integration branch and inspect current source/runtime evidence before editing. Work in an isolated worktree/branch.

## Non-overlap boundary with Workstream E

Workstream F and Workstream E may share only clean platform contracts such as:

- CloudStack native APIs;
- tenant/project/RBAC identity;
- common LayerSentry UI shell/design language;
- approved secrets infrastructure;
- audit/events/status vocabulary;
- release signing/SBOM/provenance infrastructure;
- common observability presentation when evidence remains distinguishable.

They must **not** share or merge:

- lifecycle controller/state machine;
- guest engine/provider state with Kubernetes operator state;
- topology/job state;
- Kubernetes CAPI/CRD/operator objects;
- package reconciliation authority;
- runtime certification evidence from different targets.

A request must explicitly resolve to one deployment model. Never silently send a Single-OS request into Kubernetes or a Kubernetes DBaaS request into the guest-engine path.

## Primary ownership

Expected F-owned areas include:

- `layersentryd` guest lifecycle engine and service packaging;
- schema-versioned guest configuration;
- durable operation state/journal/idempotency locking;
- product provider/manifests;
- safe install/configure/upgrade/repair/uninstall lifecycle;
- Single-OS guest hardening assets/tests;
- provider-specific storage/mount/network preflight inside the guest;
- secret-reference integration;
- package/repository verification;
- residue/cleanup audits;
- one-VM Hyper-V acceptance automation/evidence for this workstream;
- module-specific support bundle/diagnostics.

Do not modify CloudStack Java/backend/database/KVM core merely to make a guest lifecycle workflow easier.

## Current acceptance envelope

Until the owner changes the Single-OS master context, the workstream's live acceptance environment is exactly:

- one disposable Hyper-V Generation 2 VM;
- 2 vCPU;
- 2048 MB static RAM;
- Dynamic Memory OFF;
- Rocky Linux 9.

Do not create a second VM under this workstream to fake cluster acceptance.

Local processes/mocks/network namespaces can validate parsing, transaction/error and connectivity logic, but they are not proof of real multi-node HA/quorum/replication/failover.

A product whose supported minimum resources exceed this envelope is `BLOCKED`/`NOT_TESTED` for live install on this lab; do not weaken the product or OS to force it through.

## Security invariants

- SELinux Enforcing; no `setenforce 0` workaround.
- firewalld active/default-deny with explicit management/product rules.
- root password SSH login disabled for production images.
- no `curl | bash`, unverified remote install scripts, arbitrary URLs or `eval` as product execution boundary.
- safe argv/subprocess invocation; do not interpolate untrusted configuration into shell strings.
- canonical path/symlink safety.
- secrets by references, never durable plaintext in config/log/evidence.
- package/repository signature and TLS verification.
- bounded timeouts/retries/logs/cache/concurrency.
- operation UUID/idempotency key and exclusive lifecycle lock for mutations.
- systemd sandboxing/least privilege as strongly as compatible with the provider.
- rollback must not silently disable security controls.

The existing `tools/layersentry/single-os/rocky9-hardening` implementation is source that must be reviewed/tested; its presence is not `LIVE_VERIFIED` evidence.

## Lifecycle contract

Provider operations must be deterministic and transactional:

```text
preflight
 -> plan
 -> exact version resolve/pin
 -> checkpoint where supported
 -> install/configure
 -> health validate
 -> commit durable state/evidence
```

Supported operations may include:

- install;
- configure;
- provider-specific initialize/join;
- health/status;
- upgrade/patch;
- repair/reconcile;
- uninstall;
- rollback/recover.

Cluster-specific semantics remain provider-specific. Generic `master`/`replica` labels are not enough to certify a database topology.

## Required delivery order

### F0 — engine/security foundation

- schema and validation;
- operation state model;
- idempotency/locking;
- secret-reference boundary;
- safe filesystem/subprocess utilities;
- hardened systemd packaging;
- repository/package verification contract;
- unit/negative/security tests.

### F1 — one representative standalone provider

Choose one product that fits the lab resource envelope and implement:

- plan;
- install;
- health;
- restart/reboot recovery;
- same-line patch upgrade if supported;
- injected failure/recovery;
- uninstall/residue audit.

Do not claim all products supported because one provider works.

### F2 — storage/mount and provider matrix

- CloudStack-provisioned disk identity/mount mapping;
- filesystem/LVM behavior where applicable;
- resize/reconcile policy;
- product-specific path/ownership/permissions;
- multiple disk/mount plans;
- backup/recovery integration contract.

### F3 — cluster-provider planning

With the one-VM restriction, implement/test only schema, planning, peer-validation and safe error paths using mocks/local isolation. Real cluster bootstrap/HA remains `NOT_TESTED` until a separately approved multi-VM environment exists.

### F4 — release/upgrade/air-gap

- signed offline package/repo contract;
- exact version/provenance record;
- update/rollback/residue behavior;
- deny-all-egress test for any offline claim;
- no arbitrary Internet dependency.

## Testing minimum

Follow the Single-OS master context test matrix, including:

- exact VM resource proof;
- Rocky 9 proof;
- SELinux/firewalld/SSH hardening verification;
- malformed/unsupported config negative tests;
- path/symlink/shell-injection negative tests;
- exact version resolution/pinning;
- idempotent rerun;
- restart/reboot recovery;
- failure/rollback;
- concurrent-operation lock;
- uninstall/residue audit;
- secret/log redaction;
- resource/cache growth;
- final security revalidation.

No live assertion is valid without exact artifact/target evidence.

## Evidence/status rule

- design text: `DESIGN_DEFINED` only;
- completed source + source tests: `SOURCE_COMPLETE` only where actually proven;
- reproducible automation: `CI_VERIFIED` only with CI evidence;
- one-VM standalone behavior: `LIVE_VERIFIED` only from actual authorized target evidence;
- real multi-node HA/replication/failover: `NOT_TESTED`/`PARTIAL` under current lab constraint;
- `PRODUCTION_CERTIFIED` only after provider-specific security, backup/recovery, upgrade, rollback, resource/performance and supported-topology evidence.

## Coordination

- **A:** shared UI components and explicit deployment-mode selection.
- **B:** signed artifacts/repos/installer/update mechanics.
- **C:** independent security/negative validation.
- **D:** global DR/HA/upgrade proof when Single-OS workloads enter those programs.
- **E:** no shared lifecycle implementation; coordinate only common CloudStack/UI/security/release contracts.

## Handoff

Report:

- repository/branch/base/final commit;
- exact Single-OS provider/engine scope;
- files changed;
- CloudStack-core impact YES/NO;
- source/tests actually run;
- live target evidence if any;
- hardening/security exceptions;
- operation/rollback/retry state;
- resource observations;
- known blockers;
- next evidence gate.

Do not self-merge or edit the shared Progress Ledger unless explicitly assigned.
