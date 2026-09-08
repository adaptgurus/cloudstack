# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Archive authority and observation-only collector regressions."""
import importlib.util
import io
import json
import hashlib
from pathlib import Path
from copy import deepcopy
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from controller.components import _rke2_consumption

ROOT = Path(__file__).parent
MANIFEST = json.loads((ROOT/'release-candidate-lane-b.json').read_text())
spec = importlib.util.spec_from_file_location('host_observer', ROOT/'artifacts/collect-runtime-host.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)

class ArchiveAuthorityTests(unittest.TestCase):
    def test_verified_archive_controls_consumption_not_public_registry(self):
        for mutation in ('valid','registry','archive-sha','missing','wrong-image','bad-layer','unverified-blobs'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root=Path(directory);(root/'artifacts').mkdir()
                q=json.loads((ROOT/'artifacts/qualification-lock.json').read_text())
                proof=json.loads((ROOT/'artifacts/rke2-image-proof.json').read_text())
                if mutation=='registry':
                    for row in proof['images']:
                        row['externalRegistryObservation']={'digest':'sha256:'+'0'*64,'matchesArchiveIndex':False}
                elif mutation=='archive-sha':proof['releaseArchiveIdentity']['sha256']='0'*64
                elif mutation=='missing':proof['images'].pop()
                elif mutation=='wrong-image':proof['images'][0]['reference']='docker.io/foreign/image:wrong'
                elif mutation=='bad-layer':proof['images'][0]['archiveContainedImageIdentity']['layerDigests']=['bad']
                elif mutation=='unverified-blobs':proof['blobIntegrity']['allBlobHashesVerified']=False
                p=root/'artifacts/rke2-image-proof.json';p.write_text(json.dumps(proof))
                q['rke2Artifacts']['imageProof']['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
                p=root/'artifacts/qualification-lock.json';p.write_text(json.dumps(q))
                manifest=deepcopy(MANIFEST);manifest['qualificationArtifactLock']['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
                blockers=[];_rke2_consumption(manifest,blockers,root)
                self.assertEqual(bool(blockers),mutation not in ('valid','registry'),blockers)

    def test_registry_runtime_divergence_is_preserved(self):
        proof=json.loads((ROOT/'artifacts/rke2-image-proof.json').read_text())
        runtime=next(r for r in proof['images'] if r['reference'].startswith('docker.io/rancher/rke2-runtime:'))
        self.assertEqual(proof['status'],'PASS')
        self.assertFalse(runtime['externalRegistryObservation']['matchesArchiveIndex'])
        self.assertEqual(runtime['archiveContainedImageIdentity']['indexDigest'],
                         'sha256:7956a28b1ebd803f58341ba88fed4c8bc878ec13226c2e55959ba5a88c21341e')

class HostObservationTests(unittest.TestCase):
    def test_direct_url_credentials_never_returned(self):
        secret='synthetic-password-not-for-evidence'
        data={'INSTALLER':'pip','RECORD':'synthetic record',
              'direct_url.json':json.dumps({'url':'https://user:'+secret+'@example.invalid/package.whl',
                 'archive_info':{'hashes':{'sha256':'a'*64}}})}
        dist=SimpleNamespace(files=[],version='23.0.0',metadata={'Name':'gunicorn'},read_text=lambda n:data.get(n))
        with patch.object(observer.metadata,'distribution',return_value=dist):
            _,result=observer.distribution_observation('gunicorn')
        self.assertNotIn(secret,json.dumps(result))
        self.assertEqual(result['wheelOrSourceArchiveSha256'],'a'*64)
        self.assertEqual(result['fileCount'],0)

    def test_rpm_query_is_read_only_and_stderr_not_returned(self):
        with patch.object(observer.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='python3-0:3.9.25-1.el9.x86_64',stderr='synthetic secret')) as run:
            result=observer.rpm_owner(Path('/usr/bin/python3'))
        argv=run.call_args.args[0]
        self.assertEqual(argv[:3],['rpm','-qf','--qf'])
        self.assertNotIn('synthetic secret',result)
        self.assertTrue(run.call_args.kwargs['timeout']<=20)

    def test_shared_host_exception_is_explicit_and_bounded(self):
        self.assertFalse(observer.host_role_allowed(['10.10.10.14'], ['cloudstack-agent'], False))
        self.assertTrue(observer.host_role_allowed(['10.10.10.14'], ['cloudstack-agent'], True))
        self.assertFalse(observer.host_role_allowed(['10.10.10.20'], [], True))
        self.assertFalse(observer.host_role_allowed(['10.10.10.140'], [], True))
        self.assertFalse(observer.host_role_allowed(['10.10.10.14'], ['rke2-server'], True))
        self.assertFalse(observer.host_role_allowed(['10.10.10.14'], ['rke2-agent'], True))
        self.assertTrue(observer.host_role_allowed(['10.10.10.50'], [], False))

    def test_hashing_does_not_follow_package_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'package').mkdir();secret=root/'outside';secret.write_text('one')
            (root/'package/link').symlink_to(secret)
            a=observer.tree_hash(root/'package');secret.write_text('two')
            self.assertEqual(a,observer.tree_hash(root/'package'))
