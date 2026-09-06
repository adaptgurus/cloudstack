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
from copy import deepcopy
from pathlib import Path

from controller.components import evaluate_component_readiness, load_component_readiness
from controller.model import InvalidRequestError


ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / "release-candidate-lane-b.json").read_text())


class ComponentReadinessTest(unittest.TestCase):
    def test_repository_candidate_is_truthfully_blocked(self):
        result = evaluate_component_readiness(MANIFEST)
        self.assertFalse(result.deployable)
        self.assertIsNone(result.ccm_image)
        self.assertIsNone(result.csi_image)
        self.assertTrue(any("Kubernetes 1.36" in item for item in result.blockers))
        self.assertTrue(any("Flux catalog commit" in item for item in result.blockers))
        with self.assertRaises(InvalidRequestError):
            result.require_deployable()

    def test_exact_qualified_tuple_is_deployable(self):
        candidate = deepcopy(MANIFEST)
        candidate["cloudstackCcm"].update({
            "image": "registry.example.test/layersentry/cloudstack-ccm@sha256:" + "a" * 64,
            "kubernetes136Qualified": True,
        })
        candidate["cloudstackCsiDownstream"].update({
            "image": "registry.example.test/layersentry/cloudstack-csi@sha256:" + "b" * 64,
            "projectLifecycleQualified": True,
            "resizeIdempotencyQualified": True,
        })
        candidate["fluxCatalog"] = {
            "repository": "https://git.example.test/layersentry/catalog.git",
            "commit": "c" * 40,
            "contentDigestVerified": True,
        }
        for gate in ("tupleReconciliation", "endpoint6443", "endpoint9345", "fluxRemoteReconcile"):
            candidate["hardGates"][gate] = True
        result = evaluate_component_readiness(candidate)
        self.assertTrue(result.deployable, result.blockers)
        result.require_deployable()

    def test_mutable_tag_and_tuple_drift_fail_closed(self):
        candidate = deepcopy(MANIFEST)
        candidate["cloudstack"] = "latest"
        candidate["cloudstackCcm"]["image"] = "apache/cloudstack-kubernetes-provider:v1.2.0"
        result = evaluate_component_readiness(candidate)
        self.assertTrue(any("cloudstack must equal" in item for item in result.blockers))
        self.assertTrue(any("immutable image digest" in item for item in result.blockers))

    def test_duplicate_json_key_and_writable_manifest_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "release.json"
            path.write_text('{"cloudstack":"4.22.1.1","cloudstack":"other"}')
            with self.assertRaisesRegex(InvalidRequestError, "duplicate"):
                load_component_readiness(path)
            path.write_text(json.dumps(MANIFEST))
            path.chmod(0o666)
            with self.assertRaisesRegex(InvalidRequestError, "writable"):
                load_component_readiness(path)


if __name__ == "__main__":
    unittest.main()
