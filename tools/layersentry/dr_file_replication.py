"""File-backed replication plans, sealed epoch catalog and offline reconstruction.

Status: NOT_TESTED. Mutations occur only through explicit library/CLI calls.
Native CloudStack backup UUIDs and libvirt checkpoint epochs are never mixed.
"""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import stat
import struct
import subprocess
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Iterator

from dr_replication import (
    CHUNK_BYTES, JSON_LIMIT, CopyLimits, Repository, ReplicationError,
    canonical, component, deadline_check, directory, file_digest, fingerprint,
    identifier, read_json, regular_file, rename_once, require, write_json_once,
)


def sha256(value: str) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "INVALID_SHA256")
    return value


def absolute_path(value: str) -> Path:
    require(isinstance(value, str), "INVALID_ABSOLUTE_PATH")
    path = Path(value)
    require(path.is_absolute() and len(path.parts) >= 3 and ".." not in path.parts
            and str(path) == value and "\x00" not in value, "INVALID_ABSOLUTE_PATH")
    return path


@contextlib.contextmanager
def secure_root(path: Path, *, private: bool = True) -> Iterator[int]:
    """Open an existing trusted root without following any symlink component."""
    absolute_path(str(path))
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in path.parts[1:]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        mask = 0o077 if private else 0o022
        require(info.st_uid == os.geteuid() and not info.st_mode & mask, "TRUSTED_ROOT_OWNER_MODE_REQUIRED")
        yield fd
    finally:
        os.close(fd)


