import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


installer = module('installer', 'install-rocky9.py')


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / 'repo'
        self.repo.write_text('[cloudstack]\nbaseurl=https://example.invalid/rpm/\ngpgcheck=1\ngpgkey=file:///etc/pki/rpm-gpg/key\n')
        self.repo.chmod(0o600)
        self.cert = self.root / 'cert.pem'
        self.cert.write_text('certificate fixture; openssl validation is a runtime gate')
        self.cert.chmod(0o600)
        self.config = {'schema_version': 1, 'mode': 'combined', 'initialize_database': True,
                       'management_package': 'cloudstack-management-4.22.1.1-1.el9.x86_64',
                       'java_package': 'java-17-openjdk-headless-17.0.16.0.8-2.el9.x86_64',
                       'mysql_client_package': 'mysql-8.0.46-1.el9.x86_64',
                       'mysql_server_package': 'mysql-server-8.0.46-1.el9.x86_64',
                       'mysql_series': '8.0', 'db_host': 'localhost', 'hostname': 'mgmt1',
                       'management_ip': '192.0.2.10', 'ui_cidr': '192.0.2.0/24',
                       'agent_cidr': '192.0.2.0/24', 'firewall_zone': 'public',
                       'repo_files': [str(self.repo)], 'backup_recipient_certificate': str(self.cert)}
        self.secrets = {name: 'UnitTestOnly_42' for name in ('db_password', 'db_admin_password', 'management_key', 'database_key', 'backup_db_password')}

    def tearDown(self):
        self.temporary.cleanup()

    def test_combined_configuration(self):
        installer.validate(self.config, self.secrets)

    def test_exact_version_and_series_rejection(self):
        for key, value in [('management_package', 'cloudstack-management'), ('mysql_series', '8.4'), ('mysql_client_package', 'mysql-8.0.46.x86_64')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                installer.validate(dict(self.config, **{key: value}), self.secrets)

    def test_password_shell_sql_injection_rejected_without_value(self):
        for value in ('12345678;id', "foo'bar123", '$(id)abcde', 'ab`id`xyz', 'one\ntwo345'):
            with self.subTest(value=value), self.assertRaises(ValueError) as error:
                installer.validate(self.config, dict(self.secrets, db_password=value))
            self.assertNotIn(value, str(error.exception))

    def test_public_all_and_invalid_cidr_rejected(self):
        for value in ('0.0.0.0/0', '192.0.2.10/24', '192.0.2.0/24\naccept'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                installer.validate(dict(self.config, ui_cidr=value), self.secrets)

    def test_every_repository_section_must_check_signatures(self):
        with self.repo.open('a') as stream:
            stream.write('[second]\nbaseurl=https://example.invalid/rpm/\ngpgcheck=0\ngpgkey=file:///key\n')
        with self.assertRaisesRegex(ValueError, 'every repository'):
            installer.validate(self.config, self.secrets)

    def test_rejects_secret_symlink_and_permissions(self):
        link = self.root / 'link'
        link.symlink_to(self.cert)
        with self.assertRaises(ValueError):
            installer.private_file(link)
        self.cert.chmod(0o644)
        with self.assertRaises(ValueError):
            installer.private_file(self.cert)

    def test_external_join_requires_matching_encrypted_tls_config(self):
        db = self.root / 'db.properties'
        db.write_text('db.cloud.host=db.example\ndb.usage.host=db.example\ndb.cloud.password=ENC(ciphertext)\ndb.cloud.url.params=useSSL=true&verifyServerCertificate=true\n')
        db.chmod(0o600)
        config = dict(self.config, mode='external', initialize_database=False, db_host='db.example',
                      db_properties_file=str(db), encryption_key_file=str(self.cert), db_tls_ca=str(self.cert))
        installer.validate(config, self.secrets)
        db.write_text(db.read_text().replace('db.example', 'other.example'))
        with self.assertRaisesRegex(ValueError, 'host mismatch'):
            installer.validate(config, self.secrets)

    def test_journal_skips_successful_mutation(self):
        with patch.object(installer, 'STATE', self.root):
            instance = installer.Installer(self.config, self.secrets)
            calls = []
            instance.stage('database', lambda: calls.append(1))
            instance.stage('database', lambda: calls.append(2))
            self.assertEqual(calls, [1])

    def test_interrupted_schema_is_not_blindly_retried(self):
        with patch.object(installer, 'STATE', self.root):
            instance = installer.Installer(self.config, self.secrets)
            def crash():
                raise RuntimeError('injected failure')
            with self.assertRaises(RuntimeError):
                instance.stage('database', crash)
            reloaded = installer.Installer(self.config, self.secrets)
            with self.assertRaisesRegex(ValueError, 'initialization interrupted'):
                reloaded.stage('database', lambda: self.fail('must not execute'))

    def test_changed_configuration_rejects_resume(self):
        with patch.object(installer, 'STATE', self.root):
            instance = installer.Installer(self.config, self.secrets)
            instance.save()
            with self.assertRaisesRegex(ValueError, 'configuration changed'):
                installer.Installer(dict(self.config, hostname='mgmt2'), self.secrets)

    def test_command_failure_never_prints_sensitive_stderr(self):
        with self.assertRaises(RuntimeError) as error:
            installer.run(['/bin/sh', '-c', 'echo secret-test-value >&2; exit 1'])
        self.assertNotIn('secret-test-value', str(error.exception))

    def test_atomic_private_writer(self):
        target = self.root / 'config'
        installer.write_private(target, 'first')
        installer.write_private(target, 'second')
        self.assertEqual(target.read_text(), 'second')
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)


if __name__ == '__main__':
    unittest.main()
