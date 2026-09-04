# LayerSentry Future KubeBlocks DBaaS/APaaS

Status: FUTURE / ISOLATED BRANCH ONLY. This does not reintroduce DBaaS or APaaS into current V1.

## Control-plane boundary

Apache CloudStack remains authoritative for KVM VM, volume, network, tenancy/RBAC, placement and infrastructure lifecycle. DBaaS/APaaS use supported CloudStack APIs and never call virsh/libvirt directly.

## One DBaaS API, two backends

### vm-native
Use when DB data plane must run directly on KVM VMs without Kubernetes.

LayerSentry -> DBaaS service -> CloudStack API -> KVM VM/volume -> ConfigDrive/cloud-init bootstrap -> outbound-mTLS runner -> signed provider automation -> database.

Guest storage: CloudStack data volume -> stable device identity -> optional encryption -> LVM -> certified filesystem -> guarded mountpoint. DB startup is blocked unless the expected volume/LV/filesystem/mount is proven.

### kubeblocks
Use for Kubernetes-backed managed databases.

LayerSentry -> DBaaS service -> managed Kubernetes on CloudStack KVM -> KubeBlocks -> Cluster/OpsRequest/Backup/Restore -> Pods/PVCs -> database.

KubeBlocks owns Kubernetes DB reconciliation. LayerSentry owns tenancy, plans, policy, quotas, service catalog, CloudStack integration, user-facing operations, audit and aggregated health.

Do not apply guest-LVM automation underneath KubeBlocks PVCs; CSI/StorageClass/PVC/VolumeSnapshot semantics own that path.

## APaaS

KubeBlocks is not the APaaS runtime. LayerSentry APaaS provides Kubernetes application deployment (OCI/Helm), namespace/project isolation, ingress/TLS, secrets/service binding, autoscaling, health, logs/metrics and rollout/rollback. KubeBlocks supplies managed stateful services consumed by APaaS applications.

## Engine policy

- PostgreSQL: first production target. KubeBlocks backend uses its PostgreSQL/Patroni model; vm-native uses PostgreSQL + Patroni + pgBackRest.
- MySQL: certify after PostgreSQL.
- MariaDB: separate provider/certification; never assume MySQL interchangeability.
- MongoDB: replica-set production profile after lifecycle/recovery certification.
- OpenSearch: future provider.
- Elasticsearch: explicitly excluded.

## Kubernetes production policy

- dedicated DB worker pool where practical;
- no intentional memory overcommit for production DB workers;
- CPU/RAM requests and limits from LayerSentry plans;
- performance tier may use dedicated CPUs/static CPU manager and topology-aware placement after certification;
- anti-affinity/topology spread across CloudStack/KVM failure domains;
- PodDisruptionBudget where topology supports it;
- one PVC per DB replica unless addon documentation requires another design;
- production PVC retention must prevent accidental deletion;
- backup goes to independent object storage, not snapshots alone.

## Storage capability contract

A LayerSentry storage plan maps to a certified StorageClass and records: backend/failure domain, durability, access mode, expansion support, VolumeSnapshot support, encryption, expected latency/IOPS/throughput, reclaim policy and backup compatibility. VolumeExpansion is exposed only when supported by the selected StorageClass.

## Performance policy

LayerSentry is the product-level tuning policy engine; KubeBlocks remains the reconciler. Inputs: engine/version, CPU, RAM, workload, connections, topology, storage class, measured latency/IOPS and durability. Outputs: resources, replicas/topology, PVC plan, connection-pool policy and bounded engine parameters.

Every tuning value must have rationale, min/max, version compatibility and rollback behavior. Production profiles never disable fsync, WAL/binlog durability, journaling or crash recovery.

Day-2 operations use KubeBlocks APIs such as VerticalScaling, HorizontalScaling, VolumeExpansion, Reconfiguring, Upgrade, Backup, Restore, Switchover and RebuildInstance when supported by that addon/version.

## Backup/recovery contract

LayerSentry exposes backup-now, schedules, retention, PITR where supported, restore-as-new (preferred), safe in-place restore where supported, clone, verification, scheduled restore tests, recoverable time range and operation history. KubeBlocks resources implement this for Kubernetes; vm-native providers use DB-aware native tools. A backup is not healthy until recoverability is tested.

## QCOW2 families

KubeBlocks/database engines are not baked into Kubernetes node images.

1. `layersentry-k8s-node-rocky9-<build>.qcow2`: cloud-init, qemu-guest-agent, Kubernetes/container prerequisites, chrony, storage/network prerequisites and security baseline.
2. `layersentry-dbaas-vm-rocky9-<build>.qcow2`: cloud-init, qemu-guest-agent, DBaaS bootstrap/runner prerequisites, CA trust, LVM/filesystem tools, monitoring prerequisites and security baseline.

Images are built from version-pinned upstream QCOW2 artifacts, signature/checksum verified and published with SHA-256, SBOM and build/source provenance.

## Rollout gates

A. Build/certify QCOW2 and Kubernetes/storage prerequisites.
B. Install stable KubeBlocks in non-production; validate CRDs/controllers, snapshot controller and backup repository.
C. PostgreSQL create/connect/write/read/restart/scale/volume-expand/backup/restore/PITR tests.
D. PostgreSQL HA/performance certification under node loss, storage pressure, controller restart and interrupted operations.
E. Certify MySQL, MariaDB, MongoDB and OpenSearch one at a time.

READY requires authenticated DB connection, write/read validation, topology/replication validation, TLS, backup initialization, monitoring readiness, storage/capacity checks and engine-specific health gates.