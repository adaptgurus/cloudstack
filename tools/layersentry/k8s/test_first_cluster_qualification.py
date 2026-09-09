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
from controller.qualification import FirstClusterQualification, fingerprint, DEFERRED, allocated_control_plane_compute
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

    def test_changing_allocation_cannot_authorize_capacity(self):
        q=self.build();(self.root/'host.json').write_text('{}')
        with patch('controller.capacity.plan_cluster',return_value=(None,None)), \
             patch('controller.capacity.discover_capacity',return_value={}), \
             patch('controller.qualification.allocated_control_plane_compute',side_effect=[{}, {'vm':{'cpu':8,'cpu_mhz':16000}}]), \
             patch('controller.capacity.assess_capacity') as assess:
            with self.assertRaises(InvalidRequestError):q.admit_capacity(None,{},kubernetes=object())
            assess.assert_not_called()

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

    def test_explicit_release_revision_preserves_request_and_audit(self):
        self.build();old=deepcopy(self.context)
        self.release.write_text(json.dumps(MANIFEST,indent=2))
        self.context['releaseSha256']=hashlib.sha256(self.release.read_bytes()).hexdigest()
        self.path.write_text(json.dumps(self.context))
        q=FirstClusterQualification(self.path,self.release,self.store,previous_context=old)
        q.validate_request(self.request)
        with self.store._connect() as connection:
            self.assertEqual(connection.execute('SELECT count(*) FROM qualification_revisions').fetchone()[0],1)
        old=deepcopy(self.context);self.context['idempotencyKey']='changed-idempotency-key'
        self.path.write_text(json.dumps(self.context))
        with self.assertRaises(InvalidRequestError):
            FirstClusterQualification(self.path,self.release,self.store,previous_context=old)


class AllocatedControlPlaneComputeTest(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        self.vm_id='11111111-1111-1111-1111-111111111111'
        self.resolved=SimpleNamespace(namespace='test',project_id='project',zone_id='zone',network_id='network')
        self.request={'name':'poc','control_plane_replicas':3,'control_plane_service_offering_id':'offering','control_plane_image_id':'template'}
        def metadata(name,uid,owner=None):
            return {'name':name,'uid':uid,'namespace':'test','labels':{'layersentry.io/managed':'true','layersentry.io/project':'project'},
                    'ownerReferences':[] if owner is None else [{'kind':owner[0],'name':owner[1],'uid':owner[2]}]}
        self.cluster={'metadata':metadata('poc','cluster-uid')}
        self.cp={'metadata':metadata('poc-control-plane','cp-uid',('Cluster','poc','cluster-uid')),'spec':{'replicas':3}}
        self.machine={'metadata':metadata('machine','machine-uid',('RKE2ControlPlane','poc-control-plane','cp-uid')),
                      'spec':{'clusterName':'poc','infrastructureRef':{'apiGroup':'infrastructure.cluster.x-k8s.io','kind':'CloudStackMachine','name':'capc'}}}
        self.capc={'metadata':metadata('capc','capc-uid',('Machine','machine','machine-uid')),
                   'spec':{'offering':{'id':'offering'},'template':{'id':'template'},'instanceID':self.vm_id,'providerID':'cloudstack:///'+self.vm_id}}
        self.listing={'items':[self.machine]}
        self.offering={'cpunumber':8,'cpuspeed':2000,'memory':6144}
        self.vm={'id':self.vm_id,'projectid':'project','zoneid':'zone','hostid':'host','serviceofferingid':'offering',
                 'templateid':'template','cpunumber':8,'cpuspeed':2000,'memory':6144,'state':'Running','nic':[{'networkid':'network','isdefault':True}]}
        def get(method,path):
            self.calls.append((method,path));self.assertEqual(method,'GET')
            if '/machines?' in path:return self.listing
            return {'clusters':self.cluster,'rke2controlplanes':self.cp,'cloudstackmachines':self.capc}[path.split('/')[-2]]
        def exact(command,collection,id,**kwargs):
            self.calls.append((command,id));self.assertIn(command,('listServiceOfferings','listVirtualMachines'))
            if command=='listVirtualMachines':
                self.assertEqual(kwargs,{'projectid':'project'});self.assertEqual(id,self.vm_id)
                return self.vm
            return self.offering
        self.kubernetes=SimpleNamespace(request=get)
        self.resolver=SimpleNamespace(_exact=exact)

    def observe(self):
        return allocated_control_plane_compute(self.kubernetes,self.resolver,self.resolved,self.request,'host')

    def test_exact_running_capc_identity_is_read_only_and_counted_once(self):
        self.assertEqual(self.observe(),{self.vm_id:{'cpu':8,'cpu_mhz':16000}})
        self.assertEqual(self.observe(),self.observe())  # Restart is fresh observation, not durable credit.
        self.assertTrue(all(c[0] in ('GET','listServiceOfferings','listVirtualMachines') for c in self.calls))

    def test_absent_capc_allocation_and_nonrunning_vm_get_no_credit(self):
        self.capc['spec'].pop('instanceID');self.assertEqual(self.observe(),{})
        self.capc['spec']['instanceID']=self.vm_id
        for state in ('Starting','Stopped','Error','Destroyed'):
            self.vm['state']=state;self.assertEqual(self.observe(),{})

    def test_foreign_native_scope_and_changed_profile_are_rejected(self):
        original=deepcopy(self.vm)
        for field in ('projectid','zoneid','hostid','serviceofferingid','templateid','cpunumber','cpuspeed','memory','nic'):
            with self.subTest(field=field):
                self.vm=deepcopy(original);self.vm[field]=[] if field=='nic' else 'foreign'
                with self.assertRaises(InvalidRequestError):self.observe()

    def test_owner_uid_tampering_and_deleting_objects_are_rejected(self):
        for resource in (self.cp,self.machine,self.capc):
            with self.subTest(resource=resource['metadata']['name']):
                ref=resource['metadata']['ownerReferences'][0];old=ref['uid'];ref['uid']='foreign'
                with self.assertRaises(InvalidRequestError):self.observe()
                ref['uid']=old;resource['metadata']['deletionTimestamp']='2026-09-09T00:00:00Z'
                with self.assertRaises(InvalidRequestError):self.observe()
                resource['metadata'].pop('deletionTimestamp')

    def test_duplicate_truncated_and_oversized_inventory_rejected(self):
        for listing in ({'items':[self.machine,self.machine]}, {'items':[],'metadata':{'continue':'next'}}, {'items':[self.machine]*4}):
            self.listing=listing
            with self.assertRaises(InvalidRequestError):self.observe()

    def test_wrong_provider_id_or_capc_profile_rejected(self):
        original=deepcopy(self.capc)
        for field,value in [('providerID','cloudstack:///foreign'),('offering',{'id':'foreign'}),('template',{'id':'foreign'})]:
            self.capc=deepcopy(original);self.capc['spec'][field]=value
            with self.assertRaises(InvalidRequestError):self.observe()
