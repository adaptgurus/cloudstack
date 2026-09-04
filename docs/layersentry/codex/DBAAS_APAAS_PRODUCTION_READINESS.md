# LayerSentry Future DBaaS/APaaS — Production Readiness Contract

Status: `DESIGN_DEFINED`

This document tightens the future DBaaS/APaaS workstream into a production engineering contract. It does **not** re-enable DBaaS/APaaS in LayerSentry V1. It does not authorize Apache CloudStack core rewrites.

## 1. Definition of production ready

A feature is production ready only when the exact released artifacts and the exact supported topology have passed all applicable gates below. Source code, a successful build, a running process, a healthy Kubernetes Pod, or HTTP 200 are not sufficient.

Required evidence classes:

1. architecture and threat model;
2. immutable artifact and dependency provenance;
3. CI/unit/integration/security tests;
4. exact KVM/Kubernetes live deployment;
5. data-path validation;
6. backup + restore + PITR validation where advertised;
7. failure and recovery validation;
8. upgrade + rollback validation;
9. performance envelope validation;
10. documented operational limits and failure envelope.

Use the existing LayerSentry evidence states truthfully: `DESIGN_DEFINED`, `SOURCE_COMPLETE`, `CI_VERIFIED`, `LIVE_VERIFIED`, `PRODUCTION_CERTIFIED` and lower/blocked states as appropriate.

## 2. Supported platform baseline

The initial production certification baseline remains Apache CloudStack 4.22.1.1 LTS with native KVM orchestration. A newer regular release may be evaluated but does not replace the LTS baseline without deliberate certification.

KubeBlocks initial candidate baseline is 1.0.2, pinned by exact staged artifacts rather than a mutable remote Helm repository.

Every release matrix must pin:

- CloudStack release;
- KVM host OS/QEMU/libvirt versions;
- guest image build and SHA-256;
- Kubernetes distribution and version;
- KubeBlocks version;
- KubeBlocks add-on/chart versions;
- database engine/version;
- storage provider/StorageClass;
- backup repository/provider;
- LayerSentry controller/runner/provider versions.

No `latest` tags are permitted in a production catalog.

## 3. Final service-plane architecture

Use a unified LayerSentry UX/API facade with independent reconciled service planes:

```text
User / UI / CLI / Terraform / API
                 |
                 v
+--------------------------------------------+
| LayerSentry XaaS Service Catalog/API       |
| plans / RBAC / quotas / operations / audit |
+----------------------+---------------------+
                       |
          +------------+-------------+
          |                          |
          v                          v
+-----------------------+   +-------------------------+
| VM-native DBaaS       |   | Kubernetes Service     |
| controller/reconciler |   | Plane                   |
+-----------+-----------+   |                         |
            |               | APaaS runtime           |
            |               | KubeBlocks DBaaS        |
            |               | service bindings        |
            |               +------------+------------+
            |                            |
            v                            v
     supported CloudStack API        CloudStack KVM VMs
            |                            |
            v                            v
       native KVM VMs                 Kubernetes
            |                            |
            v                            v
       DBaaS runner                 KubeBlocks/Apps
            |                            |
            v                            v
      database engine                 PVCs/services
```

CloudStack remains authoritative for VM, volume, network, placement, project/account, quota and KVM lifecycle state. DBaaS/APaaS services must not use direct `virsh`, libvirt XML mutation or private KVM state as an alternate infrastructure control plane.

## 4. Product modes

Expose three user-facing service families:

### DBaaS Standard

Kubernetes-native database service using KubeBlocks. Optimized for lifecycle automation, standardized HA, rapid provisioning and broad service catalog.

### DBaaS Performance

VM-native CloudStack/KVM database service. Optimized for direct OS/LVM/filesystem control, large databases, predictable resource reservation, database-specific NUMA/huge-page/storage tuning and operational isolation.

### APaaS

Kubernetes application runtime. KubeBlocks is a backing-service provider, not the application runtime itself.

Initial APaaS production slice is OCI-image based:

- deploy immutable OCI image by digest;
- Deployment/Service or selected runtime abstraction;
- route/Gateway/Ingress;
- TLS;
- Config/Secret references;
- rolling rollout/rollback;
- HPA/KEDA where certified;
- logs/metrics/events;
- service binding to DBaaS.

