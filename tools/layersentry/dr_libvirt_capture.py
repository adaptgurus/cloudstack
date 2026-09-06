"""Durable, explicit libvirt capture/replication controller. Status: NOT_TESTED."""

from __future__ import annotations

import contextlib
import fcntl
import multiprocessing
import os
import signal
import stat
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from dr_file_replication import (
    FilePlan, QcowTools, check_qcow2, replace_json, secure_root,
    validate_manifest, verify_disks,
)
from dr_replication import (
    ReplicationError, directory, file_digest, fingerprint, identifier,
    read_json, regular_file, require, write_json_once,
)


def xml_document(value: str) -> ET.Element:
    require(isinstance(value, str) and len(value) <= 2 * 1024 * 1024
            and "<!DOCTYPE" not in value.upper() and "<!ENTITY" not in value.upper(), "UNSAFE_LIBVIRT_XML")
    try:
        return ET.fromstring(value)
    except ET.ParseError:
        raise ReplicationError("INVALID_LIBVIRT_XML") from None


def _checkpoint(domain, name: str, plan: FilePlan) -> ET.Element:
    value = xml_document(domain.checkpointLookupByName(name, 0).getXMLDesc(0))
    require(value.findtext("name") == name and value.findtext("domain/uuid") == plan.domain_uuid
            and value.findtext("description") == "LayerSentry " + fingerprint(plan.scope()), "CHECKPOINT_SCOPE_MISMATCH_RESEED_REQUIRED")
    disks = {disk.get("name"): disk for disk in value.findall("disks/disk") if disk.get("checkpoint") != "no"}
    require(set(disks) == {disk.device for disk in plan.disks}
            and all(item.get("checkpoint") == "bitmap" for item in disks.values()), "CHECKPOINT_DISK_MISMATCH")
    return value


