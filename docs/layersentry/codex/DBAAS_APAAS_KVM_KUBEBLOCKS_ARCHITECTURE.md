# LayerSentry Future DBaaS/APaaS — KVM + Kubernetes/KubeBlocks Architecture

Status: `DESIGN_DEFINED`

This document defines a future XaaS workstream. It does **not** re-enable DBaaS/APaaS in LayerSentry V1 and does not change Apache CloudStack core semantics.

## 1. Architectural decision

Use two distinct service planes behind one LayerSentry UX/API facade:

1. **VM-native DBaaS** — databases run directly on CloudStack-managed KVM VMs.
2. **Kubernetes-native DBaaS** — databases run on a LayerSentry-managed Kubernetes cluster using KubeBlocks.
3. **APaaS** — applications run on Kubernetes using a dedicated application runtime/platform layer. KubeBlocks supplies stateful backing services, not the application runtime itself.

CloudStack remains authoritative for KVM VM, storage, network, placement, account/project, quota and lifecycle state. LayerSentry services/controllers call supported CloudStack APIs. Do not call libvirt/virsh directly from DBaaS/APaaS services.

## 2. High-level topology

```text
User / API / CLI / Terraform
            |
            v
+---------------------------------------+
| LayerSentry XaaS API + UI facade      |
| catalog / plans / RBAC / operations   |
+-------------------+-------------------+
                    |
         +----------+----------+
         |                     |
         v                     v
+----------------+    +-----------------------+
| VM DBaaS       |    | Kubernetes Service    |
| Controller     |    | Plane                 |
| + Reconciler   |    |                       |
+-------+--------+    | APaaS runtime         |
        |             | KubeBlocks DBaaS      |
        |             | Prometheus/Grafana    |
        |             | Backup repositories   |
        |             +-----------+-----------+
        |                         |
        v                         v
CloudStack API               CloudStack KVM VMs
        |                    hosting K8s nodes
        v                         |
CloudStack KVM VMs                v
        |                    Kubernetes
        v                         |
DBaaS runner                      v
        |                    KubeBlocks CRDs
        v                         |
PostgreSQL/MySQL/...              v
                            DB Pods + PVCs
```

## 3. Provider policy

### VM-native DBaaS

Initial production order:

1. PostgreSQL
2. MariaDB
3. MySQL
4. MongoDB
5. OpenSearch

Elasticsearch is excluded.

VM-native mode is preferred where operators need predictable guest OS control, direct LVM/filesystem layout, database-specific kernel/NUMA tuning, dedicated storage paths, or non-Kubernetes operational isolation.

### Kubernetes-native DBaaS

Use KubeBlocks as an optional provider for Kubernetes-native stateful services. Pin a tested KubeBlocks release and tested add-on versions. Do not expose every upstream add-on automatically. Each engine/version/topology must pass LayerSentry certification before it appears in the production catalog.

Initial candidate catalog:

- PostgreSQL
- MySQL
- MariaDB where the selected add-on is verified
- MongoDB
- Redis/Valkey where selected
- Kafka/RabbitMQ as middleware services where selected
- OpenSearch only after add-on lifecycle validation

### APaaS

KubeBlocks is not the APaaS runtime. APaaS must have a separate application deployment layer for stateless/web/worker workloads, with KubeBlocks exposed as a backing-service catalog.

Application lifecycle and database lifecycle must remain independently reconcilable.

## 4. Unified service model

Expose one user model while preserving provider-specific implementations:

```text
ServiceInstance
  type: database | application | middleware
  provider: vm-native | kubeblocks | app-runtime
  engine/runtime
  version
  plan
  compute
  storage
  network
  backupPolicy
  availabilityPolicy
  performanceProfile
  maintenanceWindow
  status
```

A normal user should choose:

- service/engine
- version
- plan
- size
- storage capacity/class
- HA requirement
- backup retention/PITR where supported
- performance profile
- network exposure

The platform calculates the remaining implementation details and records the calculation result for auditability.

