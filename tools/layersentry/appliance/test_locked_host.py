import json
import pathlib
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).parent
SCRIPT = HERE / "layersentry-locked-host"
POLICY = HERE / "locked-host-policy.json"


class LockedHostSourceTests(unittest.TestCase):
    def test_policy_is_valid_and_scoped(self):
        policy = json.loads(POLICY.read_text())
        self.assertEqual(policy["os"], {"id": "rocky", "major": 9})
        self.assertEqual(policy["root_ssh_login"], "no")
        self.assertEqual(policy["ebpf_mode"], "observe-only")
        self.assertIn("cloudstack-agent", policy["package_allowlist"])
        self.assertIn("device-mapper-multipath", policy["package_allowlist"])
        self.assertIn("iscsi-initiator-utils", policy["package_allowlist"])
        self.assertEqual(len(policy["package_allowlist"]), len(set(policy["package_allowlist"])))

    def test_shell_parses(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_apply_fails_closed_without_execute(self):
        result = subprocess.run([str(SCRIPT), "apply"], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dry by default", result.stderr)

    def test_symlink_policy_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            link = pathlib.Path(directory) / "policy.json"
            link.symlink_to(POLICY)
            result = subprocess.run([str(SCRIPT), "apply", "--policy", str(link)], text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non-symlink", result.stderr)

    def test_package_lock_requires_regular_file(self):
        result = subprocess.run([str(SCRIPT), "verify-package-lock"], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--lock", result.stderr)


if __name__ == "__main__":
    unittest.main()
