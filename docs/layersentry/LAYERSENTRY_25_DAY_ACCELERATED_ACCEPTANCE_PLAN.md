# LayerSentry V1 — 25-Day Accelerated Acceptance Plan

**Status:** `DESIGN_DEFINED`

**Calendar:** 25 consecutive days; Day 1 starts only after the Day 0 gate

**Baseline:** Apache CloudStack 4.22.1.1, KVM-first, Rocky Linux 9

This is the fastest defensible path to a bounded release candidate. It is not implementation evidence or a promise of `PRODUCTION_CERTIFIED`. Parallel coding cannot eliminate serial infrastructure changes, replication, failure observation, recovery or soak time.

## 1. Day 25 target and bounded scope

Target deliverables:

- verified immutable UI/release artifact; no npm build on Management VMs;
- fresh install, resume, repair, staged promotion and tested rollback;
- KVM-only customer profile, role-aware UI, direct-API RBAC negatives and simplified VM flow;
- feature-gated CKS, Bucket and Backup & Recovery surfaces;
- automated configuration of three pre-provisioned Management VMs and two LB VMs;
- integration and evidence for an operator-built three-member DB topology;
- native B&R, one older recovery point and cross-Zone recovery;
- minimum two-Site DR: mapping, isolated Test Recovery, planned failover, reverse replication and failback;
- supported N-1 -> N upgrade, interruption/resume and recovery evidence;
- Rocky 9 SELinux, firewalld, repository, browser and support-evidence checks.

Conditional/deferred unless included before Day 1: DBaaS/APaaS (V1 excluded), multiple DR providers, storage-native low-RPO replication without an installed provider, automatic failover without witness/exclusive lease/fencing, physical OOBM without hardware, arbitrary two-node survival, full air-gap CKS and scale beyond the tested matrix. Deferred items remain `PENDING`, `NOT_TESTED` or `BLOCKED`.

## 2. Day 0 infrastructure entry gate

| Requirement | Deadline | Proof | If absent |
| --- | --- | --- | --- |
| Current fetched CloudStack/runner branches and clean inventory | Day 0 | Git/worktree evidence | integration `BLOCKED` |
| Rocky 9 targets for 3 Management, 3 DB and 2 LB roles | Day 0 | OS/capacity/NIC/failure-domain inventory | topology certification `BLOCKED` |
| Two reachable CloudStack Sites/Zones with KVM, network and storage capacity | Day 0, healthy Day 2 | read-only API/host/provider inventory | DR `BLOCKED` |
| Serialized runner path and runtime-only credentials | Day 0 | redacted auth probes | live work `BLOCKED` |
| DNS/VIP and API/agent traffic paths | Day 1 | topology/connectivity evidence | LB HA `BLOCKED` |
| DB version/topology decision and stable writer endpoint | decision Day 1, ready Day 4 | compatibility rationale and health output | DB/Management HA `BLOCKED` |
| Backup repository reachable from both Sites | Day 2 | provider/mount/capacity proof | B&R/DR `BLOCKED` |
| Witness/fencing if automatic failover is requested | Day 3 | independent placement and executable test plan | automatic failover removed |
| N-1 artifact and supported upgrade basis | Day 3 | exact manifest/packages/path | upgrade `BLOCKED` |

Secrets and live addresses stay in approved runtime stores and volatile evidence, never this document.

## 3. Parallel execution and integration

| Stream | Parallel responsibility |
| --- | --- |
| B | build, artifact/manifest/SBOM/provenance/signing, installer, Management/LB automation, upgrade |
| A | KVM profile, dashboards, VM/CKS/Bucket/B&R UX, browser/accessibility/availability states |
| C | RBAC/API/tampering, SELinux/firewalld/repositories, redaction and artifact negatives |
| D | inventory, B&R, DB/Management/LB failures, two-Site DR, upgrade and timing evidence |

Research, source, unit tests and documentation run in isolated worktrees. The root reviews and integrates B -> A -> C -> D. One named live-test controller serializes every shared-environment deployment, restart, VM/network/storage/DB mutation, backup/restore, upgrade, failover/failback and fencing action.

## 4. Day-by-day critical path

