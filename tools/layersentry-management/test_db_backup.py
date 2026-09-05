import contextlib
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('backup', Path(__file__).with_name('db-backup.py'))
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
SOURCE = '11111111-1111-4111-8111-111111111111'
TARGET = '22222222-2222-4222-8222-222222222222'


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.old_umask = os.umask(0o077)
        self.key = self.root / 'key.pem'
        self.cert = self.root / 'cert.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(self.key),
                        '-out', str(self.cert), '-days', '2', '-subj', '/CN=Disposable unit test'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.defaults = self.root / 'client.cnf'
        self.defaults.write_text('[client]\nuser=unit_test_only\n')
        self.config = {'directory': str(self.root / 'backups'), 'defaults_file': str(self.defaults),
                       'recipient_certificate': str(self.cert), 'retention': 2}
        self.actual_command = backup.command
        self.dump = b'-- Unit-test SQL only\nCREATE DATABASE cloud;\nCREATE DATABASE cloud_usage;\n'

    def tearDown(self):
        os.umask(self.old_umask)
        self.temporary.cleanup()

    def query(self, _defaults, sql):
        if '@@server_uuid' in sql:
            return SOURCE
        if 'COUNT(*) FROM information_schema.schemata' in sql:
            return '2'
        if 'engine !=' in sql:
            return '0'
        if 'SUM(data_length' in sql:
            return '123'
        self.fail('unexpected query')

    def command(self, argv, **kwargs):
        if argv[0] == 'mysqldump':
            self.assertIn('--single-transaction', argv)
            self.assertIn('--routines', argv)
            self.assertIn('--set-gtid-purged=OFF', argv)
            kwargs['output'].write(self.dump)
            return ''
        return self.actual_command(argv, **kwargs)

    def create(self):
        with patch.object(backup, 'query', self.query), patch.object(backup, 'command', self.command), contextlib.redirect_stdout(io.StringIO()):
            backup.backup(self.config)
        return max((self.root / 'backups').glob('backup-*'), key=lambda x: x.stat().st_mtime)

    def test_actual_cms_encrypt_decrypt_and_integrity(self):
        result = self.create()
        manifest = backup.verify(result)
        self.assertEqual(manifest['source_server_uuid'], SOURCE)
        decrypted = self.root / 'decrypted.gz'
        self.actual_command(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER',
                             '-in', str(result / manifest['file']), '-inkey', str(self.key), '-out', str(decrypted)])
        with gzip.open(decrypted, 'rb') as stream:
            self.assertEqual(stream.read(), self.dump)
        self.assertEqual({p.name for p in result.iterdir()}, {'manifest.json', 'databases.sql.gz.cms'})
        self.assertEqual((result / manifest['file']).stat().st_mode & 0o777, 0o600)

    def test_retention_only_after_three_valid_successes(self):
        for _ in range(3):
            self.create()
        self.assertEqual(len(list((self.root / 'backups').glob('backup-*'))), 2)

    def test_tampered_payload_rejected(self):
        result = self.create()
        with (result / 'databases.sql.gz.cms').open('ab') as stream:
            stream.write(b'tamper')
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            backup.verify(result)

    def test_manifest_path_traversal_rejected(self):
        result = self.create()
        path = result / 'manifest.json'
        data = json.loads(path.read_text())
        data['file'] = '../other-secret'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'payload filename'):
            backup.verify(result)

    def test_failed_dump_publishes_nothing(self):
        with patch.object(backup, 'query', self.query), patch.object(backup, 'command', side_effect=ValueError('dump failed')):
            with self.assertRaisesRegex(ValueError, 'dump failed'):
                backup.backup(self.config)
        self.assertEqual(list((self.root / 'backups').glob('backup-*')), [])
        self.assertEqual(list((self.root / 'backups').glob('.pending-*')), [])

    def test_nontransactional_source_rejected(self):
        def query(defaults, sql):
            return '1' if 'engine !=' in sql else self.query(defaults, sql)
        with patch.object(backup, 'query', query), self.assertRaisesRegex(ValueError, 'nontransactional'):
            backup.backup(self.config)

    def test_restore_refuses_source_and_unconfirmed_target(self):
        result = self.create()
        args = SimpleNamespace(backup=str(result), target_defaults=str(self.defaults), confirm_target_uuid=SOURCE,
                               private_key=str(self.key))
        with patch.object(backup, 'query', return_value=SOURCE), self.assertRaisesRegex(ValueError, 'source database'):
            backup.restore_check(args)
        with patch.object(backup, 'query', return_value=TARGET), self.assertRaisesRegex(ValueError, 'UUID confirmation'):
            backup.restore_check(args)

    def test_restore_refuses_nonempty_target(self):
        result = self.create()
        args = SimpleNamespace(backup=str(result), target_defaults=str(self.defaults), confirm_target_uuid=TARGET,
                               private_key=str(self.key))
        with patch.object(backup, 'query', side_effect=[TARGET, '1']), self.assertRaisesRegex(ValueError, 'no application databases'):
            backup.restore_check(args)


if __name__ == '__main__':
    unittest.main()
