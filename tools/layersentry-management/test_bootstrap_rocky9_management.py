import os
import pathlib
import subprocess
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).with_name("bootstrap-rocky9-management.sh")


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        self.db = self.root / "input-db.properties"
        self.db.write_text("db.cloud.host=db-vip.example\n", encoding="utf-8")
        self.db.chmod(0o600)

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, action="preflight", **updates):
        env = os.environ.copy()
        env.update({
            "LAYERSENTRY_ROOT": str(self.root / "target"),
            "LAYERSENTRY_PACKAGE_NEVRA": "cloudstack-management-4.22.1.1-1.el9.x86_64",
            "LAYERSENTRY_DB_PROPERTIES_FILE": str(self.db),
            "LAYERSENTRY_FIREWALL_PORTS": "8080/tcp,8250/tcp",
        })
        env.update(updates)
        return subprocess.run([str(SCRIPT), action], env=env, text=True, capture_output=True)

    def test_preflight_accepts_explicit_inputs(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("preflight passed", result.stderr)

    def test_rejects_unpinned_package(self):
        result = self.run_script(LAYERSENTRY_PACKAGE_NEVRA="cloudstack-management")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("exact cloudstack-management NEVRA", result.stderr)

    def test_rejects_overly_permissive_secret(self):
        self.db.chmod(0o644)
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("0600 or stricter", result.stderr)

    def test_rejects_symlinked_secret(self):
        link = self.root / "db-link.properties"
        link.symlink_to(self.db)
        result = self.run_script(LAYERSENTRY_DB_PROPERTIES_FILE=str(link))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("non-symlink", result.stderr)

    def test_rejects_repository_without_signature_check(self):
        repo = self.root / "cloudstack.repo"
        repo.write_text("[cloudstack]\ngpgcheck=0\n", encoding="utf-8")
        repo.chmod(0o600)
        result = self.run_script(LAYERSENTRY_REPO_FILE=str(repo))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gpgcheck=1", result.stderr)

    def test_rooted_apply_is_idempotent(self):
        first = self.run_script("apply")
        second = self.run_script("apply")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        target = self.root / "target/etc/cloudstack/management/db.properties"
        self.assertEqual(target.read_text(encoding="utf-8"), self.db.read_text(encoding="utf-8"))
        self.assertTrue((self.root / "target/var/lib/layersentry/management-bootstrap/applied").is_file())


if __name__ == "__main__":
    unittest.main()
