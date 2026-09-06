import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('prepare_apk', ROOT / 'prepare_apk.py')
apk = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(apk)


class PackageClosureTest(unittest.TestCase):
    def test_manifest_integrity_bindings_are_preserved(self):
        manifest = json.loads((ROOT / 'manifest.json').read_text())
        release = json.loads((ROOT.parent.parent / 'release-candidate-lane-b.json').read_text())
        patch_sha = hashlib.sha256((ROOT / manifest['patches'][0]['path']).read_bytes()).hexdigest()
        lock_sha = hashlib.sha256((ROOT / 'apk-lock.json').read_bytes()).hexdigest()
        self.assertEqual(manifest['patches'][0]['sha256'], patch_sha)
        self.assertEqual(manifest['buildImages']['apkPackageLayer']['sha256'], lock_sha)
        self.assertEqual(release['cloudstackCsiDownstream']['patchSha256'], patch_sha)
        self.assertEqual(release['cloudstackCsiDownstream']['apkLockSha256'], lock_sha)

    def test_checked_in_closure_preserves_mount_resize_and_trust(self):
        lock = apk.load_lock(ROOT / 'apk-lock.json')
        patch = (ROOT / '0001-layersentry-idempotent-expand.diff').read_text()
        for entry in lock['architectures'].values():
            for profile, data in entry['profiles'].items():
                self.assertIn(data['checksumsSha256'], patch)
                files = [p['file'] for p in data['packages']]
                required = ['ca-certificates-']
                if profile == 'driver':
                    required += ['e2fsprogs-', 'e2fsprogs-extra-', 'xfsprogs-', 'xfsprogs-extra-', 'mount-', 'umount-', 'blkid-', 'eudev-']
                for prefix in required:
                    self.assertTrue(any(f.startswith(prefix) for f in files), prefix)
        self.assertEqual(patch.count('+RUN --network=none --mount='), 2)
        self.assertNotIn('+RUN apk add --no-cache', patch)
        self.assertNotIn('--allow-untrusted', patch)

    def test_lock_rejects_path_url_digest_arch_and_duplicate_tampering(self):
        original = json.loads((ROOT / 'apk-lock.json').read_text())
        for field, value in [('file', '../evil.apk'), ('url', 'http://127.0.0.1/secret'), ('size', True), ('sha256', 'f'*64)]:
            lock = json.loads(json.dumps(original))
            lock['architectures']['amd64']['profiles']['driver']['packages'][0][field] = value
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'lock.json'
                path.write_text(json.dumps(lock))
                with self.assertRaises(apk.LockError):
                    apk.load_lock(path)
        with self.assertRaises(apk.LockError):
            apk.unique_object([('schemaVersion', '1.0'), ('schemaVersion', '2.0')])

    def test_tampered_truncated_and_oversize_package_fail(self):
        item = {'size': 3, 'sha256': hashlib.sha256(b'abc').hexdigest()}
        for content in [b'ab', b'abcd', b'xyz']:
            with tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(apk.LockError):
                    apk.copy_verified(io.BytesIO(content), Path(directory) / 'test.apk', item)

    def test_offline_stage_is_atomic_and_does_not_fallback_to_network(self):
        content = b'fixture'
        package = {'file': 'fixture-1-r0.apk', 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest()}
        lock = {'architectures': {'amd64': {'profiles': {'driver': {'packages': [package]}}}}}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / 'cache'
            package_dir = cache / 'amd64' / 'driver'
            package_dir.mkdir(parents=True)
            output = root / 'output'
            with self.assertRaises(apk.LockError):
                apk.prepare(lock, output, 'amd64', cache)
            self.assertFalse(output.exists())
            self.assertFalse(list(root.glob('.csi-apk-*')))
            source = package_dir / package['file']
            source.write_bytes(content)
            apk.prepare(lock, output, 'amd64', cache)
            self.assertEqual((output / 'amd64/driver/SHA256SUMS').read_bytes(), apk.checksums([package]))
            with self.assertRaises(apk.LockError):
                apk.prepare(lock, output, 'amd64', cache)

    def test_offline_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / 'cache/amd64/driver'
            cache.mkdir(parents=True)
            (root / 'outside').write_bytes(b'fixture')
            (cache / 'fixture.apk').symlink_to(root / 'outside')
            lock = {'architectures': {'amd64': {'profiles': {'driver': {'packages': [{'file': 'fixture.apk'}]}}}}}
            with self.assertRaises(apk.LockError):
                apk.prepare(lock, root / 'output', 'amd64', root / 'cache')

    def test_redirect_is_rejected(self):
        with self.assertRaises(apk.LockError):
            apk.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://127.0.0.1')


if __name__ == '__main__':
    unittest.main()
