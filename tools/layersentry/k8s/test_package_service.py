"""Exercise authenticated package intent, restart fencing and cluster locks."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.parse import urlencode

from controller.auth import CloudStackCapabilityAuthorizer
from controller.bff import BFFApplication
from controller.model import Actor, AuthorizationError, ConflictError, OperationStatus, InvalidRequestError
from controller.package_catalog import PackageCatalog, FLUX_TUPLE
from controller.package_executor import PackageExecutor
from controller.package_resources import build_package_resources
from controller.service import ControllerService
from controller.store import SagaStore
from test_package_reconcile import Native, REQUEST, GATES, profile, ready

ACTOR = Actor('session-a', '', '', ('project-a',), capabilities=(
    'listProjects', 'listVirtualMachines', 'deployVirtualMachine', 'createVolume', 'destroyVirtualMachine'))


class PackageServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.entry = profile()
        value = {'schemaVersion': '1.0', 'fluxVersions': FLUX_TUPLE,
                 'platformRegistry': {'host': 'registry.example.test', 'bootstrapIndependent': True, 'evidenceSha256': 'c'*64},
                 'packages': [self.entry]}
        path = self.root/'catalog.json'
        path.write_text(json.dumps(value))
        self.catalog = PackageCatalog(path, hashlib.sha256(path.read_bytes()).hexdigest())
        self.native = Native()
        self.authorizer = CloudStackCapabilityAuthorizer()
        self.packages = PackageExecutor(self.native, self.authorizer, self.catalog, GATES)
        self.store = SagaStore(self.root/'state.sqlite')
        self.service = self.restarted_service()
        auth = Mock()
        auth.authenticate.return_value = ACTOR
        self.app = BFFApplication(self.service, auth)

    def restarted_service(self):
        return ControllerService(SagaStore(self.root/'state.sqlite'), self.authorizer, Mock(), GATES,
                                 package_executor=self.packages)

    def submit(self, key='package-install-0001', deleting=False):
        return self.service.submit_package(ACTOR, REQUEST, key, deleting=deleting)[0]

    def request(self, method, path, payload=None, query=None):
        body = json.dumps(payload).encode() if payload is not None else b''
        environ = {'REQUEST_METHOD': method, 'PATH_INFO': path, 'QUERY_STRING': urlencode(query or {}),
                   'CONTENT_TYPE': 'application/json', 'CONTENT_LENGTH': str(len(body)),
                   'wsgi.input': io.BytesIO(body), 'HTTP_IDEMPOTENCY_KEY': 'package-api-request-0001'}
        statuses = []
        result = self.app(environ, lambda status, headers: statuses.append(status))
        return int(statuses[0].split()[0]), json.loads(b''.join(result))

    def test_acceptance_is_read_only_and_restart_observes_ambiguous_native_create(self):
        operation = self.submit()
        self.assertEqual(self.native.writes, [])
        self.assertEqual(operation.request['binding'], {'catalogSha256': self.catalog.digest, 'clusterUid': 'cluster-uid'})
        self.native.ambiguous = True
        self.assertEqual(self.service.advance(operation.id).status, OperationStatus.UNKNOWN)
        restarted = self.restarted_service()
        self.assertEqual(restarted.reconcile_unknown(operation.id).status, OperationStatus.RUNNING)
        self.assertEqual(len(self.native.writes), 1)
        for row in self.native.rows.values():
            if row['kind'] == 'OCIRepository': ready(row, self.entry['chartDigest'])
        restarted.advance(operation.id)
        for row in self.native.rows.values():
            if row['kind'] == 'HelmRelease': ready(row, self.entry['chartDigest'])
        self.assertEqual(restarted.advance(operation.id).status, OperationStatus.READY)
        self.assertEqual(len(self.native.writes), 2)

    def test_cluster_replacement_before_first_mutation_cannot_rebind_intent(self):
        operation = self.submit()
        self.native.rows[('Cluster','tenant-a','cluster-a')]['metadata']['uid'] = 'replacement'
        self.native.rows[('RKE2ControlPlane','tenant-a','cluster-a-control-plane')]['metadata']['ownerReferences'][0]['uid'] = 'replacement'
        result = self.service.advance(operation.id)
        self.assertEqual(result.status, OperationStatus.FAILED)
        self.assertEqual(self.native.writes, [])

    def test_catalog_change_cannot_rebind_accepted_intent_or_duplicate_it(self):
        operation = self.submit()
        self.catalog.digest = 'f'*64
        duplicate, created = self.service.submit_package(ACTOR, REQUEST, 'package-install-0001')
        self.assertFalse(created)
        self.assertEqual(operation.id, duplicate.id)
        self.assertEqual(self.service.advance(operation.id).status, OperationStatus.FAILED)
        self.assertEqual(self.native.writes, [])

    def test_cluster_lock_survives_unknown_and_rejects_scale_delete_and_package_races(self):
        operation = self.submit()
        self.native.ambiguous = True
        self.service.advance(operation.id)
        restarted = self.restarted_service()
        for kind in ('kubernetes.cluster.scale','kubernetes.cluster.delete','kubernetes.package.install'):
            with self.assertRaises(ConflictError):
                restarted.store.create_or_get(idempotency_key=kind, request_sha256='a'*64,
                    kind=kind, target_name='cluster-a', project_id='project-a', actor_subject=ACTOR.subject,
                    request={}, plan=[])
        self.assertEqual(len(self.native.writes), 1)

    def test_concurrent_acceptance_uses_transactional_cluster_reservation(self):
        def submit(index):
            try:
                service = self.restarted_service()
                service.submit_package(ACTOR, REQUEST, 'package-concurrent-'+str(index))
                return 'accepted'
            except ConflictError:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as workers:
            self.assertCountEqual(list(workers.map(submit, [1,2])), ['accepted','conflict'])
        self.assertEqual(self.native.writes, [])

    def test_project_and_capability_checks_precede_native_reads_and_duplicate_lookup(self):
        operation = self.submit()
        for actor in (Actor('session-a','','',('project-b',),capabilities=ACTOR.capabilities),
                      Actor('session-a','','',('project-a',),capabilities=('listProjects',))):
            with self.assertRaises(AuthorizationError):
                self.service.submit_package(actor, REQUEST, 'package-install-0001')
        self.assertEqual(self.store.get(operation.id).status, OperationStatus.REQUESTED)
        self.assertEqual(self.native.writes, [])

    def test_delete_waits_for_native_finalization_and_reports_deleted_only_after_absence(self):
        operation = self.submit(deleting=True)
        # Delete of an already absent exact stateless release is idempotent.
        self.assertEqual(self.service.advance(operation.id).status, OperationStatus.DELETED)
        self.assertEqual(self.native.writes, [])

    def test_bff_catalog_install_status_and_invalid_target(self):
        status, body = self.request('GET','/v1/kubernetes/packages',query={'projectId':'project-a'})
        self.assertEqual(status, 200)
        self.assertEqual(len(body['packages']), 1)
        path = '/v1/kubernetes/clusters/cluster-a/packages'
        self.assertEqual(self.request('POST',path,{**REQUEST,'clusterName':'cluster-b'})[0],400)
        self.assertEqual(self.request('POST',path,{**REQUEST,'kubeconfig':'sensitive'})[0],400)
        status, body = self.request('POST',path,REQUEST)
        self.assertEqual(status,202)
        self.assertEqual(body['operation']['status'],'REQUESTED')
        self.assertNotIn('request',body['operation'])
        query = {key:value for key,value in REQUEST.items() if key!='clusterName'}
        status, body = self.request('GET',path,query=query)
        self.assertEqual((status,body['status']),(200,'PENDING'))
        self.assertEqual(self.native.writes, [])
        self.assertEqual(self.request('GET','/v1/kubernetes/packages',query={'projectId':'project-b'})[0],403)

    def catalog_with(self, entries):
        path = self.root/('catalog-'+str(len(entries))+'-'+str(id(entries))+'.json')
        path.write_text(json.dumps({'schemaVersion':'1.0','fluxVersions':FLUX_TUPLE,
            'platformRegistry':{'host':'registry.example.test','bootstrapIndependent':True,'evidenceSha256':'c'*64},
            'packages':entries}))
        return PackageCatalog(path, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_missing_dependency_rejects_before_reserving_cluster_and_can_be_installed(self):
        dependency = {**profile(),'package':'dependency'}
        dependent = deepcopy(self.entry)
        dependent['dependsOn'] = [{key:dependency[key] for key in ('package','version','profile')}]
        catalog = self.catalog_with([dependent,dependency])
        self.packages = PackageExecutor(self.native,self.authorizer,catalog,GATES)
        self.service = self.restarted_service()
        with self.assertRaisesRegex(InvalidRequestError,'install and qualify dependency dependency'):
            self.submit()
        self.assertEqual(self.store.actionable_ids(), [])
        operation, created = self.service.submit_package(ACTOR,{**REQUEST,'package':'dependency'},'dependency-install-01')
        self.assertTrue(created)
        self.assertEqual(operation.status,OperationStatus.REQUESTED)

    def test_approved_history_preserves_retired_profile_lifecycle_and_blocks_new_historical_installs(self):
        source, release = build_package_resources(REQUEST,self.entry,self.catalog.digest,'cluster-uid')
        for row in (source, release):
            actual=self.native.create(row)
            ready(self.native.rows[self.native.key(actual)],self.entry['chartDigest'])
        replacement=self.catalog_with([{**profile(),'package':'unrelated'}])
        self.packages=PackageExecutor(self.native,self.authorizer,replacement,GATES,previous_catalogs=(self.catalog,))
        self.service=self.restarted_service()
        selected={**REQUEST,'catalogSha256':self.catalog.digest}
        self.assertEqual(self.service.package_status(ACTOR,selected)['status'],'CONVERGED')
        with self.assertRaisesRegex(InvalidRequestError,'new installs require'):
            self.service.submit_package(ACTOR,selected,'retired-install-0001')
        deletion,_=self.service.submit_package(ACTOR,selected,'retired-uninstall-01',deleting=True)
        self.assertEqual(self.service.advance(deletion.id).status,OperationStatus.RUNNING)
        self.assertEqual(self.native.writes[-1],('delete',self.native.key(release)))
        self.native.rows.pop(self.native.key(release))
        self.assertEqual(self.service.advance(deletion.id).status,OperationStatus.RUNNING)
        self.native.rows.pop(self.native.key(source))
        self.assertEqual(self.service.advance(deletion.id).status,OperationStatus.DELETED)

    def test_unrelated_catalog_additions_keep_profile_identity_but_profile_edits_do_not(self):
        source, release=build_package_resources(REQUEST,self.entry,self.catalog.digest,'cluster-uid')
        for ref in (source,release):
            self.native.create(ref)
            ready(self.native.rows[self.native.key(ref)],self.entry['chartDigest'])
        extended=self.catalog_with([self.entry,{**profile(),'package':'unrelated'}])
        current=PackageExecutor(self.native,self.authorizer,extended,GATES)
        self.assertEqual(current.reconcile(ACTOR,REQUEST,inspect_only=True).outcome.value,'CONVERGED')
        changed=deepcopy(self.entry);changed['values']['replicaCount']=3
        changed_catalog=self.catalog_with([changed])
        current=PackageExecutor(self.native,self.authorizer,changed_catalog,GATES)
        with self.assertRaisesRegex(InvalidRequestError,'immutable request binding'):
            current.reconcile(ACTOR,REQUEST,inspect_only=True)
        self.assertEqual(len(self.native.writes),2)

    def test_dependent_uninstall_check_precedes_reservation_across_approved_history(self):
        dependent={**profile(),'package':'dependent','dependsOn':[{key:self.entry[key] for key in ('package','version','profile')}]}
        extended=self.catalog_with([self.entry,dependent])
        refs=build_package_resources({**REQUEST,'package':'dependent'},dependent,extended.digest,'cluster-uid')
        self.native.create(refs[0])
        self.packages=PackageExecutor(self.native,self.authorizer,extended,GATES,previous_catalogs=(self.catalog,))
        self.service=self.restarted_service()
        with self.assertRaisesRegex(InvalidRequestError,'uninstall dependent package'):
            self.service.submit_package(ACTOR,{**REQUEST,'catalogSha256':self.catalog.digest},'dependency-delete-01',deleting=True)
        self.assertEqual(self.store.actionable_ids(),[])

    def test_authenticated_unknown_observation_route_recovers_without_duplicate_create(self):
        operation=self.submit()
        self.native.ambiguous=True
        self.service.advance(operation.id)
        status,body=self.request('POST','/v1/kubernetes/operations/'+operation.id+'/reconcile',{})
        self.assertEqual((status,body['operation']['status']),(200,'RUNNING'))
        self.assertEqual(len(self.native.writes),1)
        self.assertEqual(self.request('POST','/v1/kubernetes/operations/'+operation.id+'/reconcile',{})[0],400)