def _capture_worker(plan: FilePlan, intent: dict, capture_root: str, journal_path: str,
                    qemu_uid: int, qemu_gid: int, qemu_img: str, probe: str | None = None) -> None:
    """Runs in a bounded child; terminating it never cancels/replays a QEMU job."""
    connection = None
    try:
        import libvirt  # Installed/pinned by the appliance, never pip-installed here.
        libvirt.registerErrorHandler(lambda _context, _error: None, None)
        connection = libvirt.open("qemu:///system")
        require(connection is not None and connection.getLibVersion() == plan.libvirt_version
                and connection.getVersion() == plan.qemu_version, "LIBVIRT_QEMU_VERSION_PIN_MISMATCH")
        domain = connection.lookupByUUIDString(plan.domain_uuid)
        require(domain.UUIDString() == plan.domain_uuid and domain.name() == plan.domain_name, "DOMAIN_IDENTITY_MISMATCH")
        if probe:
            require(domain.isActive() == 0 or domain.jobStats(0).get("type") == libvirt.VIR_DOMAIN_JOB_NONE,
                    "HYPERVISOR_JOB_STILL_ACTIVE")
            with secure_root(Path(journal_path)) as journal:
                write_json_once(journal, probe, {"idle": True, "domain_uuid": plan.domain_uuid,
                                                "observed_at_epoch": int(time.time())})
            return
        require(domain.isActive() == 1 and domain.snapshotNum(0) == 0, "RUNNING_SNAPSHOT_FREE_DOMAIN_REQUIRED")
        require(domain.jobStats(0).get("type") == libvirt.VIR_DOMAIN_JOB_NONE, "DOMAIN_JOB_ALREADY_ACTIVE")
        document = xml_document(domain.XMLDesc(0))
        actual = {item.find("target").get("dev"): item for item in document.findall("devices/disk")
                  if item.get("device") == "disk" and item.find("readonly") is None and item.find("target") is not None}
        require(set(actual) == {disk.device for disk in plan.disks}, "WRITABLE_DISK_MEMBERSHIP_CHANGED")
        for disk in plan.disks:
            item = actual[disk.device]
            require(item.get("type") == "file" and item.find("driver") is not None
                    and item.find("driver").get("type") == "qcow2" and item.find("source") is not None
                    and item.find("source").get("file") == disk.source_path
                    and item.find("encryption") is None and domain.blockInfo(disk.device, 0)[0] == disk.virtual_bytes,
                    "SOURCE_DISK_BINDING_OR_FORMAT_CHANGED")
        checkpoints = domain.listAllCheckpoints(0)
        require(len(checkpoints) < plan.max_points, "SOURCE_CHECKPOINT_CAPACITY_REACHED")
        name = "lsdr-" + intent["epoch_id"]
        require(all(item.getName() != name for item in checkpoints), "CHECKPOINT_ALREADY_EXISTS_NO_REPLAY")
        if intent["parent"]:
            _checkpoint(domain, "lsdr-" + intent["parent"]["epoch_id"], plan)
        # Consume old completed statistics before beginning this new, exclusive job.
        domain.jobStats(libvirt.VIR_DOMAIN_JOB_STATS_COMPLETED)
        backup = ET.Element("domainbackup", {"mode": "push"})
        if intent["parent"]:
            ET.SubElement(backup, "incremental").text = "lsdr-" + intent["parent"]["epoch_id"]
        backup_disks = ET.SubElement(backup, "disks")
        checkpoint = ET.Element("domaincheckpoint")
        ET.SubElement(checkpoint, "name").text = name
        ET.SubElement(checkpoint, "description").text = "LayerSentry " + fingerprint(plan.scope())
        checkpoint_disks = ET.SubElement(checkpoint, "disks")
        output = Path(capture_root) / intent["epoch_id"]
        with secure_root(Path(capture_root), private=False) as root:
            root_info = os.fstat(root)
            require(root_info.st_gid == qemu_gid and root_info.st_mode & 0o010, "QEMU_CAPTURE_ROOT_TRAVERSAL_REQUIRED")
            available = os.fstatvfs(root)
            needed = sum(disk.virtual_bytes for disk in plan.disks)
            require(available.f_bavail * available.f_frsize >= needed + needed // 10 + plan.reserve_bytes,
                    "CAPTURE_CAPACITY_INSUFFICIENT")
            os.mkdir(intent["epoch_id"], 0o700, dir_fd=root)
            output_fd = os.open(intent["epoch_id"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
            try:
                os.fchown(output_fd, qemu_uid, qemu_gid)
                os.fsync(output_fd)
            finally:
                os.close(output_fd)
            os.fsync(root)
        for disk in plan.disks:
            item = ET.SubElement(backup_disks, "disk", {"name": disk.device, "type": "file", "backup": "yes"})
            ET.SubElement(item, "driver", {"type": "qcow2"})
            ET.SubElement(item, "target", {"file": str(output / (disk.device + ".qcow2"))})
            ET.SubElement(checkpoint_disks, "disk", {"name": disk.device, "checkpoint": "bitmap"})
        started = int(time.time())
        require(domain.backupBegin(ET.tostring(backup, encoding="unicode"),
                                   ET.tostring(checkpoint, encoding="unicode"), 0) == 0, "BACKUP_BEGIN_UNCERTAIN")
        deadline = time.monotonic() + plan.capture_timeout
        while True:
            require(time.monotonic() < deadline, "CAPTURE_TIMEOUT_RECONCILE_REQUIRED")
            completed = domain.jobStats(libvirt.VIR_DOMAIN_JOB_STATS_COMPLETED | libvirt.VIR_DOMAIN_JOB_STATS_KEEP_COMPLETED)
            if completed.get("type") == libvirt.VIR_DOMAIN_JOB_COMPLETED:
                require(completed.get("operation") == libvirt.VIR_DOMAIN_JOB_OPERATION_BACKUP, "COMPLETED_JOB_IDENTITY_UNKNOWN")
                break
            require(completed.get("type") not in {libvirt.VIR_DOMAIN_JOB_FAILED, libvirt.VIR_DOMAIN_JOB_CANCELLED},
                    "CAPTURE_JOB_FAILED_RECONCILE_REQUIRED")
            # A different active target can never supply completion evidence for us.
            try:
                active = xml_document(domain.backupGetXMLDesc(0))
            except libvirt.libvirtError:
                # Completion can race the preceding statistics query. Re-read
                # terminal evidence; disappearance alone is never success.
                final = domain.jobStats(libvirt.VIR_DOMAIN_JOB_STATS_COMPLETED | libvirt.VIR_DOMAIN_JOB_STATS_KEEP_COMPLETED)
                require(final.get("type") == libvirt.VIR_DOMAIN_JOB_COMPLETED
                        and final.get("operation") == libvirt.VIR_DOMAIN_JOB_OPERATION_BACKUP,
                        "BACKUP_DISAPPEARED_WITHOUT_COMPLETION")
                break
            targets = {item.get("name"): item.find("target").get("file") for item in active.findall("disks/disk")
                       if item.get("backup") != "no" and item.find("target") is not None}
            require(active.get("mode", "push") == "push" and targets == {
                disk.device: str(output / (disk.device + ".qcow2")) for disk in plan.disks
            }, "ACTIVE_BACKUP_IDENTITY_MISMATCH")
            time.sleep(0.5)
        captured = _checkpoint(domain, name, plan)
        captured_at = int(captured.findtext("creationTime"))
        require(started - 1 <= captured_at <= int(time.time()) + 1, "CHECKPOINT_TIME_MISMATCH")
        # The provider job has completed. Remove QEMU write access before sealing.
        raw = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            require(os.fstat(raw).st_uid == qemu_uid, "CAPTURE_DIRECTORY_OWNER_CHANGED")
            for disk in plan.disks:
                fd = os.open(disk.device + ".qcow2", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=raw)
                try:
                    info = os.fstat(fd)
                    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid in {qemu_uid, os.geteuid()},
                            "UNSAFE_CAPTURE_FILE")
                    os.fchown(fd, os.geteuid(), os.getegid())
                    os.fchmod(fd, 0o400)
                    os.fsync(fd)
                finally:
                    os.close(fd)
            os.fchown(raw, os.geteuid(), os.getegid())
            os.fchmod(raw, 0o700)
            os.fsync(raw)
        finally:
            os.close(raw)
        tools = QcowTools(Path(qemu_img), plan.qemu_version)
        tools.check_version(deadline)
        entries = []
        with secure_root(output) as folder:
            for disk in plan.disks:
                filename = disk.device + ".qcow2"
                size, digest = file_digest(folder, filename, deadline, plan.max_bytes)
                entry = {"device": disk.device, "volume_id": disk.volume_id, "virtual_bytes": disk.virtual_bytes,
                         "filename": filename, "size": size, "sha256": digest}
                check_qcow2(folder, entry)
                tools.check(output / filename, deadline)
                entries.append(entry)
        manifest = {"schema": 1, "provider": "LIBVIRT_QCOW2", "scope": plan.scope(),
                    "epoch_id": intent["epoch_id"], "mode": intent["mode"], "parent": intent["parent"],
                    "captured_at_epoch": captured_at, "checkpoint": name, "consistency": "CRASH", "disks": entries}
        validate_manifest(manifest, plan)
        with secure_root(Path(journal_path)) as journal:
            write_json_once(journal, "manifest.json", manifest)
            write_json_once(journal, "capture-complete.json", {"intent_sha256": fingerprint(intent),
                                                               "manifest_sha256": fingerprint(manifest)})
    except BaseException as error:
        code = str(error) if isinstance(error, ReplicationError) else "LIBVIRT_CAPTURE_UNCERTAIN"
        try:
            with secure_root(Path(journal_path)) as journal:
                replace_json(journal, "capture-error.json", {"reason": code, "replay": "PROHIBITED"})
        except Exception:
            pass  # Missing durable success is still ambiguous; never publish a point.
    finally:
        if connection is not None:
            connection.close()


def _gated_worker(gate, arguments: tuple) -> None:
    # The parent first fsyncs this child's identity. An orphan waiting before that
    # durable handoff exits without ever connecting to libvirt.
    if gate.wait(timeout=30):
        _capture_worker(*arguments)


def process_identity(pid: int) -> dict | None:
    require(type(pid) is int and pid > 1, "INVALID_WORKER_PID")
    try:
        value = Path("/proc") / str(pid) / "stat"
        fields = value.read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return {"pid": pid, "start_ticks": int(fields[19]),
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
    except FileNotFoundError:
        return None


class FileReplicationEngine:
    """One source-owned workload writer; destination ACK commits its lineage."""
    def __init__(self, plan: FilePlan, state_root: Path, capture_root: Path, transport,
                 *, qemu_uid: int, qemu_gid: int, qemu_img: Path):
        plan.validate()
        require(type(qemu_uid) is int and qemu_uid > 0 and type(qemu_gid) is int and qemu_gid > 0,
                "DEDICATED_QEMU_IDENTITY_REQUIRED")
        require(state_root != capture_root and state_root not in capture_root.parents
                and capture_root not in state_root.parents, "SEPARATE_CAPTURE_AND_PRIVATE_STATE_ROOTS_REQUIRED")
        self.plan, self.state_root, self.capture_root, self.transport = plan, state_root, capture_root, transport
        self.qemu_uid, self.qemu_gid, self.qemu_img = qemu_uid, qemu_gid, qemu_img

    @contextlib.contextmanager
    def _locked(self, *, create: bool = True):
        with secure_root(self.state_root) as root:
            lock = regular_file(root, "workload-" + self.plan.domain_uuid + ".lock", os.O_RDWR | os.O_CREAT)
            try:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ReplicationError("WORKLOAD_WRITER_BUSY") from None
                with directory(root, [self.plan.plan_id], create=create, private=True) as plan:
                    if create:
                        write_json_once(plan, "scope.json", self.plan.scope())
                    else:
                        require(read_json(plan, "scope.json") == self.plan.scope(), "SOURCE_SCOPE_CHANGED")
                    with directory(plan, ["epochs"], create=create, private=True) as epochs:
                        yield plan, epochs
            finally:
                os.close(lock)

    @staticmethod
    def _optional(folder: int, name: str, default: dict) -> dict:
        try:
            return read_json(folder, name)
        except FileNotFoundError:
            return default

    def _worker(self, intent: dict, journal: Path, *, probe: str | None = None) -> None:
        require(os.geteuid() == 0, "ROOT_OPERATOR_REQUIRED_FOR_LIBVIRT_CAPTURE")
        context = multiprocessing.get_context("spawn")
        gate = context.Event()
        arguments = (self.plan, intent, str(self.capture_root), str(journal), self.qemu_uid, self.qemu_gid,
                     str(self.qemu_img), probe)
        worker = context.Process(target=_gated_worker, args=(gate, arguments))
        worker.start()
        try:
            identity = process_identity(worker.pid)
            require(identity is not None, "CAPTURE_WORKER_START_FAILED")
            with secure_root(journal) as folder:
                replace_json(folder, "probe-worker.json" if probe else "worker.json", identity)
            gate.set()
            worker.join(60 if probe else self.plan.capture_timeout)
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
                if worker.is_alive():
                    worker.kill()
                    worker.join(5)
                # Hypervisor backup state is deliberately untouched.
        finally:
            if worker.is_alive():
                worker.kill()
                worker.join(5)
            worker.close()

    def _captured(self, epoch: int, intent: dict) -> dict:
        proof = read_json(epoch, "capture-complete.json")
        manifest = read_json(epoch, "manifest.json")
        validate_manifest(manifest, self.plan)
        require(proof == {"intent_sha256": fingerprint(intent), "manifest_sha256": fingerprint(manifest)}
                and manifest["epoch_id"] == intent["epoch_id"] and manifest["mode"] == intent["mode"]
                and manifest["parent"] == intent["parent"]
                and manifest["captured_at_epoch"] >= intent.get("previous_captured_at_epoch", 0), "CAPTURE_PROOF_OR_CLOCK_MISMATCH")
        with secure_root(self.capture_root / intent["epoch_id"]) as folder:
            verify_disks(folder, manifest, self.plan, time.monotonic() + self.plan.transfer_timeout)
        return manifest

    def _finish_ack(self, plan: int, epoch: int, intent: dict, manifest: dict, receipt: dict) -> dict:
        require(receipt.get("state") == "COMMITTED" and receipt.get("epoch_id") == intent["epoch_id"]
                and receipt.get("manifest_sha256") == fingerprint(manifest)
                and receipt.get("captured_at_epoch") == manifest["captured_at_epoch"]
                and type(receipt.get("chain_length")) is int and 1 <= receipt["chain_length"] <= self.plan.max_chain,
                "DESTINATION_ACK_MISMATCH")
        head = self._optional(plan, "head.json", {})
        if head.get("epoch_id") != intent["epoch_id"]:
            require(head.get("epoch_id") == intent["previous_head"], "SOURCE_CURSOR_CHANGED")
        replace_json(epoch, "state.json", {"state": "COMMITTED", "receipt": receipt})
        replace_json(plan, "head.json", {"epoch_id": intent["epoch_id"], "receipt": receipt,
                                          "manifest_sha256": fingerprint(manifest), "reseed_required": False})
        replace_json(plan, "active.json", {"epoch_id": None})
        return receipt

    def replicate(self, epoch_id: str, *, mode: str = "AUTO", allow_capture: bool = True) -> dict:
        identifier(epoch_id)
        require(mode in {"AUTO", "FULL", "INCREMENTAL"}, "INVALID_CAPTURE_MODE")
        with self._locked() as (plan, epochs):
            active = self._optional(plan, "active.json", {"epoch_id": None})["epoch_id"]
            if active and active != epoch_id:
                with directory(epochs, [identifier(active)], private=True) as old:
                    old_state = read_json(old, "state.json")
                    require(old_state.get("state") == "COMMITTED", "PRIOR_EPOCH_REQUIRES_RESUME_OR_RECONCILIATION")
                    self._finish_ack(plan, old, read_json(old, "intent.json"), read_json(old, "manifest.json"), old_state["receipt"])
            with directory(epochs, [epoch_id], create=True, private=True) as epoch:
                intent = self._optional(epoch, "intent.json", {})
                if not intent:
                    require(allow_capture, "CAPTURE_NOT_SUBMITTED")
                    head = self._optional(plan, "head.json", {})
                    require(not (mode == "INCREMENTAL" and (not head or head.get("reseed_required"))), "NEW_BASELINE_REQUIRED")
                    use_parent = bool(head) and mode != "FULL" and not head.get("reseed_required")
                    if use_parent:
                        receipt = self.transport.verify(head["epoch_id"])
                        require(receipt.get("manifest_sha256") == head["manifest_sha256"], "ACKNOWLEDGED_PARENT_CHANGED")
                        if receipt["chain_length"] >= self.plan.max_chain:
                            require(mode == "AUTO", "NEW_BASELINE_REQUIRED")
                            use_parent = False
                    parent = {"epoch_id": head["epoch_id"], "manifest_sha256": head["manifest_sha256"]} if use_parent else None
                    intent = {"epoch_id": epoch_id, "scope_sha256": fingerprint(self.plan.scope()),
                              "mode": "INCREMENTAL" if parent else "FULL", "parent": parent,
                              "previous_head": head.get("epoch_id"),
                              "previous_captured_at_epoch": head.get("receipt", {}).get("captured_at_epoch", 0),
                              "requested_at_epoch": int(time.time())}
                    write_json_once(epoch, "intent.json", intent)
                    replace_json(epoch, "state.json", {"state": "PREPARED"})
                require(intent["scope_sha256"] == fingerprint(self.plan.scope()) and intent["epoch_id"] == epoch_id,
                        "EPOCH_REQUEST_CONFLICT")
                require(mode == "AUTO" or mode == intent["mode"], "EPOCH_MODE_CONFLICT")
                try:
                    state = read_json(epoch, "state.json")
                except FileNotFoundError:
                    state = None
                if state is None:
                    # Intent is durable before the first PREPARED checkpoint.
                    # No child can run until CAPTURING and its worker identity
                    # have been saved. Recover only that pre-submission window;
                    # any provider evidence without state remains ambiguous.
                    require(not ({"worker.json", "manifest.json", "capture-complete.json",
                                  "capture-error.json"} & set(os.listdir(epoch))),
                            "CAPTURE_STATE_MISSING_RECONCILE_REQUIRED")
                    require(not os.path.lexists(self.capture_root / epoch_id),
                            "CAPTURE_STATE_MISSING_RECONCILE_REQUIRED")
                    state = {"state": "PREPARED"}
                    replace_json(epoch, "state.json", state)
                if state["state"] == "COMMITTED":
                    head = self._optional(plan, "head.json", {})
                    if active == epoch_id or head.get("epoch_id") == intent["previous_head"]:
                        return self._finish_ack(plan, epoch, intent, read_json(epoch, "manifest.json"), state["receipt"])
                    return state["receipt"]
                require(state["state"] != "ABANDONED", "ABANDONED_EPOCH_CANNOT_BE_REPLAYED")
                require(self._optional(plan, "head.json", {}).get("epoch_id") == intent["previous_head"],
                        "SOURCE_CURSOR_CHANGED")
                replace_json(plan, "active.json", {"epoch_id": epoch_id})
                if state["state"] == "PREPARED":
                    require(allow_capture, "CAPTURE_NOT_SUBMITTED")
                    replace_json(epoch, "state.json", {"state": "CAPTURING"})
                    journal = self.state_root / self.plan.plan_id / "epochs" / epoch_id
                    self._worker(intent, journal)
                try:
                    manifest = self._captured(epoch, intent)
                except Exception:
                    replace_json(epoch, "state.json", {"state": "RECONCILIATION_REQUIRED", "capture_replay": "PROHIBITED"})
                    raise ReplicationError("CAPTURE_PROOF_UNAVAILABLE_RECONCILE_REQUIRED") from None
                replace_json(epoch, "state.json", {"state": "TRANSFERRING", "manifest_sha256": fingerprint(manifest)})
                # Retrying transfer is safe: immutable bytes plus an exact epoch ID;
                # this never calls backupBegin again for an uncertain operation.
                with secure_root(self.capture_root / epoch_id) as source:
                    receipt = self.transport.send(manifest, source)
                return self._finish_ack(plan, epoch, intent, manifest, receipt)

    def status(self) -> dict:
        with secure_root(self.state_root) as root:
            try:
                os.stat(self.plan.plan_id, dir_fd=root, follow_symlinks=False)
            except FileNotFoundError:
                return {"plan_id": self.plan.plan_id, "head": None, "active_epoch": None, "active_state": None,
                        "age_of_last_acknowledged_point_seconds": None, "destination_current_health": "UNKNOWN"}
        with self._locked(create=False) as (plan, epochs):
            head = self._optional(plan, "head.json", {})
            active = self._optional(plan, "active.json", {"epoch_id": None})["epoch_id"]
            state = None
            if active:
                with directory(epochs, [identifier(active)], private=True) as epoch:
                    state = read_json(epoch, "state.json")["state"]
            captured = head.get("receipt", {}).get("captured_at_epoch")
            age = int(time.time()) - captured if captured else None
            return {"plan_id": self.plan.plan_id, "head": head or None, "active_epoch": active, "active_state": state,
                    "age_of_last_acknowledged_point_seconds": age if age is not None and age >= 0 else None,
                    "target_rpo_seconds": self.plan.rpo_seconds, "destination_current_health": "UNKNOWN"}

    def tick(self) -> dict:
        status = self.status()
        active = status["active_epoch"]
        if active:
            return self.replicate(active, allow_capture=status["active_state"] == "PREPARED")
        age = status["age_of_last_acknowledged_point_seconds"]
        if age is not None and age < self.plan.rpo_seconds and not status["head"].get("reseed_required"):
            return {"state": "NOT_DUE", "next_in_seconds": self.plan.rpo_seconds - age}
        return self.replicate(str(uuid.uuid4()))

    def abandon(self, epoch_id: str) -> dict:
        """Explicit operator reconciliation: require a fresh idle-domain observation.

        Preserve files/checkpoints and force a full baseline on the next capture.
        This is not a hypervisor abort or a destructive source cleanup.
        """
        identifier(epoch_id)
        with self._locked() as (plan, epochs):
            require(self._optional(plan, "active.json", {}).get("epoch_id") == epoch_id, "ACTIVE_EPOCH_MISMATCH")
            with directory(epochs, [epoch_id], private=True) as epoch:
                require(read_json(epoch, "state.json")["state"] in {"CAPTURING", "RECONCILIATION_REQUIRED", "TRANSFERRING"},
                        "EPOCH_CANNOT_BE_ABANDONED")
                intent = read_json(epoch, "intent.json")
                recorded = self._optional(epoch, "worker.json", {})
                if recorded and process_identity(recorded["pid"]) == recorded:
                    # Stop only our exact capture child (boot ID + PID start time),
                    # never a QEMU/libvirt process or a recycled PID.
                    require(hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"), "PIDFD_RECONCILIATION_REQUIRED")
                    try:
                        process_fd = os.pidfd_open(recorded["pid"])
                    except ProcessLookupError:
                        process_fd = None
                    if process_fd is not None:
                        try:
                            if process_identity(recorded["pid"]) == recorded:
                                try:
                                    signal.pidfd_send_signal(process_fd, signal.SIGKILL)
                                except ProcessLookupError:
                                    pass
                        finally:
                            os.close(process_fd)
                    stop_deadline = time.monotonic() + 5
                    while process_identity(recorded["pid"]) == recorded and time.monotonic() < stop_deadline:
                        time.sleep(0.1)
                    require(process_identity(recorded["pid"]) != recorded, "CAPTURE_WORKER_STILL_RUNNING")
                probe = "idle-" + uuid.uuid4().hex + ".json"
                self._worker(intent, self.state_root / self.plan.plan_id / "epochs" / epoch_id, probe=probe)
                observation = read_json(epoch, probe)
                require(observation.get("idle") is True and observation.get("domain_uuid") == self.plan.domain_uuid
                        and 0 <= int(time.time()) - observation.get("observed_at_epoch", 0) <= 60, "FRESH_IDLE_PROOF_REQUIRED")
                replace_json(epoch, "state.json", {"state": "ABANDONED", "provider_objects_deleted": False})
                head = self._optional(plan, "head.json", {})
                replace_json(plan, "head.json", {**head, "reseed_required": True})
                replace_json(plan, "active.json", {"epoch_id": None})
                return {"state": "ABANDONED", "epoch_id": epoch_id, "next_capture": "FULL", "provider_objects_deleted": False}
