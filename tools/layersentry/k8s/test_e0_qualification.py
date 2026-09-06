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

import copy
import unittest

from e0_qualification import EXPECTED_SOURCE, REQUIRED_CASES, evaluate


def passing_report():
    cases = []
    for case_id in REQUIRED_CASES:
        case = {"id": case_id, "status": "PASS", "evidence": [f"artifact/cases/{case_id}.json"]}
        if case_id.startswith("pvc-survives-") or case_id == "csi-snapshot-restore":
            case.update(data_sha256_before="a" * 64, data_sha256_after="a" * 64)
        if case_id in {
            "endpoint-6443-reconcile", "endpoint-9345-reconcile",
            "csi-attach-detach-idempotent", "csi-expand-idempotent", "csi-delete-idempotent",
        }:
            case.update(attempts=2, mutations=1)
        if case_id == "csi-cross-project-denied":
            case["actual"] = "DENIED"
        if case_id == "nodedisk-retain-replacement":
            case["same_volume_id"] = True
        if case_id == "nodedisk-delete-replacement":
            case["old_volume_absent"] = True
        cases.append(case)
    return {
        "source": dict(EXPECTED_SOURCE),
        "environment": {
            "os_family": "Rocky Linux", "os_major": 9, "run_id": "1",
            "artifact_id": "2", "project_id": "project-a", "zone_id": "zone-a",
        },
        "cases": cases,
    }


class E0QualificationTest(unittest.TestCase):
    def test_complete_evidence_is_live_verified(self):
        result = evaluate(passing_report())
        self.assertTrue(result["qualified"])
        self.assertEqual(result["status"], "LIVE_VERIFIED")

    def test_missing_case_fails_closed(self):
        report = passing_report()
        report["cases"].pop()
        result = evaluate(report)
        self.assertFalse(result["qualified"])
        self.assertIn("missing case", " ".join(result["blockers"]))

    def test_data_mismatch_and_mutation_replay_fail(self):
        report = passing_report()
        report["cases"][2]["data_sha256_after"] = "b" * 64
        expand = next(case for case in report["cases"] if case["id"] == "csi-expand-idempotent")
        expand["mutations"] = 2
        result = evaluate(report)
        self.assertFalse(result["qualified"])
        self.assertIn("identical data", " ".join(result["blockers"]))
        self.assertIn("more than one mutation", " ".join(result["blockers"]))

    def test_source_drift_and_secret_fields_fail(self):
        report = copy.deepcopy(passing_report())
        report["source"]["cloudstack_csi_commit"] = "0" * 40
        report["environment"]["apiSecret"] = "must-not-be-recorded"
        result = evaluate(report)
        self.assertFalse(result["qualified"])
        self.assertIn("secret-bearing", " ".join(result["blockers"]))
        self.assertIn("source.cloudstack_csi_commit", " ".join(result["blockers"]))


if __name__ == "__main__":
    unittest.main()