Source-to-image/build pipelines are a later independently certified capability. This reduces the initial APaaS supply-chain and build-system attack surface.

## 5. Kubernetes production topology

A KubeBlocks database is only as highly available as the Kubernetes and CloudStack failure domains beneath it.

Minimum production contract:

- three control-plane/etcd failure-domain participants where the selected Kubernetes distribution uses stacked/independent etcd accordingly;
- at least three worker capacity/failure domains for HA database placement;
- Kubernetes nodes placed on separate CloudStack KVM hosts/failure domains using supported placement controls;
- N+1 compute capacity after one certified failure-domain loss;
- redundant network and storage paths;
- topology labels that reflect real physical failure domains rather than cosmetic labels;
- Pod anti-affinity/topology spread for database replicas;
- PodDisruptionBudget where compatible with the selected add-on/topology;
- PriorityClass/resource reservation for platform and database control components;
- requests/limits and namespace quotas;
- separate administrative and tenant access boundaries.

CloudStack 4.22.1.1 certification must not assume later CKS node-affinity features. If CKS cannot express the required placement contract on the certified release, create/manage the Kubernetes node VMs through supported CloudStack VM/affinity APIs or use another explicitly certified cluster provisioning path. Do not weaken the failure-domain requirement merely to use a convenient installer.

## 6. KubeBlocks production policy

KubeBlocks is an optional Kubernetes-native DBaaS provider, not the sole DBaaS implementation.

Production rules:

- install only from locally staged checksum-locked artifacts;
- automatic add-on installation disabled;
- mirror all required container images into an approved internal registry;
- pin images by digest in the promoted bundle where tooling permits;
- certify each add-on/version/topology independently;
- expose only capabilities proven for that exact add-on/version;
- reject unsupported cross-version upgrades rather than improvising them;
- validate BackupRepo, BackupPolicy, restore and PITR semantics per add-on;
- validate scaling/volume expansion against the exact StorageClass;
- never infer production HA solely from `replicas: 3`.

Initial production candidate order:

1. PostgreSQL;
2. MySQL;
3. MariaDB only after the exact add-on topology is verified;
4. MongoDB;
5. Redis/Valkey/middleware where useful;
6. OpenSearch after lifecycle/backup validation.

Elasticsearch is excluded from this workstream.

## 7. VM-native KVM guest image

Use a small database substrate image rather than one QCOW2 per database/version.

Initial image:

`layersentry-dbaas-rocky9-<build>.qcow2`

Contains only:

- cloud-init;
- qemu-guest-agent;
- chrony;
- CA trust;
- LVM/XFS/ext4 tooling;
- basic diagnostics required by the runner;
- hardened DBaaS bootstrap/runner substrate;
- SELinux-compatible directories/policy required by the substrate.

Does not contain long-lived customer secrets or a mutable database-specific install script.

Production image build must require:

- trusted base-image SHA-256;
- immutable internal package-repository snapshot;
- exact source commit;
- runner SHA-256;
- package inventory;
- image SHA-256;
- release manifest;
- SBOM before promotion;
- vulnerability/license scan policy;
- artifact signature before production promotion;
- cloud-init clean/sysprep;
- unique machine identity regeneration on first boot;
- SELinux enforcing live validation;
- qemu-guest-agent live validation;
- CloudStack ConfigDrive/user-data live validation;
- reboot validation.

Production nodes must never download an unsigned mutable `latest` guest payload.

## 8. Cloud-init and enrollment

Cloud-init is a one-time bootstrap mechanism only.

It may provide:

- controller endpoint/identity;
- database instance/node identity;
- provider intent;
- a cryptographically random single-use enrollment token.

It must not contain:

- database admin passwords;
- replication passwords;
- object-storage credentials;
- private TLS keys;
- reusable service/API tokens;
- signing keys.

Enrollment token requirements:

- single use;
- short TTL;
- bound to CloudStack VM ID + DB instance ID + node ID + account/project;
- scope limited to agent enrollment;
- atomically consumed;
- replay detected/audited.

