# DR replication source qualification

Status: `PARTIAL`. Local regression and QEMU disk reconstruction passed. No DC, DR, Hyper-V, CloudStack API, libvirt domain, storage attachment, network or traffic mutation occurred. This checkpoint does not establish `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED`.

## Source continuity and decision

The isolated `codex/dr-module-completion` branch starts at fetched CloudStack integration `9d0b924493`. Prior unpublished source commits `9eaa121762` and `38a3ff5e55` were preserved and cherry-picked as `435ae432be` and `cd3562094c`; neither original worktree nor integration branch was reset or overwritten. The existing architecture remains native CloudStack NAS recovery first, with a distinct libvirt file-backed checkpoint path. No CloudStack Java, API, schema, scheduler or tenancy contract changed.

The bounded review found two reproducible interruption defects in that existing implementation: a sealed `0400` transfer partial could not be reopened by its dedicated unprivileged owner if interrupted before rename, and a durable source intent without the initial state checkpoint could never resume. Both were reproduced as failures before changing code. The fix reopens only the owned partial inside its locked staging directory and repairs only the pre-submission state window with no worker/capture evidence. Any uncertainty after hypervisor submission still prohibits replay. The CLI now validates the entire configuration even during `inspect` and offers `check-config` without connecting or creating runtime paths.

Alternatives were unnecessary for these causal fixes: replacing the storage provider, bypassing permissions, retrying a hypervisor mutation or weakening immutable publication would expand risk without fixing the journal/permission boundary. The exact existing CloudStack `Backup.VolumeInfo`, `BackupResponse`, NAS provider and native runner adapter were rechecked for metadata compatibility. [Libvirt backup XML](https://libvirt.org/formatbackup.html) confirms explicit disk/checkpoint capture semantics; [QEMU incremental backup documentation](https://www.qemu.org/docs/master/interop/bitmaps.html) describes restoring backing-free incrementals through an explicit private backing chain. These moving documentation pages are semantic references only; no new version support is inferred. The previous research matrix and alternatives remain in [the source design](2026-09-06-replication-source-design.md).

## Executed evidence

Tests are `tools/layersentry/tests/test_dr_replication_runtime.py` and `test_dr_native_binding.py`. The full local run passed **27 tests**, including:

- Real filesystem publication/fsync/rename, multi-disk incomplete transfer, immutable replay, corrupted parent, path/symlink/hardlink rejection, tenant/scope substitution, concurrent writer rejection, dependency-aware retention and recoverable trash.
- Both original failure reproductions now pass; missing state alongside worker evidence remains blocked.
- Protocol truncation, strict bound-file selection and unauthorized plan rejection.
- Lost destination acknowledgement resumes transfer without a second capture; missing durable capture proof never replays hypervisor submission.
- Real QEMU `6.2.0` construction and reconstruction of two disks across a full point plus two backing-free incremental points. Latest and both older outputs were converted to raw and compared byte-for-byte against independent expected arrays, including changed-to-zero blocks. Retained replica digests were rechecked after reconstruction.
- Native provider binding against the existing reviewed runner adapter: selected older backup creates exactly one stopped clone in the offline API fixture; ambiguous submission never resubmits; authorization, repository-route and isolated-network negatives prevent native mutation. No guest/API call ran against the lab.
- Complete offline configuration validation and both required enablement gates before CLI mutation.

The reproduction command is:

```bash
LAYERSENTRY_TEST_QEMU_IMG=/path/to/reviewed/qemu-img \
LAYERSENTRY_TEST_QEMU_IO=/path/to/reviewed/qemu-io \
LAYERSENTRY_NATIVE_ACCEPTANCE_DIR=/path/to/reviewed/cozystack/hack/layersentry \
python3 -m unittest discover -s tools/layersentry/tests -p 'test_dr*.py' -v
```

Missing QEMU/runner dependencies are explicit test skips, never proof of reconstruction/native integration. Synthetic QCOW headers in remaining tests exercise defensive parsing only; they are not usable guest images. Native authorization/route callbacks are controlled fixtures in these tests, not production implementations.

Local environment: Ubuntu development workspace, Python `3.10.12`; no host package installation. QEMU tools and two dependencies were downloaded through APT's existing package index into a private temporary directory and extracted there. Package SHA-256 values: `qemu-utils 1:6.2+dfsg-2ubuntu6.31` = `a12f6867b8c76f0184f3b247df41d20da8fee67f9eff0a01eecbb96bd6a32334`; `liburing2 2.1-2build1` = `f6e9bdf50c9683cd9a74ad92d51dde085f40baf0a5fcd8a56fc68425c1bd3c5f`; `libaio1 0.3.112-13build1` = `2dcfe0b49d7cccfbf1bd6a3f627cf44bea9f51fb32f7e0e552a0df75698e0d27`. This old QEMU version is preliminary regression evidence, not a selected production package recommendation. Native runner source is Cozystack `c8ad45c4dca0755ba3091a4ee3f445e5ba9b8361`, `dr_recovery_acceptance.py` SHA-256 `085d179822fb94e6bc7e19a0623fb3d127d57bd813df0a6d6965e875657942c3`.

## Remaining gates and handoff

Root reported fresh read-only DC run `34046294664`: Basic Zone `dc` remains Disabled, one KVM host Up/Enabled, no primary/image storage or guest VM rows reported. Optional API failure is not evidence of absence. The next live prerequisite is a real fixture with two Zones in one management database, an Advanced recovery destination, valid storage/network/SystemVM prerequisites, native NAS B&R enabled, a retained source VM and two distinguishable backups. A separate DR manager and file copies do not create native backup catalog identity.

Deploy all seven reviewed Python files together through the versioned runner path before using the fixed SSH receiver location. Receiver identity/known_hosts, forced-command policy, SELinux labels, service ownership, repository routing and retention authorization still require actual integration. The native adapter remains explicitly injected with trusted server-side authorization, repository-route and isolated-network verifiers; no permissive production defaults were added. The file provider materializes standalone disks but does not yet import/start a CloudStack recovery VM. CloudStack-supported import/attachment and isolated guest validation remain required.

Rocky validation must exercise real libvirt full/incremental capture, host restart, interrupted/ambiguous capture, authenticated transfer/lost ACK, latest and older guest data/network hashes, exact provider versions, capacity/failure cases and measured workload-specific RPO/RTO. Native recovery comes before planned failover, reverse replication/failback and any witness/fencing automation. No automatic failover or production eligibility is enabled. Same-host Hyper-V cannot establish physical-site independence.

Rollback is removal of this undeployed candidate source; no runtime rollback is needed. Once deployed, preserve journals, captured files and immutable replicas while reconciling exact operations; never reset source history or delete recovery data as an automatic rollback. Shared Progress Ledger updates remain with the integration lead.
