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

import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).with_name("module_path_fence.py")
SPEC = importlib.util.spec_from_file_location("module_path_fence", MODULE_PATH)
assert SPEC and SPEC.loader
FENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FENCE)


class ModulePathFenceTests(unittest.TestCase):
    def test_k8s_owned_paths_pass(self):
        paths = [
            "tools/layersentry/k8s/controller/service.py",
            "tools/layersentry/k8s/test_controller.py",
            "docs/layersentry/evidence/k8s/result.md",
            ".github/workflows/layersentry-k8s-source-validation.yml",
        ]
        self.assertEqual(FENCE.foreign_paths("k8s", paths), [])

    def test_k8s_commit_touching_single_os_fails(self):
        paths = [
            "tools/layersentry/k8s/controller/service.py",
            "tools/layersentry/single-os/agent/main.go",
        ]
        self.assertEqual(
            FENCE.foreign_paths("k8s", paths),
            ["tools/layersentry/single-os/agent/main.go"],
        )

    def test_k8s_commit_touching_global_governance_fails(self):
        paths = ["tools/layersentry/k8s/node_disk_set.py", "AGENTS.md"]
        self.assertEqual(FENCE.foreign_paths("k8s", paths), ["AGENTS.md"])

    def test_unrelated_commit_is_ignored(self):
        paths = ["ui/src/views/dashboard/Index.vue"]
        self.assertEqual(FENCE.foreign_paths("k8s", paths), [])

    def test_unsafe_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "unsafe changed path"):
            FENCE.foreign_paths("k8s", ["tools/layersentry/k8s/a.py", "../AGENTS.md"])


if __name__ == "__main__":
    unittest.main()
