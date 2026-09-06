import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('binding', Path(__file__).with_name('bind_components.py'))
binding = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(binding)


class BindingTest(unittest.TestCase):
    def test_only_audited_defaults_are_substituted(self):
        self.assertEqual(binding.concrete('--sync=${CAPC_CLOUDSTACKMACHINE_CKS_SYNC:=false}'), '--sync=false')
        for value in ['${UNKNOWN:=value}', '${CAPI_INSECURE_DIAGNOSTICS:=true}', '$(INJECT)', '${MISSING}']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                binding.concrete(value)

    def test_ccm_exact_digest_binding_and_unqualified_image_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'deployment.yaml').write_text('kind: Deployment\nimage: apache/cloudstack-kubernetes-provider:v1.2.0\n')
            verification = {'status': 'CI_VERIFIED', 'imageIndexDigest': 'sha256:' + 'a'*64, 'imageManifestDigest': 'sha256:' + 'd'*64,
                            'archiveSha256': 'b'*64, 'layersentrySourceCommit': 'c'*40}
            evidence = root / 'cloudstack-ccm-verification.json'
            evidence.write_text(json.dumps(verification))
            with patch('builtins.print'):
                binding.bind('cloudstack-ccm', root, root)
            self.assertIn('layersentry.local/cloudstack-ccm@sha256:' + 'a'*64, (root / 'cloud-controller-manager.yaml').read_text())
            result = json.loads((root / 'cloudstack-ccm-component-binding.json').read_text())
            self.assertFalse(result['productionCertified'])
            verification['status'] = 'NOT_TESTED'
            evidence.write_text(json.dumps(verification))
            with self.assertRaises(ValueError):
                binding.bind('cloudstack-ccm', root, root)

    def test_extra_unpinned_image_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'deployment.yaml').write_text('image: apache/cloudstack-kubernetes-provider:v1.2.0\nimage: unsafe:latest\n')
            (root / 'cloudstack-ccm-verification.json').write_text(json.dumps({'status': 'CI_VERIFIED', 'imageIndexDigest': 'sha256:' + 'a'*64, 'imageManifestDigest': 'sha256:' + 'd'*64}))
            with self.assertRaises(ValueError):
                binding.bind('cloudstack-ccm', root, root)


if __name__ == '__main__':
    unittest.main()
