# LayerSentry V1 — Evidence-Driven Debugging Runbook

## Purpose

This is the canonical debugging/triage method for ChatGPT, Codex and human engineers working on LayerSentry. It defines **how to diagnose** failures without guessing, weakening controls, or turning a symptom into an unverified root-cause claim.

Stable product/security rules remain in `LAYERSENTRY_SUPER_MASTER_CONTEXT.md` and `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`. Current failures, commits, workflow IDs and runtime observations belong in `LAYERSENTRY_PROGRESS_LEDGER.md` or task evidence.

This runbook is read on demand when troubleshooting, investigating regressions, reviewing failed CI/live deployments, or diagnosing an unknown production-like state.

---

## 1. Debugging invariant

**Do not optimize for the fastest plausible fix. Optimize for the smallest evidence-backed explanation and the smallest safe correction.**

A hypothesis is not a fact. A workaround is not a root-cause fix. A service restart is not proof that the underlying defect is resolved.

For every material failure distinguish:

- **symptom** — what was observed;
- **scope** — which target/release/role/workflow is affected;
- **reproduction** — whether it can be repeated safely;
- **first known bad / last known good** — when available;
- **hypotheses** — ranked possible causes;
- **evidence** — observations that support/reject each hypothesis;
- **root cause** — only after evidence isolates it sufficiently;
- **fix** — smallest supportable change;
- **regression test** — proves the defect does not silently return;
- **runtime validation** — required before using `LIVE_VERIFIED`;
- **remaining uncertainty** — explicitly stated.

---

## 2. Read-only first

Start with R0 discovery wherever possible.

Before changing source or runtime, capture:

```text
repository
branch
HEAD
worktree status
release/artifact identity
intended target
service/process state
relevant workflow/job state
error timestamp
correlation/job/request ID
last known-good evidence
```

Do not reboot, restart, reinstall, change firewall/storage/network/DB state, delete resources, clear caches, rotate configs, or rerun a mutating workflow merely to “see if it helps” before the initial evidence snapshot is preserved.

If another operation may already be running, inspect it before starting another.

---

## 3. Standard diagnostic loop

Use this loop for every non-trivial defect.

### Step 1 — Define the failure precisely

Write one falsifiable sentence:

`Expected <behavior>; observed <behavior> on <exact target/release/role> at <time/evidence>.`

Avoid vague labels such as “CloudStack broken”, “network issue”, or “UI not working”.

### Step 2 — Classify the layer

Initial layers:

1. source/build;
2. release/artifact/provenance;
3. installer/bootstrap;
4. browser/UI/runtime config;
5. authentication/RBAC/API;
6. CloudStack management/async job;
7. KVM/libvirt/agent;
8. network/System VM/VR;
9. storage/image store/B&R repository;
10. database;
11. CKS/CSI/CNI;
12. object store;
13. HA/DR/upgrade;
14. host/Hyper-V/lab infrastructure.

A symptom may cross layers, but begin with the narrowest layer supported by evidence.

### Step 3 — Preserve exact evidence

Capture only relevant, bounded evidence with timestamps and secret redaction:

- exact command/API/action;
- exit code/HTTP status/async job result;
- relevant log window, not an unbounded log dump;
- source/artifact hash;
- config values that materially affect the failure;
- before/after state for mutations;
- browser console/network request for UI defects when needed;
- screenshot only as supplemental evidence.

### Step 4 — Reproduce safely

Prefer a deterministic reproduction on disposable/staging resources.

If the action is R3/R4 or destructive, do not reproduce on production-like data unless explicitly authorized and a recovery path exists.

### Step 5 — Establish last-known-good / first-known-bad

Use Git history, release manifests, workflow artifacts and durable runtime evidence.

Do not assume the most recent commit caused the failure merely because it is recent.

### Step 6 — Rank hypotheses

Maintain a short table:

```text
H1 | hypothesis | evidence for | evidence against | next discriminating check
H2 | ...
H3 | ...
```

Prefer checks that distinguish multiple hypotheses at once.

### Step 7 — Change one causal variable at a time

Avoid bundles of unrelated fixes. If three things are changed simultaneously and the problem disappears, root cause remains uncertain.

### Step 8 — Validate the proposed cause