## 5. VM-native KVM DBaaS storage contract

Default production node layout:

```text
root volume
  -> OS / cloud-init / qemu-guest-agent / DBaaS runner

data volume
  -> persistent device identity
  -> optional encryption
  -> LVM PV
  -> vg_dbaas
  -> lv_data
  -> XFS (default certified filesystem)
  -> /var/lib/dbaas/data

optional dedicated WAL/binlog volume for certified write-intensive profiles
```

Rules:

- never persist `/dev/vdb`/`/dev/vdc` as identity;
- bind the expected CloudStack volume ID to persistent guest identifiers;
- reject root, mounted, foreign-filesystem, foreign-LVM or unexpected devices;
- use LVM by default for managed production data volumes;
- do not automatically stripe multiple volumes;
- do not use `nofail` for critical DB mounts;
- DB service startup requires verification that the expected LV/filesystem is mounted at the expected mountpoint;
- database data-volume shrink is unsupported; use migration/restore workflows;
- volume expansion is controller-driven: CloudStack resize -> guest rescan -> pvresize -> lvextend -> filesystem grow -> DB validation.

## 6. VM bootstrap contract

Certified QCOW2 images contain only the stable guest substrate:

- cloud-init
- qemu-guest-agent
- CA trust
- time synchronization
- LVM/XFS/ext4 tooling
- SELinux-compatible DBaaS directories/policies where required
- metrics prerequisites
- small DBaaS runner/bootstrap binary

Cloud-init is **bootstrap only**. It must not own database lifecycle.

First boot:

```text
ConfigDrive/user-data
 -> one-time node identity/enrollment token
 -> dbaas-bootstrap.service
 -> agent generates local private key/CSR
 -> controller validates VM/account/node binding
 -> short-lived mTLS identity issued
 -> token consumed
 -> outbound agent work channel starts
```

Do not place database passwords, private keys, reusable service credentials or backup credentials in persistent user-data.

## 7. Script/provider execution model

Database-specific automation may use signed, versioned Bash/Python/Ansible assets behind a strict operation schema.

No arbitrary remote shell API is permitted.

Every operation must be:

- typed and allowlisted;
- idempotent;
- resumable;
- bounded by timeout/retry policy;
- concurrency-locked per node/instance where required;
- parameter validated;
- atomic for managed configuration files;
- logged without secrets;
- post-validated against actual database behavior.

## 8. Performance engine

Performance profiles are deterministic and versioned:

- GENERAL_PURPOSE
- OLTP
- READ_HEAVY
- WRITE_HEAVY
- ANALYTICS
- MEMORY_OPTIMIZED
- CONNECTION_HEAVY
- CUSTOM

Inputs:

- engine/version
- vCPU
- RAM
- topology
- storage capability profile
- measured latency/IOPS where an empty-volume benchmark is allowed
- expected connection count
- durability policy
- backup concurrency
- network characteristics

Outputs may include:

- database memory settings
- connection-pool limits
- worker/parallelism settings
- WAL/binlog/checkpoint settings
- autovacuum/background maintenance settings
- engine-specific I/O concurrency settings
- huge-page policy
- validated THP policy
- filesystem/storage layout choice
- monitoring/capacity thresholds

Production profiles must never disable durability merely to improve benchmark numbers.

## 9. Backup and restore contract

Backups are database-aware. CloudStack snapshots are supplementary protection only.

Every production database plan must define:

- backup method
- repository
- encryption
- schedule
- retention
- PITR capability/range where supported
- checksum/verification state
- restore-as-new workflow
- scheduled recovery test policy

VM-native PostgreSQL initial target: pgBackRest + WAL archive/PITR.

KubeBlocks mode uses its BackupRepo/BackupPolicy/restore mechanisms only for add-ons whose LayerSentry certification proves backup, restore and PITR semantics for the exact version.

A backup is not considered healthy only because a command or CR completed; restore validation is required for higher certification states.

## 10. Kubernetes/KubeBlocks storage contract

