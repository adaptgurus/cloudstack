"""Native clusterctl installation with protected certificate auth and bounded observation."""
from __future__ import annotations

import base64
import http.client
import json
import os
from pathlib import Path
import re
import ssl
import subprocess
import tempfile
import urllib.parse

from bootstrap.native import canonical
from controller.model import InvalidRequestError
from .remote import NativeImageStager


class ManagementAPI:
    def __init__(self,credentials,endpoint):
        self.credentials,self.endpoint=credentials,endpoint

    def get(self,path):
        if not re.fullmatch(r'/(?:api/v1|apis/(?:apps|apiextensions.k8s.io)/v1|apis/clusterctl.cluster.x-k8s.io/v1alpha3)/[A-Za-z0-9_./-]+',path) or '..' in path:
            raise InvalidRequestError('management installer read is outside its fixed API scope')
        value=self.credentials.read(self.endpoint)
        cluster=value['clusters'][0]['cluster'];user=value['users'][0]['user']
        try:
            with tempfile.TemporaryDirectory(prefix='layersentry-provider-tls-') as directory:
                paths=[]
                for index,encoded in enumerate((cluster['certificate-authority-data'],user['client-certificate-data'],user['client-key-data'])):
                    pathfile=Path(directory)/str(index)
                    fd=os.open(pathfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
                    with os.fdopen(fd,'wb') as stream:stream.write(base64.b64decode(encoded,validate=True))
                    paths.append(pathfile)
                context=ssl.create_default_context(cafile=str(paths[0]));context.load_cert_chain(str(paths[1]),str(paths[2]))
                connection=http.client.HTTPSConnection(self.endpoint,6443,context=context,timeout=20)
                try:
                    connection.request('GET',path,headers={'Accept':'application/json'})
                    response=connection.getresponse();raw=response.read(8*1024**2+1)
                    if response.status==404:return None
                    if response.status!=200 or len(raw)>8*1024**2:raise ValueError()
                    result=json.loads(raw)
                    if not isinstance(result,dict):raise ValueError()
                    return result
                finally:connection.close()
        except (OSError,ValueError,http.client.HTTPException):
            raise InvalidRequestError('management provider observation failed; no mutation was inferred') from None


def clusterctl_config(bundle):
    return {'providers':[{'name':p['name'],'type':p['type'],'url':str(bundle.file(p['file']))} for p in bundle.value['providers']],
            'cert-manager':{'url':str(bundle.file('repositories/cert-manager/v1.21.1/cert-manager.yaml')),'version':'v1.21.1','timeout':'300s'}}


def clusterctl_env(directory):
    # Never inherit ambient provider/API tokens or arbitrary clusterctl variables.
    return {'PATH':'/usr/bin:/bin','XDG_CONFIG_HOME':str(directory),'CLUSTERCTL_DISABLE_VERSIONCHECK':'true','GOPROXY':'off'}


class ProviderInstaller:
    def __init__(self,bundle,*,qualification_environment,runner=subprocess.run,api_factory=ManagementAPI):
        if qualification_environment!='disposable-lab':
            raise InvalidRequestError('unsigned management bundle is restricted to the designated disposable qualification environment')
        if bundle.value['status']!='CI_VERIFIED':
            raise InvalidRequestError('management bundle must have recorded CI qualification before installation')
        self.bundle,self.runner,self.api_factory=bundle,runner,api_factory

    def observe(self,api,*,started):
        expected=self.bundle.value
        rows=api.get('/apis/clusterctl.cluster.x-k8s.io/v1alpha3/providers')
        inventory=[] if rows is None else rows.get('items')
        if not isinstance(inventory,list) or len(inventory)>16:raise InvalidRequestError('provider inventory is invalid')
        expected_ids={(p['namespace'],p['label']):p for p in expected['providers']}
        observed=set()
        for row in inventory:
            metadata=row.get('metadata',{});identity=(metadata.get('namespace'),metadata.get('name'))
            provider=expected_ids.get(identity)
            if not provider or identity in observed or any(row.get(key)!=provider[field] for key,field in (('providerName','name'),('type','type'),('version','version'))):
                raise InvalidRequestError('management provider version, identity or ownership differs from the approved tuple')
            observed.add(identity)
        ready=len(observed)==len(expected_ids)
        present=bool(inventory)
        for namespace in expected['namespaceNames']:
            resource=api.get('/api/v1/namespaces/'+namespace)
            if resource is not None:
                present=True
                if resource.get('metadata',{}).get('name')!=namespace:raise InvalidRequestError('provider namespace identity drifted')
                label=next((p['label'] for p in expected['providers'] if p['namespace']==namespace),None)
                if label and resource.get('metadata',{}).get('labels',{}).get('cluster.x-k8s.io/provider')!=label:
                    raise InvalidRequestError('provider namespace is owned by a different installer')
        for deployment in expected['deployments']:
            resource=api.get('/apis/apps/v1/namespaces/'+deployment['namespace']+'/deployments/'+deployment['name'])
            if resource is None:ready=False;continue
            present=True;metadata=resource.get('metadata',{});spec=resource.get('spec',{});status=resource.get('status',{})
            actual={c.get('name'):c.get('image') for c in spec.get('template',{}).get('spec',{}).get('containers',[])}
            if actual!=deployment['images'] or metadata.get('namespace')!=deployment['namespace'] or metadata.get('name')!=deployment['name']:
                raise InvalidRequestError('provider controller image or identity drifted')
            replicas=spec.get('replicas',1)
            if not isinstance(replicas,int) or replicas<1 or status.get('observedGeneration',0)<metadata.get('generation',1) or status.get('updatedReplicas',0)!=replicas or status.get('availableReplicas',0)!=replicas or status.get('readyReplicas',0)!=replicas:
                ready=False
        for crd in expected['crds']:
            resource=api.get('/apis/apiextensions.k8s.io/v1/customresourcedefinitions/'+crd['name'])
            if resource is None:ready=False;continue
            present=True
            if resource.get('metadata',{}).get('name')!=crd['name'] or [v['name'] for v in resource.get('spec',{}).get('versions',[]) if v.get('served')] != crd['versions']:
                raise InvalidRequestError('provider CRD served contract changed')
            conditions=resource.get('status',{}).get('conditions',[])
            if not any(c.get('type')=='Established' and c.get('status')=='True' for c in conditions) or any(c.get('type')=='NamesAccepted' and c.get('status')=='False' for c in conditions):ready=False
        if present and not started:raise InvalidRequestError('preexisting provider resources are not owned by this bootstrap journal')
        return {'ready':ready,'inventoryComplete':len(observed)==len(expected_ids),'providerCount':len(observed)}

    def advance(self,native,transport,credentials,nodes):
        journal=native.journal
        expected=journal.state.get('providerBundleSha256')
        if expected is not None and expected!=self.bundle.digest:raise InvalidRequestError('provider bundle changed during management bootstrap')
        journal.state['providerBundleSha256']=self.bundle.digest;journal.save()
        api=self.api_factory(credentials,native.endpoint)
        record=journal.state.get('providerInstall')
        if record is not None and (record.get('bundleSha256')!=self.bundle.digest or record.get('state') not in ('SUBMITTING','SUBMITTED','UNKNOWN','OBSERVED_READY')):
            raise InvalidRequestError('provider installation journal binding changed')
        before=self.observe(api,started=record is not None)
        if before['ready']:
            journal.state['providerInstall']={'state':'OBSERVED_READY','bundleSha256':self.bundle.digest}
            journal.save();return True
        if not NativeImageStager(self.bundle,transport,journal).advance(nodes,native.hosts):return False
        if before['inventoryComplete']:
            # Native init skips installed providers; do not pretend that rerunning
            # it repairs externally deleted resources or an unhealthy controller.
            return False
        journal.state['providerInstall']={'state':'SUBMITTING','bundleSha256':self.bundle.digest};journal.save()
        with tempfile.TemporaryDirectory(prefix='layersentry-clusterctl-') as directory:
            config=Path(directory)/'clusterctl.json';config.write_bytes(canonical(clusterctl_config(self.bundle)));config.chmod(0o600)
            argv=[str(self.bundle.file('bin/clusterctl')),'init','--config',str(config),'--kubeconfig',str(credentials.path),
                  '--core','cluster-api:v1.13.5','--bootstrap','rke2:v0.25.2','--control-plane','rke2:v0.25.2',
                  '--infrastructure','cloudstack:v0.6.1','--wait-providers','--wait-provider-timeout','120','--validate=true']
            try:
                result=self.runner(argv,capture_output=True,timeout=600,check=False,env=clusterctl_env(directory))
                state='SUBMITTED' if result.returncode==0 else 'UNKNOWN'
            except (OSError,subprocess.SubprocessError):state='UNKNOWN'
        # clusterctl stdout/stderr may include credentials from admission errors;
        # never persist it or treat a successful exit as provider readiness.
        journal.state['providerInstall']={'state':state,'bundleSha256':self.bundle.digest};journal.save()
        after=self.observe(api,started=True)
        if after['ready']:
            journal.state['providerInstall']['state']='OBSERVED_READY';journal.save();return True
        return False

    def inspect(self,native,credentials):
        record=native.journal.state.get('providerInstall',{})
        if record.get('bundleSha256')!=self.bundle.digest or record.get('state')!='OBSERVED_READY':return False
        return self.observe(self.api_factory(credentials,native.endpoint),started=True)['ready']