A strong root-cause statement should explain:

- why the observed failure occurred;
- why the failure started when it did;
- why the proposed evidence matches;
- why plausible alternatives were rejected.

### Step 9 — Implement the minimum safe fix

Preserve CloudStack core when an overlay/config/API/service fix is sufficient. Do not weaken security controls simply to restore function.

### Step 10 — Add regression coverage

For a software defect, add the narrowest useful automated test. For environment/config defects, add preflight/health/validation evidence so recurrence becomes visible.

### Step 11 — Validate through the correct gates

Use the project's governed status model:

- source fix only -> at most `SOURCE_COMPLETE`;
- automated checks passed -> `CI_VERIFIED` only for those checks;
- exact artifact deployed and assertions pass -> `LIVE_VERIFIED` for that scope;
- production release gates -> `PRODUCTION_CERTIFIED` only when all applicable gates pass.

### Step 12 — Record residual risk and next gate

Do not close a debugging record with hidden uncertainty.

---

## 4. No-blind-retry rule

Retries can hide defects and create duplicates.

Before retrying a timed-out or failed mutation:

1. inspect authoritative state;
2. determine whether the original request executed partially/fully;
3. identify job/resource IDs;
4. confirm idempotency or deduplication behavior;
5. retry only when safe.

This is mandatory for VM creation, artifact deployment, backup, recovery, network/storage changes, update/upgrade, DR operations and any asynchronous CloudStack mutation.

---

## 5. No-random-restart rule

A restart/reboot may be a diagnostic experiment only when:

- current state/evidence is captured first;
- the restart tests a stated hypothesis;
- blast radius is understood;
- rollback/recovery is known;
- post-restart evidence is captured.

Do not declare the defect fixed merely because restart temporarily removes the symptom.

---

## 6. Source/build debugging

Check in this order:

1. clean/dirty worktree and exact HEAD;
2. dependency lock/toolchain identity;
3. changed-file boundary;
4. syntax/type/lint/unit errors;
5. deterministic reproduction from clean checkout;
6. generated files/source-map/placeholder/terminology policy gates;
7. upstream-vs-LayerSentry delta if the problem follows an upstream rebase.

Use `git diff`, `git log`, `git blame`, targeted search and narrow tests before large refactors.

Do not “fix” a build by disabling failing tests, relaxing compiler/linter/security settings, or adding broad dependency upgrades without proving necessity.

---

## 7. Release/artifact debugging

Always distinguish **source correctness** from **artifact correctness**.

Verify:

- source commit recorded in manifest;
- builder/workflow identity;
- artifact digest;
- signature/trust verification result;
- SBOM/provenance presence when required;
- production source-map policy;
- artifact contents match expected LayerSentry branding/config and exclusions;
- deployment consumed the intended immutable artifact rather than rebuilding locally.

If source is correct but served behavior is wrong, inspect artifact/deployment/runtime config before editing source again.

---

## 8. Installer/bootstrap debugging

Treat installer stages as a state machine.

For each failed stage capture:

- stage name/state marker;
- exact input inventory/config schema version;
- preflight results;
- exact artifact/repository/package versions;
- command/exit code/log window;
- mutations completed before failure;
- whether resume is safe;
- rollback/recovery path.

Do not rerun the full installer blindly. Resume from a proven idempotent boundary or recover to a known-good checkpoint.

A package-manager error must be diagnosed as repository metadata, dependency resolution, network/TLS, version compatibility, signature/trust or local state—not simply treated as “dnf failed”.

---

## 9. Browser/UI debugging

Separate UI symptoms into:

1. source/rendering;
2. built artifact/static assets;
3. runtime `config.json`/branding;
4. browser cache/service worker where applicable;
5. routing/navigation;
6. API request/response;
7. RBAC/permission;
8. provider/prerequisite feature gating.

Evidence can include browser console, network request/response metadata, route state and exact account/role.

Never infer authorization from hidden menu entries. Test direct URL/API denial where security is involved.

If browser debugging requires full DevTools/CDP access, treat browser/customer session data as sensitive and use the minimum access necessary.

---

## 10. CloudStack API / asynchronous-job debugging

For every mutating API call preserve:

- API/action name;
- authenticated role/account context;
- target resource IDs;
- request ID/job ID;
- immediate response;
- terminal async-job result;
- relevant management log correlation.

A client timeout does not mean the operation failed. Query the job/resource before retrying.

For API failures, distinguish:

- authorization;
- invalid state transition;
- missing prerequisite/provider/offering;
- scheduler/capacity failure;
- storage/network/backend failure;
- agent failure;
- database/management issue.

Do not bypass CloudStack APIs through direct DB writes to “repair” state unless a documented recovery procedure explicitly requires it.

---

## 11. Management-server debugging

Collect bounded evidence for:

- process/service state;
- listening endpoints;
- management DB connectivity;
- relevant application logs around the event;
- async-job backlog/failure;
- System VM/agent communication relevant to the symptom;
- load-balancer/VIP state when HA topology is involved;
- exact management version/release manifest.

Do not interpret HTTP 200 alone as management-plane health.

In multi-manager cases determine whether the defect is node-local, shared-DB/shared-config, LB persistence/routing, or agent-manager distribution before changing topology.

---

## 12. KVM/libvirt/agent debugging

Layer the checks:

1. host reachability/OS state;
2. KVM capability and libvirt process;
3. CloudStack agent state/version;
4. management-agent communication;
5. libvirt security/certificate behavior;
6. VM/domain state;
7. bridge/VLAN/network state;
8. storage path/mount/multipath state;
9. migration-specific source/destination compatibility.

Do not weaken libvirt authentication/TLS/firewall/SELinux globally to make one lab test pass.

For live migration compare source and destination CPU/libvirt/QEMU/network/storage prerequisites and inspect both ends.

---

## 13. Network/System-VM debugging

Avoid the label “network problem” until the layer is isolated.

Trace the path explicitly:

```text
client/workload
 -> guest interface
 -> bridge/VLAN/security policy
 -> virtual router/System VM where applicable
 -> physical/uplink path
 -> gateway/firewall/NAT/LB
 -> destination
```

Capture relevant addressing, routes, neighbor/ARP state, firewall/nftables rules, bridge/VLAN membership and packet evidence only as needed.

Check configuration ownership before changing rules: CloudStack-managed network state must not be “fixed” with ad-hoc manual changes that the orchestrator later overwrites.

For `firewalld`/SELinux-related failures, isolate the exact denied flow/AVC rather than disabling the control.

---

## 14. Storage/debugging

Classify the storage path first:

- Primary Storage;
- Image/Secondary Storage;
- NFS/CIFS/Ceph;
- block/multipath/SAN profile;
- backup repository.

Check:

1. control-plane object/config state;
2. host reachability/mount/session state;
3. permissions/security context;
4. capacity/free space/inodes;
5. latency/error state;
6. CloudStack/agent job error;
7. underlying storage health evidence if available.

Do not use destructive filesystem or block-device repair commands without R4 authorization and a proven disposable/recoverable target.

For snapshot/restore incidents account for the documented KVM Instance/VM-snapshot vs Volume-snapshot conflict before testing recovery.

---

## 15. Database debugging

Start read-only.

Check:

- connectivity from the intended management node;
- exact DB/version/topology;
- replication/failover state using reliable DB-native evidence;
- connection exhaustion/timeouts/deadlocks when relevant;
- storage/disk-space state;
- recent schema/upgrade changes;
- CloudStack application errors correlated to DB events.

Do not promote historical CloudStack replication documentation into proof that the current LayerSentry DB topology is healthy.

Direct mutation of CloudStack tables is not a normal troubleshooting technique. Schema repair/restore/failover is R4 and requires an approved recovery procedure.

---

## 16. CKS / CSI / CNI debugging

Separate:

- CloudStack CKS lifecycle/API;
- template/ISO/version prerequisites;
- Kubernetes control-plane/node health;
- CNI/networking;
- CSI/CloudStack volume provisioning;
- StorageClass mapping from Disk Offerings;
- pod metadata-isolation policy;
- DNS/registry/image-pull/internet or air-gap dependencies.

Do not diagnose every cluster-create failure as “Kubernetes issue”. Preserve the CloudStack async job result and then isolate the Kubernetes layer.

For air-gap claims, explicitly prove all external dependency paths are absent/controlled; do not infer from having a binaries ISO.