def replace_json(parent: int, name: str, payload: dict) -> None:
    """Mutable private journal checkpoint; caller holds its workload lock."""
    data = canonical(payload)
    require(len(data) <= JSON_LIMIT, "JOURNAL_TOO_LARGE")
    temporary = "state-" + uuid.uuid4().hex
    fd = regular_file(parent, temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    # Reject an unsafe existing target before replacing only this service's state.
    try:
        previous = regular_file(parent, name)
    except FileNotFoundError:
        pass
    else:
        os.close(previous)
    os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
    os.fsync(parent)


@dataclass(frozen=True)
class FileDisk:
    device: str
    volume_id: str
    source_path: str
    virtual_bytes: int

    def validate(self) -> None:
        require(isinstance(self.device, str) and re.fullmatch(r"(?:vd|sd|hd)[a-z]{1,3}", self.device) is not None,
                "INVALID_LIBVIRT_DISK_TARGET")
        identifier(self.volume_id)
        absolute_path(self.source_path)
        require(type(self.virtual_bytes) is int and 0 < self.virtual_bytes <= 1024 ** 5, "INVALID_VIRTUAL_DISK_SIZE")


@dataclass(frozen=True)
class FilePlan:
    plan_id: str
    tenant_id: str
    workload_id: str
    source_site_id: str
    recovery_site_id: str
    repository_id: str
    domain_uuid: str
    domain_name: str
    disks: tuple[FileDisk, ...]
    libvirt_version: int
    qemu_version: int
    max_chain: int = 24
    retention_count: int = 24
    minimum_retention_seconds: int = 86400
    rpo_seconds: int = 300
    capture_timeout: int = 3600
    transfer_timeout: int = 3600
    max_bytes: int = 16 * 1024 ** 4
    reserve_bytes: int = 1024 ** 3
    max_points: int = 4096

    @classmethod
    def from_dict(cls, value: dict) -> FilePlan:
        require(isinstance(value, dict) and isinstance(value.get("disks"), list), "INVALID_FILE_PLAN")
        try:
            return cls(**{**value, "disks": tuple(FileDisk(**item) for item in value["disks"])})
        except (TypeError, KeyError):
            raise ReplicationError("INVALID_FILE_PLAN") from None

    def validate(self) -> None:
        for value in (self.plan_id, self.tenant_id, self.workload_id, self.source_site_id,
                      self.recovery_site_id, self.repository_id, self.domain_uuid):
            identifier(value)
        component(self.domain_name)
        require(self.source_site_id != self.recovery_site_id, "DISTINCT_SITES_REQUIRED")
        require(isinstance(self.disks, tuple) and 1 <= len(self.disks) <= 64, "INVALID_DISK_COUNT")
        for disk in self.disks:
            disk.validate()
        for field in ("device", "volume_id", "source_path"):
            require(len({getattr(disk, field) for disk in self.disks}) == len(self.disks), "DUPLICATE_DISK")
        require(type(self.libvirt_version) is int and self.libvirt_version >= 7002000
                and type(self.qemu_version) is int and self.qemu_version >= 4002000, "PIN_SUPPORTED_PROVIDER_VERSIONS")
        bounds = ((self.max_chain, 1, 128), (self.retention_count, 2, 4096),
                  (self.minimum_retention_seconds, 0, 10 * 365 * 86400),
                  (self.rpo_seconds, 1, 86400), (self.capture_timeout, 1, 86400),
                  (self.transfer_timeout, 1, 86400), (self.max_points, 2, 100000))
        require(all(type(value) is int and low <= value <= high for value, low, high in bounds), "INVALID_PLAN_LIMIT")
        require(self.retention_count <= self.max_points, "RETENTION_EXCEEDS_CATALOG_LIMIT")
        CopyLimits(self.max_bytes, self.transfer_timeout, self.reserve_bytes).validate()
        require(sum(disk.virtual_bytes for disk in self.disks) <= self.max_bytes, "WORKLOAD_EXCEEDS_PLAN_LIMIT")

    def scope(self) -> dict:
        self.validate()
        # Policy changes do not rewrite already sealed epoch identity.
        payload = asdict(self)
        payload["disks"] = [asdict(disk) for disk in self.disks]
        return {key: value for key, value in payload.items() if key in {
            "plan_id", "tenant_id", "workload_id", "source_site_id", "recovery_site_id",
            "repository_id", "domain_uuid", "domain_name", "disks", "libvirt_version", "qemu_version",
        }}

    def limits(self) -> CopyLimits:
        return CopyLimits(self.max_bytes, self.transfer_timeout, self.reserve_bytes)


def validate_manifest(value: dict, plan: FilePlan) -> None:
    require(isinstance(value, dict) and set(value) == {
        "schema", "provider", "epoch_id", "scope", "mode", "parent", "captured_at_epoch",
        "checkpoint", "consistency", "disks",
    }, "INVALID_EPOCH_MANIFEST")
    require(value["schema"] == 1 and value["provider"] == "LIBVIRT_QCOW2"
            and value["scope"] == plan.scope() and value["consistency"] == "CRASH", "EPOCH_SCOPE_MISMATCH")
    identifier(value["epoch_id"])
    require(value["checkpoint"] == "lsdr-" + value["epoch_id"], "CHECKPOINT_IDENTITY_MISMATCH")
    require(type(value["captured_at_epoch"]) is int and 0 < value["captured_at_epoch"] <= int(time.time()) + 300,
            "SOURCE_CLOCK_OR_CAPTURE_TIME_INVALID")
    require(value["mode"] in {"FULL", "INCREMENTAL"}, "INVALID_CAPTURE_MODE")
    parent = value["parent"]
    if value["mode"] == "FULL":
        require(parent is None, "FULL_POINT_CANNOT_DEPEND_ON_PARENT")
    else:
        require(isinstance(parent, dict) and set(parent) == {"epoch_id", "manifest_sha256"}, "INCREMENTAL_PARENT_REQUIRED")
        identifier(parent["epoch_id"])
        sha256(parent["manifest_sha256"])
        require(parent["epoch_id"] != value["epoch_id"], "SELF_REFERENTIAL_EPOCH")
    entries = value["disks"]
    require(isinstance(entries, list) and len(entries) == len(plan.disks), "EPOCH_DISKS_MISSING")
    total = 0
    for entry, disk in zip(entries, plan.disks):
        require(isinstance(entry, dict) and set(entry) == {
            "device", "volume_id", "virtual_bytes", "filename", "size", "sha256",
        }, "INVALID_EPOCH_DISK")
        require(entry["device"] == disk.device and entry["volume_id"] == disk.volume_id
                and entry["virtual_bytes"] == disk.virtual_bytes
                and entry["filename"] == disk.device + ".qcow2", "EPOCH_DISK_IDENTITY_MISMATCH")
        require(type(entry["size"]) is int and 0 < entry["size"] <= plan.max_bytes, "INVALID_EPOCH_DISK_SIZE")
        sha256(entry["sha256"])
        total += entry["size"]
    require(total <= plan.max_bytes, "EPOCH_EXCEEDS_PLAN_LIMIT")


def check_qcow2(parent: int, entry: dict) -> None:
    """Reject external/backing references before any qemu-img parser can open them."""
    fd = regular_file(parent, entry["filename"])
    with os.fdopen(fd, "rb") as handle:
        header = handle.read(104)
    require(len(header) == 104 and header[:4] == b"QFI\xfb", "QCOW2_HEADER_REQUIRED")
    version = struct.unpack_from(">I", header, 4)[0]
    backing_offset, backing_size = struct.unpack_from(">QI", header, 8)
    size = struct.unpack_from(">Q", header, 24)[0]
    crypt = struct.unpack_from(">I", header, 32)[0]
    snapshots = struct.unpack_from(">I", header, 60)[0]
    incompatible = struct.unpack_from(">Q", header, 72)[0] if version == 3 else 0
    require(version in {2, 3} and backing_offset == 0 and backing_size == 0
            and size == entry["virtual_bytes"] and crypt == 0 and snapshots == 0 and incompatible == 0,
            "UNSAFE_OR_UNSEALED_QCOW2")


def verify_disks(folder: int, manifest: dict, plan: FilePlan, deadline: float) -> None:
    validate_manifest(manifest, plan)
    for entry in manifest["disks"]:
        require(file_digest(folder, entry["filename"], deadline, plan.max_bytes)
                == (entry["size"], entry["sha256"]), "EPOCH_DISK_INTEGRITY_FAILURE")
        check_qcow2(folder, entry)
        fd = regular_file(folder, entry["filename"])
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def write_disk(folder: int, entry: dict, chunks: Iterable[bytes], limits: CopyLimits, deadline: float) -> None:
    import hashlib
    available = os.fstatvfs(folder)
    require(available.f_bavail * available.f_frsize >= entry["size"] + limits.reserve_bytes, "DESTINATION_CAPACITY_INSUFFICIENT")
    temporary = entry["filename"] + ".partial"
    # A crash can occur after sealing/fsync but before publication. Reopen only
    # the service-owned partial for this locked immutable intent; completed
    # point files remain read-only and are never rewritten.
    try:
        previous = regular_file(folder, temporary)
    except FileNotFoundError:
        pass
    else:
        try:
            require(os.fstat(previous).st_uid == os.geteuid(), "PARTIAL_FILE_OWNER_CHANGED")
            os.fchmod(previous, 0o600)
        finally:
            os.close(previous)
    fd = regular_file(folder, temporary, os.O_WRONLY | os.O_CREAT)
    with os.fdopen(fd, "wb") as target:
        os.ftruncate(target.fileno(), 0)
        digest, size = hashlib.sha256(), 0
        for block in chunks:
            deadline_check(deadline)
            require(isinstance(block, bytes) and 0 < len(block) <= CHUNK_BYTES, "INVALID_TRANSFER_CHUNK")
            size += len(block)
            require(size <= entry["size"], "TRANSFER_EXCEEDS_MANIFEST")
            digest.update(block)
            target.write(block)
        require(size == entry["size"] and digest.hexdigest() == entry["sha256"], "TRANSFER_INTEGRITY_FAILURE")
        target.flush()
        os.fchmod(target.fileno(), 0o400)
        os.fsync(target.fileno())
    rename_once(folder, temporary, folder, entry["filename"])
    os.fsync(folder)


def disk_chunks(folder: int, entry: dict) -> Iterator[bytes]:
    fd = regular_file(folder, entry["filename"])
    with os.fdopen(fd, "rb") as source:
        before = os.fstat(source.fileno())
        require(before.st_size == entry["size"], "SEALED_SOURCE_CHANGED")
        remaining = entry["size"]
        while remaining:
            block = source.read(min(CHUNK_BYTES, remaining))
            require(bool(block), "SEALED_SOURCE_TRUNCATED")
            remaining -= len(block)
            yield block
        after = os.fstat(source.fileno())
        require((before.st_ino, before.st_mtime_ns, before.st_ctime_ns, before.st_size)
                == (after.st_ino, after.st_mtime_ns, after.st_ctime_ns, after.st_size), "SEALED_SOURCE_CHANGED")


class FileCatalog:
    def __init__(self, repository: Repository, plan: FilePlan):
        plan.validate()
        require(repository.site_id == plan.recovery_site_id and repository.repository_id == plan.repository_id,
                "DESTINATION_PLAN_MISMATCH")
        self.repository, self.plan = repository, plan

    @contextlib.contextmanager
    def locked(self, *, create: bool = False):
        with self.repository.opened() as root:
            with directory(root, [".layersentry-file", self.plan.plan_id], create=create, private=True) as folder:
                lock = regular_file(folder, "writer.lock", os.O_RDWR | os.O_CREAT)
                try:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        raise ReplicationError("CATALOG_BUSY") from None
                    with directory(folder, ["points"], create=create, private=True) as points:
                        yield folder, points
                finally:
                    os.close(lock)

    def _manifest(self, points: int, epoch_id: str) -> dict:
        identifier(epoch_id)
        with directory(points, [epoch_id], private=True) as folder:
            value = read_json(folder, "manifest.json")
        validate_manifest(value, self.plan)
        require(value["epoch_id"] == epoch_id, "CATALOG_POINT_MISMATCH")
        return value

    def _chain(self, points: int, epoch_id: str, *, verify: bool, deadline: float) -> list[dict]:
        chain, seen, expected = [], set(), None
        while epoch_id:
            deadline_check(deadline)
            require(epoch_id not in seen and len(chain) < 128, "CHAIN_CYCLE_OR_LIMIT")
            seen.add(epoch_id)
            manifest = self._manifest(points, epoch_id)
            require(expected is None or fingerprint(manifest) == expected, "PARENT_MANIFEST_CHANGED")
            if chain:
                require(manifest["captured_at_epoch"] <= chain[-1]["captured_at_epoch"], "CHAIN_TIME_ORDER_INVALID")
            if verify:
                with directory(points, [epoch_id], private=True) as folder:
                    verify_disks(folder, manifest, self.plan, deadline)
            chain.append(manifest)
            parent = manifest["parent"]
            epoch_id, expected = (parent["epoch_id"], parent["manifest_sha256"]) if parent else (None, None)
        return list(reversed(chain))

    def verify(self, epoch_id: str) -> dict:
        deadline = time.monotonic() + self.plan.transfer_timeout
        with self.locked() as (_, points):
            chain = self._chain(points, epoch_id, verify=True, deadline=deadline)
            os.fsync(points)
            return self.receipt(chain[-1], len(chain))

    @staticmethod
    def receipt(manifest: dict, chain_length: int) -> dict:
        return {"state": "COMMITTED", "epoch_id": manifest["epoch_id"],
                "manifest_sha256": fingerprint(manifest), "chain_length": chain_length,
                "captured_at_epoch": manifest["captured_at_epoch"], "acknowledged_at_epoch": int(time.time()),
                "bytes": sum(entry["size"] for entry in manifest["disks"]), "guest_validation": "NOT_TESTED"}

    @contextlib.contextmanager
    def incoming(self, manifest: dict):
        validate_manifest(manifest, self.plan)
        deadline = time.monotonic() + self.plan.transfer_timeout
        with self.locked(create=True) as (root, points):
            parent = manifest["parent"]
            chain_length = 1
            if parent:
                chain = self._chain(points, parent["epoch_id"], verify=True, deadline=deadline)
                require(fingerprint(chain[-1]) == parent["manifest_sha256"], "DESTINATION_PARENT_MISMATCH")
                require(chain[-1]["captured_at_epoch"] <= manifest["captured_at_epoch"], "CHAIN_TIME_ORDER_INVALID")
                chain_length += len(chain)
                require(chain_length <= self.plan.max_chain, "NEW_BASELINE_REQUIRED")
            try:
                existing = self._manifest(points, manifest["epoch_id"])
            except FileNotFoundError:
                existing = None
            if existing is not None:
                require(existing == manifest, "EPOCH_IDEMPOTENCY_CONFLICT")
                with directory(points, [manifest["epoch_id"]], private=True) as final:
                    verify_disks(final, manifest, self.plan, deadline)
                    os.fsync(final)
                os.fsync(points)
                yield IncomingEpoch(self, manifest, None, points, None, deadline, chain_length)
                return
            require(len(os.listdir(points)) < self.plan.max_points, "CATALOG_CAPACITY_REACHED")
            with directory(root, ["incoming"], create=True, private=True) as pending:
                require(manifest["epoch_id"] in os.listdir(pending)
                        or len(os.listdir(pending)) < self.plan.max_points, "STAGING_CAPACITY_REACHED")
                with directory(pending, [manifest["epoch_id"]], create=True, private=True) as stage:
                    write_json_once(stage, "intent.json", manifest)
                    yield IncomingEpoch(self, manifest, stage, points, pending, deadline, chain_length)

    def receive_local(self, manifest: dict, source_folder: int) -> dict:
        with self.incoming(manifest) as incoming:
            for entry in incoming.missing():
                incoming.write(entry, disk_chunks(source_folder, entry))
            return incoming.commit()

    def _inventory(self, points: int) -> list[dict]:
        ids = os.listdir(points)
        require(len(ids) <= self.plan.max_points, "CATALOG_CAPACITY_REACHED")
        return sorted((self._manifest(points, epoch_id) for epoch_id in ids),
                      key=lambda item: (item["captured_at_epoch"], item["epoch_id"]), reverse=True)

    def listing(self, *, offset: int = 0, limit: int = 100) -> dict:
        require(type(offset) is int and offset >= 0 and type(limit) is int and 1 <= limit <= 100, "INVALID_PAGE")
        with self.locked() as (_, points):
            inventory = self._inventory(points)
            return {"points": [{"epoch_id": item["epoch_id"], "mode": item["mode"], "parent": item["parent"],
                                "captured_at_epoch": item["captured_at_epoch"], "manifest_sha256": fingerprint(item),
                                "integrity": "NOT_RECHECKED", "guest_validation": "NOT_TESTED"}
                               for item in inventory[offset:offset + limit]],
                    "total": len(inventory), "next_offset": offset + limit if offset + limit < len(inventory) else None}

    def _retention(self, root: int, points: int, pinned: tuple[str, ...]) -> dict:
        inventory = self._inventory(points)
        keep = {item["epoch_id"] for item in inventory[:self.plan.retention_count]}
        if inventory:
            # Checkpoint clocks have second precision. Retain the whole cutoff
            # timestamp, rather than guessing order between equal-time UUIDs.
            cutoff = inventory[min(self.plan.retention_count, len(inventory)) - 1]["captured_at_epoch"]
            keep.update(item["epoch_id"] for item in inventory if item["captured_at_epoch"] >= cutoff)
        keep.update(identifier(item) for item in pinned)
        now = int(time.time())
        keep.update(item["epoch_id"] for item in inventory
                    if now - item["captured_at_epoch"] < self.plan.minimum_retention_seconds)
        pending_bindings = []
        try:
            os.stat("incoming", dir_fd=root, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            with directory(root, ["incoming"], private=True) as pending:
                for epoch_id in os.listdir(pending):
                    identifier(epoch_id)
                    with directory(pending, [epoch_id], private=True) as folder:
                        manifest = read_json(folder, "intent.json")
                    validate_manifest(manifest, self.plan)
                    pending_bindings.append((epoch_id, fingerprint(manifest)))
                    if manifest["parent"]:
                        keep.add(manifest["parent"]["epoch_id"])
        protected = set()
        deadline = time.monotonic() + self.plan.transfer_timeout
        for epoch_id in keep:
            protected.update(item["epoch_id"] for item in self._chain(points, epoch_id, verify=False, deadline=deadline))
        return {"catalog_sha256": fingerprint({"points": [(item["epoch_id"], fingerprint(item)) for item in inventory],
                                               "pending": sorted(pending_bindings), "pinned": sorted(pinned)}),
                "retire": [item["epoch_id"] for item in inventory if item["epoch_id"] not in protected],
                "protected": sorted(protected), "action": "MOVE_TO_RECOVERABLE_TRASH"}

    def retention(self, *, pinned: tuple[str, ...] = ()) -> dict:
        with self.locked() as (root, points):
            return self._retention(root, points, pinned)

    def retire(self, expected_catalog_sha256: str, *, pinned: tuple[str, ...] = ()) -> dict:
        sha256(expected_catalog_sha256)
        with self.locked() as (root, points):
            decision = self._retention(root, points, pinned)
            require(decision["catalog_sha256"] == expected_catalog_sha256, "RETENTION_VIEW_CHANGED")
            with directory(root, ["trash"], create=True, private=True) as trash:
                for epoch_id in decision["retire"]:
                    rename_once(points, epoch_id, trash, epoch_id)
                    os.fsync(points)
                    os.fsync(trash)
            return {"retired": decision["retire"], "recoverable": True, "bytes_reclaimed": 0}

    def materialize(self, epoch_id: str, output_root: Path, tools: QcowTools) -> dict:
        """Reconstruct into new private files; never change a retained/source image."""
        identifier(epoch_id)
        deadline = time.monotonic() + self.plan.transfer_timeout
        tools.check_version(deadline)
        with self.locked() as (_, points), secure_root(output_root) as outputs:
            chain = self._chain(points, epoch_id, verify=True, deadline=deadline)
            needed = sum(disk.virtual_bytes for disk in self.plan.disks) * 2
            needed += sum(entry["size"] for manifest in chain for entry in manifest["disks"])
            available = os.fstatvfs(outputs)
            require(available.f_bavail * available.f_frsize >= needed + self.plan.reserve_bytes, "MATERIALIZATION_CAPACITY_INSUFFICIENT")
            attempt = "restore-" + str(uuid.uuid4())
            os.mkdir(attempt, 0o700, dir_fd=outputs)
            os.fsync(outputs)
            workspace = output_root / attempt
            with directory(outputs, [attempt], private=True) as work:
                write_json_once(work, "intent.json", {"epoch_id": epoch_id, "manifest_sha256": fingerprint(chain[-1])})
                with directory(work, ["chain"], create=True, private=True) as layers:
                    for index, manifest in enumerate(chain):
                        with directory(layers, [str(index)], create=True, private=True) as target:
                            with directory(points, [manifest["epoch_id"]], private=True) as source:
                                for entry in manifest["disks"]:
                                    write_disk(target, entry, disk_chunks(source, entry), self.plan.limits(), deadline)
                                    if index:
                                        path = workspace / "chain" / str(index) / entry["filename"]
                                        previous = workspace / "chain" / str(index - 1) / entry["filename"]
                                        # Only our verified private copies get writable metadata.
                                        fd = regular_file(target, entry["filename"])
                                        try:
                                            os.fchmod(fd, 0o600)
                                        finally:
                                            os.close(fd)
                                        tools.rebase_copy(path, previous, deadline)
                outputs_manifest = []
                with directory(work, ["disks"], create=True, private=True) as full:
                    for disk in self.plan.disks:
                        filename = disk.device + ".qcow2"
                        source = workspace / "chain" / str(len(chain) - 1) / filename
                        target = workspace / "disks" / filename
                        tools.flatten(source, target, deadline)
                        size, digest = file_digest(full, filename, deadline, self.plan.max_bytes)
                        entry = {"device": disk.device, "volume_id": disk.volume_id, "virtual_bytes": disk.virtual_bytes,
                                 "filename": filename, "size": size, "sha256": digest}
                        check_qcow2(full, entry)
                        fd = regular_file(full, filename)
                        try:
                            os.fsync(fd)
                        finally:
                            os.close(fd)
                        outputs_manifest.append(entry)
                    os.fsync(full)
                receipt = {"epoch_id": epoch_id, "source_manifest_sha256": fingerprint(chain[-1]),
                           "disks": outputs_manifest, "state": "MATERIALIZED", "guest_validation": "NOT_TESTED"}
                write_json_once(work, "complete.json", receipt)
                os.fsync(work)
            os.fsync(outputs)
            return {**receipt, "output_directory": str(workspace)}


class IncomingEpoch:
    def __init__(self, catalog, manifest, stage, points, pending, deadline, chain_length):
        self.catalog, self.manifest, self.stage = catalog, manifest, stage
        self.points, self.pending, self.deadline, self.chain_length = points, pending, deadline, chain_length
        self.committed = stage is None

    def missing(self) -> list[dict]:
        if self.committed:
            return []
        missing = []
        for entry in self.manifest["disks"]:
            try:
                actual = file_digest(self.stage, entry["filename"], self.deadline, self.catalog.plan.max_bytes)
            except FileNotFoundError:
                missing.append(entry)
                continue
            require(actual == (entry["size"], entry["sha256"]), "STAGED_EPOCH_CONFLICT")
        return missing

    def write(self, entry: dict, chunks: Iterable[bytes]) -> None:
        require(not self.committed and entry in self.manifest["disks"], "UNEXPECTED_EPOCH_DISK")
        write_disk(self.stage, entry, chunks, self.catalog.plan.limits(), self.deadline)

    def commit(self) -> dict:
        if not self.committed:
            verify_disks(self.stage, self.manifest, self.catalog.plan, self.deadline)
            write_json_once(self.stage, "manifest.json", self.manifest)
            os.fsync(self.stage)
            rename_once(self.pending, self.manifest["epoch_id"], self.points, self.manifest["epoch_id"])
            os.fsync(self.points)
            os.fsync(self.pending)
            self.committed = True
        return self.catalog.receipt(self.manifest, self.chain_length)


class QcowTools:
    """Trusted qemu-img, bounded output, no shell, no repair or active-disk edits."""
    def __init__(self, executable: Path, expected_version: int):
        absolute_path(str(executable))
        require(executable.resolve() == executable and executable.is_file(), "TRUSTED_QEMU_IMG_REQUIRED")
        info = executable.stat()
        require(info.st_uid in {0, os.geteuid()} and not info.st_mode & 0o022, "TRUSTED_QEMU_IMG_REQUIRED")
        self.executable, self.expected_version = executable, expected_version

    def run(self, arguments: list[str], deadline: float) -> bytes:
        deadline_check(deadline)
        with tempfile.TemporaryFile() as output:
            try:
                result = subprocess.run([str(self.executable), *arguments], stdin=subprocess.DEVNULL,
                                        stdout=output, stderr=subprocess.DEVNULL,
                                        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                                        timeout=max(0.1, deadline - time.monotonic()), check=False)
            except subprocess.TimeoutExpired:
                raise ReplicationError("QCOW_OPERATION_TIMEOUT_KEEP_WORKSPACE") from None
            require(result.returncode == 0, "QCOW_OPERATION_FAILED_KEEP_WORKSPACE")
            require(output.tell() <= JSON_LIMIT, "QCOW_OUTPUT_LIMIT")
            output.seek(0)
            return output.read(JSON_LIMIT)

    def check_version(self, deadline: float) -> None:
        output = self.run(["--version"], deadline).decode("ascii", errors="strict")
        match = re.search(r"qemu-img version (\d+)\.(\d+)\.(\d+)", output)
        require(match is not None, "QCOW_VERSION_UNKNOWN")
        actual = int(match[1]) * 1000000 + int(match[2]) * 1000 + int(match[3])
        require(actual == self.expected_version, "QCOW_VERSION_PIN_MISMATCH")

    def check(self, path: Path, deadline: float) -> None:
        self.run(["check", "-f", "qcow2", "--output=json", str(path)], deadline)

    def rebase_copy(self, path: Path, parent: Path, deadline: float) -> None:
        self.run(["rebase", "-u", "-f", "qcow2", "-F", "qcow2", "-b", str(parent), str(path)], deadline)

    def flatten(self, source: Path, destination: Path, deadline: float) -> None:
        require(not destination.exists() and not destination.is_symlink(), "RESTORE_TARGET_EXISTS")
        self.run(["convert", "-f", "qcow2", "-O", "qcow2", str(source), str(destination)], deadline)
        self.check(destination, deadline)
