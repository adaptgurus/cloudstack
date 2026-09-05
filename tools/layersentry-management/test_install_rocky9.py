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

    def test_preflight_requires_checkpoint_tooling(self):
        state = installer.Installer.__new__(installer.Installer)
        state.c = self.config
        with patch.object(installer.os, 'geteuid', return_value=0), \
                patch.object(installer.shutil, 'which', side_effect=lambda name: None if name == 'tar' else '/usr/bin/' + name), \
                self.assertRaisesRegex(ValueError, 'required host command missing: tar'):
            state.preflight()

    def test_blank_mysql_datadir_is_initialized_insecurely_for_immediate_rotation(self):
        datadir = self.root / 'mysql'
        datadir.mkdir()

        def command(argv, **_kwargs):
            if argv[0] == 'mysqld':
                (datadir / 'mysql').mkdir()
            return ''

        with patch.object(installer, 'run', side_effect=command) as run:
            self.assertTrue(installer.initialize_insecure_mysql_datadir(datadir))
        self.assertIn(['mysqld', '--no-defaults', '--initialize-insecure', '--user=mysql',
                       '--datadir=' + str(datadir)], [call.args[0] for call in run.call_args_list])
        with patch.object(installer, 'run') as run:
            self.assertFalse(installer.initialize_insecure_mysql_datadir(datadir))
            run.assert_not_called()

    def test_ambiguous_mysql_datadir_is_never_initialized(self):
        datadir = self.root / 'mysql-ambiguous'
        datadir.mkdir()
        (datadir / 'auto.cnf').write_text('server-uuid')
        with patch.object(installer, 'run') as run, self.assertRaisesRegex(ValueError, 'neither initialized nor empty'):
            installer.initialize_insecure_mysql_datadir(datadir)
        run.assert_not_called()

    def test_lost_found_and_symlink_mysql_datadirs_are_never_initialized(self):
        datadir = self.root / 'mysql-with-lost-found'
        (datadir / 'lost+found').mkdir(parents=True)
        link = self.root / 'mysql-link'
        link.symlink_to(datadir, target_is_directory=True)
        for candidate in (datadir, link):
            with self.subTest(candidate=candidate), patch.object(installer, 'run') as run, \
                    self.assertRaises(ValueError):
                installer.initialize_insecure_mysql_datadir(candidate)
            run.assert_not_called()

    def recovery_installer(self):
        state = installer.Installer.__new__(installer.Installer)
        state.c = self.config
        state.s = self.secrets
        state.journal = {'stages': {'checkpoint': 'applied', 'packages': 'applied',
                                    'database': 'in_progress'}}
        return state

    def test_database_bootstrap_recovery_requires_empty_cloudstack_schemas(self):
        datadir = self.root / 'mysql-recovery'
        (datadir / 'mysql').mkdir(parents=True)
        (datadir / 'auto.cnf').write_text('server_uuid=test')
        state = self.recovery_installer()
        stopped = type('Result', (), {'returncode': 3})()
        with patch.object(installer, 'MYSQL_DATADIR', datadir), \
                patch.object(installer, 'MYSQL_BOOTSTRAP', self.root / 'absent.sql'), \
                patch.object(installer, 'RUNTIME_DIR', self.root), \
                patch.object(installer, 'write_private'), patch.object(installer, 'run'), \
                patch.object(installer, 'mysql', side_effect=['1', '0']), \
                patch.object(installer.subprocess, 'run', return_value=stopped), \
                patch.object(state, 'save') as save:
            state.recover_database_bootstrap()
        self.assertNotIn('database', state.journal['stages'])
        save.assert_called_once()

        state = self.recovery_installer()
        with patch.object(installer, 'MYSQL_DATADIR', datadir), \
                patch.object(installer, 'MYSQL_BOOTSTRAP', self.root / 'absent.sql'), \
                patch.object(installer, 'RUNTIME_DIR', self.root), \
                patch.object(installer, 'write_private'), patch.object(installer, 'run'), \
                patch.object(installer, 'mysql', side_effect=['1', '1']), \
                patch.object(installer.subprocess, 'run', return_value=stopped) as systemctl, \
                patch.object(state, 'save') as save, self.assertRaisesRegex(ValueError, 'schema exists'):
            state.recover_database_bootstrap()
        self.assertEqual('in_progress', state.journal['stages']['database'])
        save.assert_not_called()
        self.assertGreaterEqual(systemctl.call_count, 2)

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
        db.write_text(self.external_properties())
        db.chmod(0o600)
        config = dict(self.config, mode='external', initialize_database=False, db_host='db.example',
                      db_properties_file=str(db), encryption_key_file=str(self.cert), db_tls_ca=str(self.cert))
        installer.validate(config, self.secrets)
        db.write_text(db.read_text().replace('db.example', 'other.example'))
        with self.assertRaisesRegex(ValueError, 'host mismatch'):
            installer.validate(config, self.secrets)

    def external_properties(self):
        lines = ['cluster.node.IP=192.0.2.10']
        for schema, name in [('cloud', 'cloud'), ('usage', 'cloud_usage')]:
            prefix = 'db.' + schema + '.'
            lines.extend(prefix + key + '=' + value for key, value in {
                'host': 'db.example', 'port': '3306', 'driver': 'jdbc:mysql', 'name': name,
                'password': 'ENC(ciphertext)',
                'url.params': 'useSSL=true&requireSSL=true&verifyServerCertificate=true&sslMode=VERIFY_IDENTITY&serverTimezone=UTC'
            }.items())
        return '\n'.join(lines) + '\n'

    def check_external(self, content):
        installer.validate_external_properties(content, dict(self.config, db_host='db.example'))

    def test_external_uri_override_always_rejected(self):
        for key in ('db.cloud.uri', 'db.usage.uri', r'db.cloud.\u0075ri'):
            for value in ('jdbc:mysql://other.example/cloud?useSSL=false', ''):
                with self.subTest(key=key, value=value), self.assertRaisesRegex(ValueError, 'URI override'):
                    self.check_external(self.external_properties() + key + '=' + value + '\n')

    def test_external_tls_in_comments_does_not_count(self):
        content = self.external_properties().replace('db.cloud.url.params=', '#db.cloud.url.params=')
        with self.assertRaisesRegex(ValueError, 'explicit verified TLS'):
            self.check_external(content)

    def test_external_tls_required_for_usage_independently(self):
        content = '\n'.join(line for line in self.external_properties().splitlines() if not line.startswith('db.usage.url.params'))
        with self.assertRaisesRegex(ValueError, 'explicit verified TLS'):
            self.check_external(content)

    def test_external_last_property_controls_tls(self):
        with self.assertRaisesRegex(ValueError, 'explicit verified TLS'):
            self.check_external(self.external_properties() + 'db.cloud.url.params=useSSL=false\n')

    def test_external_tls_downgrade_and_duplicate_parameters_rejected(self):
        for change in ('sslMode=DISABLED', 'sslMode=VERIFY_CA', 'sslMode=VERIFY_IDENTITY&sslMode=DISABLED',
                       'sslMode=VERIFY_IDENTITY&sslmode=DISABLED', 'sslMode=VERIFY_IDENTITY&socketFactory=OtherClass'):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.check_external(self.external_properties().replace('sslMode=VERIFY_IDENTITY', change))

    def test_external_rejects_other_node_ip(self):
        for content in (self.external_properties().replace('192.0.2.10', '192.0.2.11'),
                        self.external_properties() + 'cluster.node.IP:192.0.2.11\n',
                        self.external_properties().replace('cluster.node.IP=', '#cluster.node.IP=')):
            with self.subTest(content=content), self.assertRaisesRegex(ValueError, 'cluster.node.IP'):
                self.check_external(content)

    def test_external_rejects_endpoint_redirection(self):
        for key, value in [('db.ha.enabled', 'true'), ('db.cloud.replicas', 'other.example'),
                           ('db.usage.driver', 'jdbc:custom'), ('db.cloud.name', 'cloud?useSSL=false')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check_external(self.external_properties() + key + '=' + value + '\n')

    def test_java_properties_escape_continuation_and_precedence(self):
        content = '#ignored=yes\r\n!also=ignored\n escaped\\ key : first\\nsecond\n'
        content += 'dup=old\ndup new\njoined=useSSL=true&\\\n  requireSSL=true\n'
        content += r'db.cloud.\u0075ri=redirect' + '\n'
        result = installer.java_properties(content)
        self.assertEqual(result, {'escaped key': 'first\nsecond', 'dup': 'new',
                                 'joined': 'useSSL=true&requireSSL=true', 'db.cloud.uri': 'redirect'})

    def test_external_valid_escaped_keys_and_continuations(self):
        content = self.external_properties().replace('cluster.node.IP=', r'cluster.node.\u0049P : ')
        content = content.replace('&requireSSL', '&\\\n  requireSSL')
        self.check_external(content)

    def test_java_properties_malformed_escape_rejected(self):
        for content in (r'key=\uZZZZ', r'key=\u12', 'key=unfinished\\'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                installer.java_properties(content)

    def test_external_comment_encrypted_password_is_not_a_credential(self):
        with self.assertRaisesRegex(ValueError, 'passwords must be encrypted'):
            self.check_external(self.external_properties().replace('db.usage.password=', '#db.usage.password='))

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

    def test_private_writer_preserves_java_properties_bytes(self):
        target = self.root / 'latin1.properties'
        content = b'comment=\xe9\n'
        installer.write_private(target, content)
        self.assertEqual(target.read_bytes(), content)


if __name__ == '__main__':
    unittest.main()