---

## 17. Object-storage / Backup & Recovery debugging

For object storage distinguish:

- provider configuration/reachability;
- credentials/authorization;
- account quota;
- bucket API behavior;
- object data path.

For B&R distinguish:

- provider/repository configuration;
- repository mount/reachability;
- backup offering/policy assignment;
- source VM metadata/state;
- backup job result;
- repository data presence;
- destination-zone mappings;
- restore copy/import/boot stages.

For cross-zone recovery preserve the source-instance-record retention dependency and destination network/storage mappings. Do not delete/purge source metadata during troubleshooting unless the negative test explicitly requires disposable data.

---

## 18. HA / DR / upgrade debugging

These are R3/R4 domains and require stronger evidence.

### HA

Separate:

- management service availability;
- LB/VIP behavior;
- agent-to-manager connectivity;
- database availability/consistency;
- KVM host/guest HA;
- OOBM/fencing.

A management-node reboot test does not prove DB failover or physical fencing.

### DR

Separate backup success, repository replication, destination mapping, restore, guest boot, network/application validation, source fencing and traffic switching. Only claim the stages actually tested.

### Upgrade

Record source release, target release, preflight, backup/checkpoint, first mutation, schema result, management-node sequencing, KVM-agent path, post-upgrade checks and rollback class.

Do not attempt an unsupported downgrade merely to clear an upgrade failure.

---

## 19. Host / WSL / runner debugging

The Windows/WSL/Codex workstation and GitHub self-hosted runner are development/control infrastructure, not LayerSentry runtime truth.

For workstation/runner problems distinguish:

- WSL distribution state;
- PATH/tool installation;
- Codex authentication/connectivity;
- Git/GitHub authentication;
- runner service state;
- Hyper-V PowerShell permissions;
- local CPU/RAM/disk pressure;
- repository/worktree state;
- network reachability to GitHub/lab.

Do not reinstall tools before checking the existing binary, PATH/config and authentication state.

---

## 20. Stop conditions / escalation

Stop mutation and preserve evidence when:

- evidence contradicts the assumed target/release;
- the operation may already be in flight;
- rollback/recovery is not understood for an R3/R4 action;
- the only proposed “fix” is disabling a security/integrity control;
- data-loss risk is unclear;
- a production-like DB/storage/network change would be experimental;
- a suspected upstream defect requires CloudStack-core modification without the core-change exception gate;
- the lab cannot prove the claimed hardware/site property.

Use `BLOCKED`/`UNKNOWN` rather than escalating risk to obtain a green result.

---

## 21. Debug record template

Use this for material incidents/regressions:

```text
DEBUG_ID=
TIME_WINDOW=
REPOSITORY=
BRANCH=
HEAD=
RELEASE_OR_ARTIFACT=
TARGET=
RISK_CLASS=R0|R1|R2|R3|R4
EXPECTED=
OBSERVED=
REPRODUCTION=
LAST_KNOWN_GOOD=
FIRST_KNOWN_BAD=
CORRELATION_OR_JOB_IDS=
EVIDENCE=
HYPOTHESES=
DISCRIMINATING_CHECKS=
ROOT_CAUSE_STATUS=UNKNOWN|SUPPORTED|CONFIRMED
ROOT_CAUSE=
FIX=
CHECKS_RUN=
LIVE_VALIDATION=
REGRESSION_TEST=
ROLLBACK_OR_RETRY_STATE=
RESIDUAL_RISK=
NEXT_GATE=
```

`ROOT_CAUSE_STATUS=CONFIRMED` requires evidence sufficient to explain the symptom and reject material alternatives; otherwise use `SUPPORTED` or `UNKNOWN`.

---

## 22. Definition of a debugged defect

A defect is not considered fully debugged merely because the symptom disappeared.

A strong closure has:

- a reproducible or otherwise evidence-supported failure;
- a supported/confirmed root cause;
- a minimal correction;
- relevant automated or durable regression guard;
- CI validation where applicable;
- live validation when the defect affected runtime behavior;
- no hidden security weakening;
- recorded limitations/residual risk;
- durable evidence in Git/workflow/artifact/ledger as appropriate.

If live validation was not performed, report the source/CI state accurately and leave runtime status unpromoted.