The guest generates its private key locally, submits a CSR and establishes an outbound mTLS work channel. No generic inbound remote shell API is permitted.

## 9. VM-native storage identity contract

For CloudStack 4.22.1.1 KVM, current source sets a libvirt disk serial from the CloudStack volume UUID by removing hyphens and taking at most the first 20 characters. The guest storage layer uses this as the initial exact volume-to-device binding.

This is a release-specific implementation invariant, not a timeless API contract. Every CloudStack upgrade certification must prove the mapping again before destructive storage automation is enabled.

Storage preparation must fail closed unless exactly one disk matches the expected identity.

Never persist `/dev/vdb`, `/dev/vdc` or attach order as the authoritative device identity.

## 10. VM-native LVM/filesystem contract

Default production data path:

```text
CloudStack data volume
  -> verified guest disk identity
  -> optional certified encryption layer
  -> raw-disk LVM PV
  -> vg_dbaas
  -> lv_data
  -> XFS
  -> /var/lib/dbaas/data
```

Rules:

- root disk is never used as database data storage;
- one independent database data volume per database node by default;
- shared guest LVM between DB nodes is prohibited;
- no partition table is required in the default managed layout;
- existing filesystems/LVM/signatures cause a hard stop unless an explicit import workflow owns them;
- critical DB mount must not use `nofail`;
- DB service start requires the expected mount to be present and validated;
- filesystem is mounted by UUID, not transient block-device name;
- database-volume shrink is unsupported;
- expansion is: CloudStack resize -> guest device rescan -> `pvresize` -> `lvextend` -> filesystem grow -> DB validation;
- automatic striping is prohibited;
- separate WAL/binlog volume is available only in a certified profile where it represents a genuinely independent useful storage path;
- guest LVM snapshots are not the authoritative backup strategy.

## 11. CloudStack snapshot safety

Database-aware backup is authoritative. CloudStack volume/VM snapshots are supplementary infrastructure protection only.

The certified 4.22 line has an important KVM safety consideration: VM snapshots and volume snapshots cannot safely be treated as freely composable mechanisms. LayerSentry must implement a guard so a DBaaS plan cannot run conflicting snapshot workflows blindly.

Production backup/restore logic must never depend solely on VM crash-consistent snapshots.

## 12. KubeBlocks/PVC storage contract

Kubernetes-native DBaaS uses PVCs and a certified StorageClass. Do not introduce guest LVM inside database Pods as the normal architecture.

LayerSentry StorageClass capability metadata must include at minimum:

- backend/provider;
- durability/failure domain;
- access mode;
- reclaim policy;
- online expansion capability;
- snapshot capability;
- expected latency/IOPS/throughput tier;
- topology awareness;
- backup compatibility;
- encryption capability;
- tested database/add-on combinations.

CloudStack/storage tags and Kubernetes StorageClass names are selectors, not proof of performance. Promotion to `premium`, `oltp`, etc. requires measured/certified characteristics.

## 13. Compute/performance policy

Production performance must be deterministic and bounded, not an unbounded autotuner.

Profiles:

- GENERAL_PURPOSE
- OLTP
- READ_HEAVY
- WRITE_HEAVY
- ANALYTICS
- MEMORY_OPTIMIZED
- CONNECTION_HEAVY
- CUSTOM

Inputs:

- engine/version;
- vCPU;
- RAM;
- topology;
- expected connections;
- storage capability class;
- measured empty-volume latency/IOPS when enabled;
- network characteristics;
- durability policy;
- backup/replication overhead.

Outputs may control:

- database memory budget;
- connection-pool limits;
- parallel/background workers;
- WAL/binlog/checkpoint behavior;
- vacuum/maintenance behavior;
- engine-specific I/O concurrency;
- huge-page/THP policy;
- storage layout;
- backup concurrency;
- alert thresholds.

Production profiles must never disable fsync/durable commit/journaling merely to improve benchmarks.

## 14. KVM CPU/RAM policy

Default HA/migratable DB offering should use a migration-compatible KVM CPU policy such as CloudStack/libvirt `host-model` on a homogeneous certified host cluster.

`host-passthrough` may be offered only as an explicit performance tier after proving:

