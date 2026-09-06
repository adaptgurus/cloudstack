"""Offline first-plane bundle, ownership, import and interrupted-install checks."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bootstrap_management import complete_provider_install
from controller.model import InvalidRequestError
from management.bundle import verify_oci,safe_file
from management.install import ProviderInstaller,clusterctl_config
from management.remote import NativeImageStager,_STATUS,_PREPARE,_IMPORT


def oci_fixture(path,*,corrupt=False):
    blobs={}
    def blob(value):
        raw=json.dumps(value).encode();digest='sha256:'+hashlib.sha256(raw).hexdigest();blobs[digest]=raw
        return {'digest':digest,'size':len(raw),'mediaType':'application/vnd.oci.image.manifest.v1+json'}
    config=blob({'os':'linux','architecture':'amd64'})
    image=blob({'schemaVersion':2,'config':config,'layers':[]})
    index=blob({'schemaVersion':2,'manifests':[image]})
    if corrupt:blobs[config['digest']]=b'wrong'
    with tarfile.open(path,'w') as archive:
        files={'index.json':json.dumps({'schemaVersion':2,'manifests':[index]}).encode(),'oci-layout':b'{"imageLayoutVersion":"1.0.0"}'}
        files.update({'blobs/sha256/'+digest.split(':')[1]:raw for digest,raw in blobs.items()})
        for name,raw in files.items():
            info=tarfile.TarInfo(name);info.size=len(raw);archive.addfile(info,io.BytesIO(raw))
    return 'registry.example/provider@'+index['digest']


class BundleTests(unittest.TestCase):
    def test_bundle_paths_cannot_follow_links_or_writable_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'file';path.write_text('public')
            self.assertEqual(safe_file(root,'file'),path)
            with self.assertRaises(InvalidRequestError):safe_file(root,'../file')
            (root/'link').symlink_to(path)
            with self.assertRaises(InvalidRequestError):safe_file(root,'link')
            path.chmod(0o666)
            with self.assertRaises(InvalidRequestError):safe_file(root,'file')

    def test_index_identity_and_every_blob_are_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'image.tar';image=oci_fixture(path)
            verify_oci(path,image)
            with self.assertRaises(InvalidRequestError):verify_oci(path,'registry.example/provider@sha256:'+'0'*64)
            image=oci_fixture(path,corrupt=True)
            with self.assertRaises(InvalidRequestError):verify_oci(path,image)

    def test_remote_programs_compile_without_host_execution(self):
        for script in (_STATUS,_PREPARE,_IMPORT):compile(script,'fixed-management-import','exec')
        self.assertIn("'--all-platforms','--digests'",_IMPORT)
        self.assertNotIn('shell=True',_IMPORT)


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.images=[{'image':f'registry.example/provider{i}@sha256:'+'a'*64,'file':f'images/{i}.tar','sha256':'b'*64,'activate':True} for i in range(8)]
        self.bundle=SimpleNamespace(digest='c'*64,value={'images':self.images})
        self.transport=Mock();self.journal=Mock();self.journal.state={}
        self.stager=NativeImageStager(self.bundle,self.transport,self.journal)
        self.nodes=[{'id':str(i),'hostid':'host'} for i in range(3)];self.hosts={'host':{}}
        self.stager.transfer=Mock()

    def test_only_one_missing_archive_is_imported_per_reconcile(self):
        self.transport.guest_call.return_value={'images':{}}
        self.assertFalse(self.stager.advance(self.nodes,self.hosts))
        self.assertEqual(self.transport.guest_call.call_count,3)
        self.stager.transfer.assert_called_once_with(self.nodes[0],{},self.images[0])

    def test_present_exact_images_resume_without_transfer(self):
        self.transport.guest_call.return_value={'images':{item['image']:'sha256:'+'a'*64 for item in self.images}}
        self.assertTrue(self.stager.advance(self.nodes,self.hosts))
        self.stager.transfer.assert_not_called()
        self.assertEqual(self.journal.state['providerImagesImported']['bundleSha256'],self.bundle.digest)

    def test_wrong_native_digest_fails_without_import(self):
        self.transport.guest_call.return_value={'images':{self.images[0]['image']:'sha256:'+'f'*64}}
        with self.assertRaises(InvalidRequestError):self.stager.advance(self.nodes,self.hosts)
        self.stager.transfer.assert_not_called()


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.provider={'name':'cluster-api','type':'CoreProvider','version':'v1.13.5','label':'cluster-api','namespace':'capi-system','file':'repositories/cluster-api/v1.13.5/core-components.yaml'}
        self.deployment={'name':'capi-controller-manager','namespace':'capi-system','images':{'manager':'registry.example/provider@sha256:'+'a'*64},'provider':'cluster-api'}
        self.bundle=SimpleNamespace(digest='b'*64,value={'status':'CI_VERIFIED','providers':[self.provider],'namespaceNames':['capi-system'],'deployments':[self.deployment],'crds':[{'name':'clusters.cluster.x-k8s.io','versions':['v1beta1','v1beta2']}]},file=lambda name:Path('/approved/bundle')/name)
        self.rows={}
        self.api=SimpleNamespace(get=lambda path:self.rows.get(path))
        self.runner=Mock(return_value=subprocess.CompletedProcess([],0,b'not proof',b''))
        self.installer=ProviderInstaller(self.bundle,qualification_environment='disposable-lab',runner=self.runner,api_factory=lambda *_:self.api)
        self.native=Mock();self.native.journal.state={};self.native.endpoint='192.0.2.10';self.native.hosts={}
        self.credentials=SimpleNamespace(path=Path('/protected/management.json'))

    def ready(self):
        p=self.provider;d=self.deployment
        self.rows['/apis/clusterctl.cluster.x-k8s.io/v1alpha3/providers']={'items':[{'metadata':{'name':p['label'],'namespace':p['namespace']},'providerName':p['name'],'type':p['type'],'version':p['version']}]}
        self.rows['/api/v1/namespaces/capi-system']={'metadata':{'name':'capi-system','labels':{'cluster.x-k8s.io/provider':'cluster-api'}}}
        self.rows['/apis/apps/v1/namespaces/capi-system/deployments/capi-controller-manager']={'metadata':{'name':d['name'],'namespace':d['namespace'],'generation':2},'spec':{'replicas':1,'template':{'spec':{'containers':[{'name':name,'image':image} for name,image in d['images'].items()]}}},'status':{'observedGeneration':2,'updatedReplicas':1,'availableReplicas':1,'readyReplicas':1}}
        self.rows['/apis/apiextensions.k8s.io/v1/customresourcedefinitions/clusters.cluster.x-k8s.io']={'metadata':{'name':'clusters.cluster.x-k8s.io'},'spec':{'versions':[{'name':'v1beta1','served':True},{'name':'v1beta2','served':True}]},'status':{'conditions':[{'type':'Established','status':'True'}]}}

    def test_foreign_preexisting_installation_is_not_adopted(self):
        self.ready()
        with self.assertRaises(InvalidRequestError):self.installer.observe(self.api,started=False)
        self.runner.assert_not_called()

    def test_wrong_version_image_and_stale_generation_are_not_ready(self):
        self.ready();provider=self.rows['/apis/clusterctl.cluster.x-k8s.io/v1alpha3/providers']['items'][0]
        provider['version']='v9.0.0'
        with self.assertRaises(InvalidRequestError):self.installer.observe(self.api,started=True)
        self.ready();deployment=self.rows['/apis/apps/v1/namespaces/capi-system/deployments/capi-controller-manager']
        deployment['status']['observedGeneration']=1
        self.assertFalse(self.installer.observe(self.api,started=True)['ready'])
        deployment['spec']['template']['spec']['containers'][0]['image']='unsafe:latest'
        with self.assertRaises(InvalidRequestError):self.installer.observe(self.api,started=True)

    def test_successful_exit_is_not_readiness_and_secrets_are_not_journaled(self):
        with patch('management.install.NativeImageStager') as stager:
            stager.return_value.advance.return_value=True
            self.runner.side_effect=lambda *args,**kwargs:subprocess.CompletedProcess([],0,b'private diagnostic',b'private token')
            self.assertFalse(self.installer.advance(self.native,Mock(),self.credentials,[]))
        self.assertEqual(self.native.journal.state['providerInstall']['state'],'SUBMITTED')
        self.assertNotIn('private',repr(self.native.journal.state))
        args,kwargs=self.runner.call_args
        self.assertIn('cloudstack:v0.6.1',args[0]);self.assertEqual(kwargs['timeout'],600)
        self.assertEqual(set(kwargs['env']),{'PATH','XDG_CONFIG_HOME','CLUSTERCTL_DISABLE_VERSIONCHECK','GOPROXY'})

    def test_late_ready_after_timeout_is_observed_without_replaying_clusterctl(self):
        self.native.journal.state['providerInstall']={'state':'UNKNOWN','bundleSha256':self.bundle.digest}
        self.ready()
        self.assertTrue(self.installer.advance(self.native,Mock(),self.credentials,[]))
        self.runner.assert_not_called()
        self.assertEqual(self.native.journal.state['providerInstall']['state'],'OBSERVED_READY')

    def test_bundle_rebinding_and_nonlab_or_unqualified_install_are_rejected(self):
        self.native.journal.state['providerBundleSha256']='d'*64
        with self.assertRaises(InvalidRequestError):self.installer.advance(self.native,Mock(),self.credentials,[])
        with self.assertRaises(InvalidRequestError):ProviderInstaller(self.bundle,qualification_environment='production')
        self.bundle.value['status']='SOURCE_COMPLETE'
        with self.assertRaises(InvalidRequestError):ProviderInstaller(self.bundle,qualification_environment='disposable-lab')

    def test_ready_inventory_cannot_hide_a_different_install_journal(self):
        self.ready()
        self.native.journal.state['providerInstall']={'state':'UNKNOWN','bundleSha256':'f'*64}
        with self.assertRaises(InvalidRequestError):self.installer.advance(self.native,Mock(),self.credentials,[])
        self.runner.assert_not_called()

    def test_installed_unhealthy_inventory_is_pending_without_init_replay(self):
        self.ready()
        self.native.journal.state['providerInstall']={'state':'UNKNOWN','bundleSha256':self.bundle.digest}
        self.rows['/apis/apps/v1/namespaces/capi-system/deployments/capi-controller-manager']['status']['readyReplicas']=0
        with patch('management.install.NativeImageStager') as stager:
            stager.return_value.advance.return_value=True
            self.assertFalse(self.installer.advance(self.native,Mock(),self.credentials,[]))
        self.runner.assert_not_called()

    def test_cleanup_is_impossible_until_provider_install_is_verified(self):
        native,transport,credentials,installer=Mock(),Mock(),Mock(),Mock();native.journal.state={}
        installer.advance.return_value=False
        result=complete_provider_install(native,transport,credentials,[],installer,{'status':'PENDING'})
        self.assertEqual(result['status'],'PENDING');self.assertNotIn('credentialsEscrowed',native.journal.state)
        native.cleanup_transport.assert_not_called()
        installer.advance.return_value=True;native.cleanup_transport.return_value=True
        result=complete_provider_install(native,transport,credentials,[],installer,{'status':'PENDING'})
        self.assertEqual(result['status'],'LIVE_VERIFIED')

    def test_clusterctl_uses_only_explicit_local_provider_repositories(self):
        config=clusterctl_config(self.bundle)
        self.assertTrue(all(p['url'].startswith('/approved/bundle/') for p in config['providers']))
        self.assertTrue(config['cert-manager']['url'].startswith('/approved/bundle/'))


if __name__=='__main__':unittest.main()
