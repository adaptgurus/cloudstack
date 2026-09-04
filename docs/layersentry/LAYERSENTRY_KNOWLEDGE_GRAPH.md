# LayerSentry Engineering Knowledge Graph

**Status:** `SOURCE_COMPLETE` for documentation structure only  
**Role:** stable relationship/index layer for future ChatGPT/Codex/engineering sessions  
**Product baseline:** Apache CloudStack 4.22.1.1 + LayerSentry KVM-first product layer

This file connects the important product, architecture, environment, evidence and operational concepts. It is intentionally not a duplicate progress ledger and does not contain plaintext credentials, current workflow IDs, current IP addresses or other volatile state. Follow the linked authoritative source for each fact.

## 1. Authority graph

```text
AGENTS.md
  -> operating rules / startup / test lifecycle / safety

LAYERSENTRY_SUPER_MASTER_CONTEXT.md
  -> stable product + architecture + security + evidence contracts

LAYERSENTRY_PROGRESS_LEDGER.md
  -> current HEADs / workflow IDs / artifacts / live observations / blockers

LAYERSENTRY_KNOWLEDGE_GRAPH.md
  -> stable relationships and navigation between concepts/sources

Specialist policy / architecture docs
  -> secure engineering
  -> upgrade/release/IP protection
  -> DRaaS architecture
  -> workstream contracts
  -> debugging runbook

Current repository + workflow evidence + live target
  -> implementation/execution/runtime truth
```

Conflict precedence remains: live runtime -> workflow/artifact -> current source -> version-pinned upstream documentation -> stable project contracts -> historical handoffs.

## 2. Product graph

```text
LayerSentry
  IS_A -> commercial on-prem KVM private-cloud product
  BUILT_ON -> Apache CloudStack 4.22.1.1
  PRESERVES -> CloudStack VM/network/storage/account/RBAC/KVM lifecycle
  ADDS -> simplified UI
  ADDS -> appliance/installer/release discipline
  ADDS -> security hardening
  ADDS -> validation/evidence tooling
  ADDS -> storage-aware DR orchestration
  EXCLUDES_V1 -> DBaaS/APaaS CloudStack-native placeholders
```

## 3. Repository graph

```text
adaptgurus/cloudstack
  BRANCH -> layersentry/4.22.1.1-ui
  CONTAINS -> LayerSentry UI/product overlay
  CONTAINS -> canonical docs/policies/architecture
  CONTAINS -> CloudStack upstream source baseline

adaptgurus/cozystack
  ROLE -> integration/live-test runner repository
  BRANCH -> inspect actual current integration branch before use
  RUNS_ON -> authorized Hyper-V/GitHub runner environment
  VALIDATES -> LayerSentry Rocky Linux 9 test target
  EMITS -> durable workflow/job/artifact evidence
```

Current commit/run IDs are volatile and belong in `LAYERSENTRY_PROGRESS_LEDGER.md` or evidence artifacts, never here.

## 4. Development and acceptance environment graph

```text
WSL Ubuntu 22.04
  ROLE -> development/preliminary tooling environment
  USER_IDENTITY -> opc
  MAY_TEST -> source tooling / scripts / preliminary automation
  CANNOT_ALONE_PROMOTE -> LIVE_VERIFIED

Rocky Linux 9 LayerSentry VM
  ROLE -> primary acceptance environment
  USER_IDENTITY -> root for currently authorized development administration
  VALIDATES -> application/services/APIs/UI integrations/deployment/recovery
  REQUIRED_FOR -> LIVE_VERIFIED runtime-affecting changes

CloudStack browser/UI
  USER_IDENTITY -> admin for currently authorized development administration
  VALIDATES -> browser UI/UX + CloudStack/LayerSentry workflows
```

### Credential relationship

Plaintext passwords/private keys are deliberately **not stored in Git** even when temporary credentials are supplied in a chat/session. Runtime automation must inject them through approved secrets/existing authorized access.

Recommended logical secret references for the temporary development environment:

```text
LAYERSENTRY_DEV_WSL_PASSWORD
LAYERSENTRY_DEV_ROCKY_ROOT_PASSWORD
LAYERSENTRY_DEV_CLOUDSTACK_ADMIN_PASSWORD
```

The mapping from secret reference to actual value belongs only in the authorized runtime secret store/operator session. If a credential is exposed beyond the authorized channel, rotate it.

## 5. Acceptance/testing graph

```text
Meaningful Change
  -> Research
  -> Design Review
  -> Implementation
  -> Functional + Regression Tests
  -> Failure / Edge-Case Validation
  -> Optimization Review
  -> Documentation
  -> Knowledge Graph Update
  -> Stable-context update when policy/architecture changed
  -> Git Commit
  -> Final Verification

Runtime-affecting Change
  REQUIRES -> exact artifact/source identity
  REQUIRES -> cozystack runner or explicitly approved durable validation path
  REQUIRES -> Rocky Linux 9 acceptance
  REQUIRES -> product/API/guest/host evidence as applicable
  REQUIRES -> rollback/recovery evidence
  MAY_REQUIRE -> Chrome + Firefox UI validation
  MAY_REQUIRE -> security/RBAC negative tests
  MAY_REQUIRE -> restart/recovery/upgrade regression
```

