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
import os
import tempfile
import unittest
from pathlib import Path

from controller.model import InvalidRequestError
from controller.runtime import build_runtime, load_runtime_config


ROOT = Path(__file__).resolve().parent


class RuntimeConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        self.release = self.root / "release.json"
        self.release.write_text((ROOT / "release-candidate-lane-b.json").read_text())
        for name in ("api", "secret", "token"):
            path = self.root / name
            path.write_text(name)
            path.chmod(0o600)
        for name in ("cloud-ca", "kube-ca"):
            (self.root / name).write_text("test-ca")
        self.config = self.root / "runtime.json"
        self.values = {
            "schemaVersion": "1.0",
            "releaseManifest": str(self.release),
            "stateDatabase": str(self.state / "controller.sqlite"),
            "cloudstack": {
                "endpoint": "https://cloud.example.test/client/api",
                "apiKeyFile": str(self.root / "api"),
                "secretKeyFile": str(self.root / "secret"),
                "caFile": str(self.root / "cloud-ca"),
                "allowInsecureHttp": False,
                "trustedBrowserOrigins": ["https://cloud.example.test"],
            },
            "kubernetes": {
                "server": "https://kube.example.test:6443",
                "caFile": str(self.root / "kube-ca"),
                "tokenFile": str(self.root / "token"),
            },
            "clusterProfile": {
                "namespacePrefix": "lsk8s", "credentialSecretName": "capc-credentials",
                "credentialSecretNamespace": "capc-system",
            },
            "flux": {"path": "./clusters/e1", "sourceNamespace": "flux-system"},
        }

    def write(self):
        self.config.write_text(json.dumps(self.values))
        self.config.chmod(0o640)

    def test_loads_only_secret_file_references_and_blocked_release_will_not_build(self):
        self.write()
        config = load_runtime_config(self.config)
        self.assertEqual(config.cloudstack.api_key_file, self.root / "api")
        serialized = self.config.read_text()
        self.assertNotIn("secret-key-value", serialized)
        with self.assertRaisesRegex(InvalidRequestError, "component tuple is blocked"):
            build_runtime(self.config)

    def test_unknown_fields_duplicate_keys_and_weak_secret_mode_fail(self):
        self.values["unexpected"] = True
        self.write()
        with self.assertRaisesRegex(InvalidRequestError, "unknown=unexpected"):
            load_runtime_config(self.config)
        self.values.pop("unexpected")
        (self.root / "token").chmod(0o644)
        self.write()
        with self.assertRaisesRegex(InvalidRequestError, "0600"):
            load_runtime_config(self.config)
        self.config.write_text('{"schemaVersion":"1.0","schemaVersion":"2.0"}')
        with self.assertRaisesRegex(InvalidRequestError, "duplicate"):
            load_runtime_config(self.config)

    def test_state_parent_must_not_be_writable_by_other_principals(self):
        os.chmod(self.state, 0o777)
        self.write()
        with self.assertRaisesRegex(InvalidRequestError, "parent"):
            load_runtime_config(self.config)


if __name__ == "__main__":
    unittest.main()
