"""Native package ownership/revision/ambiguity qualification; no live cluster."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import urllib.error

from controller.flux_resources import FluxBaseline,build_flux_baseline,baseline_ready,git_source_ready
from controller.kubernetes import KubernetesClient
from controller.model import Actor,AuthorizationError,InvalidRequestError,NotFoundError,AmbiguousMutationError,ConflictError
from controller.package_catalog import PackageCatalog,FLUX_TUPLE
from controller.package_executor import PackageExecutor
from controller.package_resources import build_package_resources
from controller.service import StepOutcome
from layersentry_k8s_policy import ReleaseGates

REQUEST={'clusterName':'cluster-a','namespace':'tenant-a','projectId':'project-a','package':'example-operator','version':'1.2.3','profile':'qualified-test'}
ACTOR=Actor('test','account','domain',('project-a',))
GATES=ReleaseGates(tuple_reconciliation=True,endpoint_6443=True,endpoint_9345=True,flux_remote_reconcile=True)


def profile():
    return {'package':'example-operator','version':'1.2.3','profile':'qualified-test','chartUrl':'oci://registry.example.test/charts/example',
            'chartDigest':'sha256:'+'a'*64,'targetNamespace':'example-system','values':{'replicaCount':2},
            'stateful':False,'qualified':True,'uninstallQualified':True,'evidenceSha256':'b'*64,'requiredHostCapabilities':[],'dependsOn':[]}


def ready(row,revision=None):
    row['status']={'observedGeneration':row['metadata']['generation'],'conditions':[{'type':'Ready','status':'True','observedGeneration':row['metadata']['generation']}]}
    if row['kind'] in ('GitRepository','OCIRepository'):row['status']['artifact']={'revision':revision}
    elif row['kind']=='Kustomization':row['status']['lastAppliedRevision']=revision
    elif row['kind']=='HelmRelease':row['status']['lastAttemptedRevisionDigest']=revision
    return row


class Native:
    def __init__(self):
        self.rows={};self.writes=[];self.ambiguous=False
        cluster={'apiVersion':'cluster.x-k8s.io/v1beta2','kind':'Cluster','metadata':{'name':'cluster-a','namespace':'tenant-a','uid':'cluster-uid','resourceVersion':'1','generation':1,'labels':{'layersentry.io/managed':'true','layersentry.io/project':'project-a'}}}
        self.rows[self.key(cluster)]=ready(cluster)
        cluster['spec']={'controlPlaneRef':{'apiGroup':'controlplane.cluster.x-k8s.io','kind':'RKE2ControlPlane','name':'cluster-a-control-plane'}}
        plane={'apiVersion':'controlplane.cluster.x-k8s.io/v1beta2','kind':'RKE2ControlPlane','metadata':{'name':'cluster-a-control-plane','namespace':'tenant-a','uid':'plane-uid','labels':deepcopy(cluster['metadata']['labels']),
               'ownerReferences':[{'apiVersion':'cluster.x-k8s.io/v1beta2','kind':'Cluster','name':'cluster-a','uid':'cluster-uid'}]}}
        self.rows[self.key(plane)]=plane
        self.secret={'apiVersion':'meta.k8s.io/v1','kind':'PartialObjectMetadata','metadata':{'name':'cluster-a-kubeconfig','namespace':'tenant-a','ownerReferences':[
            {'apiVersion':'controlplane.cluster.x-k8s.io/v1beta2','kind':'RKE2ControlPlane','name':'cluster-a-control-plane','uid':'plane-uid','controller':True}]}}

    def get_capi_kubeconfig_metadata(self,namespace,name):return deepcopy(self.secret)

    @staticmethod
    def key(row):return row['kind'],row['metadata']['namespace'],row['metadata']['name']

    def get(self,ref):
        if self.key(ref) not in self.rows:raise NotFoundError('absent')
        return deepcopy(self.rows[self.key(ref)])

    def create(self,row):
        key=self.key(row)
        if key in self.rows:raise ConflictError('already exists')
        self.writes.append(('create',key));actual=deepcopy(row)
        actual['metadata'].update(uid='uid-'+row['metadata']['name'],resourceVersion='1',generation=1)
        self.rows[key]=actual
        if self.ambiguous:self.ambiguous=False;raise AmbiguousMutationError('timed out after create')
        return deepcopy(actual)

    def delete_observed(self,row):
        self.writes.append(('delete',self.key(row)));self.rows[self.key(row)]['metadata']['deletionTimestamp']='2026-09-06T00:00:00Z'


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.entry=profile();self.native=Native();self.authorizer=Mock()
        self.catalog=self.load([self.entry]);self.executor=PackageExecutor(self.native,self.authorizer,self.catalog,GATES)

    def load(self,entries):
        value={'schemaVersion':'1.0','fluxVersions':FLUX_TUPLE,'platformRegistry':{'host':'registry.example.test','bootstrapIndependent':True,'evidenceSha256':'c'*64},'packages':entries}
        path=Path(self.directory.name)/'catalog.json';path.write_text(json.dumps(value));path.chmod(0o644)
        return PackageCatalog(path,hashlib.sha256(path.read_bytes()).hexdigest())

    def refs(self,request=REQUEST,entry=None):return build_package_resources(request,entry or self.entry,self.catalog.digest,'cluster-uid')

    def install(self):
        source,release=self.refs()
        self.executor.reconcile(ACTOR,REQUEST)
        ready(self.native.rows[self.native.key(source)],self.entry['chartDigest'])
        self.executor.reconcile(ACTOR,REQUEST)
        ready(self.native.rows[self.native.key(release)],self.entry['chartDigest'])
        return source,release

    def test_remote_only_target_and_exact_oci_chart_binding(self):
        source,release=self.refs()
        self.assertEqual(source['metadata']['namespace'],'tenant-a')
        self.assertEqual(release['metadata']['namespace'],'tenant-a')
        self.assertEqual(release['spec']['kubeConfig'],{'secretRef':{'name':'cluster-a-kubeconfig','key':'value'}})
        self.assertEqual(source['spec']['ref'],{'digest':self.entry['chartDigest']})
        self.assertEqual(source['spec']['layerSelector']['operation'],'copy')
        self.assertNotIn('namespace',release['spec']['chartRef'])

    def test_acceptance_is_pending_until_generation_and_digest_ready(self):
        source,release=self.install()
        self.assertEqual(self.executor.reconcile(ACTOR,REQUEST).outcome,StepOutcome.CONVERGED)
        row=self.native.rows[self.native.key(release)];row['status']['observedGeneration']=0
        self.assertEqual(self.executor.reconcile(ACTOR,REQUEST).outcome,StepOutcome.PENDING)
        ready(row,'sha256:'+'f'*64)
        self.assertEqual(self.executor.reconcile(ACTOR,REQUEST).outcome,StepOutcome.PENDING)
        self.assertEqual(len(self.native.writes),2)

    def test_restart_after_ambiguous_create_observes_without_duplicate_submission(self):
        self.native.ambiguous=True
        with self.assertRaises(AmbiguousMutationError):self.executor.reconcile(ACTOR,REQUEST)
        restarted=PackageExecutor(self.native,self.authorizer,self.catalog,GATES)
        self.assertEqual(restarted.observe_ambiguous(ACTOR,REQUEST).outcome,StepOutcome.PENDING)
        self.assertEqual(len(self.native.writes),1)

    def test_read_is_nonmutating_and_authorization_happens_first(self):
        self.assertEqual(self.executor.reconcile(ACTOR,REQUEST,inspect_only=True).outcome,StepOutcome.PENDING)
        self.assertEqual(self.native.writes,[])
        self.authorizer.require.assert_called_with(ACTOR,'kubernetes.package.read','project-a')
        self.authorizer.require.side_effect=AuthorizationError('denied')
        with self.assertRaises(AuthorizationError):self.executor.reconcile(ACTOR,REQUEST)
        self.assertEqual(self.native.writes,[])

    def test_added_execution_overrides_are_not_reported_as_approved_readiness(self):
        source,release=self.install()
        release_key=self.native.key(release)
        approved=deepcopy(self.native.rows[release_key])
        for field,value in [('valuesFrom',[{'kind':'ConfigMap','name':'unapproved'}]),
                            ('postRenderers',[{'kustomize':{'patches':[]}}]),
                            ('serviceAccountName','privileged-account')]:
            self.native.rows[release_key]=deepcopy(approved)
            self.native.rows[release_key]['spec'][field]=value
            with self.assertRaisesRegex(InvalidRequestError,'desired state drifted'):
                self.executor.reconcile(ACTOR,REQUEST,inspect_only=True)
        self.native.rows[release_key]=deepcopy(approved)
        self.native.rows[release_key]['spec']['values']['unapprovedPrivilegedWorkload']=True
        with self.assertRaisesRegex(InvalidRequestError,'desired state drifted'):
            self.executor.reconcile(ACTOR,REQUEST,inspect_only=True)
        self.native.rows[release_key]=approved
        source_row=self.native.rows[self.native.key(source)]
        source_row['spec']['provider']='generic'
        self.assertEqual(self.executor.reconcile(ACTOR,REQUEST,inspect_only=True).outcome,StepOutcome.CONVERGED)
        source_row['spec']['insecure']=True
        with self.assertRaisesRegex(InvalidRequestError,'desired state drifted'):
            self.executor.reconcile(ACTOR,REQUEST,inspect_only=True)
        self.assertEqual(len(self.native.writes),2)

    def test_cross_project_cluster_and_raw_secret_request_are_rejected(self):
        cluster=self.native.rows[('Cluster','tenant-a','cluster-a')];cluster['metadata']['labels']['layersentry.io/project']='project-b'
        with self.assertRaises(InvalidRequestError):self.executor.reconcile(ACTOR,REQUEST)
        with self.assertRaises(InvalidRequestError):self.executor.reconcile(ACTOR,{**REQUEST,'kubeconfig':'private'})
        with self.assertRaises(InvalidRequestError):self.executor.reconcile(ACTOR,{**REQUEST,'version':{'unsafe':'input'}})
        self.assertEqual(self.native.writes,[])

    def test_replaced_cluster_uid_and_foreign_objects_block(self):
        source,_=self.install()
        self.native.rows[('Cluster','tenant-a','cluster-a')]['metadata']['uid']='replacement-uid'
        with self.assertRaises(InvalidRequestError):self.executor.reconcile(ACTOR,REQUEST)
        self.native.rows[('Cluster','tenant-a','cluster-a')]['metadata']['uid']='cluster-uid'
        self.native.rows[self.native.key(source)]['metadata']['labels']['layersentry.io/project']='foreign'
        with self.assertRaises(InvalidRequestError):self.executor.reconcile(ACTOR,REQUEST)

    def test_kubeconfig_and_chart_drift_are_not_repaired_silently(self):
        _,release=self.install();row=self.native.rows[self.native.key(release)]
        row['spec']['kubeConfig']['secretRef']['name']='another-kubeconfig'
        with self.assertRaises(InvalidRequestError):self.executor.reconcile(ACTOR,REQUEST)
        self.assertEqual(len(self.native.writes),2)

    def test_orphan_or_wrong_control_plane_credential_is_rejected_without_reading_bytes(self):
        self.native.secret['metadata']['ownerReferences'][0]['uid']='another-plane'
        with self.assertRaises(InvalidRequestError):self.executor.reconcile(ACTOR,REQUEST)
        self.assertEqual(self.native.writes,[])

    def test_stateful_unqualified_and_host_rollout_gates_fail_before_writes(self):
        for change in ({'stateful':True},{'qualified':False},{'requiredHostCapabilities':['nvme-tcp']}):
            entry={**profile(),**change};executor=PackageExecutor(self.native,self.authorizer,self.load([entry]),GATES)
            with self.subTest(change=change),self.assertRaises(InvalidRequestError):executor.reconcile(ACTOR,REQUEST)
        self.assertEqual(self.native.writes,[])
        with self.assertRaises(InvalidRequestError):PackageExecutor(self.native,self.authorizer,self.catalog,ReleaseGates()).reconcile(ACTOR,REQUEST)

    def test_unqualified_uninstall_is_blocked(self):
        entry={**profile(),'uninstallQualified':False}
        with self.assertRaises(InvalidRequestError):PackageExecutor(self.native,self.authorizer,self.load([entry]),GATES).delete(ACTOR,REQUEST)
        self.assertEqual(self.native.writes,[])

    def test_dependency_generation_digest_and_order_are_required(self):
        dependency={**profile(),'package':'first-operator'}
        entry={**profile(),'dependsOn':[{key:dependency[key] for key in ('package','version','profile')}]}
        self.catalog=self.load([entry,dependency]);self.executor=PackageExecutor(self.native,self.authorizer,self.catalog,GATES)
        self.assertEqual(self.executor.reconcile(ACTOR,REQUEST).outcome,StepOutcome.PENDING)
        self.assertEqual(self.native.writes,[])
        dep_request={**REQUEST,'package':'first-operator'}
        for ref in self.refs(dep_request,dependency):
            self.native.create(ref);ready(self.native.rows[self.native.key(ref)],dependency['chartDigest'])
        self.executor.reconcile(ACTOR,REQUEST)
        self.assertEqual(len(self.native.writes),3)
        with self.assertRaises(InvalidRequestError):self.executor.delete(ACTOR,dep_request)

    def test_native_delete_waits_for_helm_finalization_then_source_absence(self):
        source,release=self.install()
        self.assertEqual(self.executor.delete(ACTOR,REQUEST).outcome,StepOutcome.PENDING)
        self.executor.delete(ACTOR,REQUEST)
        self.assertEqual(self.native.writes[-1],('delete',self.native.key(release)))
        self.assertEqual(len(self.native.writes),3)
        del self.native.rows[self.native.key(release)]
        self.executor.delete(ACTOR,REQUEST)
        self.assertEqual(self.native.writes[-1],('delete',self.native.key(source)))
        del self.native.rows[self.native.key(source)]
        self.assertEqual(self.executor.delete(ACTOR,REQUEST).outcome,StepOutcome.CONVERGED)

    def test_catalog_rejects_dependency_cycles_wrong_registry_and_secret_values(self):
        for entry in ({**profile(),'chartUrl':'oci://tenant-harbor.example.test/chart'},{**profile(),'values':{'password':'must-not-enter-catalog'}},
                      {**profile(),'dependsOn':[{'package':'example-operator','version':'1.2.3','profile':'qualified-test'}]}):
            with self.subTest(entry=entry),self.assertRaises(InvalidRequestError):self.load([entry])


class BaselineTests(unittest.TestCase):
    def test_baseline_is_colocated_with_capi_secret_and_requires_current_revision(self):
        config=FluxBaseline('https://git.example.test/catalog.git','a'*40,'./baseline')
        source,baseline=build_flux_baseline('cluster-a','tenant-a','project-a',config)
        self.assertEqual(source['metadata']['namespace'],'tenant-a')
        self.assertEqual(baseline['metadata']['namespace'],'tenant-a')
        self.assertEqual(baseline['spec']['kubeConfig']['secretRef']['name'],'cluster-a-kubeconfig')
        for ref,check in ((source,git_source_ready),(baseline,baseline_ready)):
            row=deepcopy(ref);row['metadata']['generation']=2;ready(row,'sha1:'+'a'*40)
            self.assertTrue(check(ref,row,config.commit))
            row['status']['observedGeneration']=1;self.assertFalse(check(ref,row,config.commit))
            ready(row,'sha1:'+'b'*40);self.assertFalse(check(ref,row,config.commit))
        row=deepcopy(baseline);row['metadata']['generation']=1;ready(row,'sha1:'+'a'*40)
        del row['spec']['kubeConfig'];self.assertFalse(baseline_ready(baseline,row,config.commit))


class NativeWireTests(unittest.TestCase):
    def test_secret_observation_requires_partial_metadata_with_no_full_secret_fallback(self):
        client=object.__new__(KubernetesClient);client.request=Mock(return_value={'kind':'Secret','apiVersion':'v1','data':{'value':'must-not-be-used'}})
        with self.assertRaises(InvalidRequestError):client.get_capi_kubeconfig_metadata('tenant-a','cluster-a')
        self.assertEqual(client.request.call_args.kwargs['accept'],'application/json;as=PartialObjectMetadata;g=meta.k8s.io;v=v1')

    def test_create_only_and_fenced_delete_use_exact_flux_routes(self):
        client=object.__new__(KubernetesClient);client.request=Mock(return_value={})
        resource={'apiVersion':'helm.toolkit.fluxcd.io/v2','kind':'HelmRelease','metadata':{'name':'example','namespace':'tenant-a','uid':'observed','resourceVersion':'3'}}
        client.create(resource)
        self.assertEqual(client.request.call_args.args,('POST','/apis/helm.toolkit.fluxcd.io/v2/namespaces/tenant-a/helmreleases'))
        client.delete_observed(resource)
        self.assertEqual(client.request.call_args.kwargs['body']['preconditions'],{'uid':'observed','resourceVersion':'3'})
        del resource['metadata']['uid']
        with self.assertRaises(InvalidRequestError):client.delete_observed(resource)

    def test_server_error_after_mutation_is_ambiguous_without_response_diagnostics(self):
        client=object.__new__(KubernetesClient);client.origin='https://kubernetes.example.test';client.config=SimpleNamespace(timeout_seconds=1)
        client._token=lambda:'runtime-only';client.opener=Mock()
        client.opener.open.side_effect=urllib.error.HTTPError(client.origin,503,'private diagnostic',{},None)
        with self.assertRaises(AmbiguousMutationError) as error:client.request('POST','/apis/example',body={})
        self.assertNotIn('private',str(error.exception))


if __name__=='__main__':unittest.main()