Documentation-only design changes may be `SOURCE_COMPLETE` without a meaningless VM mutation. The runtime capability described by them remains `NOT_TESTED`/`PENDING` until implemented and exercised.

## 6. CloudStack architecture graph

```text
LayerSentry UI
  -> LayerSentry product/controller services
  -> supported CloudStack APIs/contracts
  -> CloudStack Management Server
  -> KVM/libvirt
  -> primary/secondary/backup storage

CloudStack
  AUTHORITY_FOR -> Zone/Site
  AUTHORITY_FOR -> Pod/Infrastructure Group
  AUTHORITY_FOR -> Cluster/Compute Cluster
  AUTHORITY_FOR -> KVM Host
  AUTHORITY_FOR -> VM
  AUTHORITY_FOR -> Volume
  AUTHORITY_FOR -> Network
  AUTHORITY_FOR -> Account/Domain/Project/RBAC

LayerSentry
  MUST_NOT_CREATE -> second VM scheduler
  MUST_NOT_CREATE -> second CloudStack inventory authority
  MAY_CREATE -> product/DR state outside CloudStack core
```

## 7. Backup and DR graph

```text
CloudStack B&R Framework
  PROVIDES -> provider abstraction
  PROVIDES -> NAS KVM B&R
  PROVIDES -> backup schedules/offers/APIs
  PROVIDES -> restore selected older backup
  PROVIDES_4_22 -> create VM from NAS backup in another Zone
  LIMITS -> no generic sub-hour continuous VM replication scheduler
  LIMITS -> no complete Recovery Plan/witness/fencing/failback controller

LayerSentry DR Orchestration Plane
  OWNS -> Protection Plan
  OWNS -> DR Site pairing metadata
  OWNS -> provider capability selection
  OWNS -> Recovery Point Catalog
  OWNS -> Recovery Group/dependency order
  OWNS -> network/VLAN/IP mappings
  OWNS -> Test Recovery
  OWNS -> planned failover/failback state machine
  OWNS -> automatic failover eligibility
  OWNS -> witness/fencing/exclusive lease
  OWNS -> traffic switch orchestration
  OWNS -> RPO/RTO evidence
  DOES_NOT_OWN -> normal CloudStack VM scheduler/lifecycle authority
```

## 8. DR provider decision graph

```text
Protection Plan
  -> detect source/destination storage capability

IF CloudStack-native capability meets SLA
  -> use CloudStack-native operation
ELSE IF certified storage-native replication exists
  -> use storage-native adapter
ELSE IF supported file-backed QCOW2/libvirt path exists
  -> use libvirt backup/checkpoint adapter
ELSE
  -> offer Backup DR/native B&R only
```

Provider examples:

```text
LINSTOR/DRBD
  HOT_REPLICA -> DRBD/LINSTOR continuous or certified async replication
  PITR -> LINSTOR snapshots / snapshot shipping
  BASELINE_FALLBACK -> CloudStack NAS B&R where supported

Ceph RBD
  HOT_REPLICA -> rbd-mirror
  PITR -> RBD snapshots/catalog

Enterprise SAN
  HOT_REPLICA -> certified array-native replication
  PITR -> consistency-group snapshots/bookmarks/clones
  HOST_ACCESS -> WWID/multipath/presentation validation

NFS/SharedMountPoint/QCOW2
  GENERIC_INCREMENTAL -> libvirt domain backup + checkpoints
  BASELINE_FALLBACK -> CloudStack NAS B&R

rsync
  ALLOWED_FOR -> explicitly validated repository/config sync
  REJECTED_FOR -> generic running-VM replication engine
```

Detailed decision rationale: `docs/layersentry/evidence/dr/2026-09-05-draas-architecture-revalidation.md`.

## 9. Recovery Point graph

```text
Protected VM/Application
  HAS -> Hot Replica
  HAS_MANY -> Recovery Points

Recovery Point
  HAS -> consistency epoch
  HAS -> timestamp
  HAS -> consistency type
  HAS -> complete participating disk set
  HAS -> provider checkpoint IDs
  HAS -> baseline/parent dependencies
  HAS -> destination storage identifiers
  HAS -> retention class
  HAS -> measured lag/RPO
  HAS -> validation state

Recovery Point
  CAN_ACTION -> Recover
  CAN_ACTION -> Test Recovery
  MUST_NOT_SHOW_HEALTHY_IF -> dependent data/checkpoint missing or corrupt
```

Latest-replica promotion and old-checkpoint restore are deliberately separate operations.

