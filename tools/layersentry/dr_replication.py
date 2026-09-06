"""Sealed CloudStack NAS backup replication. Status: NOT_TESTED.

This is an explicit-call library, not a scheduler or a running-VM disk copier.
Repository mounts and their trust/retention configuration belong to the operator.
No source deletion, automatic pruning, mounting, promotion or VM mutation occurs.
"""

from __future__ import annotations

import contextlib
import ctypes
import fcntl
import hashlib
import json
import os
import re
import stat
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterator, Mapping

from dr_state_machine import ValidationError


MANIFEST_NAME = "layersentry-replica.json"
IDENTITY_NAME = ".layersentry-repository.json"
JSON_LIMIT = 128 * 1024
CHUNK_BYTES = 4 * 1024 * 1024


class ReplicationError(ValidationError):
    """Fixed diagnostic codes only; never include disk data or credentials."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReplicationError(code)


def identifier(value: str) -> str:
    try:
        require(isinstance(value, str) and str(uuid.UUID(value)) == value, "INVALID_UUID")
    except (ValueError, AttributeError, TypeError):
        raise ReplicationError("INVALID_UUID") from None
    return value


def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def rename_once(source_dir: int, source: str, target_dir: int, target: str) -> None:
    """Linux atomic no-replace rename; unsupported filesystems fail closed."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    require(rename is not None, "ATOMIC_NOREPLACE_RENAME_REQUIRED")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(source_dir, os.fsencode(source), target_dir, os.fsencode(target), 1) != 0:
        # Never downgrade to a replacing rename, including on NFS/SMB mounts
        # lacking the required operation. Keep staging intact for inspection.
        raise ReplicationError("ATOMIC_PUBLICATION_REFUSED")


def component(value: str) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,199}", value) is not None,
            "UNSAFE_PATH_COMPONENT")
    return value


@dataclass(frozen=True)
class BackupDisk:
    device_id: int
    volume_id: str
    filename: str

    def validate(self) -> None:
        require(type(self.device_id) is int and 0 <= self.device_id < 256, "INVALID_DEVICE_ID")
        identifier(self.volume_id)
        component(self.filename)
        prefix = "root." if self.device_id == 0 else "datadisk."
        require(self.filename.startswith(prefix) and self.filename.endswith(".qcow2"), "INVALID_BACKUP_FILENAME")


@dataclass(frozen=True)
class BackupIdentity:
    plan_id: str
    account_id: str
    domain_id: str
    workload_id: str
    source_site_id: str
    recovery_site_id: str
    repository_id: str
    offering_id: str
    backup_id: str
    external_id: str
    captured_at_epoch: int
    disks: tuple[BackupDisk, ...]

    def validate(self) -> None:
        for field in (self.plan_id, self.account_id, self.domain_id, self.workload_id,
                      self.source_site_id, self.recovery_site_id, self.repository_id,
                      self.offering_id, self.backup_id):
            identifier(field)
        require(self.source_site_id != self.recovery_site_id, "DISTINCT_SITES_REQUIRED")
        require(type(self.captured_at_epoch) is int and 0 < self.captured_at_epoch <= int(time.time()),
                "INVALID_SOURCE_CAPTURE_TIME")
        require(isinstance(self.external_id, str) and len(self.external_id.split("/")) == 2,
                "INVALID_NATIVE_BACKUP_PATH")
        for part in self.external_id.split("/"):
            component(part)
        require(isinstance(self.disks, tuple) and 1 <= len(self.disks) <= 64, "INVALID_DISK_MEMBERSHIP")
        for disk in self.disks:
            disk.validate()
        for field in ("device_id", "volume_id", "filename"):
            require(len({getattr(disk, field) for disk in self.disks}) == len(self.disks), "DUPLICATE_DISK")
        require(sum(disk.device_id == 0 for disk in self.disks) == 1, "EXACT_ROOT_DISK_REQUIRED")

    def payload(self) -> dict:
        self.validate()
        data = asdict(self)
        data["disks"] = [asdict(disk) for disk in sorted(self.disks, key=lambda item: item.device_id)]
        return data


