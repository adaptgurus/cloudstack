import copy
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
SPEC = importlib.util.spec_from_file_location("evaluate_rbac_observations", HERE / "evaluate_rbac_observations.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.matrix = json.loads((HERE / "rbac_matrix.json").read_text(encoding="utf-8"))
        self.observations = {
            "schema_version": 1,
            "suite_id": self.matrix["suite_id"],
            "source_commit": "a" * 40,
            "target": {"environment": "rocky9-test", "base_url": "https://example.invalid/client"},
            "started_at": "2026-09-05T10:00:00Z",
            "finished_at": "2026-09-05T10:01:00Z",
            "results": [],
        }
        for test in self.matrix["tests"]:
            item = {"id": test["id"], "http_status": 200, "response_body": "sensitive payload"}
            if test["kind"] == "direct_url":
                item["route_accessible"] = test["expect"] == "allowed"
            elif test["expect"] == "api_allowed":
                item["result_count"] = 1
            elif test["expect"] == "api_denied_or_empty":
                item["result_count"] = 0
            else:
                item["cloudstack_error_code"] = 531
            self.observations["results"].append(item)

    def test_passed_evidence_contains_no_url_or_body(self):
        evidence = MODULE.build_evidence(self.matrix, self.observations, "LIVE_VERIFIED")
        serialized = json.dumps(evidence)
        self.assertEqual(evidence["status"], "LIVE_VERIFIED")
        self.assertNotIn("example.invalid", serialized)
        self.assertNotIn("sensitive payload", serialized)
        self.assertTrue(all(result["passed"] for result in evidence["results"]))

    def test_failed_case_downgrades_to_partial(self):
        changed = copy.deepcopy(self.observations)
        changed["results"][0]["route_accessible"] = False
        evidence = MODULE.build_evidence(self.matrix, changed, "LIVE_VERIFIED")
        self.assertEqual(evidence["status"], "PARTIAL")

    def test_missing_or_extra_case_fails_closed(self):
        changed = copy.deepcopy(self.observations)
        changed["results"].pop()
        with self.assertRaises(MODULE.ObservationError):
            MODULE.build_evidence(self.matrix, changed, "CI_VERIFIED")
        extra = copy.deepcopy(self.observations)
        extra["results"].append({"id": "unexpected", "http_status": 200})
        with self.assertRaises(MODULE.ObservationError):
            MODULE.build_evidence(self.matrix, extra, "CI_VERIFIED")

    def test_duplicate_case_fails_closed(self):
        changed = copy.deepcopy(self.observations)
        changed["results"].append(copy.deepcopy(changed["results"][0]))
        with self.assertRaises(MODULE.ObservationError):
            MODULE.build_evidence(self.matrix, changed, "CI_VERIFIED")

    def test_secret_named_field_is_rejected_anywhere(self):
        changed = copy.deepcopy(self.observations)
        changed["results"][0]["sessionCookie"] = "do-not-store"
        with self.assertRaises(MODULE.ObservationError):
            MODULE.build_evidence(self.matrix, changed, "CI_VERIFIED")

    def test_invalid_status_and_oversized_body_fail_closed(self):
        changed = copy.deepcopy(self.observations)
        changed["results"][0]["http_status"] = True
        with self.assertRaises(MODULE.ObservationError):
            MODULE.build_evidence(self.matrix, changed, "CI_VERIFIED")
        changed = copy.deepcopy(self.observations)
        changed["results"][0]["response_body"] = "x" * (MODULE.MAX_BODY_CHARS + 1)
        with self.assertRaises(MODULE.ObservationError):
            MODULE.build_evidence(self.matrix, changed, "CI_VERIFIED")

    def test_error_code_cannot_carry_arbitrary_text(self):
        changed = copy.deepcopy(self.observations)
        api_result = next(result for result in changed["results"] if "cloudstack_error_code" in result)
        api_result["cloudstack_error_code"] = "secret-looking free text"
        with self.assertRaises(MODULE.ObservationError):
            MODULE.build_evidence(self.matrix, changed, "CI_VERIFIED")

    def test_timestamps_require_timezone_and_forward_order(self):
        changed = copy.deepcopy(self.observations)
        changed["started_at"] = "2026-09-05T10:00:00"
        with self.assertRaises(MODULE.ObservationError):
            MODULE.build_evidence(self.matrix, changed, "CI_VERIFIED")
        changed = copy.deepcopy(self.observations)
        changed["finished_at"] = "2026-09-05T09:59:00Z"
        with self.assertRaises(MODULE.ObservationError):
            MODULE.build_evidence(self.matrix, changed, "CI_VERIFIED")

    def test_output_is_private_and_never_overwritten(self):
        evidence = MODULE.build_evidence(self.matrix, self.observations, "CI_VERIFIED")
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / "evidence.json"
            MODULE.write_exclusive(output, evidence)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                MODULE.write_exclusive(output, evidence)


if __name__ == "__main__":
    unittest.main()
