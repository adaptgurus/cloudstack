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

"""Offline tests for the immutable controller/qualification consumption contract."""
import json
import hashlib
import shlex
import shutil
import subprocess
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from controller.components import _controller_distribution, evaluate_component_readiness, rke2_artifacts
from controller.e1_resources import qualification_bootstrap, build_cluster_resources
from controller.model import InvalidRequestError
from artifacts.distribution import inventory, tree_sha
from test_e1_resources import request, resolved

ROOT = Path(__file__).parent
MANIFEST = json.loads((ROOT/'release-candidate-lane-b.json').read_text())
LOCK = json.loads((ROOT/'artifacts/qualification-lock.json').read_text())

class ConsumptionTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        for folder in ('controller','systemd','artifacts'):
            shutil.copytree(ROOT/folder, root/folder, ignore=shutil.ignore_patterns('__pycache__'))
        for filename in ('layersentry_k8s_policy.py','layersentry_k8s_controller.py'):
            shutil.copy2(ROOT/filename, root/filename)
        runtime = {'schemaVersion':'1.0','status':'PINNED','architecture':'x86_64','os':{'id':'rocky','versionId':'9.8'},
                   'python':{'path':'/usr/bin/python3','implementation':'CPython','version':'3.12.1','sha256':'a'*64},
                   'gunicorn':{'version':'23.0.0','contentSha256':'b'*64},
                   'packages':[{'name':n,'version':'3.12.1','installationSource':{'kind':'rpm','url':'https://synthetic.invalid/package.rpm','nevra':'synthetic-3.12.1-1.x86_64','artifactSha256':'d'*64},'sha256':'c'*64} for n in ('python','gunicorn')],
                   'dependencyClosureVerified':True}
        rp=root/'artifacts/runtime-dependencies.json';rp.write_text(json.dumps(runtime))
        rows=inventory(root)
        receipt={'schemaVersion':'1.0','distribution':'systemd-filesystem','sourceCommit':'a'*40,
                 'files':rows,'treeSha256':tree_sha(rows),
                 'runtimeDependencyLock':{'path':'tools/layersentry/k8s/artifacts/runtime-dependencies.json','sha256':hashlib.sha256(rp.read_bytes()).hexdigest()},
                 'runtimeIdentity':{'os':{'id':'rocky','versionId':'9.8'},'pythonVersion':'3.12.1','gunicornVersion':'23.0.0','pythonSha256':'a'*64,'gunicornContentSha256':'b'*64}}
        manifest=deepcopy(MANIFEST)
        self.bind(root, manifest, receipt)
        return root, manifest, receipt, runtime

    def bind(self, root, manifest, receipt):
        p=root/'artifacts/controller-distribution.json';p.write_text(json.dumps(receipt))
        manifest['controllerDistribution']={'path':'tools/layersentry/k8s/artifacts/controller-distribution.json',
            'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'sourceCommit':receipt['sourceCommit'],'treeSha256':receipt['treeSha256']}

    def test_valid_synthetic_distribution_and_corruption(self):
        for mutation in ('valid','missing','hash','source','target','omit','duplicate','symlink','mode'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as directory:
                root,m,d,r=self.fixture(directory)
                if mutation=='missing':m.pop('controllerDistribution')
                elif mutation=='hash':m['controllerDistribution']['sha256']='0'*64
                elif mutation=='source':(root/'controller/bff.py').write_text('# tampered')
                elif mutation=='symlink':
                    (root/'controller/bff.py').unlink();(root/'controller/bff.py').symlink_to(ROOT/'controller/bff.py')
                elif mutation not in ('valid','missing','hash'):
                    if mutation=='target':d['files'][0]['installedPath']='/etc/cron.d/evil'
                    elif mutation=='omit':d['files']=[r for r in d['files'] if r['path']!='controller/bff.py']
                    elif mutation=='duplicate':d['files'][-1]=d['files'][0]
                    elif mutation=='mode':d['files'][0]['mode']='0777'
                    d['treeSha256']=tree_sha(d['files']);self.bind(root,m,d)
                blockers=[];_controller_distribution(m,blockers,root)
                self.assertEqual(bool(blockers),mutation!='valid',blockers)

    def test_dependency_lock_and_interpreter_module_mismatch(self):
        for mutation in ('missing','hash','blocked','python','gunicorn','python-hash','gunicorn-hash'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as directory:
                root,m,d,r=self.fixture(directory);p=root/'artifacts/runtime-dependencies.json'
                if mutation=='missing':p.unlink()
                elif mutation=='hash':p.write_text('{}')
                else:
                    if mutation=='blocked':r['status']='BLOCKED'
                    if mutation=='python':r['python']['version']='3.13.0'
                    if mutation=='gunicorn':r['gunicorn']['version']='24.0.0'
                    if mutation=='python-hash':r['python']['sha256']='e'*64
                    if mutation=='gunicorn-hash':r['gunicorn']['contentSha256']='e'*64
                    p.write_text(json.dumps(r));d['runtimeDependencyLock']['sha256']=hashlib.sha256(p.read_bytes()).hexdigest();self.bind(root,m,d)
                blockers=[];_controller_distribution(m,blockers,root)
                self.assertIn('Controller runtime dependency identity is unresolved',blockers)

    def test_cp_worker_exact_supported_staging(self):
        pid=LOCK['projectId'];tid=LOCK['template']['id']
        docs=build_cluster_resources(request(project_id=pid,cni='canal',control_plane_image_id=tid),
            resolved(project_id=pid,control_plane_template_id=tid,worker_template_ids={'workers':tid}))
        cp=next(x['spec'] for x in docs if x['kind']=='RKE2ControlPlane')
        worker=next(x['spec']['template']['spec'] for x in docs if x['kind']=='RKE2ConfigTemplate')
        for spec in (cp,worker):
            self.assertIs(spec['agentConfig']['airGapped'],True)
            self.assertEqual(spec['agentConfig']['airGappedChecksum'],LOCK['rke2Artifacts']['assets'][0]['sha256'])
            self.assertNotIn('airGapped',spec)
            self.assertNotIn('airGappedChecksum',spec)
            command=spec['preRKE2Commands'][0]
            self.assertNotIn('get.rke2.io',command);self.assertNotIn('latest',command)
            for item in LOCK['rke2Artifacts']['assets']:
                self.assertIn(item['sha256'],command);self.assertIn(item['url'],command)
            policy=LOCK['rke2Artifacts']['selinuxPrerequisites']
            for item in policy['assets']:
                self.assertIn(item['sha256'],command);self.assertIn(item['url'],command)
            script=shlex.split(command)[3];subprocess.run(['sh','-n'],input=script,text=True,check=True)
            self.assertLess(script.index('dnf -y'),script.index(LOCK['rke2Artifacts']['assets'][0]['url']))
            self.assertIn('--disablerepo="*"',script)
            self.assertIn('--setopt=localpkg_gpgcheck=1',script)
            self.assertIn('rpm --checksig',script)
            self.assertIn('test "$(getenforce)" = Enforcing',script)
            self.assertNotIn('setenforce',script)
            self.assertNotIn('--nogpgcheck',script)
            for package in policy['packages']:self.assertIn(package,script)
            self.assertIn('disable-default-registry-endpoint: true',script)
            self.assertEqual(spec['privateRegistriesConfig']['mirrors']['*']['endpoint'],['https://127.0.0.1:1'])
            self.assertTrue(command.endswith(' || exit 1'))
            self.assertNotIn('systemctl start',script)
        self.assertEqual(cp['serverConfig']['cni'],'canal')
        templates=[x for x in docs if x['kind']=='CloudStackMachineTemplate']
        for t in templates:
            self.assertTrue(t['metadata']['name'].endswith('-cpu-v2'))
            self.assertEqual(t['spec']['template']['spec']['details'],{'guest.cpu.mode':'host-model'})

    def test_ordinary_project_unchanged_and_wrong_cni_rejected(self):
        docs=build_cluster_resources(request(),resolved())
        cp=next(x['spec'] for x in docs if x['kind']=='RKE2ControlPlane')
        self.assertFalse(cp['agentConfig']['airGapped']);self.assertNotIn('preRKE2Commands',cp)
        self.assertEqual(cp['serverConfig']['cni'],'cilium')
        for t in docs:
            if t['kind']=='CloudStackMachineTemplate':self.assertNotIn('details',t['spec']['template']['spec'])
        with self.assertRaisesRegex(InvalidRequestError,'CNI'):
            build_cluster_resources(request(project_id=LOCK['projectId']),resolved(project_id=LOCK['projectId'],control_plane_template_id=LOCK['template']['id'],worker_template_ids={'workers':LOCK['template']['id']}))

    def test_asset_checksum_tampering_rejected(self):
        lock=deepcopy(LOCK);lock['rke2Artifacts']['assets'][1]['sha256']='0'*64
        with self.assertRaises(InvalidRequestError):rke2_artifacts(lock)

    def test_selinux_policy_identity_is_required_and_exact(self):
        for change in ('missing','checksum','url','package','rocky-key'):
            with self.subTest(change=change):
                lock=deepcopy(LOCK);policy=lock['rke2Artifacts']['selinuxPrerequisites']
                if change=='missing':del lock['rke2Artifacts']['selinuxPrerequisites']
                elif change=='checksum':policy['assets'][1]['sha256']='0'*64
                elif change=='url':policy['assets'][1]['url']='https://example.invalid/policy.rpm'
                elif change=='package':policy['packages'][0]='container-selinux-4:9-1.el9.noarch'
                else:policy['rockyKeySha256']='0'*64
                with self.assertRaises(InvalidRequestError):qualification_bootstrap(lock)

    def test_checksum_failure_exits_without_following_bootstrap(self):
        script=shlex.split(qualification_bootstrap(LOCK)['preRKE2Commands'][0])[3]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'bin').mkdir()
            curl=root/'bin/curl';curl.write_text('#!/bin/sh\ntouch '+str(root/'curl-called')+'\nwhile [ "$1" != "--output" ]; do shift; done\nprintf tampered > "$2"\n');curl.chmod(0o700)
            script=script.replace('/opt',str(root/'opt')).replace('/etc/rancher',str(root/'etc/rancher')).replace(' -o root -g root','')
            import os
            result=subprocess.run(['sh','-c','sh -eu -c '+shlex.quote(script)+' || exit 1\ntouch '+str(root/'continued')],env={**os.environ,'PATH':str(root/'bin')+':'+os.environ['PATH']},capture_output=True)
            self.assertNotEqual(result.returncode,0);self.assertTrue((root/'curl-called').exists());self.assertFalse((root/'continued').exists())
            self.assertFalse((root/'opt/install.sh').exists())

    def test_verified_release_archive_divergence_is_not_a_blocker(self):
        self.assertNotIn('RKE2 release archive consumption proof is invalid',evaluate_component_readiness(MANIFEST).blockers)
        self.assertTrue(all(v is False for v in MANIFEST['hardGates'].values()))

    def test_candidate_rollout_is_a_plan_not_an_applied_identity_pin(self):
        path=ROOT.parents[2]/'docs/layersentry/evidence/k8s/2026-09-08-immutable-artifacts/capc-candidate-rollout.json'
        plan=json.loads(path.read_text())
        self.assertEqual(plan['classification'],'CANDIDATE_ROLLOUT_REQUIRED')
        self.assertIs(plan['applied'],False)
        self.assertTrue(plan['workloadResourcesForbidden'])
        self.assertEqual({p['path'] for p in plan['patch']},{'/spec/template/spec/containers/0/image'})

    def test_product_imports_are_stdlib_or_local(self):
        import ast, sys
        imports=set()
        for path in [*ROOT.glob('controller/*.py'), ROOT/'layersentry_k8s_policy.py', ROOT/'layersentry_k8s_controller.py']:
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Import): imports.update(n.name.split('.')[0] for n in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module: imports.add(node.module.split('.')[0])
        self.assertFalse(imports-set(sys.stdlib_module_names)-{'controller','layersentry_k8s_policy'})
        self.assertIn('/usr/bin/python3 -m gunicorn', (ROOT/'systemd/layersentry-k8s-bff.service').read_text())