KubeBlocks databases use Kubernetes PVCs and a LayerSentry-certified StorageClass. Do not put guest LVM inside a KubeBlocks database Pod as a default architecture.

The StorageClass catalog must publish capability metadata such as:

- durability/failure domain
- reclaim policy
- volume expansion
- snapshot support
- access mode
- expected latency/IOPS tier
- topology awareness
- backup compatibility

KubeBlocks PVC expansion is used only where both the selected add-on and StorageClass are certified for it.

## 11. HA/failure-domain rules

VM DBaaS:

- separate replicas across certified CloudStack failure domains;
- engine-aware quorum/fencing;
- stable writer/read endpoints;
- no blind primary promotion;
- replacement-node workflow must reseed and validate before joining service.

KubeBlocks:

- database anti-affinity/topology spread must map to actual Kubernetes node/failure-domain labels;
- K8s nodes themselves must be distributed across CloudStack KVM failure domains;
- a three-replica database is not HA if all Kubernetes nodes live on one KVM host/storage failure domain.

## 12. User operations

UI/API must support provider capability-gated operations:

- create
- delete protection
- start/stop where semantically valid
- resize compute
- expand storage
- add/remove replica
- backup now
- scheduled backup
- restore as new
- PITR where supported
- clone
- switchover/failover where supported
- credential rotation
- TLS rotation
- parameter/profile change
- minor/major upgrade where certified
- health/metrics/logs/operation timeline

Unsupported operations must be absent/disabled based on real provider capability, not simulated in UI.

## 13. QCOW2 image policy

Build two image classes, not a database image per engine/version:

1. `layersentry-dbaas-rocky9-<build>.qcow2` — VM-native DBaaS guest substrate.
2. `layersentry-k8s-node-rocky9-<build>.qcow2` — Kubernetes worker/control-plane substrate where the selected K8s distribution supports the image model.

Do not bake KubeBlocks into a QCOW2 image; deploy KubeBlocks into Kubernetes by pinned Helm/chart/manifests.

Every released QCOW2 artifact requires:

- immutable version
- source commit
- SHA-256
- SBOM
- package inventory
- build log/provenance
- signature when signing pipeline is available
- cloud-init cleanup/sysprep
- unique machine-id regeneration
- qemu-guest-agent validation
- SELinux enforcing validation
- CloudStack KVM boot test
- data-volume/LVM/mount test for DBaaS image

## 14. Deployment/certification gates

Use LayerSentry evidence states accurately:

- `DESIGN_DEFINED`: architecture only
- `SOURCE_COMPLETE`: implementation committed
- `CI_VERIFIED`: automated build/tests passed
- `LIVE_VERIFIED`: exact artifacts exercised on authorized CloudStack/KVM/Kubernetes lab
- `PRODUCTION_CERTIFIED`: failure, backup/restore, security, upgrade and performance envelopes are documented and repeatedly proven

Do not claim deployment or production readiness from source alone.

## 15. First implementation slices

### Slice A — VM PostgreSQL

Create PostgreSQL on CloudStack KVM using certified QCOW2 -> attach data volume -> LVM/XFS mount -> secure bootstrap -> signed provider automation -> TLS -> database-aware backup/PITR -> monitoring -> CPU/RAM/storage-aware profile -> restore test -> READY.

### Slice B — Kubernetes/KubeBlocks PostgreSQL

Provision/select LayerSentry Kubernetes cluster -> install pinned KubeBlocks -> install pinned PostgreSQL add-on -> certified StorageClass -> create HA cluster -> configure BackupRepo/BackupPolicy -> backup -> restore-as-new -> performance/resource profile -> metrics -> failure-domain validation.

### Slice C — APaaS

Deploy the selected APaaS runtime separately -> application build/deploy/scale/log/route lifecycle -> service binding to VM-native or KubeBlocks DBaaS instances -> backup remains a DBaaS responsibility.

Only after these vertical slices are reliable should additional engines and advanced topologies be exposed.
