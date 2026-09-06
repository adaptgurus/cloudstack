import copy
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import render
import prepare_images


class NativeRenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        helm = os.environ.get('LAYERSENTRY_TEST_HELM')
        if not helm:
            raise unittest.SkipTest('set LAYERSENTRY_TEST_HELM to the exact pinned Helm binary for real rendering')
        cls.helm = Path(helm)
        cls.objects, cls.lock, cls.artifact = render.render(cls.helm)

    def setUp(self):
        self.objects = copy.deepcopy(type(self).objects)

    def resource(self, kind):
        return next(x for x in self.objects if x['kind'] == kind)

    def rejected(self):
        with self.assertRaises(render.InvalidBundle):
            render.validate(self.objects, self.lock, self.artifact)

    def test_real_helm_render_deterministic_and_no_credentials_or_syncer(self):
        second, _, _ = render.render(self.helm)
        self.assertEqual(second, self.objects)
        self.assertEqual(len(self.objects), 16)
        for item in self.objects:
            self.assertNotIn(item['kind'], {'Secret', 'Job', 'StorageClass', 'PersistentVolumeClaim'})
        self.assertFalse(any(self.lock['qualification'].values()))

    def test_digest_mutation_rejected(self):
        self.resource('Deployment')['spec']['template']['spec']['containers'][0]['image'] = 'registry.k8s.io/unpinned:latest'
        self.rejected()

    def test_namespace_escape_rejected(self):
        self.resource('ServiceAccount')['metadata']['namespace'] = 'tenant'
        self.rejected()

    def test_cross_namespace_rbac_rejected(self):
        self.resource('ClusterRoleBinding')['subjects'][0]['namespace'] = 'tenant'
        self.rejected()

    def test_wildcard_and_secret_read_rejected(self):
        role = self.resource('ClusterRole')
        for resource in ('*', 'secrets'):
            with self.subTest(resource=resource):
                role['rules'][0]['resources'] = [resource]
                self.rejected()

    def test_syncer_and_pvc_rejected(self):
        for kind in ('Job', 'StorageClass', 'PersistentVolumeClaim', 'Secret'):
            with self.subTest(kind=kind):
                self.objects.append({'kind': kind, 'metadata': {'name': 'unexpected'}})
                self.rejected()
                self.objects.pop()

    def test_credentials_host_path_and_other_secret_rejected(self):
        pod = self.resource('Deployment')['spec']['template']['spec']
        volume = next(x for x in pod['volumes'] if x['name'] == 'cloud-config')
        volume['secret']['secretName'] = 'another-project'
        self.rejected()

    def test_metadata_directory_and_writable_mount_rejected(self):
        pod = self.resource('DaemonSet')['spec']['template']['spec']
        mount = next(x for x in pod['containers'][0]['volumeMounts'] if x['name'] == 'cloud-init-dir')
        self.assertEqual(mount['mountPath'], render.METADATA)
        mount['readOnly'] = False
        self.rejected()

    def test_invented_node_identity_rejected(self):
        pod = self.resource('DaemonSet')['spec']['template']['spec']
        pod['containers'][0]['env'].append({'name': 'NODE_ID', 'value': 'invented'})
        self.rejected()

    def test_non_amd64_and_extra_container_rejected(self):
        pod = self.resource('DaemonSet')['spec']['template']['spec']
        pod['nodeSelector']['kubernetes.io/arch'] = 'arm64'
        self.rejected()
        pod['nodeSelector']['kubernetes.io/arch'] = 'amd64'
        pod['containers'].append({'name': 'unexpected'})
        self.rejected()

    def test_absent_duplicate_resource_rejected(self):
        self.objects.append(copy.deepcopy(self.objects[0]))
        self.rejected()
        self.objects.pop()
        self.objects = [x for x in self.objects if x['kind'] != 'CSIDriver']
        self.rejected()

    def test_unpublished_and_false_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            result = render.write_bundle(Path(temp) / 'review', self.objects, self.lock, self.artifact)
            self.assertFalse(result['deployable'])
            self.assertTrue(all(x['registryReference'] is None for x in result['images'][:2]))
            self.assertTrue(all(x['plannedReference'].startswith('registry.invalid/') for x in result['images'][:2]))
            self.assertFalse(result['images'][1]['enabled'])

    def test_chart_metadata_and_tool_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'native'
            shutil.copytree(render.ROOT, root, ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copy2(render.ROOT.parent / 'artifact-lock.json', root.parent / 'artifact-lock.json')
            path = root / 'chart' / 'values.yaml'
            original = path.read_bytes()
            path.write_bytes(original + b'\n# drift\n')
            with self.assertRaisesRegex(render.InvalidBundle, 'chart content'):
                render.locked_inputs(root)
            path.write_bytes(original)
            path = root / 'registry-evidence' / 'csi-attacher-amd64.json'
            path.write_bytes(path.read_bytes() + b'\n')
            with self.assertRaisesRegex(render.InvalidBundle, 'registry metadata'):
                render.locked_inputs(root)
            tool = Path(temp) / 'helm'
            tool.write_text('untrusted')
            with self.assertRaisesRegex(render.InvalidBundle, 'Helm binary'):
                render.helm_objects(tool, self.lock)


class ArchiveTests(unittest.TestCase):
    def test_deterministic_archive_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / 'a.tar', Path(temp) / 'b.tar'
            files = {'index.json': b'{"schemaVersion":2}', 'blobs/sha256/test': b'exactbytes'}
            prepare_images.write_archive(first, files)
            prepare_images.write_archive(second, files)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with tarfile.open(first) as archive:
                self.assertEqual(archive.extractfile('blobs/sha256/test').read(), b'exactbytes')
                self.assertTrue(all(x.uid == 0 and x.mtime == 0 for x in archive.getmembers()))

    def test_corrupt_and_oversized_download_rejected(self):
        class Response(io.BytesIO):
            def geturl(self):
                return 'https://registry.k8s.io/example'
        descriptor = {'digest': 'sha256:' + '0' * 64, 'size': 3}
        with tempfile.TemporaryDirectory() as temp:
            for body in (b'bad', b'excess'):
                with self.subTest(body=body), patch('urllib.request.OpenerDirector.open', return_value=Response(body)):
                    with self.assertRaises(render.InvalidBundle):
                        prepare_images.download_blob('registry.k8s.io/sig-storage/csi-attacher', descriptor, Path(temp) / body.decode())

    def test_archive_rejects_wrong_uncompressed_identity(self):
        def digest(raw):
            return 'sha256:' + hashlib.sha256(raw).hexdigest()
        layer = gzip.compress(b'layer fixture', mtime=0)
        descriptor = {'mediaType': 'application/vnd.docker.image.rootfs.diff.tar.gzip', 'digest': digest(layer), 'size': len(layer)}
        # All compressed hashes match; only the declared uncompressed identity is false.
        config = render.json_bytes({'os': 'linux', 'architecture': 'amd64', 'rootfs': {'diff_ids': ['sha256:' + '0' * 64]}})
        runtime = render.json_bytes({'config': {'digest': digest(config), 'size': len(config)}, 'layers': [descriptor]})
        item = {'runtimeManifestDigest': digest(runtime), 'configDigest': digest(config), 'layers': [descriptor]}
        files = {'oci-layout': b'{"imageLayoutVersion":"1.0.0"}',
                 'index.json': render.json_bytes({'manifests': [{'digest': digest(runtime), 'size': len(runtime)}]}),
                 'blobs/sha256/' + digest(runtime)[7:]: runtime,
                 'blobs/sha256/' + digest(config)[7:]: config,
                 'blobs/sha256/' + digest(layer)[7:]: layer}
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'fixture.tar'
            prepare_images.write_archive(archive, files)
            with self.assertRaisesRegex(render.InvalidBundle, 'uncompressed layer identity'):
                prepare_images.verify_sidecar_archive(archive, item)

    def test_plaintext_redirect_rejected(self):
        with self.assertRaises(render.InvalidBundle):
            prepare_images.TLSRedirect().redirect_request(None, None, 302, '', {}, 'http://example.com/blob')


if __name__ == '__main__':
    unittest.main()
