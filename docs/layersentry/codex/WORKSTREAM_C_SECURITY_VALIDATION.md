# LayerSentry Workstream C — Security / Validation

**Default state:** `DORMANT_MILESTONE_OR_DEFECT_GATED`  
**Default owner:** ChatGPT unless explicitly reassigned  
**Purpose:** independent security/negative evidence, not a standing implementation stream

## 1. Activation

Activate this workstream only when:

- a concrete trust-boundary/security defect blocks a vertical slice;
- a module reaches a security/negative-test milestone;
- an exact release artifact is ready for security promotion testing.

Do not keep a permanent security agent active while product source is still changing.

## 2. Minimal startup

Read only:

1. `/AGENTS.md`;
2. `LAYERSENTRY_EXECUTION_CONTRACT.md`;
3. `LAYERSENTRY_PROGRESS_LEDGER.md`;
4. this file;
5. exact module/artifact/failure being validated.

Read the secure-engineering policy or specialist architecture only for the current trust boundary. Do not load every module context.

## 3. File fence and independence

Normal writable scope:

- security/negative test assets specifically assigned to the milestone;
- redacted security evidence;
- narrow validation tooling that does not become a second product implementation.

Do not edit UI, K8s lifecycle, Single-OS provider, DR, bootstrap/hypervisor or release implementation merely to make a test pass. If validation proves a product defect, hand the exact failure to the owning module.

Do not weaken SELinux, firewalld, RBAC, NetworkPolicy, signature checks or tests to obtain a green result.

## 4. Core validation areas

As applicable to the exact module/release:

- server-side RBAC/direct-route/direct-API negatives;
- tenant/project/object ownership boundaries;
- feature/prerequisite gating;
- secret redaction and credential scope;
- SELinux Enforcing behavior and reviewed AVC handling;
- firewalld/default-deny traffic matrix;
- repository/update lockdown;
- safe paths/archive/symlink handling;
- SSRF/TLS boundaries for external providers;
- snapshot/storage destructive-safety checks;
- K8s CAPI/Flux/kubeconfig/provider-secret/project isolation;
- CSI Machine/PVC deletion/resize/project safety;
- package/artifact digest/signature/trust negatives;
- support/evidence sanitization.

Use existing module fixtures whenever possible rather than building duplicate controllers/providers solely for testing.

## 5. Evidence rule

A security result records exact source/artifact, target, role/project, preconditions, action, expected result, actual result, relevant bounded logs/evidence and cleanup state.

A source test is not runtime proof. A green UI state is not authorization proof. A single failover/backup test is not full DB/data-integrity certification.

Use project statuses honestly: `SOURCE_COMPLETE`, `CI_VERIFIED`, `LIVE_VERIFIED`, `PARTIAL`, `BLOCKED`, `NOT_TESTED`, etc., only for the exact scope evidenced.

## 6. Handoff

Report exact module/artifact tested, security cases executed, failures handed to module owners, evidence, untestable items and next security gate. Do not cross-edit another module or create broad architecture documents.
