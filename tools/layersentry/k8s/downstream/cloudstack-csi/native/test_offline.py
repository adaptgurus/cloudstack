import json
import hashlib
import tarfile
import tempfile
import io
from pathlib import Path
import unittest
from unittest.mock import patch

import qualify_offline
from render import ROOT, InvalidBundle, locked_inputs


class OfflineImportTests(unittest.TestCase):
    def setUp(self):
        self.lock, self.artifact = locked_inputs()
        self.expected = qualify_offline.expected_images(self.lock, self.artifact)

    def rows(self):
        return ('REF TYPE DIGEST SIZE PLATFORMS LABELS\n' + '\n'.join(
            x['reference'] + ' application/vnd.oci.image.manifest.v1+json ' + x['digest'] + ' 10MiB linux/amd64 -'
            for x in self.expected) + '\n' + '\n'.join(
            x['repository'] + '@' + x['retainedIndexDigest'] + ' application/vnd.oci.image.index.v1+json ' + x['retainedIndexDigest'] + ' 10MiB linux/amd64 -'
            for x in self.expected if 'retainedIndexDigest' in x)).encode()

    def test_exact_runtime_targets_and_repeat_observation(self):
        first = qualify_offline.verify_rows(self.rows(), self.expected)
        second = qualify_offline.verify_rows(self.rows(), self.expected)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 7)
        self.assertTrue(self.expected[0]['reference'].startswith('registry.invalid/'))
        self.assertNotEqual(self.expected[0]['digest'], self.expected[0]['retainedIndexDigest'])

    def test_index_cannot_impersonate_runtime_target(self):
        raw = self.rows().replace((' ' + self.expected[0]['digest'] + ' ').encode(),
                                  (' ' + self.expected[0]['retainedIndexDigest'] + ' ').encode())
        with self.assertRaisesRegex(InvalidBundle, 'descriptor differs'):
            qualify_offline.verify_rows(raw, self.expected)

    def test_missing_target_rejected(self):
        raw = b'\n'.join(self.rows().splitlines()[:1] + self.rows().splitlines()[2:])
        with self.assertRaisesRegex(InvalidBundle, 'descriptor differs'):
            qualify_offline.verify_rows(raw, self.expected)

    def test_changed_repository_rejected(self):
        with self.assertRaisesRegex(InvalidBundle, 'descriptor differs'):
            qualify_offline.verify_rows(self.rows().replace(b'registry.invalid/', b'foreign.invalid/'), self.expected)

    def test_runtime_envelope_keeps_exact_blobs_and_original_archive(self):
        def digest(raw):
            return 'sha256:' + hashlib.sha256(raw).hexdigest()
        runtime = b'{"config":{}}'
        inner = qualify_offline.json_bytes({'manifests': [{'digest': digest(runtime), 'size': len(runtime),
            'mediaType': 'application/vnd.oci.image.manifest.v1+json', 'platform': {'os': 'linux', 'architecture': 'amd64'}}]})
        top = qualify_offline.json_bytes({'manifests': [{'digest': digest(inner), 'size': len(inner),
            'mediaType': 'application/vnd.oci.image.index.v1+json', 'annotations': {'org.opencontainers.image.ref.name': 'old'}}]})
        files = {'index.json': top, 'oci-layout': b'{"imageLayoutVersion":"1.0.0"}',
                 'blobs/sha256/' + digest(inner)[7:]: inner, 'blobs/sha256/' + digest(runtime)[7:]: runtime}
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp) / 'original.tar', Path(temp) / 'envelope.tar'
            with tarfile.open(source, 'w') as archive:
                directory = tarfile.TarInfo('blobs'); directory.type = tarfile.DIRTYPE; archive.addfile(directory)
                for name, raw in files.items():
                    member = tarfile.TarInfo(name); member.size = len(raw); archive.addfile(member, io.BytesIO(raw))
            original = source.read_bytes()
            image = {'archiveSha256': hashlib.sha256(original).hexdigest(), 'imageIndexDigest': digest(inner), 'imageManifestDigest': digest(runtime)}
            result = qualify_offline.runtime_envelope(source, target, image)
            self.assertFalse(result['imageBlobsModified'])
            self.assertEqual(source.read_bytes(), original)
            with tarfile.open(target) as archive:
                root = json.load(archive.extractfile('index.json'))
                self.assertEqual([x['digest'] for x in root['manifests']], [digest(inner), digest(runtime)])
                self.assertNotIn('annotations', root['manifests'][0])
                for name, raw in files.items():
                    if name.startswith('blobs/'):
                        self.assertEqual(archive.extractfile(name).read(), raw)
            image['archiveSha256'] = '0' * 64
            with self.assertRaisesRegex(InvalidBundle, 'retained archive changed'):
                qualify_offline.runtime_envelope(source, target, image)

    def test_no_lab_or_local_daemon_execution(self):
        runtime = json.loads((ROOT / 'qualification-tools.lock.json').read_text())
        with patch.dict('os.environ', {'GITHUB_ACTIONS': '', 'RUNNER_ENVIRONMENT': ''}), patch('subprocess.Popen') as daemon:
            with self.assertRaisesRegex(InvalidBundle, 'disposable GitHub-hosted'):
                qualify_offline.native_import(Path('/absent'), Path('/absent'), Path('/absent'), self.lock, self.artifact, runtime)
            daemon.assert_not_called()


if __name__ == '__main__':
    unittest.main()
