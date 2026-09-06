"""Native central Flux ownership, exact-spec, crash and readiness edge checks."""
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from controller.model import InvalidRequestError
from management.flux import FluxInstaller,route,contains,desired_resource,ready,NAMESPACE,resource_matches
from management.install import ManagementAPI


class FluxAttestationTests(unittest.TestCase):
    def archive(self,path,*,wrong_subject=False,missing_sbom=False):
        import hashlib,io,tarfile
        blobs={}
        def blob(value):
            raw=json.dumps(value).encode();digest='sha256:'+hashlib.sha256(raw).hexdigest();blobs[digest]=raw
            return {'digest':digest,'size':len(raw),'mediaType':'application/vnd.oci.image.manifest.v1+json'}
        config=blob({'os':'linux','architecture':'amd64'})
        runtime=blob({'schemaVersion':2,'config':config,'layers':[]});runtime['platform']={'os':'linux','architecture':'amd64'}
        subject='f'*64 if wrong_subject else runtime['digest'].split(':')[1]
        layers=[]
        for predicate,detail in [('https://slsa.dev/provenance/v1',{'buildDefinition':{'buildType':'native'}}),('https://spdx.dev/Document',{'packages':[{'name':'controller'}]})]:
            if missing_sbom and predicate=='https://spdx.dev/Document':continue
            layers.append(blob({'predicateType':predicate,'subject':[{'digest':{'sha256':subject}}],'predicate':detail}))
        attestation=blob({'schemaVersion':2,'config':config,'layers':layers})
        attestation['annotations']={'vnd.docker.reference.digest':runtime['digest'],'vnd.docker.reference.type':'attestation-manifest'}
        index=blob({'schemaVersion':2,'manifests':[runtime,attestation]})
        files={'index.json':json.dumps({'schemaVersion':2,'manifests':[index]}).encode(),'oci-layout':b'{"imageLayoutVersion":"1.0.0"}'}
        files.update({'blobs/sha256/'+d.split(':')[1]:raw for d,raw in blobs.items()})
        with tarfile.open(path,'w') as archive:
            for name,raw in files.items():
                info=tarfile.TarInfo(name);info.size=len(raw);archive.addfile(info,io.BytesIO(raw))
        return 'ghcr.io/fluxcd/source-controller@'+index['digest']

    def test_runtime_bound_sbom_and_provenance_required(self):
        from management.bundle import verify_oci
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'image.tar';image=self.archive(path)
            evidence=verify_oci(path,image)
            self.assertEqual(set(evidence['attestations']),{'sbom','provenance'})
            self.assertFalse(evidence['signatureVerified'])
            for kwargs in ({'wrong_subject':True},{'missing_sbom':True}):
                image=self.archive(path,**kwargs)
                with self.assertRaises(InvalidRequestError):verify_oci(path,image)


class FluxTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.docs=[{'apiVersion':'v1','kind':'Namespace','metadata':{'name':NAMESPACE}},
          {'apiVersion':'apiextensions.k8s.io/v1','kind':'CustomResourceDefinition','metadata':{'name':'helmreleases.helm.toolkit.fluxcd.io'},'spec':{'versions':[{'name':'v2','served':True,'storage':True}]}},
          {'apiVersion':'rbac.authorization.k8s.io/v1','kind':'ClusterRole','metadata':{'name':'crd-controller-'+NAMESPACE},'rules':[{'apiGroups':['helm.toolkit.fluxcd.io'],'resources':['*'],'verbs':['*']}]},
          {'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'helm-controller','namespace':NAMESPACE},'spec':{'replicas':1,'template':{'spec':{'containers':[{'name':'manager','image':'ghcr.io/fluxcd/helm-controller@sha256:'+'a'*64,'args':['--no-cross-namespace-refs=true']}]}}}}]
        path=Path(self.tmp.name)/'central-flux.json';path.write_text(json.dumps(self.docs))
        self.bundle=SimpleNamespace(digest='b'*64,value={'centralFlux':{'file':path.name}},file=lambda _:path)
        self.installer=FluxInstaller(self.bundle);self.journal=Mock();self.journal.state={};self.rows={};self.calls=[]
        def create(collection,value):
            self.calls.append((collection,copy.deepcopy(value)))
            row=copy.deepcopy(value);row['metadata'].update(uid='native-'+str(len(self.calls)),generation=1)
            row['status']={'phase':'Active','observedGeneration':1,'updatedReplicas':1,'availableReplicas':1,'readyReplicas':1,'conditions':[{'type':'Established','status':'True'}]}
            self.rows[route(row)[1]]=row
        self.api=SimpleNamespace(get=lambda path:self.rows.get(path),create=create)

    def complete(self):
        for _ in range(6):
            if self.installer.advance(self.api,self.journal):return
        self.fail('fixture failed to reconcile')

    def test_create_only_bounded_and_repeat_without_mutation(self):
        self.assertFalse(self.installer.advance(self.api,self.journal));self.assertEqual(len(self.calls),1)
        self.complete();self.assertEqual(len(self.calls),4)
        self.assertTrue(self.installer.advance(self.api,self.journal));self.assertEqual(len(self.calls),4)
        self.assertTrue(self.installer.inspect(self.api,self.journal))
        self.assertNotIn('kubeconfig',json.dumps(self.journal.state))

    def test_timeout_after_native_commit_is_observed_without_replay(self):
        create=self.api.create
        def timeout(path,value):
            create(path,value)
            raise InvalidRequestError('outcome unknown')
        self.api.create=timeout
        with self.assertRaises(InvalidRequestError):self.installer.advance(self.api,self.journal)
        self.api.create=create;self.complete()
        self.assertEqual(len(self.calls),4)
        self.assertEqual(len({v['metadata']['annotations']['layersentry.io/flux-install-id'] for _,v in self.calls}),4)
        self.assertTrue(all(r['state']=='OBSERVED' for r in self.journal.state['centralFluxInstall']['objects'].values()))

    def test_unknown_without_native_object_retries_same_named_request(self):
        def timeout(*_):raise InvalidRequestError('outcome unknown')
        create=self.api.create;self.api.create=timeout
        with self.assertRaises(InvalidRequestError):self.installer.advance(self.api,self.journal)
        nonce=self.journal.state['centralFluxInstall']['nonce']
        object_nonce=self.journal.state['centralFluxInstall']['objects'][route(self.docs[0])[1]]['nonce']
        self.api.create=create;self.complete()
        self.assertEqual(self.journal.state['centralFluxInstall']['nonce'],nonce)
        self.assertEqual(self.calls[0][1]['metadata']['annotations']['layersentry.io/flux-install-id'],object_nonce)

    def test_earlier_public_nonce_cannot_claim_a_later_resource(self):
        self.installer.advance(self.api,self.journal)
        earlier=self.calls[0][1]['metadata']['annotations']['layersentry.io/flux-install-id']
        create=self.api.create
        def raced(collection,value):
            foreign=copy.deepcopy(value);foreign['metadata']['annotations']['layersentry.io/flux-install-id']=earlier
            create(collection,foreign)
            raise InvalidRequestError('native conflict')
        self.api.create=raced
        with self.assertRaises(InvalidRequestError):self.installer.advance(self.api,self.journal)
        self.api.create=create
        with self.assertRaises(InvalidRequestError):self.installer.advance(self.api,self.journal)
        self.assertEqual(len(self.calls),2)

    def test_foreign_resource_even_with_approved_bundle_annotation_rejected(self):
        doc=self.docs[0];row=desired_resource(doc,self.bundle.digest,'f'*32);row['metadata']['uid']='foreign'
        self.rows[route(doc)[1]]=row
        with self.assertRaises(InvalidRequestError):self.installer.advance(self.api,self.journal)
        self.assertEqual(self.calls,[])

    def test_owned_deletion_and_uid_replacement_require_explicit_recovery(self):
        self.complete();path=route(self.docs[0])[1];row=self.rows.pop(path)
        with self.assertRaises(InvalidRequestError):self.installer.advance(self.api,self.journal)
        row['metadata']['uid']='different';self.rows[path]=row
        with self.assertRaises(InvalidRequestError):self.installer.advance(self.api,self.journal)
        self.assertEqual(len(self.calls),4)

    def test_added_rbac_right_or_container_and_removed_security_arg_rejected(self):
        for index,mutate in [(2,lambda r:r['rules'].append({'apiGroups':['*'],'resources':['*'],'verbs':['*']})),(3,lambda r:r['spec']['template']['spec']['containers'].append({'name':'injected','image':'unsafe'})),(3,lambda r:r['spec']['template']['spec']['containers'][0].update(args=[]))]:
            with self.subTest(index=index):
                self.complete();path=route(self.docs[index])[1];before=copy.deepcopy(self.rows[path]);mutate(self.rows[path])
                with self.assertRaises(InvalidRequestError):self.installer.inspect(self.api,self.journal)
                self.rows[path]=before

    def test_injected_execution_fields_are_not_native_defaults(self):
        self.complete();path=route(self.docs[3])[1];original=copy.deepcopy(self.rows[path])
        for key,value in {'command':['/bin/sh','-c','unapproved'],'envFrom':[{'secretRef':{'name':'foreign'}}],'env':[{'name':'UNAPPROVED','value':'yes'}],'lifecycle':{'postStart':{'exec':{'command':['unapproved']}}},'workingDir':'/unapproved'}.items():
            with self.subTest(field=key):
                self.rows[path]=copy.deepcopy(original);self.rows[path]['spec']['template']['spec']['containers'][0][key]=value
                with self.assertRaises(InvalidRequestError):self.installer.inspect(self.api,self.journal)
        for key,value in {'runtimeClassName':'foreign','dnsConfig':{'nameservers':['192.0.2.3']},'hostAliases':[{'ip':'192.0.2.3','hostnames':['api']}],'imagePullSecrets':[{'name':'foreign'}]}.items():
            with self.subTest(field=key):
                self.rows[path]=copy.deepcopy(original);self.rows[path]['spec']['template']['spec'][key]=value
                with self.assertRaises(InvalidRequestError):self.installer.inspect(self.api,self.journal)

    def test_audited_template_defaults_and_quantity_normalization_are_accepted(self):
        desired=copy.deepcopy(self.docs[3]);pod=desired['spec']['template']['spec']
        pod['serviceAccountName']='helm-controller';container=pod['containers'][0]
        container.update(resources={'limits':{'cpu':'1000m','memory':'1Gi'}},env=[{'name':'NS','valueFrom':{'fieldRef':{'fieldPath':'metadata.namespace'}}},{'name':'MEM','valueFrom':{'resourceFieldRef':{'containerName':'manager','resource':'limits.memory'}}}],readinessProbe={'httpGet':{'path':'/readyz','port':9440}})
        actual=copy.deepcopy(desired);pod=actual['spec']['template']['spec']
        pod.update(dnsPolicy='ClusterFirst',restartPolicy='Always',schedulerName='default-scheduler',securityContext={},terminationGracePeriodSeconds=30,serviceAccount='helm-controller')
        actual['spec']['template']['metadata']={'creationTimestamp':None}
        container=pod['containers'][0];container.update(terminationMessagePath='/dev/termination-log',terminationMessagePolicy='File',imagePullPolicy='IfNotPresent')
        container['resources']['limits']['cpu']='1'
        container['env'][0]['valueFrom']['fieldRef']['apiVersion']='v1'
        container['env'][1]['valueFrom']['resourceFieldRef']['divisor']='0'
        container['readinessProbe'].update(timeoutSeconds=1,periodSeconds=10,successThreshold=1,failureThreshold=3)
        container['readinessProbe']['httpGet']['scheme']='HTTP'
        self.assertTrue(resource_matches(actual,desired))
        container['env'][1]['valueFrom']['resourceFieldRef']['divisor']='2'
        self.assertFalse(resource_matches(actual,desired))

    def test_pod_only_token_projection_is_not_a_deployment_template_default(self):
        desired=copy.deepcopy(self.docs[3]);actual=copy.deepcopy(desired)
        actual['spec']['template']['spec']['volumes']=[{'name':'kube-api-access-forged','projected':{'sources':[{'serviceAccountToken':{'path':'token'}}]}}]
        self.assertFalse(resource_matches(actual,desired))
        actual=copy.deepcopy(desired);actual['spec']['template']['metadata']={'annotations':{'sidecar.istio.io/inject':'true'}}
        self.assertFalse(resource_matches(actual,desired))

    def test_injected_cluster_role_aggregation_or_host_authority_rejected(self):
        self.complete()
        for index,mutate in [(2,lambda r:r['metadata'].update(labels={'rbac.authorization.k8s.io/aggregate-to-edit':'true'})),(3,lambda r:r['spec']['template']['spec'].update(hostNetwork=True)),(3,lambda r:r['spec']['template']['spec'].update(initContainers=[{'name':'injected'}]))]:
            path=route(self.docs[index])[1];before=copy.deepcopy(self.rows[path]);mutate(self.rows[path])
            with self.assertRaises(InvalidRequestError):self.installer.inspect(self.api,self.journal)
            self.rows[path]=before

    def test_stale_deployment_generation_and_crd_not_established_block(self):
        self.complete();path=route(self.docs[3])[1];self.rows[path]['status']['observedGeneration']=0
        self.assertFalse(self.installer.inspect(self.api,self.journal))
        self.rows[path]['status']['observedGeneration']=1
        self.rows[route(self.docs[1])[1]]['status']['conditions']=[]
        self.assertFalse(self.installer.inspect(self.api,self.journal))
        self.assertEqual(len(self.calls),4)

    def test_namespace_pending_stops_next_create(self):
        self.installer.advance(self.api,self.journal)
        self.rows[route(self.docs[0])[1]]['status']['phase']='Terminating'
        self.assertFalse(self.installer.advance(self.api,self.journal));self.assertEqual(len(self.calls),1)

    def test_binding_drift_rejected_before_any_create(self):
        self.installer.advance(self.api,self.journal)
        self.journal.state['centralFluxInstall']['bundleSha256']='e'*64
        with self.assertRaises(InvalidRequestError):self.installer.advance(self.api,self.journal)
        self.assertEqual(len(self.calls),1)

    def test_routes_reject_secret_and_other_namespace_or_mismatched_collection(self):
        for row in [{'apiVersion':'v1','kind':'Secret','metadata':{'name':'credentials','namespace':NAMESPACE}}, {'apiVersion':'apps/v1','kind':'Deployment','metadata':{'name':'controller','namespace':'customer'}}]:
            with self.assertRaises(InvalidRequestError):route(row)
        api=ManagementAPI(Mock(),'192.0.2.10')
        with self.assertRaises(InvalidRequestError):api.create('/api/v1/secrets',self.docs[0])
        api.credentials.read.assert_not_called()


if __name__=='__main__':unittest.main()
