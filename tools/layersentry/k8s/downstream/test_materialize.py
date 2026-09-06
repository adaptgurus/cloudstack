#!/usr/bin/env python3

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from materialize import OverlayError, load_manifest, materialize


class MaterializeTest(unittest.TestCase):
    def test_loads_pinned_capc_manifest(self):
        path = Path(__file__).parent / "capc" / "manifest.json"
        manifest = load_manifest(path)
        self.assertEqual(manifest["upstreamCommit"], "7521b14a31e6c46f81f16aae3738a27c08ad063f")
        self.assertEqual(manifest["status"], "NOT_TESTED")

    def test_rejects_manifest_without_patches(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            path.write_text(json.dumps({
                "schemaVersion": "1.0",
                "component": "capc",
                "upstreamCommit": "a" * 40,
                "patches": [],
            }), encoding="utf-8")
            with self.assertRaisesRegex(OverlayError, "no patches"):
                load_manifest(path)

    def test_rejects_wrong_source_head_before_patch(self):
        manifest = Path(__file__).parent / "capc" / "manifest.json"
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            (source / ".git").mkdir()
            completed = mock.Mock(returncode=0, stdout="0" * 40 + "\n", stderr="")
            with mock.patch("materialize.subprocess.run", return_value=completed):
                with self.assertRaisesRegex(OverlayError, "does not match"):
                    materialize(source, manifest, apply=False)


if __name__ == "__main__":
    unittest.main()