- homogeneous/matching CPU estate;
- migration constraints;
- host-failure recovery behavior;
- upgrade compatibility;
- customer-visible limitation.

For production DB pools:

- do not depend on memory ballooning/oversubscription for normal operation;
- reserve N+1 RAM/CPU capacity for the certified failure envelope;
- use low/no CPU overcommit for latency-sensitive tiers;
- NUMA/vCPU pinning/huge pages/I/O threads require an independently certified performance tier;
- a tuning profile must not assume CPU/RAM that the underlying host scheduler cannot reliably provide.

## 15. Backup/PITR contract

Every production database plan defines:

- backup technology;
- repository and failure domain;
- encryption;
- schedule;
- retention;
- PITR range where advertised;
- verification state;
- restore-as-new workflow;
- restore test cadence;
- RPO/RTO targets and evidence.

VM-native PostgreSQL initial target:

- pgBackRest;
- base/full/differential/incremental policy as certified;
- WAL archive;
- PITR;
- object storage separated from the DB compute/storage failure domain.

KubeBlocks mode:

- use BackupRepo/BackupPolicy only for an add-on whose exact backup/restore/PITR behavior is certified;
- prefer repository access mechanisms appropriate for the tenant-security model;
- object-storage credentials remain secrets, not LayerSentry UI fields persisted in plaintext.

A backup is not `Healthy` merely because a backup command/CR reports completion. Higher certification requires an actual restore test and, where PITR is supported, recovery to at least two retained points during certification.

## 16. HA and endpoint contract

HA means:

- independent placement/failure domains;
- quorum/election semantics;
- replication;
- health checks;
- fencing/split-brain protection where relevant;
- stable writer endpoint;
- read endpoint where supported;
- node replacement/reseed;
- backup/PITR;
- observability.

A single proxy in front of a three-node DB is not an HA service. Endpoint infrastructure itself must be redundant or provided by a proven distributed/native mechanism.

Never promote a replica because of one failed health probe. Every provider defines failover preconditions, candidate eligibility, fencing/old-primary handling and post-failover validation.

## 17. Network/security contract

Default databases are private-only.

Use separate logical policies for:

- client data plane;
- database replication/quorum;
- management/agent traffic;
- backup/object storage;
- monitoring;
- Kubernetes control plane.

Rules:

- TLS for DB client traffic where the engine supports it;
- TLS/mTLS for management identities;
- least-privilege service accounts;
- no public DB port by default;
- explicit allowlists/security groups/firewall policy;
- egress policy for Kubernetes workloads where supported/certified;
- secrets redacted from logs/events/async operation payloads;
- provider scripts treat all user parameters as untrusted;
- no raw user shell execution;
- signed provider/image/release artifacts;
- audit every destructive or security-sensitive operation.

## 18. Upgrade/rollback contract

Every provider release and KubeBlocks add-on must publish a tested compatibility graph rather than assuming arbitrary upgrades work.

Before upgrade:

- compatibility preflight;
- health/quorum check;
- capacity check;
- backup + recoverability check;
- maintenance-window policy;
- exact current/target versions recorded.

During upgrade:

- typed idempotent operation;
- secondary/replica-first where appropriate;
- health gate between steps;
- bounded timeout/retries;
- no blind retry after an uncertain mutation.

After upgrade:

- authenticated read/write validation;
- replication/quorum validation;
- backup/PITR validation;
- metrics/endpoint validation;
- rollback/fallback state explicitly recorded.

## 19. Capacity protection

Track separately:

- filesystem usage/inodes;
- LVM/PVC capacity;
- WAL/binlog/oplog growth;
- replication lag;
- backup repository capacity;
- CloudStack/Kubernetes compute capacity;
- storage-pool capacity;
- connection saturation;
- memory pressure;
- certificate/token expiry.

Auto-expand requires an explicit policy and customer/admin maximum. Never create unbounded automatic cost/storage growth.

## 20. Observability

Expose four layers:

1. infrastructure — VM/node CPU, RAM, storage, network;
2. database — engine-specific health/performance;
3. service lifecycle — reconciliation/operation state;
4. recovery — backup, restore test, PITR/DR readiness.