@dataclass(frozen=True)
class Repository:
    """Pinned local mount identity. Marker provisioning is deliberately external.

    Mount roots must be canonical absolute paths without symlink components.
    Destination is a dedicated replica namespace, never the active source share.
    """

    root: Path
    site_id: str
    repository_id: str

    @contextlib.contextmanager
    def opened(self) -> Iterator[int]:
        identifier(self.site_id)
        identifier(self.repository_id)
        require(self.root.is_absolute() and len(self.root.parts) >= 3, "DEDICATED_ABSOLUTE_ROOT_REQUIRED")
        require(".." not in self.root.parts, "UNSAFE_REPOSITORY_ROOT")
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
        try:
            for name in self.root.parts[1:]:
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            info = os.fstat(fd)
            require(info.st_uid in {0, os.geteuid()} and not info.st_mode & 0o022,
                    "REPOSITORY_ROOT_MUST_BE_OPERATOR_OWNED")
            marker = read_json(fd, IDENTITY_NAME)
            require(marker == {"schema": 1, "site_id": self.site_id, "repository_id": self.repository_id},
                    "REPOSITORY_IDENTITY_MISMATCH")
            yield fd
        finally:
            os.close(fd)


@contextlib.contextmanager
def directory(parent: int, parts: list[str], *, create: bool = False, private: bool = False) -> Iterator[int]:
    current = os.dup(parent)
    try:
        for name in parts:
            # Internal names are constants; native path components are validated by BackupIdentity.
            require(name not in {"", ".", ".."} and "/" not in name, "UNSAFE_DIRECTORY")
            if create:
                try:
                    os.mkdir(name, 0o700 if private else 0o750, dir_fd=current)
                    os.fsync(current)
                except FileExistsError:
                    pass
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
            info = os.fstat(current)
            require(info.st_uid in {0, os.geteuid()} and not info.st_mode & 0o022, "UNSAFE_DIRECTORY_OWNER_OR_MODE")
            if private:
                require(info.st_uid == os.geteuid() and not info.st_mode & 0o077, "PRIVATE_STAGING_REQUIRED")
        yield current
    finally:
        os.close(current)


def regular_file(parent: int, name: str, flags: int = os.O_RDONLY) -> int:
    fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=parent)
    info = os.fstat(fd)
    if not (stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            and info.st_uid in {0, os.geteuid()} and not info.st_mode & 0o022):
        os.close(fd)
        raise ReplicationError("UNSAFE_FILE_TYPE_OWNER_OR_LINK")
    return fd


def read_json(parent: int, name: str) -> dict:
    fd = regular_file(parent, name)
    with os.fdopen(fd, "rb") as handle:
        raw = handle.read(JSON_LIMIT + 1)
    require(len(raw) <= JSON_LIMIT, "METADATA_TOO_LARGE")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise ReplicationError("INVALID_METADATA") from None
    require(isinstance(value, dict), "INVALID_METADATA")
    return value


