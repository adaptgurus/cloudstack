"""Filesystem/protocol/journal tests; no CloudStack or libvirt mutation."""

import copy
import hashlib
import io
import json
import os
import subprocess
from pathlib import Path
import struct
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid
from dataclasses import replace
from dataclasses import asdict
from contextlib import redirect_stdout

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dr_file_replication import FileCatalog, FileDisk, FilePlan, QcowTools, secure_root
from dr_libvirt_capture import FileReplicationEngine
from dr_replication import (
    BackupDisk, BackupIdentity, CopyLimits, NasReplicator, Repository,
    ReplicationError, fingerprint, write_json_once,
)
from dr_replication_transport import MountedTransport, read_frame, receive_one, write_frame


def uid():
    return str(uuid.uuid4())


class ReplicationCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="layersentry-dr-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.plan = FilePlan(
            plan_id=uid(), tenant_id=uid(), workload_id=uid(),
            source_site_id=uid(), recovery_site_id=uid(), repository_id=uid(),
            domain_uuid=uid(), domain_name="i-test-VM", disks=(
                FileDisk("vda", uid(), "/var/lib/libvirt/images/root.qcow2", 4096),
                FileDisk("vdb", uid(), "/var/lib/libvirt/images/data.qcow2", 4096),
            ), libvirt_version=10000000, qemu_version=6002000,
            max_bytes=8 * 1024 * 1024, reserve_bytes=0,
            retention_count=2, minimum_retention_seconds=0,
        )
        self.destination = self.repository("destination", self.plan.recovery_site_id)
        self.catalog = FileCatalog(self.destination, self.plan)

    def folder(self, name):
        path = self.root / name
        path.mkdir(mode=0o700)
        return path

    def repository(self, name, site):
        path = self.folder(name)
        (path / ".layersentry-repository.json").write_text(json.dumps({
            "schema": 1, "site_id": site, "repository_id": self.plan.repository_id,
        }))
        return Repository(path, site, self.plan.repository_id)

    def point(self, parent=None, epoch=None, captured=None):
        epoch = epoch or uid()
        folder = self.folder(epoch)
        entries = []
        for disk in self.plan.disks:
            # Minimal QCOW2 header fixture exercises the defensive parser only.
            # It is not advertised as a usable QEMU image or guest recovery.
            data = bytearray(104)
            data[:4] = b"QFI\xfb"
            struct.pack_into(">I", data, 4, 3)
            struct.pack_into(">Q", data, 24, disk.virtual_bytes)
            data.extend(epoch.encode() + disk.device.encode())
            filename = disk.device + ".qcow2"
            (folder / filename).write_bytes(data)
            entries.append({"device": disk.device, "volume_id": disk.volume_id,
                            "virtual_bytes": disk.virtual_bytes, "filename": filename,
                            "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        manifest = {"schema": 1, "provider": "LIBVIRT_QCOW2", "scope": self.plan.scope(),
                    "epoch_id": epoch, "mode": "INCREMENTAL" if parent else "FULL",
                    "parent": {"epoch_id": parent["epoch_id"], "manifest_sha256": fingerprint(parent)} if parent else None,
                    "captured_at_epoch": captured or int(time.time()) - 100,
                    "checkpoint": "lsdr-" + epoch, "consistency": "CRASH", "disks": entries}
        return manifest, folder

    def send(self, manifest, folder):
        with secure_root(folder) as source:
            return self.catalog.receive_local(manifest, source)

    def test_full_and_two_incrementals_remain_individually_verifiable(self):
        parent = None
        for index in range(3):
            manifest, folder = self.point(parent, captured=int(time.time()) - 30 + index)
            receipt = self.send(manifest, folder)
            self.assertEqual(receipt["chain_length"], index + 1)
            self.assertEqual(self.catalog.verify(manifest["epoch_id"])["manifest_sha256"], fingerprint(manifest))
            parent = manifest
        self.assertEqual(self.catalog.listing()["total"], 3)

    def test_lost_ack_reuses_published_bytes_without_overwriting(self):
        manifest, folder = self.point()
        self.send(manifest, folder)
        target = self.destination.root / ".layersentry-file" / self.plan.plan_id / "points" / manifest["epoch_id"] / "vda.qcow2"
        before = target.stat()
        self.send(manifest, folder)
        self.assertEqual((target.stat().st_ino, target.stat().st_mtime_ns), (before.st_ino, before.st_mtime_ns))

    def test_interruption_between_disk_seal_and_rename_can_resume(self):
        manifest, folder = self.point()
        import dr_file_replication
        real_rename = dr_file_replication.rename_once

        def interrupt(source, name, target, final):
            if name == "vda.qcow2.partial":
                raise ReplicationError("SIMULATED_POWER_LOSS")
            return real_rename(source, name, target, final)

        with patch.object(dr_file_replication, "rename_once", side_effect=interrupt):
            with self.assertRaisesRegex(ReplicationError, "SIMULATED_POWER_LOSS"):
                self.send(manifest, folder)
        self.assertEqual(self.send(manifest, folder)["state"], "COMMITTED")

    def test_incomplete_multidisk_transfer_never_publishes(self):
        manifest, folder = self.point()
        with self.catalog.incoming(manifest) as incoming:
            first = manifest["disks"][0]
            incoming.write(first, [(folder / first["filename"]).read_bytes()])
            with self.assertRaises(FileNotFoundError):
                incoming.commit()
        self.assertEqual(self.catalog.listing()["total"], 0)
        self.assertEqual(self.send(manifest, folder)["state"], "COMMITTED")

    def test_corrupted_parent_blocks_incremental_and_does_not_publish(self):
        parent, folder = self.point()
        self.send(parent, folder)
        target = self.destination.root / ".layersentry-file" / self.plan.plan_id / "points" / parent["epoch_id"] / "vda.qcow2"
        target.chmod(0o600)
        target.write_bytes(b"corrupted")
        child, child_folder = self.point(parent)
        with self.assertRaisesRegex(ReplicationError, "INTEGRITY"):
            self.send(child, child_folder)
        self.assertEqual(self.catalog.listing()["total"], 1)

    def test_scope_substitution_and_epoch_reuse_are_denied(self):
        manifest, folder = self.point()
        self.send(manifest, folder)
        wrong = copy.deepcopy(manifest)
        wrong["scope"]["tenant_id"] = uid()
        with self.assertRaisesRegex(ReplicationError, "SCOPE"):
            self.send(wrong, folder)
        changed = copy.deepcopy(manifest)
        changed["captured_at_epoch"] -= 1
        with self.assertRaisesRegex(ReplicationError, "IDEMPOTENCY"):
            self.send(changed, folder)

    def test_symlink_and_hardlinked_disks_are_denied(self):
        for kind in ("symlink", "hardlink"):
            manifest, folder = self.point()
            path = folder / "vda.qcow2"
            other = folder / "other"
            path.rename(other)
            if kind == "symlink":
                path.symlink_to(other)
            else:
                os.link(other, path)
            with self.assertRaises((OSError, ReplicationError)):
                self.send(manifest, folder)

    def test_external_qcow_backing_reference_is_denied_before_publication(self):
        manifest, folder = self.point()
        path = folder / "vda.qcow2"
        data = bytearray(path.read_bytes())
        struct.pack_into(">Q", data, 8, 104)
        path.write_bytes(data)
        manifest["disks"][0]["sha256"] = hashlib.sha256(data).hexdigest()
        with self.assertRaisesRegex(ReplicationError, "UNSAFE_OR_UNSEALED"):
            self.send(manifest, folder)
        self.assertEqual(self.catalog.listing()["total"], 0)

    def test_retention_keeps_ancestors_and_pending_incremental_parent(self):
        old, old_folder = self.point(captured=int(time.time()) - 400)
        self.send(old, old_folder)
        child, child_folder = self.point(old, captured=int(time.time()) - 300)
        self.send(child, child_folder)
        pending, _ = self.point(child, captured=int(time.time()) - 200)
        with self.catalog.incoming(pending):
            pass
        for age in (100, 50):
            manifest, folder = self.point(captured=int(time.time()) - age)
            self.send(manifest, folder)
        decision = self.catalog.retention()
        self.assertIn(old["epoch_id"], decision["protected"])
        self.assertIn(child["epoch_id"], decision["protected"])
        self.assertEqual(decision["retire"], [])

    def test_retention_rechecks_catalog_and_preserves_data_in_trash(self):
        oldest = None
        for age in (400, 300, 200):
            manifest, folder = self.point(captured=int(time.time()) - age)
            self.send(manifest, folder)
            oldest = oldest or manifest
        previous = self.catalog.retention()
        manifest, folder = self.point(captured=int(time.time()) - 100)
        self.send(manifest, folder)
        with self.assertRaisesRegex(ReplicationError, "VIEW_CHANGED"):
            self.catalog.retire(previous["catalog_sha256"])
        current = self.catalog.retention()
        result = self.catalog.retire(current["catalog_sha256"])
        self.assertEqual(result["bytes_reclaimed"], 0)
        self.assertTrue((self.destination.root / ".layersentry-file" / self.plan.plan_id / "trash" / oldest["epoch_id"] / "vda.qcow2").is_file())

    def test_receiver_protocol_transfers_only_bound_files(self):
        manifest, folder = self.point()
        incoming, outgoing = io.BytesIO(), io.BytesIO()
        write_frame(incoming, {"op": "PUSH", "scope_sha256": fingerprint(self.plan.scope()), "manifest": manifest})
        for entry in manifest["disks"]:
            write_frame(incoming, {"filename": entry["filename"], "size": entry["size"]})
            incoming.write((folder / entry["filename"]).read_bytes())
        incoming.seek(0)
        receive_one(self.catalog, incoming, outgoing)
        outgoing.seek(0)
        self.assertEqual(read_frame(outgoing)["state"], "NEED")
        self.assertEqual(read_frame(outgoing), {"received": "vda.qcow2"})
        self.assertEqual(read_frame(outgoing), {"received": "vdb.qcow2"})
        self.assertEqual(read_frame(outgoing)["state"], "COMMITTED")

    def test_receiver_rejects_foreign_scope_before_repository_creation(self):
        incoming = io.BytesIO()
        write_frame(incoming, {"op": "VERIFY", "scope_sha256": "0" * 64, "epoch_id": uid()})
        incoming.seek(0)
        with self.assertRaisesRegex(ReplicationError, "NOT_AUTHORIZED"):
            receive_one(self.catalog, incoming, io.BytesIO())
        self.assertFalse((self.destination.root / ".layersentry-file").exists())

    def engine(self):
        state, capture = self.folder("state"), self.folder("capture")
        return FileReplicationEngine(self.plan, state, capture, MountedTransport(self.catalog),
                                     qemu_uid=107, qemu_gid=107, qemu_img=Path("/usr/bin/qemu-img"))

    def capture_worker(self, engine):
        def capture(intent, journal):
            manifest, folder = self.point(epoch=intent["epoch_id"], captured=int(time.time()))
            manifest.update(mode=intent["mode"], parent=intent["parent"])
            folder.rename(engine.capture_root / intent["epoch_id"])
            with secure_root(journal) as handle:
                write_json_once(handle, "manifest.json", manifest)
                write_json_once(handle, "capture-complete.json", {
                    "intent_sha256": fingerprint(intent), "manifest_sha256": fingerprint(manifest),
                })
        return capture

    def test_missing_capture_proof_never_replays_hypervisor_submission(self):
        engine, epoch = self.engine(), uid()
        with patch.object(engine, "_worker") as worker:
            for allow_capture in (True, True, False):
                with self.assertRaisesRegex(ReplicationError, "RECONCILE_REQUIRED"):
                    engine.replicate(epoch, allow_capture=allow_capture)
            self.assertEqual(worker.call_count, 1)
        self.assertIsNone(engine.status()["head"])

    def test_lost_destination_ack_resumes_transfer_without_new_capture(self):
        engine, epoch = self.engine(), uid()
        real_send = engine.transport.send

        def lose_ack(manifest, source):
            real_send(manifest, source)
            raise OSError("simulated acknowledgement loss")

        with patch.object(engine, "_worker", side_effect=self.capture_worker(engine)) as worker:
            with patch.object(engine.transport, "send", side_effect=lose_ack):
                with self.assertRaises(OSError):
                    engine.replicate(epoch)
            self.assertIsNone(engine.status()["head"])
            self.assertEqual(engine.replicate(epoch, allow_capture=False)["state"], "COMMITTED")
            self.assertEqual(worker.call_count, 1)
        self.assertEqual(engine.status()["head"]["epoch_id"], epoch)

    def test_intent_without_initial_state_recovers_before_any_capture(self):
        engine, epoch = self.engine(), uid()
        import dr_libvirt_capture
        real_replace = dr_libvirt_capture.replace_json

        def interrupt(folder, name, value):
            if value == {"state": "PREPARED"}:
                raise OSError("simulated power loss after intent")
            return real_replace(folder, name, value)

        with patch.object(dr_libvirt_capture, "replace_json", side_effect=interrupt):
            with self.assertRaises(OSError):
                engine.replicate(epoch)
        with patch.object(engine, "_worker", side_effect=self.capture_worker(engine)) as worker:
            self.assertEqual(engine.replicate(epoch)["state"], "COMMITTED")
            self.assertEqual(worker.call_count, 1)

    def test_missing_state_with_worker_identity_never_replays(self):
        engine, epoch = self.engine(), uid()
        with patch.object(engine, "_worker"):
            with self.assertRaises(ReplicationError):
                engine.replicate(epoch)
        journal = engine.state_root / self.plan.plan_id / "epochs" / epoch
        (journal / "state.json").unlink()
        (journal / "worker.json").write_text(json.dumps({"pid": 123, "start_ticks": 1, "boot_id": uid()}))
        with patch.object(engine, "_worker") as worker:
            with self.assertRaisesRegex(ReplicationError, "STATE_MISSING_RECONCILE_REQUIRED"):
                engine.replicate(epoch)
            worker.assert_not_called()

    def test_concurrent_destination_writer_fails_without_waiting(self):
        first, _ = self.point()
        second, folder = self.point()
        with self.catalog.incoming(first):
            with self.assertRaisesRegex(ReplicationError, "CATALOG_BUSY"):
                self.send(second, folder)

    def test_truncated_wire_disk_does_not_publish(self):
        manifest, _ = self.point()
        incoming = io.BytesIO()
        write_frame(incoming, {"op": "PUSH", "scope_sha256": fingerprint(self.plan.scope()), "manifest": manifest})
        entry = manifest["disks"][0]
        write_frame(incoming, {"filename": entry["filename"], "size": entry["size"]})
        incoming.write(b"truncated")
        incoming.seek(0)
        with self.assertRaisesRegex(ReplicationError, "DISCONNECTED"):
            receive_one(self.catalog, incoming, io.BytesIO())
        self.assertEqual(self.catalog.listing()["total"], 0)

    @unittest.skipUnless(os.environ.get("LAYERSENTRY_TEST_QEMU_IMG") and os.environ.get("LAYERSENTRY_TEST_QEMU_IO"),
                         "real QEMU binaries not provided; synthetic headers do not prove reconstruction")
    def test_real_qcow_latest_and_older_reconstruction_including_zero_blocks(self):
        qemu_img = os.environ["LAYERSENTRY_TEST_QEMU_IMG"]
        qemu_io = os.environ["LAYERSENTRY_TEST_QEMU_IO"]

        def run(*args):
            return subprocess.run(args, check=True, capture_output=True, timeout=30).stdout

        version_text = run(qemu_img, "--version").decode()
        import re
        match = re.search(r"version (\d+)\.(\d+)\.(\d+)", version_text)
        version = int(match[1]) * 1000000 + int(match[2]) * 1000 + int(match[3])
        self.plan = replace(self.plan, qemu_version=version,
                            disks=tuple(replace(disk, virtual_bytes=1024 * 1024) for disk in self.plan.disks))
        self.catalog = FileCatalog(self.destination, self.plan)
        expected = {disk.device: bytearray([0x11] * disk.virtual_bytes) for disk in self.plan.disks}
        saved, parent = [], None
        for index in range(3):
            epoch = uid()
            folder = self.folder(epoch)
            entries = []
            for disk in self.plan.disks:
                path = folder / (disk.device + ".qcow2")
                run(qemu_img, "create", "-f", "qcow2", str(path), str(disk.virtual_bytes))
                if index == 0:
                    command = "write -P 0x11 0 1048576"
                elif index == 1:
                    command = "write -P 0x22 0 65536"
                    expected[disk.device][:65536] = bytes([0x22]) * 65536
                else:
                    command = "write -z 0 65536"
                    expected[disk.device][:65536] = bytes(65536)
                run(qemu_io, "-f", "qcow2", "-c", command, str(path))
                data = path.read_bytes()
                entries.append({"device": disk.device, "volume_id": disk.volume_id, "virtual_bytes": disk.virtual_bytes,
                                "filename": path.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()})
            manifest = {"schema": 1, "provider": "LIBVIRT_QCOW2", "scope": self.plan.scope(), "epoch_id": epoch,
                        "mode": "INCREMENTAL" if parent else "FULL", "parent": parent,
                        "captured_at_epoch": int(time.time()) - 10 + index,
                        "checkpoint": "lsdr-" + epoch, "consistency": "CRASH", "disks": entries}
            self.send(manifest, folder)
            saved.append((manifest, {key: bytes(value) for key, value in expected.items()}))
            parent = {"epoch_id": epoch, "manifest_sha256": fingerprint(manifest)}
        outputs = self.folder("restore-outputs")
        tools = QcowTools(Path(qemu_img), version)
        for manifest, expected_disks in reversed(saved):
            receipt = self.catalog.materialize(manifest["epoch_id"], outputs, tools)
            self.assertEqual(receipt["state"], "MATERIALIZED")
            for disk in self.plan.disks:
                recovered = Path(receipt["output_directory"]) / "disks" / (disk.device + ".qcow2")
                raw = Path(receipt["output_directory"]) / (disk.device + ".raw")
                run(qemu_img, "convert", "-f", "qcow2", "-O", "raw", str(recovered), str(raw))
                self.assertEqual(raw.read_bytes(), expected_disks[disk.device])
            # Retained replicas must remain backing-free and byte-identical.
            self.catalog.verify(manifest["epoch_id"])

    def test_native_nas_copy_and_replay_preserve_selected_backup_identity(self):
        source = self.repository("nas-source", self.plan.source_site_id)
        identity = BackupIdentity(self.plan.plan_id, self.plan.tenant_id, uid(), self.plan.workload_id,
                                  self.plan.source_site_id, self.plan.recovery_site_id, self.plan.repository_id,
                                  uid(), uid(), "i-test-VM/20260906090000", int(time.time()) - 100,
                                  (BackupDisk(0, self.plan.disks[0].volume_id, "root.disk.qcow2"),))
        folder = source.root / identity.external_id
        folder.mkdir(parents=True, mode=0o700)
        (folder / "root.disk.qcow2").write_bytes(b"immutable backup bytes")
        copier = NasReplicator(source, self.destination, CopyLimits(reserve_bytes=0))
        guarded = []
        first = copier.replicate(identity, guard=guarded.append)
        replay = copier.replicate(identity, guard=guarded.append)
        self.assertEqual(first["manifest_sha256"], replay["manifest_sha256"])
        self.assertEqual(copier.verify(identity)["backup_id"], identity.backup_id)
        self.assertGreaterEqual(len(guarded), 6)

    def test_cli_checks_full_disabled_configuration_without_creating_runtime_paths(self):
        from dr_replication_cli import main
        config = {"schema": 1, "enabled": False, "role": "receiver", "plan": asdict(self.plan),
                  "destination_root": str(self.root / "uncreated-repository"),
                  "allowed_scope_sha256": fingerprint(self.plan.scope()), "qemu_img": "/usr/bin/qemu-img"}
        path = self.root / "config.json"
        path.write_text(json.dumps(config))
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["check-config", "--config", str(path)]), 0)
        self.assertEqual(json.loads(output.getvalue())["runtime_verification"], "NOT_TESTED")
        self.assertFalse((self.root / "uncreated-repository").exists())
        config["unrecognized"] = True
        path.write_text(json.dumps(config))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["check-config", "--config", str(path)]), 2)

    def test_cli_mutation_requires_both_enabled_configuration_and_execute(self):
        from dr_replication_cli import main
        config = {"schema": 1, "enabled": False, "role": "receiver", "plan": asdict(self.plan),
                  "destination_root": str(self.root / "uncreated-repository"),
                  "allowed_scope_sha256": fingerprint(self.plan.scope()), "qemu_img": "/usr/bin/qemu-img"}
        path = self.root / "config.json"
        for enabled, execute in ((False, False), (False, True), (True, False)):
            config["enabled"] = enabled
            path.write_text(json.dumps(config))
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["retire", "--config", str(path), *( ["--execute"] if execute else [])]), 2)
            self.assertIn("EXPLICIT_EXECUTION_AND_ENABLED_CONFIG_REQUIRED", output.getvalue())
            self.assertFalse((self.root / "uncreated-repository").exists())


if __name__ == "__main__":
    unittest.main()
