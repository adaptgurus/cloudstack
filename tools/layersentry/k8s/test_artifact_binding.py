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

"""Regression tests for immutable contract data; never use a live client."""
import ast
import hashlib
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from controller.components import evaluate_component_readiness, validate_qualification_templates
from controller.model import InvalidRequestError

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / 'release-candidate-lane-b.json').read_text())

class ArtifactBindingTest(unittest.TestCase):
    def test_capc_requires_digest(self):
        for value in (None, 'ghcr.io/adaptgurus/layersentry-capc:0.6.1',
                      'ghcr.io/adaptgurus/layersentry-capc@sha256:bad'):
            with self.subTest(value=value):
                candidate = deepcopy(MANIFEST)
                candidate['capcDownstream']['image'] = value
                self.assertTrue(any('CAPC immutable' in b for b in evaluate_component_readiness(candidate).blockers))

    def test_flux_verified_boolean_cannot_replace_repository_commit_or_digest(self):
        for field, values in {'repository': [None, 'http://example.test/catalog'],
                              'commit': [None, 'main', 'a'*39],
                              'contentSha256': [None, 'A'*64, 'a'*63, 'a'*64+'\n']}.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    candidate = deepcopy(MANIFEST)
                    candidate['fluxCatalog'][field] = value
                    candidate['fluxCatalog']['contentDigestVerified'] = True
                    self.assertTrue(any('Flux catalog' in b for b in evaluate_component_readiness(candidate).blockers))

    def local_locks(self, directory):
        root = Path(directory)
        (root / 'artifacts').mkdir()
        candidate = deepcopy(MANIFEST)
        for section in ('managementArtifactLock', 'qualificationArtifactLock'):
            filename = Path(candidate[section]['path']).name
            (root / 'artifacts' / filename).write_bytes((ROOT / 'artifacts' / filename).read_bytes())
        return root, candidate

    def test_management_lock_tamper_and_schema_fail_closed(self):
        mutations = ['sha', 'path', 'altered', 'missing-file', 'duplicate', 'unknown', 'tag',
                     'missing-capi', 'missing-capc', 'missing-caprke2-bootstrap', 'missing-caprke2-control-plane']
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root, candidate = self.local_locks(directory)
                path = root / 'artifacts/management-lock.json'
                data = json.loads(path.read_text())
                if mutation == 'sha': candidate['managementArtifactLock']['sha256'] = '0'*64
                elif mutation == 'path': candidate['managementArtifactLock']['path'] = '/tmp/foreign.json'
                elif mutation == 'altered': path.write_text(path.read_text()+' ')
                elif mutation == 'missing-file': path.unlink()
                else:
                    if mutation == 'duplicate': data['components'][-1] = data['components'][0]
                    elif mutation == 'unknown': data['components'][0]['name'] = 'foreign-controller'
                    elif mutation == 'tag': data['components'][0]['image'] = 'registry.example.test/image:latest'
                    else: data['components'] = [r for r in data['components'] if r['name'] != mutation.removeprefix('missing-')]
                    path.write_text(json.dumps(data))
                    candidate['managementArtifactLock']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertIn('Management artifact lock is invalid', evaluate_component_readiness(candidate, artifact_root=root).blockers)

    def test_rocky_uuid_and_checksum_substitution_rejected(self):
        lock = json.loads((ROOT/'artifacts/qualification-lock.json').read_text())
        validate_qualification_templates(lock['projectId'], [lock['template']['id']]*4)
        with self.assertRaisesRegex(InvalidRequestError, 'UUID'):
            validate_qualification_templates(lock['projectId'], [lock['template']['id'], 'foreign-uuid'])
        with tempfile.TemporaryDirectory() as directory:
            root, candidate = self.local_locks(directory)
            path = root/'artifacts/qualification-lock.json'
            lock['template']['qcow2Sha256'] = '0'*64
            path.write_text(json.dumps(lock))
            with self.assertRaisesRegex(InvalidRequestError, 'SHA256 mismatch'):
                validate_qualification_templates(lock['projectId'], [lock['template']['id']], candidate, root)

    def test_live_gates_remain_false_with_consumption_blockers(self):
        self.assertTrue(all(value is False for value in MANIFEST['hardGates'].values()))
        for section, field in [('cloudstackCcm','kubernetes136Qualified'),
                               ('cloudstackCsiDownstream','projectLifecycleQualified'),
                               ('cloudstackCsiDownstream','resizeIdempotencyQualified')]:
            self.assertIs(MANIFEST[section][field], False)
        blockers = evaluate_component_readiness(MANIFEST).blockers
        self.assertEqual(len([b for b in blockers if b.startswith("E1 evidence gate")]), 4)
        self.assertFalse(evaluate_component_readiness(MANIFEST).deployable)

    def test_resource_generation_enforces_reserved_project_template(self):
        from test_e1_resources import request, resolved
        from controller.e1_resources import build_cluster_resources
        lock = json.loads((ROOT/'artifacts/qualification-lock.json').read_text())
        with self.assertRaisesRegex(InvalidRequestError, 'qualification template UUID'):
            build_cluster_resources(request(project_id=lock['projectId']),
                                    resolved(project_id=lock['projectId']))

    def test_artifact_validation_has_no_command_or_network_execution(self):
        source = (ROOT/'controller/components.py').read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [n.name for n in node.names] if isinstance(node, ast.Import) else [node.module or '']
                self.assertFalse(any(n.startswith(('subprocess','socket','requests','urllib.request')) for n in names))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(node.func.id, ('exec','eval','compile','__import__'))
        self.assertNotIn('deployVirtualMachine', source)
        self.assertNotIn('createNetwork', source)