## 10. Failover graph

```text
Planned Failover
  PRECEDES_CERTIFICATION_OF -> Automatic Emergency Failover

Automatic Emergency Failover
  REQUIRES -> multiple failure signals
  REQUIRES -> third-fault-domain witness/quorum
  REQUIRES -> exclusive recovery lease
  REQUIRES -> source fencing
  REQUIRES -> no dual-writer storage state
  REQUIRES -> application health gates
  REQUIRES -> traffic switch after validation

Failback
  REQUIRES -> reverse replication/reseed
  REQUIRES -> source readiness validation
  REQUIRES -> controlled cutback/fencing
  REQUIRES -> application health validation
  REQUIRES -> traffic return
```

`ping failed -> boot DR` is explicitly prohibited.

## 11. Network recovery graph

```text
Source Network/VLAN
  MAPS_TO -> DR Network/VLAN

Source NIC/IP
  MAPS_BY_POLICY -> Keep IP only when topology proves safe
  OR -> deterministic DR IP pool
  OR -> static mapping
  OR -> intentional DHCP

Recovered Application
  HEALTH_GATE -> Traffic Switch

Traffic Switch Adapter
  MAY_USE -> DNS/GSLB
  MAY_USE -> BGP
  MAY_USE -> ADC/LB
  MAY_USE -> NAT/firewall
  MAY_USE -> certified stretched L2
```

## 12. Security graph

```text
CloudStack RBAC
  REMAINS -> server-side authorization boundary for CloudStack resources

LayerSentry privileged service
  MUST_AUTHZ -> exact DR/support/update action and exact tenant/resource
  USES -> least-privilege service identities
  USES -> mTLS between trusted site components
  USES -> bounded retries/timeouts/idempotency
  AUDITS -> failover/fencing/restore/delete/update operations

Secrets
  NEVER_FLOW_TO -> Git
  NEVER_FLOW_TO -> browser bundle
  NEVER_FLOW_TO -> logs/evidence
  FLOW_FROM -> runtime secret store / short-lived authorized injection
```

## 13. Upgrade and rollback graph

```text
New CloudStack/LayerSentry Release
  -> compatibility audit
  -> upstream-delta review
  -> rebuild immutable artifacts
  -> fresh install test
  -> supported N-1 -> N upgrade test
  -> rollback/recovery classification
  -> Rocky Linux 9 regression
  -> storage/B&R/DR regression for every enabled certified provider
  -> staging/canary
  -> production promotion
```

`LAYERSENTRY_UI_RELEASE_CONTRACT.md` defines the first transport-neutral UI
artifact contract and links a CI build to its manifest, CycloneDX SBOM,
provenance, SHA-256 integrity checks, production source-map policy and future
installer/signature gates.

Schema/database rollback is not equivalent to simple package downgrade. Follow `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`.

## 14. Support identity graph

LayerSentry requires a proprietary installation/cluster support UUID so support cases can identify the exact installed product environment without exposing credentials.

```text
LayerSentry Installation
  HAS_ONE -> Support Cluster UUID
  GENERATED_AT -> controlled installation/bootstrap
  STORED_AT -> durable local product state
  SHOWN_IN -> read-only Support/About diagnostics
  INCLUDED_IN -> sanitized support bundle
  MUST_NOT_BE -> an authentication secret
  MUST_NOT_CHANGE_ON -> normal reboot/update
  MAY_CHANGE_ON -> explicit new-cluster/reinstallation identity procedure
```

**Current development-lab Support Cluster UUID:** `UNKNOWN / PENDING LIVE DISCOVERY OR IMPLEMENTATION`.

Do not invent a UUID. Once implemented/discovered, record current volatile value in the progress ledger/evidence, not this stable relationship graph.

## 15. Knowledge/evidence graph

```text
Architecture decision
  -> design/research evidence file
  -> implementation commit(s)
  -> CI evidence
  -> Rocky Linux 9 live evidence
  -> failure/negative evidence
  -> progress-ledger status

Troubleshooting finding
  -> observed symptom
  -> evidence/log correlation
  -> confirmed or UNKNOWN root cause
  -> fix commit/config change
  -> regression test
  -> live revalidation
  -> durable runbook update if reusable
```

## 16. Continuation graph for future sessions

```text
New ChatGPT/Codex Session
  1 -> read AGENTS.md
  2 -> read LAYERSENTRY_SUPER_MASTER_CONTEXT.md
  3 -> read LAYERSENTRY_PROGRESS_LEDGER.md
  4 -> read assigned workstream
  5 -> use this Knowledge Graph to locate related architecture/policy/evidence
  6 -> fetch actual current repository + runner refs
  7 -> inspect in-flight workflows/live target before mutation
  8 -> resume first unmet evidence gate
```

Never reconstruct volatile project status from this graph alone; follow its links to current source/evidence.
