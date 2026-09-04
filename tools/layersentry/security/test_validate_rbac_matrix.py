import copy
import importlib.util
import json
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("validate_rbac_matrix", HERE / "validate_rbac_matrix.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class MatrixTests(unittest.TestCase):
    def setUp(self):
        self.matrix = json.loads((HERE / "rbac_matrix.json").read_text(encoding="utf-8"))

    def test_shipped_matrix_is_valid(self):
        MODULE.validate_matrix(self.matrix)

    def test_duplicate_ids_fail_closed(self):
        changed = copy.deepcopy(self.matrix)
        changed["tests"][1]["id"] = changed["tests"][0]["id"]
        with self.assertRaises(MODULE.MatrixError):
            MODULE.validate_matrix(changed)

    def test_mutating_command_is_rejected(self):
        changed = copy.deepcopy(self.matrix)
        api_test = next(test for test in changed["tests"] if test["kind"] == "api" and test["role"] != "platform_admin")
        api_test["command"] = "deleteHost"
        with self.assertRaises(MODULE.MatrixError):
            MODULE.validate_matrix(changed)

    def test_missing_object_tamper_coverage_is_rejected(self):
        changed = copy.deepcopy(self.matrix)
        changed["tests"] = [test for test in changed["tests"] if test["id"] != "read-only-foreign-network"]
        with self.assertRaises(MODULE.MatrixError):
            MODULE.validate_matrix(changed)

    def test_redaction_covers_nested_keys_and_query_values(self):
        value = {"Authorization": "Bearer x", "nested": ["?apikey=a&signature=b", {"password": "p"}]}
        redacted = MODULE.redact(value)
        self.assertEqual(redacted["Authorization"], "[REDACTED]")
        self.assertNotIn("=a", redacted["nested"][0])
        self.assertNotIn("=b", redacted["nested"][0])
        self.assertEqual(redacted["nested"][1]["password"], "[REDACTED]")

    def test_not_tested_evidence_does_not_promote_status(self):
        evidence = MODULE.not_tested_evidence(self.matrix, "a" * 40)
        self.assertEqual(evidence["status"], "NOT_TESTED")
        self.assertTrue(all(not result["passed"] for result in evidence["results"]))
        self.assertEqual(evidence["cleanup"], "not_required_read_only")


if __name__ == "__main__":
    unittest.main()