def write_json_once(parent: int, name: str, value: dict) -> None:
    """Atomic publication inside a private, exclusively locked staging directory."""
    data = canonical(value)
    require(len(data) <= JSON_LIMIT, "METADATA_TOO_LARGE")
    if _exists(parent, name):
        require(read_json(parent, name) == value, "IMMUTABLE_METADATA_CONFLICT")
        return
    temporary = "metadata-" + uuid.uuid4().hex
    fd = regular_file(parent, temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    require(not _exists(parent, name), "IMMUTABLE_METADATA_CONFLICT")
    rename_once(parent, temporary, parent, name)
    os.fsync(parent)


@dataclass(frozen=True)
class CopyLimits:
    max_bytes: int = 16 * 1024 ** 4
    timeout_seconds: int = 3600
    reserve_bytes: int = 1024 ** 3

    def validate(self) -> None:
        require(type(self.max_bytes) is int and 0 < self.max_bytes <= 1024 ** 5, "INVALID_COPY_LIMIT")
        require(type(self.timeout_seconds) is int and 0 < self.timeout_seconds <= 86400, "INVALID_TIMEOUT")
        require(type(self.reserve_bytes) is int and self.reserve_bytes >= 0, "INVALID_SPACE_RESERVE")


def deadline_check(deadline: float) -> None:
    require(time.monotonic() < deadline, "COPY_DEADLINE_EXCEEDED")


def file_digest(parent: int, name: str, deadline: float, max_bytes: int) -> tuple[int, str]:
    fd = regular_file(parent, name)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        require(0 < before.st_size <= max_bytes, "DISK_SIZE_OUT_OF_BOUNDS")
        digest = hashlib.sha256()
        count = 0
        while True:
            deadline_check(deadline)
            block = handle.read(CHUNK_BYTES)
            if not block:
                break
            count += len(block)
            require(count <= before.st_size, "SOURCE_DISK_CHANGED")
            digest.update(block)
        after = os.fstat(handle.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
                and count == before.st_size, "SOURCE_DISK_CHANGED")
        return count, digest.hexdigest()


class NasReplicator:
    """One complete native backup per call, serialized by destination repository.

    The caller must hold source retention and authorize tenant/object scope.
    A guard is called before planning, publication and acknowledgement, so fresh
    CloudStack metadata must still match. Local file checks are not a retention
    lease and do not replace provider-side retention coordination.
    """

    def __init__(self, source: Repository, destination: Repository, limits: CopyLimits = CopyLimits()):
        self.source = source
        self.destination = destination
        limits.validate()
        self.limits = limits

    def _validate(self, identity: BackupIdentity) -> None:
        identity.validate()
        require(self.source.site_id == identity.source_site_id
                and self.destination.site_id == identity.recovery_site_id
                and self.source.repository_id == self.destination.repository_id == identity.repository_id,
                "SITE_OR_REPOSITORY_BINDING_MISMATCH")

    def _manifest(self, source_fd: int, identity: BackupIdentity, deadline: float) -> dict:
        files = []
        total = 0
        for disk in sorted(identity.disks, key=lambda item: item.device_id):
            size, digest = file_digest(source_fd, disk.filename, deadline, self.limits.max_bytes - total)
            total += size
            files.append({**asdict(disk), "size": size, "sha256": digest})
        return {"schema": 1, "kind": "CLOUDSTACK_NAS_FULL", "identity": identity.payload(), "files": files}

    def _verify_manifest(self, folder: int, manifest: dict, identity: BackupIdentity, deadline: float) -> None:
        require(set(manifest) == {"schema", "kind", "identity", "files"}
                and manifest["schema"] == 1 and manifest["kind"] == "CLOUDSTACK_NAS_FULL"
                and manifest["identity"] == identity.payload(), "REPLICA_IDENTITY_MISMATCH")
        entries = manifest["files"]
        require(isinstance(entries, list) and len(entries) == len(identity.disks), "REPLICA_DISKS_MISSING")
        total = 0
        for entry, disk in zip(entries, sorted(identity.disks, key=lambda item: item.device_id)):
            require(isinstance(entry, dict) and set(entry) == {"device_id", "volume_id", "filename", "size", "sha256"},
                    "INVALID_REPLICA_MANIFEST")
            require(all(entry[key] == value for key, value in asdict(disk).items()), "REPLICA_DISK_IDENTITY_MISMATCH")
            size, digest = file_digest(folder, disk.filename, deadline, self.limits.max_bytes - total)
            require(type(entry["size"]) is int and size == entry["size"] and digest == entry["sha256"],
                    "REPLICA_INTEGRITY_FAILURE")
            fd = regular_file(folder, disk.filename)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            total += size

    def verify(self, identity: BackupIdentity) -> dict:
        """Verify a selected published point; no implicit latest-point lookup."""
        self._validate(identity)
        deadline = time.monotonic() + self.limits.timeout_seconds
        with self.destination.opened() as root:
            with directory(root, identity.external_id.split("/")) as final:
                manifest = read_json(final, MANIFEST_NAME)
                self._verify_manifest(final, manifest, identity, deadline)
                os.fsync(final)
            with directory(root, identity.external_id.split("/")[:1]) as parent:
                os.fsync(parent)
            os.fsync(root)
        return self._receipt(manifest)

    @staticmethod
    def _receipt(manifest: dict) -> dict:
        return {"backup_id": manifest["identity"]["backup_id"], "manifest_sha256": fingerprint(manifest),
                "identity": manifest["identity"], "bytes": sum(entry["size"] for entry in manifest["files"]),
                "integrity": "SHA256_VERIFIED", "verified_at_epoch": int(time.time()),
                "guest_data": "NOT_TESTED", "recovery": "NOT_TESTED"}

    def replicate(self, identity: BackupIdentity, *, guard: Callable[[BackupIdentity], None]) -> dict:
        self._validate(identity)
        require(callable(guard), "AUTHORIZATION_AND_RETENTION_GUARD_REQUIRED")
        guard(identity)
        deadline = time.monotonic() + self.limits.timeout_seconds
        with self.source.opened() as source_root, self.destination.opened() as destination_root:
            require((os.fstat(source_root).st_dev, os.fstat(source_root).st_ino)
                    != (os.fstat(destination_root).st_dev, os.fstat(destination_root).st_ino), "SOURCE_EQUALS_DESTINATION")
            with directory(destination_root, [".layersentry-staging"], create=True, private=True) as staging_root:
                lock = regular_file(staging_root, "writer.lock", os.O_RDWR | os.O_CREAT)
                try:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        raise ReplicationError("REPOSITORY_WRITER_BUSY") from None
                    return self._copy_locked(source_root, destination_root, staging_root, identity, guard, deadline)
                finally:
                    os.close(lock)

    def _copy_locked(self, source_root: int, destination_root: int, staging_root: int,
                     identity: BackupIdentity, guard: Callable[[BackupIdentity], None], deadline: float) -> dict:
        parts = identity.external_id.split("/")
        with directory(source_root, parts) as source:
            manifest = self._manifest(source, identity, deadline)
            guard(identity)
            with directory(destination_root, parts[:1], create=True) as parent:
                try:
                    existing = os.stat(parts[1], dir_fd=parent, follow_symlinks=False)
                except FileNotFoundError:
                    existing = None
                if existing is not None:
                    with directory(parent, parts[1:]) as final:
                        require(read_json(final, MANIFEST_NAME) == manifest, "PUBLISHED_POINT_CONFLICT")
                        self._verify_manifest(final, manifest, identity, deadline)
                        os.fsync(final)
                    os.fsync(parent)
                    guard(identity)
                    return self._receipt(manifest)

                # A backup UUID selects one immutable staging namespace across retries.
                with directory(staging_root, [identity.backup_id], create=True, private=True) as staging:
                    write_json_once(staging, "intent.json", manifest)
                    for entry in manifest["files"]:
                        deadline_check(deadline)
                        try:
                            actual = file_digest(staging, entry["filename"], deadline, self.limits.max_bytes)
                        except FileNotFoundError:
                            actual = None
                        if actual is not None:
                            require(actual == (entry["size"], entry["sha256"]), "STAGED_DISK_CONFLICT")
                            continue
                        self._copy_file(source, staging, entry, deadline)
                    self._verify_manifest(staging, manifest, identity, deadline)
                    # Source path membership/content is re-read before publication.
                    require(self._manifest(source, identity, deadline) == manifest, "SOURCE_CHANGED_BEFORE_PUBLICATION")
                    guard(identity)
                    deadline_check(deadline)
                    write_json_once(staging, MANIFEST_NAME, manifest)
                    os.fsync(staging)
                # Only this service may write the replica namespace. flock serializes
                # cooperating writers; mount-side writers must be excluded by policy.
                require(not _exists(parent, parts[1]), "PUBLISHED_POINT_CONFLICT")
                rename_once(staging_root, identity.backup_id, parent, parts[1])
                os.fsync(parent)
                os.fsync(staging_root)
                os.fsync(destination_root)
                guard(identity)
                return self._receipt(manifest)

    def _copy_file(self, source: int, staging: int, entry: Mapping, deadline: float) -> None:
        available = os.fstatvfs(staging)
        require(available.f_bavail * available.f_frsize >= entry["size"] + self.limits.reserve_bytes,
                "DESTINATION_CAPACITY_INSUFFICIENT")
        # Reuse one private partial file on retry; no completed disk is overwritten.
        partial = entry["filename"] + ".partial"
        source_fd = regular_file(source, entry["filename"])
        try:
            target_fd = regular_file(staging, partial, os.O_WRONLY | os.O_CREAT)
        except Exception:
            os.close(source_fd)
            raise
        with os.fdopen(source_fd, "rb") as reader, os.fdopen(target_fd, "wb") as writer:
            before = os.fstat(reader.fileno())
            require(before.st_size == entry["size"], "SOURCE_DISK_CHANGED")
            os.ftruncate(writer.fileno(), 0)
            digest = hashlib.sha256()
            count = 0
            while True:
                deadline_check(deadline)
                data = reader.read(CHUNK_BYTES)
                if not data:
                    break
                count += len(data)
                require(count <= entry["size"], "SOURCE_DISK_CHANGED")
                digest.update(data)
                writer.write(data)
            after = os.fstat(reader.fileno())
            require(count == entry["size"] and digest.hexdigest() == entry["sha256"]
                    and (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                    == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "SOURCE_DISK_CHANGED")
            writer.flush()
            os.fchmod(writer.fileno(), 0o640)
            os.fsync(writer.fileno())
        require(not _exists(staging, entry["filename"]), "STAGED_DISK_CONFLICT")
        rename_once(staging, partial, staging, entry["filename"])
        os.fsync(staging)


def _exists(parent: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False
