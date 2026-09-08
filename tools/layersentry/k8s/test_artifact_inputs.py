import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('artifact_build', Path(__file__).parent / 'artifacts/build.py')
artifact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(artifact)


class ArtifactInputTests(unittest.TestCase):
    def test_distribution_tree_is_deterministic_and_detects_tampering(self):
        from artifacts.distribution import inventory, tree_sha, verify
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'controller').mkdir()
            (root/'systemd').mkdir()
            for name in ('controller/runtime.py','layersentry_k8s_policy.py','layersentry_k8s_controller.py'):
                (root/name).write_text('# synthetic runtime fixture\n')
            rows = inventory(root)
            receipt = {'files':rows, 'treeSha256':tree_sha(rows)}
            self.assertTrue(verify(root, receipt))
            self.assertEqual(inventory(root), rows)
            (root/'controller/runtime.py').write_text('# altered\n')
            with self.assertRaisesRegex(ValueError, 'differs'):
                verify(root, receipt)

    def test_tampered_package_never_written(self):
        item = {'file': 'test.apk', 'url': 'https://dl-cdn.alpinelinux.org/alpine/v3.21/main/x86_64/test.apk',
                'bytes': 4, 'sha256': artifact.sha(b'good')}
        with tempfile.TemporaryDirectory() as root:
            with patch.object(artifact.urllib.request, 'urlopen', return_value=io.BytesIO(b'evil')):
                with self.assertRaises(ValueError):
                    artifact.fetch_package(item, Path(root))
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_runtime_digest_ignores_time_but_detects_content_and_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            def digest(mtime, content=b'good', mode=0o755):
                path = Path(root) / 'fs.tar'
                with tarfile.open(path, 'w') as archive:
                    item = tarfile.TarInfo('usr/bin/required-tool')
                    item.size, item.mode, item.mtime = len(content), mode, mtime
                    archive.addfile(item, io.BytesIO(content))
                return artifact.runtime_digest(path)
            first = digest(1)
            self.assertEqual(first, digest(2))
            self.assertNotEqual(first, digest(2, b'evil'))
            self.assertNotEqual(first, digest(2, mode=0o644))
