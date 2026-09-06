# Networkless libvirt provider acceptance design

Status: `SOURCE_COMPLETE`; live capture/recovery is `NOT_TESTED`. Source base is `f1e348653de40a22ee48b73d7f891570ca23c160`; runtime dispatch remains with the root integration owner.

The existing file provider already implements libvirt full/incremental capture, destination-acknowledged source lineage, immutable catalog transport and private QCOW2 reconstruction. Its source tests do not prove actual hypervisor capture or recovered guest data. Retain that provider unchanged and exercise it against the exact networkless Rocky CPU/QGA fixture produced by the separate bounded boot runner. This is a same-host provider qualification harness, not a customer VM orchestrator, native CloudStack NAS recovery, cross-Zone/site proof or failover controller.

Native CloudStack 4.22.1.1 remains the production VM/catalog authority. Existing exact-source native NAS adapter/recovery research remains applicable; this test deliberately calls the separately selected libvirt fallback on an explicitly disposable unmanaged guest. No Java, API, schema or scheduling change is justified. Replacing the provider with raw QMP, synthetic disks or file copying would not test its existing capture boundary. [Libvirt backup XML](https://libvirt.org/formatbackup.html) and [checkpoint XML](https://libvirt.org/formatcheckpoint.html) confirm explicit push targets and bitmap checkpoint lineage; [incremental handling](https://www.libvirt.org/kbase/internals/incremental-backup.html) explains reconstruction semantics. These living pages are semantic references, not version certification. The harness records and pins the actual signed Rocky libvirt/QEMU versions before invoking the existing engine, which rechecks those pins in its capture worker.

The root-only source ownership manifest must bind the exact CPU fixture UUID/name/runtime QCOW2, no NIC and explicit retention for DR qualification. The harness creates only its unique `/var/lib/libvirt/images/layersentry-drqc-<UUID>` namespace, with separate private journal, immutable destination and materialization roots plus a QEMU-traversable capture directory. Fresh UUIDs identifying this local test's plan/sites/repository are explicitly test identities; they are not fabricated CloudStack resource IDs. SELinux stays Enforcing. No service, network, storage mount, RKE2 or traffic configuration changes occur.

Through QGA, write nonsecret FULL/INC1/INC2 markers and a 1 MiB payload changing from one nonzero pattern to another and finally zero; fsync and sync before each crash-consistent capture. Capture one full plus two incrementals through FileReplicationEngine and MountedTransport. Inject one lost acknowledgement only after FileCatalog actually commits, reopen the controller and resume with capture prohibited. Require unchanged provider checkpoint count and correct source-head advancement. Replaying the same completed epoch must be idempotent; a conflicting mode must fail without a provider mutation.

Materialize the newest and older incremental checkpoint through FileCatalog/QcowTools. Record retained replica digests before and after reconstruction. Boot only fresh standalone private copies using the existing networkless CPU boot/QGA harness, then verify exact marker/payload hashes in each recovered guest. Shut down each recovered guest and remove only its owned runtime copy; retain bounded private source/catalog/journal evidence for the runtime owner's review. Never upload mutated guest disks or host private keys. Any uncertain provider mutation preserves its journal/objects for reconciliation, never blind retry.

Tests before dispatch cover ownership and invocation invariants; the primary acceptance is the real runner execution. Results must identify source/image hashes, plan/domain/epoch IDs, actual versions, capture/ACK/reconstruction/boot timings, marker hashes, negative/idempotency results and cleanup state. Successful same-host behavior cannot certify authenticated inter-site transport, multi-disk consistency, native CloudStack import, guest networking, failover/failback, witness/fencing, Kubernetes storage or production RPO/RTO. Those gates remain separate.

## Implementation and runner interface

Source implementation is `tools/layersentry/dr_cpu_capture_acceptance.py`. Deploy it together with `dr_file_replication.py`, `dr_libvirt_capture.py`, `dr_replication.py`, `dr_replication_transport.py` and `k8s/image/boot_qga_acceptance.py`, preserving the relative paths. The host requires the already installed signed `python3-libvirt`, QEMU tools, libvirt, xorriso and Enforcing SELinux. No pip package installation or Git checkout on the runtime host is needed.

```sh
python3 tools/layersentry/dr_cpu_capture_acceptance.py \
  --ownership-manifest /var/lib/libvirt/images/layersentry-cpuqc-UUID/ownership.json \
  --evidence /approved/evidence/unique-capture-run \
  --libvirt-version 11010000 --qemu-version 10001000 \
  --source-commit "$REVIEWED_SOURCE_COMMIT"
```

These version pins match the root owner's signed Rocky prerequisite evidence, not a moving package recommendation. The runner must bind the deployed source files to the supplied reviewed commit and identify the `.20` boundary before dispatch. The owned source fixture must have no prior checkpoint or snapshot; a failed capture is reconciled through its existing journal, never retried with fresh epoch IDs by rerunning this acceptance script.

The harness retains only three capture epochs, their immutable same-host repository, source journal and two standalone recovery materializations under its private workspace. Recovered running copies are cleaned immediately after marker checks. The source guest stays with its runtime owner. After all source/recovery guests are shut down, the owner may remove this exact qualification workspace through:

```sh
python3 tools/layersentry/dr_cpu_capture_acceptance.py \
  --cleanup-workspace /var/lib/libvirt/images/layersentry-drqc-UUID/ownership.json
```

This cleanup refuses an unfinished manifest, wrong root/path/UUID or an active associated domain; it neither shuts down the source nor deletes any other repository. Provider failures preserve source capture state and require reconciliation. Only bounded JSON journals and hashes belong in runner artifacts; capture/catalog/recovered QCOW2 files contain newly generated guest private keys and must remain private.

Five local acceptance-harness tests cover explicit source retention, network/checkpoint rejection before capture, exact fixture binding, ACK injection after destination commit, and non-overwrite of existing evidence. Twelve image/boot input tests also pass. No libvirt capture, guest boot, SSH or CloudStack call was executed by this source worker. Live result remains `NOT_TESTED` until the integration owner's exact runner succeeds.

QGA confinement review after initial boot: the owned NoCloud seed now runs the fixed privileged boot health diagnostic through cloud-final and publishes a root-owned, nonsecret report bound to the fresh domain UUID. QGA only reads that report; a recovered disk's stale report cannot satisfy the fresh fixture check. This avoids granting the QGA SELinux domain SSH private-key/root-home or cloud-init state access. The isolated DR marker lives under `/var/tmp/layersentry-dr-qualification` on the guest root disk, where the exact vendor policy creates `virt_qemu_ga_tmp_t` objects for QGA. It remains a short-lived nonsecret fixture, not a customer-data storage path; recovery tests must finish before normal age-based temporary-file cleanup. No QGA unconfined/manage-SSH boolean or broad SELinux policy allowance is introduced. Source guard tests and shell syntax pass; runtime remains NOT_TESTED for these corrections.

The QGA report reader also waits for the real image public-key export, validates root ownership, regular single-link bounded files and trusted directory ancestry, and compares its public wire value with the original host key inspected by the fixed privileged fixture diagnostic. DR marker creation rejects a filesystem device different from the captured root disk (including a temporary tmpfs mount).
