# Completed libvirt incremental capture sealing

Status: IMPLEMENTED_SOURCE_QUALIFIED. Source-only scope; no live mutation or recovery claim.

The retained full point committed, but incremental capture34057792718 failed the
sealed-only QCOW gate. Read-only probe34058283613 found an exact source-disk backing
filename in the incremental header (offset528,length92), crypt0,snapshots0,
incompatible0. Libvirt11.10 qemu_backup.c explicitly selects the original source
as backing for incremental push. The catalog correctly rejects that live external
reference; weakening its validation would expose recovery to mutable source data.

Keep native libvirt backup/checkpoint submission and the existing catalog contract.
After exact successful provider-job/checkpoint observation, claim the completed
capture files into the private operator directory and durably record their native
inode/device/size plus immutable intent/scope/checkpoint binding. Before any image
parser, a separate capture-only parser permits only the exact plan source backing
for an incremental, no encryption/snapshots/incompatible features, and a bounded
known metadata-extension set. It never follows the referenced path.

Persist each file's sealing intent before native `qemu-img rebase -u -f qcow2 -b ''`.
Pinned qemu-img source opens unsafe rebase with BDRV_O_NO_BACKING: it changes the
backing association without reading/copying the original disk. Do not flatten or
sparsify a delta: explicit zero extents must continue overriding parent bytes.
After detach, run the unchanged sealed-only header gate, native check without
repair, final immutable hashing and mode0400. Only then publish capture completion.

Resume offline sealing only when the durable exact provider completion receipt
exists, no recorded worker is still active and the private target inode binding
matches. A saved per-file sealing intent allows observing an already detached
header after interruption. Changed/malformed headers fail; no automatic repair or
backupBegin replay. The earlier failed run has no such receipt and must remain
operator-reconciled, without automatic salvage.

Alternatives: trusting backing filenames in the catalog would retain a live
external dependency; converting a standalone detached delta can discard allocated
zero overrides; in-place flattening against the active source corrupts historical
point semantics. Native metadata-only detach in the private completed capture is
the bounded correction. CloudStack4.22.1.1 API/core/VM ownership remains unchanged;
XaaS does not apply to this existing native libvirt checkpoint provider.

Sources inspected:
- https://github.com/libvirt/libvirt/blob/v11.10.0/src/qemu/qemu_backup.c
- https://github.com/qemu/qemu/blob/v10.2.1/qemu-img.c (img_rebase: BDRV_O_NO_BACKING)
- https://github.com/qemu/qemu/blob/v10.2.1/docs/interop/qcow2.rst
- https://libvirt.org/formatbackup.html
- https://www.qemu.org/docs/master/tools/qemu-img.html (cross-checked with pinned source)

Local qualification used real QEMU 6.2.0 (Debian 1:6.2+dfsg-2ubuntu6.31),
not the target Rocky/libvirt runtime. Full/incremental/explicit-zero reconstruction
passed with the active original changed after capture; detached images retained
allocated extent maps and physical block counts. Detaching with the original
source removed also passed. Negative checks reject foreign absolute, relative and
protocol backing references, encryption, snapshots, incompatible features and
external-data extensions before an image parser opens the capture. Tests cover
absent provider completion, changed intent/inode/header, interruption after native
detach, offline resume without a second detach, and a still-active worker.

The full DR unittest discovery ran 41 tests: 36 passed and 5 existing native
CloudStack adapter tests skipped because their external Cozystack adapter test
directory was not supplied. All 31 capture/runtime tests executed and passed.
Command (with LAYERSENTRY_TEST_QEMU_IMG and LAYERSENTRY_TEST_QEMU_IO pointing to
the local extracted real binaries): `python3 -m unittest discover -s
tools/layersentry/tests -p 'test_dr*.py' -v`. Local receipt:
`/tmp/layersentry-dr-sealing-tests.log`. These are offline source tests, not a live
libvirt backup, native recovery or Rocky production qualification.
Native fixture capture/recovery and Rocky runtime verification remain root-owned.
Retain old source/catalog/journals. No automatic deletion, failover or promotion.
