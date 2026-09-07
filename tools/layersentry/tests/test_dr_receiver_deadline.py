"""Real pipe/backpressure regression tests; no network or hypervisor operations."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from dataclasses import asdict, replace

import test_dr_replication_runtime as fixtures
from dr_replication import fingerprint
from dr_replication_transport import read_frame, write_frame


class ReceiverDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReplicationCase(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.plan = replace(self.fixture.plan, transfer_timeout=1)
        config = {
            "schema": 1, "enabled": True, "role": "receiver", "plan": asdict(self.plan),
            "destination_root": str(self.fixture.destination.root),
            "allowed_scope_sha256": fingerprint(self.plan.scope()),
            "qemu_img": "/usr/bin/qemu-img",
        }
        self.config = self.fixture.root / "receiver.json"
        self.config.write_text(json.dumps(config))
        self.command = [sys.executable, str(Path(__file__).resolve().parents[1] / "dr_replication_cli.py"),
                        "receive", "--config", str(self.config), "--execute"]

    def start(self, *, stdout=subprocess.PIPE):
        process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=stdout,
                                   stderr=subprocess.PIPE)

        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        self.addCleanup(cleanup)
        return process

    def test_idle_sender_exits_at_receiver_deadline(self):
        process = self.start()
        self.assertEqual(process.wait(timeout=4), 2)
        output, _ = process.communicate(timeout=1)
        # An expired output deadline may suppress the best-effort error frame.
        self.assertLessEqual(len(output), 1024)

    def test_output_backpressure_cannot_disable_receiver_deadline(self):
        reader, writer = os.pipe()
        self.addCleanup(os.close, reader)
        self.addCleanup(os.close, writer)
        os.set_blocking(writer, False)
        while True:
            try:
                os.write(writer, b"x" * 4096)
            except BlockingIOError:
                break
        os.set_blocking(writer, True)
        process = self.start(stdout=writer)
        manifest, _ = self.fixture.point()
        frame = io.BytesIO()
        write_frame(frame, {"op": "PUSH", "scope_sha256": fingerprint(self.plan.scope()),
                            "manifest": manifest})
        process.stdin.write(frame.getvalue())
        process.stdin.flush()
        try:
            result = process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            self.fail("receiver hung after deadline while writing to an unread full output pipe")
        self.assertEqual(result, 2)
        # Unwind the catalog lock and leave an incomplete epoch unpublished.
        self.assertEqual(self.fixture.catalog.listing()["total"], 0)

    def test_stalled_partial_disk_releases_catalog_for_retry(self):
        process = self.start()
        manifest, folder = self.fixture.point()
        frame = io.BytesIO()
        write_frame(frame, {"op": "PUSH", "scope_sha256": fingerprint(self.plan.scope()),
                            "manifest": manifest})
        entry = manifest["disks"][0]
        write_frame(frame, {"filename": entry["filename"], "size": entry["size"]})
        frame.write(b"partial")
        process.stdin.write(frame.getvalue())
        process.stdin.flush()
        self.assertEqual(process.wait(timeout=4), 2)
        self.assertEqual(self.fixture.catalog.listing()["total"], 0)
        self.assertEqual(self.fixture.send(manifest, folder)["state"], "COMMITTED")

    def test_real_cli_pipe_transfer_returns_exact_commit_receipt(self):
        process = self.start()
        manifest, folder = self.fixture.point()
        frame = io.BytesIO()
        write_frame(frame, {"op": "PUSH", "scope_sha256": fingerprint(self.plan.scope()),
                            "manifest": manifest})
        for entry in manifest["disks"]:
            write_frame(frame, {"filename": entry["filename"], "size": entry["size"]})
            frame.write((folder / entry["filename"]).read_bytes())
        output, errors = process.communicate(frame.getvalue(), timeout=5)
        self.assertEqual(process.returncode, 0, errors.decode())
        frames = io.BytesIO(output)
        self.assertEqual(read_frame(frames), {"state": "NEED", "filenames": ["vda.qcow2", "vdb.qcow2"]})
        for entry in manifest["disks"]:
            self.assertEqual(read_frame(frames), {"received": entry["filename"]})
        receipt = read_frame(frames)
        self.assertEqual(receipt["state"], "COMMITTED")
        self.assertEqual(receipt["manifest_sha256"], fingerprint(manifest))
        self.assertEqual(receipt["epoch_id"], manifest["epoch_id"])
        self.assertEqual(frames.read(), b"")
        self.assertEqual(self.fixture.catalog.verify(manifest["epoch_id"])["manifest_sha256"],
                         fingerprint(manifest))


if __name__ == "__main__":
    unittest.main()
