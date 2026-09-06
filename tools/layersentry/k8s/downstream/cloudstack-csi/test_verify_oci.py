from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('verify_oci', ROOT / 'verify_oci.py')
oci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oci)


def fixture(path, *, subject_wrong=False, sbom_missing=False, corrupt=False, platform_wrong=False, source_wrong=False, dependency_wrong=False, detached=False):
    blobs = {}
    def blob(value, media='application/vnd.oci.image.manifest.v1+json'):
        data = json.dumps(value).encode()
        digest = 'sha256:' + hashlib.sha256(data).hexdigest()
        blobs[digest] = data
        return {'digest': digest, 'size': len(data), 'mediaType': media}
    config = blob({'architecture': 'amd64', 'os': 'linux', 'config': {'Entrypoint': ['/cloudstack-csi-driver']}})
    image = blob({'schemaVersion': 2, 'config': config, 'layers': []})
    subject = {'digest': {'sha256': ('0' * 64 if subject_wrong else image['digest'].split(':')[1])}}
    approved = json.loads((ROOT / 'manifest.json').read_text())
    upstream = approved['upstreamCommit']
    vcs = {'localdir:context': '.', 'localdir:dockerfile': 'cmd/cloudstack-csi-driver',
           'revision': upstream, 'source': approved['upstreamRepository'].removesuffix('.git')}
    args = {'build-arg:LDFLAGS': '-s -w -X main.version=3.0.2-layersentry.' + 'a' * 40
        + ' -X github.com/cloudstack/cloudstack-csi-driver/pkg/driver.driverVersion=3.0.2-layersentry.' + 'a' * 40
        + ' -X github.com/cloudstack/cloudstack-csi-driver/pkg/driver.gitCommit=' + upstream}
    root_args = {**args, **{'vcs:' + key: value for key, value in vcs.items()}}
    dependencies = []
    for name, digest in [('docker/buildkit-syft-scanner', oci.SCANNER),
                         ('alpine', approved['buildImages']['runtime'].split('@sha256:')[1]),
                         ('golang', approved['buildImages']['builder'].split('@sha256:')[1])]:
        dependencies.append({'uri': f'pkg:docker/{name}?digest=sha256:{digest}&platform=linux%2Famd64', 'digest': {'sha256': digest}})
    if dependency_wrong: dependencies[0]['digest']['sha256'] = 'f' * 64
    if source_wrong: vcs['revision'] = 'f' * 40
    provenance = {'buildDefinition': {'externalParameters': {'configSource': {'path': 'Dockerfile'},
        'request': {'frontend': 'dockerfile.v0', 'args': args, 'root': {'request': {'args': root_args}}}},
        'resolvedDependencies': dependencies}, 'runDetails': {'metadata': {'buildkit_metadata': {'vcs': vcs}}}}
    predicates = [('https://slsa.dev/provenance/v1', provenance)]
    if not sbom_missing:
        predicates.append(('https://spdx.dev/Document', {'packages': [{'name': 'fixture'}]}))
    layers = [blob({'predicateType': kind, 'subject': [subject], 'predicate': value}, 'application/vnd.in-toto+json') for kind, value in predicates]
    attestation = blob({'schemaVersion': 2, 'config': blob({'architecture': 'unknown', 'os': 'unknown'}), 'layers': layers})
    image['platform'] = {'architecture': 'arm64' if platform_wrong else 'amd64', 'os': 'linux'}
    attestation['platform'] = {'architecture': 'unknown', 'os': 'unknown'}
    attestation['annotations'] = {'vnd.docker.reference.digest': image['digest'], 'vnd.docker.reference.type': 'attestation-manifest'}
    root = blob({'schemaVersion': 2, 'mediaType': oci.INDEX, 'manifests': [image, attestation]}, oci.INDEX)
    with tarfile.open(path, 'w') as tar:
        values = {'oci-layout': b'{"imageLayoutVersion":"1.0.0"}', 'index.json': json.dumps({'schemaVersion': 2, 'manifests': [image, attestation] if detached else [root]}).encode()}
        values.update({'blobs/sha256/' + digest.split(':')[1]: data for digest, data in blobs.items()})
        if corrupt:
            values['blobs/sha256/' + config['digest'].split(':')[1]] = b'corrupt'
        for name, data in values.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
    return [{'Id': config['digest']}]


class VerifyOciTest(unittest.TestCase):
    def test_matching_image_and_attestations_are_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.tar'
            inspection = fixture(path)
            result = oci.verify(path, inspection, 'cloudstack-csi-driver', 'a' * 40)
            self.assertEqual(result['imageConfigDigest'], inspection[0]['Id'])
            self.assertEqual(set(result['attestations']), {'sbom', 'provenance'})
            self.assertFalse(result['productionCertified'])
            self.assertFalse(result['liveVerified'])
            self.assertFalse(result['signed'])
            self.assertEqual(result['platform'], 'linux/amd64')
            self.assertEqual(result['provenanceSourceBinding']['layersentryCommit'], 'a' * 40)
            self.assertTrue(result['imageIndexDigest'].startswith('sha256:'))

    def test_false_source_platform_dependency_and_detached_index_fail(self):
        for options in [{'platform_wrong': True}, {'source_wrong': True}, {'dependency_wrong': True}, {'detached': True}]:
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'image.tar'
                inspection = fixture(path, **options)
                with self.assertRaises(oci.VerificationError):
                    oci.verify(path, inspection, 'cloudstack-csi-driver', 'a' * 40)

    def test_a_different_claimed_layer_commit_cannot_relabel_existing_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.tar'
            inspection = fixture(path)
            with self.assertRaisesRegex(oci.VerificationError, 'provenance does not bind'):
                oci.verify(path, inspection, 'cloudstack-csi-driver', 'b' * 40)

    def test_retained_artifact_binding_rejects_archive_index_and_attestation_substitution(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'image.tar'
            result = oci.verify(path, fixture(path), 'cloudstack-csi-driver', 'a' * 40)
            entry = {key: result[key] for key in ('archiveSha256', 'archiveSizeBytes', 'imageIndexDigest',
                'imageManifestDigest', 'imageConfigDigest', 'platform', 'provenanceSourceBinding')}
            entry['attestations'] = {kind: {'digest': item['digest'], 'predicateType': item['document']['predicateType']}
                                    for kind, item in result['attestations'].items()}
            lock = {'schemaVersion': '1.0', 'artifactType': 'layersentry-csi-build-closure',
                    'layersentrySourceCommit': 'a' * 40, 'upstreamCommit': result['provenanceSourceBinding']['upstreamCommit'],
                    'images': {'cloudstack-csi-driver': entry}}
            oci.verify_artifact_binding(result, lock)
            for key in ('archiveSha256', 'imageIndexDigest', 'platform', 'attestations'):
                tampered = deepcopy(lock)
                tampered['images']['cloudstack-csi-driver'][key] = 'substituted'
                with self.subTest(key=key), self.assertRaises(oci.VerificationError):
                    oci.verify_artifact_binding(result, tampered)

    def test_missing_sbom_wrong_subject_corrupt_blob_and_wrong_image_fail(self):
        for options in [{'subject_wrong': True}, {'sbom_missing': True}, {'corrupt': True}, {}]:
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'image.tar'
                inspection = fixture(path, **options)
                if not options:
                    inspection[0]['Id'] = 'sha256:' + 'f' * 64
                with self.assertRaises(oci.VerificationError):
                    oci.verify(path, inspection, 'cloudstack-csi-driver', 'a' * 40)


if __name__ == '__main__':
    unittest.main()