Every operation carries a durable operation ID and timeline. Logs must be structured and secret-redacted.

## 21. Required failure tests before production certification

VM-native DBaaS:

- guest reboot;
- DB process crash;
- agent restart;
- controller restart;
- CloudStack management-server restart;
- one DB node loss;
- one KVM host/failure-domain loss;
- replication network partition;
- disk full/WAL growth;
- backup repository outage;
- interrupted resize;
- interrupted upgrade;
- old-primary return after failover;
- complete cluster restart;
- restore as new;
- PITR latest and older retained point;
- credential/TLS rotation.

KubeBlocks DBaaS:

- Pod restart/reschedule;
- worker-node loss;
- one KVM host/failure-domain loss beneath Kubernetes;
- control-plane member loss;
- PVC expansion;
- BackupRepo outage;
- backup/restore/PITR;
- OpsRequest interruption/retry;
- add-on/operator upgrade and rollback;
- topology-spread/anti-affinity proof.

APaaS:

- Pod/node loss;
- rollout failure + rollback;
- route/TLS failure;
- autoscaling limit behavior;
- secret/config update behavior;
- DB service-binding rotation;
- image-registry outage and already-running workload behavior.

## 22. Performance certification

Do not advertise `optimized` without data.

For every advertised DB plan collect repeatable results for:

- baseline/default DB configuration;
- LayerSentry general-purpose profile;
- LayerSentry workload-specific profile;
- steady-state latency/throughput;
- p95/p99 DB latency;
- storage p95/p99 latency;
- CPU saturation;
- memory/headroom;
- checkpoint/flush behavior;
- replication lag;
- backup impact;
- failover/recovery time.

Use engine-appropriate benchmark tools and a documented dataset/duration/concurrency profile. Synthetic fio is allowed only on empty disposable volumes and is never the sole DB-performance proof.

## 23. Release artifact contract

A production release bundle should contain, as applicable:

- LayerSentry controller/runner binaries;
- signed provider bundles;
- QCOW2 image + SHA-256 + manifest + SBOM + signature;
- offline KubeBlocks CRDs/chart + checksum lock;
- mirrored database/add-on/container images + digest lock;
- Kubernetes/APaaS manifests/charts;
- schema/API compatibility versions;
- support matrix;
- upgrade/rollback instructions;
- known limitations;
- CI and live-validation evidence references.

No runtime production install should silently fetch mutable artifacts from the public Internet.

## 24. Initial certification sequence

Do not certify five engines at once.

### Slice 1 — VM PostgreSQL

Prove end to end:

CloudStack VM -> ConfigDrive/cloud-init -> secure runner enrollment -> exact CloudStack-volume-to-guest-disk mapping -> LVM/XFS -> PostgreSQL -> CPU/RAM/storage profile -> TLS -> pgBackRest/WAL/PITR -> monitoring -> resize -> reboot -> backup restore -> PITR -> single-node failure -> HA/failover when HA is introduced.

### Slice 2 — KubeBlocks PostgreSQL

Prove:

Kubernetes failure domains -> pinned offline KubeBlocks -> pinned PostgreSQL add-on/images -> certified StorageClass -> database HA -> BackupRepo/BackupPolicy -> backup -> restore -> PITR -> vertical scale -> PVC expansion -> node loss -> operator/add-on upgrade.

### Slice 3 — APaaS OCI-image runtime

Prove:

OCI image digest -> app deployment -> route/TLS -> scaling -> metrics/logs -> rolling update/rollback -> DB service binding -> secret rotation -> node loss.

Only after these vertical slices meet `PRODUCTION_CERTIFIED` gates should additional engines/services be promoted.

## 25. Non-negotiable stop conditions

Fail closed and do not mark READY when any of the following is uncertain:

- target VM/account/project identity;
- target block device identity;
- storage contains unexpected data/signature;
- HA quorum/fencing state;
- backup repository or PITR recoverability;
- artifact checksum/signature;
- provider/add-on compatibility;
- secret authorization;
- Kubernetes/CloudStack failure-domain placement;
- post-upgrade database correctness.

The objective is not the fastest first installation. The objective is a database/application service that can be safely operated, recovered and upgraded for years.
