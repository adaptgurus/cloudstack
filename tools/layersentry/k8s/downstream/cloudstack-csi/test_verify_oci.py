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


def fixture(path, *, subject_wrong=False, sbom_missing=False, corrupt=False):
    blobs = {}
    def blob(value, media='application/vnd.oci.image.manifest.v1+json'):
        data = json.dumps(value).encode()
        digest = 'sha256:' + hashlib.sha256(data).hexdigest()
        blobs[digest] = data
        return {'digest': digest, 'size': len(data), 'mediaType': media}
    config = blob({'architecture': 'amd64', 'os': 'linux', 'config': {'Entrypoint': ['/cloudstack-csi-driver']}})
    image = blob({'schemaVersion': 2, 'config': config, 'layers': []})
    subject = {'digest': {'sha256': ('0' * 64 if subject_wrong else image['digest'].split(':')[1])}}
    predicates = [('https://slsa.dev/provenance/v0.2', {'builder': {'id': 'fixture'}})]
    if not sbom_missing:
        predicates.append(('https://spdx.dev/Document', {'packages': [{'name': 'fixture'}]}))
    layers = [blob({'predicateType': kind, 'subject': [subject], 'predicate': value}, 'application/vnd.in-toto+json') for kind, value in predicates]
    attestation = blob({'config': blob({'architecture': 'unknown', 'os': 'unknown'}), 'layers': layers})
    with tarfile.open(path, 'w') as tar:
        values = {'oci-layout': b'{"imageLayoutVersion":"1.0.0"}', 'index.json': json.dumps({'manifests': [image, attestation]}).encode()}
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
