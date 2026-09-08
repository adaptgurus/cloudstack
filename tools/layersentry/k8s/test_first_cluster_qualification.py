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

"""Bounded first-cluster admission, restart and production separation."""
import json
import hashlib
import tempfile
import unittest
from copy import deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from controller.qualification import FirstClusterQualification, fingerprint, DEFERRED
from controller.store import SagaStore
from controller.model import InvalidRequestError, ConflictError
from controller.components import load_release_contract
from layersentry_k8s_policy import ReleaseGates, ReleaseChannel, NodePoolRequest, plan_cluster_create, ValidationError
from test_e1_resources import request

ROOT=Path(__file__).parent
MANIFEST=json.loads((ROOT/'release-candidate-lane-b.json').read_text())
LOCK=json.loads((ROOT/'artifacts/qualification-lock.json').read_text())

class QualificationTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=SagaStore(self.root/'journal.sqlite')
        image=LOCK['template']['id']
        self.request=request(project_id=LOCK['projectId'],control_plane_image_id=image,
            node_pools=(NodePoolRequest('workers',1,'worker-offering-id',image),),
            channel=ReleaseChannel.PREVIEW,cni='canal',air_gapped=True)
        value=asdict(self.request);value['channel']=self.request.channel.value
        self.release=self.root/'release.json';self.release.write_text(json.dumps(MANIFEST))
        self.context={'schemaVersion':'1.0','mode':'first-cluster-qualification',
            'expiresAt':(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),
            'releaseSha256':hashlib.sha256(self.release.read_bytes()).hexdigest(),
            'requestSha256':fingerprint(value),'idempotencyKey':'qualification-first-cluster-001',
            'hostEvidence':str(self.root/'host.json'),'clusterId':'cluster','hostId':'host','poolId':'pool'}
        self.path=self.root/'qualification.json'
        self.contract=SimpleNamespace(manifest=MANIFEST,readiness=SimpleNamespace(blockers=tuple(DEFERRED)))
        self.mock=patch('controller.qualification.load_release_contract',return_value=self.contract)
        self.mock.start();self.addCleanup(self.mock.stop)

    def build(self):
        self.path.write_text(json.dumps(self.context))
        return FirstClusterQualification(self.path,self.release,self.store)

    def test_exact_preview_3_plus_1_is_allowed_without_promoting_gates(self):
        gates=ReleaseGates();q=self.build()
        plan=plan_cluster_create(self.request,gates,(),qualification=q)
        self.assertTrue(plan.executable)
        self.assertFalse(gates.kubernetes_ready())
        self.assertFalse(plan_cluster_create(self.request,gates,()).executable)

    def test_foreign_project_template_topology_and_storage_fail_closed(self):
        q=self.build()
        for changes in ({'project_id':'foreign'},{'control_plane_image_id':'foreign'},
                        {'control_plane_replicas':1},{'control_plane_replicas':2},
                        {'cni':'cilium'},{'air_gapped':False},{'channel':ReleaseChannel.CERTIFIED},
                        {'node_pools':(replace(self.request.node_pools[0],direct_node_disks=1),)},
                        {'name':'another-cluster'}):
            with self.subTest(changes=changes), self.assertRaises((InvalidRequestError,ValidationError)):
                q.validate_request(replace(self.request,**changes))

    def test_expired_or_unbounded_context_rejected(self):
        for delta in (-1,8*86400):
            self.context['expiresAt']=(datetime.now(timezone.utc)+timedelta(seconds=delta)).isoformat()
            with self.assertRaises(InvalidRequestError):self.build()

    def test_immutable_blocker_cannot_be_deferred(self):
        self.contract.readiness.blockers=(*DEFERRED,'Controller runtime dependency identity is unresolved')
        with self.assertRaises(InvalidRequestError):self.build()

    def test_context_or_release_tampering_rejected(self):
        q=self.build();self.path.write_text('{}')
        with self.assertRaises(InvalidRequestError):q.check()
        self.path.write_text(json.dumps(self.context));self.release.write_text('{}')
        with self.assertRaises(InvalidRequestError):q.check()

    def test_restart_reuses_binding_and_retirement_is_durable(self):
        q=self.build();again=self.build();again.validate_request(self.request)
        self.store.retire_qualification()
        with self.assertRaises(ConflictError):self.build()
        with self.assertRaises(ConflictError):q.validate_request(self.request)

    def test_second_context_cannot_reuse_journal(self):
        self.build();self.context['idempotencyKey']='different-qualification-002'
        with self.assertRaises(ConflictError):self.build()

    def test_missing_context_and_malformed_hash_rejected(self):
        with self.assertRaises(InvalidRequestError):FirstClusterQualification(self.path,self.release,self.store)
        self.context['requestSha256']='bad'
        with self.assertRaises(InvalidRequestError):self.build()

    def test_capacity_failure_prevents_qualification_admission(self):
        q=self.build();(self.root/'host.json').write_text('{}')
        with patch('controller.capacity.plan_cluster',return_value=(None,None)), \
             patch('controller.capacity.discover_capacity',return_value={}), \
             patch('controller.capacity.assess_capacity',return_value={'decision':'PROVISION_BLOCKED_CAPACITY'}):
            with self.assertRaises(InvalidRequestError):q.admit_capacity(None,{})

    def test_no_live_gate_in_checked_in_release_is_promoted(self):
        self.assertFalse(any(MANIFEST['hardGates'].values()))

    def test_operator_uses_native_capabilities_and_active_project(self):
        from controller.model import AuthenticationError
        q=self.build();key=self.root/'key';key.write_text('synthetic-key')
        class Client:
            config=SimpleNamespace(api_key_file=key)
            def call(inner, command, params):
                if command=='listApis':return {'api':[{'name':'listProjects'}]}
                return {'project':[{'id':LOCK['projectId'],'state':'Active'}]}
        actor=q.operator_actor(Client())
        self.assertEqual(actor.capabilities,('listProjects',))
        self.assertNotIn('deployVirtualMachine',actor.capabilities)
        with patch.object(Client,'call',return_value={'project':[]}):
            with self.assertRaises(AuthenticationError):q.operator_actor(Client())