| Day | Critical work | Exit gate |
| --- | --- | --- |
| 1 | Freeze release scope; fetch/inventory source, runner, Rocky targets, Sites/providers and N-1. Resolve DB validation matrix, not by assumption. | scope and topology `DESIGN_DEFINED`; blockers named |
| 2 | B finalizes build/installer design; A/C finalize UI/RBAC gaps; D proves second Site, repository and provider prerequisites read-only. | architecture review; unavailable prerequisites `BLOCKED` |
| 3 | Produce immutable UI artifact, digest, SBOM/provenance and signature tests. Fix one DR provider path. Finalize DB/rollback design. | artifact `CI_VERIFIED`; decisions `DESIGN_DEFINED` |
| 4 | Preflight/configure 3 Management + 2 LB targets idempotently. Operator finishes DB HA. Integrate KVM guards and API-negative tooling. | targets reachable; DB has 3 members/one writer endpoint |
| 5 | Connect one Management node to DB using supported path; preserve DB recovery checkpoint. Stage both LBs without advertising VIP. | single Management/API smoke and durable rollback |
| 6 | Add Management 2/3 serially; verify common DB identity, coordination, agent endpoint and reboot persistence. | all three healthy with exact configuration evidence |
| 7 | Activate dual-LB VIP; test UI/API, health removal, persistence/stickiness, agent path and LB rollback. | normal LB operation `LIVE_VERIFIED` |
| 8 | Stop each Management node independently; rolling restart; async-job and agent-reconnection tests. | one-Management-failure gate passes or remains `PARTIAL` |
| 9 | Operator-led DB member and primary-loss/election tests; CloudStack reconnection and Management restart during failover. | no observed corruption; otherwise `BLOCKED` |
| 10 | DB quorum loss, partition, rejoin, split-brain prevention, backup/full restore and repeated failover. | DB module at most `LIVE_VERIFIED`; recovery proven |
| 11 | Exact-candidate Rocky install: fresh/rerun/resume/repair, integrity failure and UI rollback. | installer `LIVE_VERIFIED`; no target npm build |
| 12 | SELinux enforcing, firewalld, package policy, artifact/archive tampering and secret-redaction negatives. | tested security matrix `LIVE_VERIFIED` or exceptions listed |
| 13 | Platform/Department/User/read-only UI, direct URL/API, object-ID and cross-domain/account negatives. | server-side RBAC matrix passes |
| 14 | KVM VM lifecycle, image/profile/network/volume/console and error states; Chrome + Firefox. | customer/VM workflow `LIVE_VERIFIED` |
| 15 | CKS/Bucket/B&R gates: prove enabled backend/API behavior or truthful unavailable state. | feature-by-feature evidence status |
| 16 | Native B&R backup/restore/data/schedule/retention/source-record negative tests. | native restore `LIVE_VERIFIED`; timings captured |
| 17 | Restore selected older point; validate data/application and required source-record retention. | old-point recovery passes with lineage |
| 18 | Cross-Zone recovery with explicit network/storage mappings and destination validation. | Backup DR `LIVE_VERIFIED`; RPO/RTO recorded |
| 19 | Exercise Site Pairing, provider capabilities, Protection Plan and Recovery Point Catalog for one provider. | no false `Protected` state; mappings/catalog pass |
| 20 | Isolated Test Recovery from non-current point; fenced network, collision checks, app validation and cleanup. | repeatable, source/production traffic unaffected |
| 21 | Planned failover: final point, ordered recovery, mappings, destination gates and controlled traffic switch. | success or DR remains `PARTIAL`; no auto claim |
| 22 | Reverse replication/failback; interrupt/resume, stale/corrupt point, mapping/capacity and replay negatives. | repeatable failback and unambiguous lineage |
| 23 | Supported N-1 -> N: preflight/backups/schema-aware sequence and full post-upgrade regression. | forward upgrade `LIVE_VERIFIED`; rollback class recorded |
| 24 | Interrupt upgrade at defined stages; resume/recovery; complete-Management-outage bootstrap and combined LB/Management failure. | independent rescue executable; failures block claim |
| 25 | Repeat highest-risk recovery/RBAC/tamper cases; resource/concurrency review; verify rollback state and evidence index. | exact module matrix and truthful release decision |

## 5. Management/LB automation contract

The fast path assumes eight VMs are pre-provisioned. Automation configures rather than builds a general VM provisioner. It must:

1. consume versioned inventory with roles/failure domains;
2. preflight Rocky version, capacity, time, DNS, ports, DB endpoint and release compatibility;
3. consume only verified immutable releases;
4. configure Management nodes serially using runtime secret injection;
5. generate both LB configurations from one reviewed template and preserve API/session/agent requirements;
6. stage, validate, checkpoint, promote and health-check before LB membership;
7. journal idempotent stages for resume, dry run and one-node repair;
8. fail closed on version drift, integrity failure, DB/schema uncertainty or no safe checkpoint;
9. provide an independent all-Management-down rescue procedure.

