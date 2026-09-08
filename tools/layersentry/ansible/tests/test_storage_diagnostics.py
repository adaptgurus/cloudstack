#!/usr/bin/env python3
import base64
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "library" / "layersentry_storage.py"


def load_storage_module():
    ansible = types.ModuleType("ansible")
    module_utils = types.ModuleType("ansible.module_utils")
    basic = types.ModuleType("ansible.module_utils.basic")
    basic.AnsibleModule = object
    old = {name: sys.modules.get(name) for name in ("ansible", "ansible.module_utils", "ansible.module_utils.basic")}
    sys.modules["ansible"] = ansible
    sys.modules["ansible.module_utils"] = module_utils
    sys.modules["ansible.module_utils.basic"] = basic
    try:
        spec = importlib.util.spec_from_file_location("layersentry_storage_test_module", MODULE_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module
    finally:
        for name, value in old.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value


class StorageDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = load_storage_module()

    def test_failed_subprocess_propagates_bounded_sanitized_stderr(self):
        proc = types.SimpleNamespace(
            returncode=5,
            stdout="stdout fallback should not win",
            stderr="  lvcreate failed   token=supersecret   because device activation timed out  ",
        )
        with mock.patch.object(self.storage.subprocess, "run", return_value=proc):
            with self.assertRaises(RuntimeError) as caught:
                self.storage.run(["/usr/sbin/lvcreate", "-L", "8G", "ls_pg"])
        msg = str(caught.exception)
        self.assertIn("command failed rc=5: lvcreate", msg)
        self.assertIn("device activation timed out", msg)
        self.assertIn("token=<redacted>", msg)
        self.assertNotIn("supersecret", msg)
        self.assertNotIn("/usr/sbin/lvcreate", msg)

    def test_diagnostic_is_bounded_before_durable_token_encoding(self):
        raw = "password=topsecret " + ("x" * 2000)
        safe = self.storage.bounded_diagnostic(raw)
        self.assertNotIn("topsecret", safe)
        self.assertIn("password=<redacted>", safe)
        self.assertLessEqual(len(safe), 515)
        token = self.storage.safe_diagnostic_token(safe)
        self.assertTrue(token.startswith(self.storage.SAFE_DIAGNOSTIC_PREFIX))
        encoded = token[len(self.storage.SAFE_DIAGNOSTIC_PREFIX):]
        encoded += "=" * ((4 - len(encoded) % 4) % 4)
        decoded = base64.urlsafe_b64decode(encoded).decode("utf-8")
        self.assertEqual(decoded, safe)


if __name__ == "__main__":
    unittest.main()
