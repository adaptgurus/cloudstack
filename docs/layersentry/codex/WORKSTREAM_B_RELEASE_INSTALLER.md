# LayerSentry Workstream B — Release / Installer / Build

**Default state:** `DORMANT_MILESTONE_GATED`  
**Default owner:** ChatGPT unless explicitly reassigned  
**Purpose:** promote an exact artifact safely; not a standing parallel Codex stream

## 1. Activation

Activate this workstream only when:

- a module has an exact artifact ready for promotion;
- a release/signature/SBOM/provenance/installer defect blocks a vertical slice;
- an N-1 -> N upgrade/recovery gate is being executed.

Do not keep a permanent release agent active while product source is still changing.

## 2. Minimal startup

Read only:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. this file;
5. exact artifact/build/installer state being promoted.

Read `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`, secure-engineering policy, or a module specialist context only when the current promotion gate requires it.

## 3. File fence

Writable only for the assigned release milestone:

- LayerSentry build/release/installer tooling;
- product-artifact CI/release workflows;
- manifest/digest/SBOM/provenance/signature tooling;
- build-only UI production settings when directly required;
- signed carrier/import/update mechanics.

Do not edit customer UI feature source, K8s lifecycle/controller source, Single-OS provider logic, DR orchestration or CloudStack core merely to make release packaging easier. Hand those defects to their module owner.

## 4. Current V1 release model

Current V1 uses one logical signed platform carrier:

```text
layersentry-platform-<release>.iso
```

It may contain platform plus optional service artifacts. Bundled content is `AVAILABLE`, not installed. Flux installs selected Kubernetes packages.

Do **not** reintroduce the historical two-bundle K8s/Data Services execution model.

## 5. Required release properties

As applicable to the exact milestone:

- pinned source/version/build inputs;
- clean deterministic build property defined and tested;
- immutable artifact digest;
- SBOM/provenance;
- signature/trust verification before mutation;
- production source maps disabled unless explicitly intended;
- no target-side production UI compilation;
- manifest compatibility preflight;
- fail-closed integrity/tamper behavior;
- idempotent install/resume/repair where defined;
- atomic activation or proven equivalent;
- rollback/recovery classification;
- no committed signing/private credentials;
- license/NOTICE and redistribution checks.

K8s/Data Services versions come from the exact Workstream-E release candidate/compatibility evidence; release tooling does not invent its own tuple.

## 6. Upgrade milestone

For N-1 -> N qualification, preserve exact source/artifact/DB/schema/provider compatibility, backups/checkpoints, interruption/resume, post-upgrade regression and the documented rollback boundary. Do not promise unsupported automatic downgrade after incompatible schema changes.

## 7. Handoff

Report exact source/artifact, builder/workflow identity, checks executed, trust/digest/SBOM state, installer/rollback state, unresolved promotion blocker and next gate. Do not edit unrelated modules or create another master context.