Rollback classes: UI switches to a previous verified artifact; Management package/config rollback is allowed only without incompatible DB change; schema failure restores matching DB/config/software; LB rollback restores the last validated configuration and VIP ownership.

## 6. Manual DB HA dependency and test gate

The operator owns DB installation, membership and topology mutations. LayerSentry owns compatibility preflight, JDBC behavior, observation, CloudStack tests, backup/restore and evidence. Exact 4.22.1.1 compatibility must be established from pinned documentation/source and live results; do not choose MySQL 8.0 or 8.4 only because a context mentions it.

Required tests: normal primary writes through the stable endpoint; one secondary loss/rejoin; primary loss/election and CloudStack reconnection; Management restart during failover; quorum-loss fail-closed behavior; partition and proof against dual writers; backup/full restore and PITR only if supported; repeated failover; latency/transaction integrity; exact upgrade/recovery path. Three members do not survive arbitrary two-member or two-failure-domain loss.

## 7. Minimum two-Site DR scope

Certify one provider path only:

1. prove native CloudStack B&R;
2. retain required source records and recover one older point;
3. recover cross-Zone with explicit mappings;
4. run isolated Test Recovery;
5. run planned failover, reverse replication and failback;
6. measure point age/data RPO/recovery RTO from durable timestamps;
7. test stale/corrupt points, missing mapping, capacity shortage, interruption and replay.

Automatic failover is excluded unless independent witness, exclusive lease and reliable fencing exist by Day 3 and pass WAN-partition, witness-loss, source-return and double-promotion tests. `ping failed -> start DR` is prohibited. Same-host/nested Sites can prove function, not physical independence.

## 8. Daily evidence and commit cadence

Every day ends with current-ref reconciliation, root review, proportionate tests, coherent signed-off commits, reviewed pushes, and redacted durable evidence containing exact source/artifact digest, target role, workflow/run/job/artifact IDs, assertions, mutations and rollback state. Update the Progress Ledger for volatile outcomes and the Knowledge Graph only for stable relationships. Failed tests remain evidence. HTTP 200, process state, a build or screenshot alone never promotes a module.

Statuses progress only with evidence: `DESIGN_DEFINED` -> `SOURCE_COMPLETE` -> `CI_VERIFIED` -> `LIVE_VERIFIED` -> `PRODUCTION_CERTIFIED`. Use `PARTIAL`, `PENDING`, `BLOCKED`, `UNKNOWN` or `NOT_TESTED` when appropriate.

## 9. De-scope/blocker rules

- No second Site by Day 2: DR `BLOCKED`; do not certify one-host simulation.
- No cross-Site backup repository by Day 2: B&R/old-point/cross-Zone gates `BLOCKED`.
- DB HA not healthy by Day 4: source/single-node work continues; control-plane HA, upgrade and certification `BLOCKED`.
- No witness/fencing by Day 3: automatic failover removed; planned failover may continue.
- No storage-native provider by Day 3: Backup DR only; no low-RPO/hot-replication claim.
- No N-1 artifact/path by Day 3: upgrade `BLOCKED`; same-version reinstall is not a substitute.
- Authorization, corruption, split-brain, signature-bypass or rollback critical defect stops affected mutation until fixed and repeated.
- Failed Day 10 control-plane gate uses Days 11–12 for remediation; DR mutation waits for stability.
- Failed Day 18 cross-Zone gate prevents Days 19–22 being called DR acceptance; use them for remediation/evidence.
- Scope added after Day 3 replaces equivalent scope or moves to the next release.
- Omitted tests remain `NOT_TESTED`; schedule pressure never creates evidence.

## 10. Why this is the fastest credible route

Pre-provision VMs; use one inventory and release contract; keep CloudStack authoritative; certify one real DR provider; prove native B&R first; serialize mutations while parallelizing source/test work; keep DB operator ownership explicit; front-load infrastructure deadlines; integrate daily; and reserve Days 23–25 for recovery/repetition rather than new features.

On Day 25, only the exact exercised scope may be `LIVE_VERIFIED`. `PRODUCTION_CERTIFIED` additionally requires every release-defined production gate, adequate physical failure domains and required repetition/soak evidence. This schedule reduces breadth and idle time, never authorization, integrity, recovery or evidence requirements.
