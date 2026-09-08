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

MODULE_PATH = Path(__file__).with_name("expensive_retry_guard.py")
SPEC = importlib.util.spec_from_file_location("expensive_retry_guard", MODULE_PATH)
assert SPEC and SPEC.loader
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class ExpensiveRetryGuardTests(unittest.TestCase):
    def setUp(self):
        self.fields = {
            "module": "k8s",
            "gate": "E1-9345",
            "sourceSha": "a" * 40,
            "artifactDigest": "sha256:artifact-a",
            "environmentFingerprint": "env-a",
            "failureSignature": "9345-timeout",
            "hypothesis": "lb-healthcheck",
        }
        self.fp = GUARD.fingerprint(self.fields)

    def test_first_expensive_attempt_is_allowed(self):
        allowed, reason = GUARD.evaluate_retry(None, self.fp)
        self.assertTrue(allowed)
        self.assertEqual(reason, "no_prior_failure")

    def test_one_unchanged_confirmatory_retry_is_allowed(self):
        prior = {"fingerprint": self.fp, "attempts": 1}
        allowed, reason = GUARD.evaluate_retry(prior, self.fp)
        self.assertTrue(allowed)
        self.assertEqual(reason, "single_confirmatory_retry_available")

    def test_third_unchanged_attempt_is_blocked(self):
        prior = {"fingerprint": self.fp, "attempts": 2}
        allowed, reason = GUARD.evaluate_retry(prior, self.fp)
        self.assertFalse(allowed)
        self.assertEqual(reason, "unchanged_expensive_retry_limit_reached")

    def test_material_change_reopens_gate(self):
        prior = {"fingerprint": self.fp, "attempts": 2}
        changed = dict(self.fields)
        changed["sourceSha"] = "b" * 40
        allowed, reason = GUARD.evaluate_retry(prior, GUARD.fingerprint(changed))
        self.assertTrue(allowed)
        self.assertEqual(reason, "material_fingerprint_changed")

    def test_repeated_failure_increments_attempts(self):
        prior = GUARD.next_failure_state(None, self.fields, self.fp, "run-1")
        self.assertEqual(prior["attempts"], 1)
        current = GUARD.next_failure_state(prior, self.fields, self.fp, "run-2")
        self.assertEqual(current["attempts"], 2)

    def test_changed_failure_fingerprint_resets_attempt_count(self):
        prior = GUARD.next_failure_state(None, self.fields, self.fp, "run-1")
        changed = dict(self.fields)
        changed["failureSignature"] = "certificate-error"
        changed_fp = GUARD.fingerprint(changed)
        current = GUARD.next_failure_state(prior, changed, changed_fp, "run-2")
        self.assertEqual(current["attempts"], 1)

    def test_gate_and_source_validation_fail_closed(self):
        with self.assertRaises(ValueError):
            GUARD.validate_gate("../unsafe")
        with self.assertRaises(ValueError):
            GUARD.validate_source_sha("not-a-sha")

    def test_multiline_or_oversized_values_are_rejected(self):
        with self.assertRaises(ValueError):
            GUARD.validate_value("failure signature", "one\ntwo")
        with self.assertRaises(ValueError):
            GUARD.validate_value("hypothesis", "x" * (GUARD.MAX_VALUE + 1))


if __name__ == "__main__":
    unittest.main()
