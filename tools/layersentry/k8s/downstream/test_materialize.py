#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

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

    def test_loads_pinned_cloudstack_csi_manifest(self):
        path = Path(__file__).parent / "cloudstack-csi" / "manifest.json"
        manifest = load_manifest(path)
        self.assertEqual(manifest["upstreamCommit"], "a84477e922d62b82387ab55134fafc9c0b5aaf64")
        self.assertEqual(manifest["activation"]["projectPVCGrow"], "disabled-until-live-qualified")

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
