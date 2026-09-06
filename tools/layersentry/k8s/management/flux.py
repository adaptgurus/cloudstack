"""Pinned central Flux export and narrow management-plane resource contract."""
from __future__ import annotations
import copy
import json
import subprocess

from controller.model import InvalidRequestError

NAMESPACE='layersentry-flux-system'
COMPONENTS=('source-controller','kustomize-controller','helm-controller')
GROUPS=('source.toolkit.fluxcd.io','kustomize.toolkit.fluxcd.io','helm.toolkit.fluxcd.io')
ROUTES={
 ('v1','Namespace'):('/api/v1/namespaces',False),
 ('v1','ServiceAccount'):('/api/v1/serviceaccounts',True),
 ('v1','Service'):('/api/v1/services',True),
 ('v1','ResourceQuota'):('/api/v1/resourcequotas',True),
 ('networking.k8s.io/v1','NetworkPolicy'):('/apis/networking.k8s.io/v1/networkpolicies',True),
 ('rbac.authorization.k8s.io/v1','ClusterRole'):('/apis/rbac.authorization.k8s.io/v1/clusterroles',False),
 ('rbac.authorization.k8s.io/v1','ClusterRoleBinding'):('/apis/rbac.authorization.k8s.io/v1/clusterrolebindings',False),
 ('apiextensions.k8s.io/v1','CustomResourceDefinition'):('/apis/apiextensions.k8s.io/v1/customresourcedefinitions',False),
 ('apps/v1','Deployment'):('/apis/apps/v1/deployments',True),
}


def route(row):
    import re
    key=(row.get('apiVersion'),row.get('kind'))
    if key not in ROUTES:raise InvalidRequestError('central Flux resource kind is outside approved installation')
    collection,namespaced=ROUTES[key];meta=row.get('metadata',{});name=meta.get('name','')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,252}',name):raise InvalidRequestError('central Flux resource name is invalid')
    if namespaced:
        if meta.get('namespace')!=NAMESPACE:raise InvalidRequestError('central Flux installation namespace differs')
        prefix,plural=collection.rsplit('/',1);collection=prefix+'/namespaces/'+NAMESPACE+'/'+plural
    elif meta.get('namespace'):raise InvalidRequestError('cluster-scoped Flux resource has a namespace')
    return collection,collection+'/'+name


def render_manifest(executable,lock):
    import yaml
    result=subprocess.run([str(executable),'install','--export','--components='+','.join(COMPONENTS),'--namespace='+NAMESPACE,'--watch-all-namespaces=true','--network-policy=true'],capture_output=True,timeout=60,env={'PATH':'/usr/bin:/bin'},check=True)
    replacements={i['source']:i['image'] for i in lock['images']}
    docs=[]
    for item in yaml.safe_load_all(result.stdout):
        if not item:continue
        kind=item['kind'];name=item['metadata']['name']
        if kind=='ClusterRole' and name.startswith(('flux-edit-','flux-view-')):continue
        if kind=='ClusterRoleBinding' and name.startswith('cluster-reconciler-'):continue
        if kind=='NetworkPolicy' and name=='allow-webhooks':continue
        if kind=='ClusterRole':
            item['rules']=[r for r in item['rules'] if (not r.get('apiGroups') or all(g in ('','coordination.k8s.io',*GROUPS) for g in r['apiGroups'])) and 'serviceaccounts/token' not in r.get('resources',[])]
        if kind=='ClusterRoleBinding':item['subjects']=[s for s in item['subjects'] if s['name'] in COMPONENTS]
        if kind=='Deployment':
            container=item['spec']['template']['spec']['containers'][0]
            container['image']=replacements[container['image']]
            container['imagePullPolicy']='IfNotPresent'
            if name in ('kustomize-controller','helm-controller'):container['args'].append('--no-cross-namespace-refs=true')
            if name=='kustomize-controller':container['args'].append('--no-remote-bases=true')
        docs.append(item)
    # Namespaces/CRDs and permissions precede services/controllers. No CRs are
    # created until independent package readiness/authorization gates permit it.
    order={'Namespace':0,'CustomResourceDefinition':1,'ServiceAccount':2,'ClusterRole':3,'ClusterRoleBinding':4,'ResourceQuota':5,'NetworkPolicy':6,'Service':7,'Deployment':8}
    docs.sort(key=lambda r:(order[r['kind']],r['metadata']['name']))
    validate_manifest(docs,lock)
    return docs


def validate_manifest(docs,lock):
    if not isinstance(docs,list) or len(docs)!=21:raise InvalidRequestError('central Flux resource closure differs from approved minimal export')
    identities=[route(r)[1] for r in docs]
    if len(set(identities))!=len(identities):raise InvalidRequestError('duplicate central Flux identity')
    deployments=[r for r in docs if r['kind']=='Deployment']
    if {r['metadata']['name'] for r in deployments}!=set(COMPONENTS):raise InvalidRequestError('central Flux controller closure differs')
    images={i['source'].split('/')[-1].split(':')[0]:i['image'] for i in lock['images'] if i['source'].startswith('ghcr.io/fluxcd/')}
    for row in deployments:
        name=row['metadata']['name'];containers=row['spec']['template']['spec']['containers']
        if len(containers)!=1 or containers[0]['name']!='manager' or containers[0]['image']!=images[name] or containers[0]['imagePullPolicy']!='IfNotPresent':raise InvalidRequestError('central Flux controller image differs')
        args=containers[0]['args']
        if '--watch-all-namespaces=true' not in args or any(a.startswith('--default-service-account') for a in args):raise InvalidRequestError('central Flux remote tenancy contract differs')
        if name!='source-controller' and '--no-cross-namespace-refs=true' not in args:raise InvalidRequestError('cross-namespace Flux references must be denied')
        if name=='kustomize-controller' and '--no-remote-bases=true' not in args:raise InvalidRequestError('remote Kustomize bases must be denied')
    roles=[r for r in docs if r['kind']=='ClusterRole'];bindings=[r for r in docs if r['kind']=='ClusterRoleBinding']
    if len(roles)!=1 or len(bindings)!=1 or roles[0]['metadata']['name']!='crd-controller-'+NAMESPACE or bindings[0]['roleRef']!={'apiGroup':'rbac.authorization.k8s.io','kind':'ClusterRole','name':'crd-controller-'+NAMESPACE}:raise InvalidRequestError('central Flux management permissions differ')
    if sorted(bindings[0]['subjects'],key=lambda s:s['name'])!=sorted([{'kind':'ServiceAccount','name':c,'namespace':NAMESPACE} for c in COMPONENTS],key=lambda s:s['name']):raise InvalidRequestError('central Flux binding subjects differ')
    for rule in roles[0]['rules']:
        if any(g not in ('','coordination.k8s.io',*GROUPS) for g in rule.get('apiGroups',[])) or 'serviceaccounts/token' in rule.get('resources',[]):raise InvalidRequestError('central Flux role exceeds minimal groups')
    crds=[r for r in docs if r['kind']=='CustomResourceDefinition']
    if len(crds)!=8 or any(r['spec']['group'] not in GROUPS for r in crds):raise InvalidRequestError('central Flux CRD closure differs')
    return True


def desired_resource(row,bundle_digest,nonce):
    value=copy.deepcopy(row)
    value['metadata'].setdefault('annotations',{}).update({'layersentry.io/management-bundle-sha256':bundle_digest,'layersentry.io/flux-install-id':nonce})
    return value


def contains(actual,desired):
    """Allow native default fields, never extra list members (RBAC/containers)."""
    if isinstance(desired,dict):return isinstance(actual,dict) and all(k in actual and contains(actual[k],v) for k,v in desired.items())
    if isinstance(desired,list):return isinstance(actual,list) and len(actual)==len(desired) and all(contains(a,d) for a,d in zip(actual,desired))
    return actual==desired


def normalized_template(template):
    """Exact execution template, allowing only audited Kubernetes 1.36.4 defaults.

    ServiceAccount token projections are Pod admission defaults, NOT Deployment
    template defaults. This observer never compares live Pods to this template.
    See DESIGN.md for exact native defaulting/conversion sources.
    """
    value=copy.deepcopy(template)
    metadata=value.setdefault('metadata',{})
    if metadata.get('creationTimestamp','missing') is None:metadata.pop('creationTimestamp')
    pod=value['spec']
    for key,default in {'dnsPolicy':'ClusterFirst','restartPolicy':'Always','schedulerName':'default-scheduler','securityContext':{},'terminationGracePeriodSeconds':30}.items():
        pod.setdefault(key,default)
    if pod.get('serviceAccount')==pod.get('serviceAccountName') and 'serviceAccount' in pod:pod.pop('serviceAccount')
    for container in pod['containers']:
        container.setdefault('terminationMessagePath','/dev/termination-log')
        container.setdefault('terminationMessagePolicy','File')
        container.setdefault('imagePullPolicy','IfNotPresent')
        container.setdefault('resources',{})
        for resources in (container['resources'].get('limits',{}),container['resources'].get('requests',{})):
            # This exact export uses 1000m CPU; native Quantity JSON emits 1.
            if resources.get('cpu')=='1000m':resources['cpu']='1'
        for env in container.get('env',[]):
            source=env.get('valueFrom',{})
            if 'fieldRef' in source:source['fieldRef'].setdefault('apiVersion','v1')
            if 'resourceFieldRef' in source:
                selector=source['resourceFieldRef']
                if selector.get('divisor','0')=='0':selector['divisor']='1'
        for name in ('livenessProbe','readinessProbe','startupProbe'):
            if name not in container:continue
            probe=container[name]
            for key,default in {'timeoutSeconds':1,'periodSeconds':10,'successThreshold':1,'failureThreshold':3}.items():probe.setdefault(key,default)
            if 'httpGet' in probe:
                probe['httpGet'].setdefault('scheme','HTTP');probe['httpGet'].setdefault('path','/')
    return value


def resource_matches(actual,desired):
    if desired['kind']!='Deployment':return contains(actual,desired)
    actual=copy.deepcopy(actual);desired=copy.deepcopy(desired)
    actual_template=normalized_template(actual['spec']['template'])
    desired_template=normalized_template(desired['spec']['template'])
    if actual_template!=desired_template:return False
    actual['spec']['template']=actual_template;desired['spec']['template']=desired_template
    return contains(actual,desired)


def ready(row):
    if row.get('metadata',{}).get('deletionTimestamp'):return False
    if row['kind']=='Namespace':return row.get('status',{}).get('phase')=='Active'
    if row['kind']=='CustomResourceDefinition':
        conditions=row.get('status',{}).get('conditions',[])
        return any(c.get('type')=='Established' and c.get('status')=='True' for c in conditions) and not any(c.get('type')=='NamesAccepted' and c.get('status')=='False' for c in conditions)
    if row['kind']=='Deployment':
        spec=row.get('spec',{});status=row.get('status',{});replicas=spec.get('replicas',1)
        return type(replicas) is int and replicas>0 and status.get('observedGeneration',0)>=row['metadata'].get('generation',1) and all(status.get(key,0)==replicas for key in ('updatedReplicas','availableReplicas','readyReplicas'))
    return True


class FluxInstaller:
    def __init__(self,bundle):
        self.bundle=bundle
        self.docs=json.loads(bundle.file(bundle.value['centralFlux']['file']).read_bytes())

    def observe(self,api,journal):
        record=journal.state.get('centralFluxInstall')
        if record is not None and (record.get('bundleSha256')!=self.bundle.digest or not isinstance(record.get('objects'),dict) or not isinstance(record.get('nonce'),str) or len(record['nonce'])!=32):raise InvalidRequestError('central Flux durable binding differs')
        results=[]
        for doc in self.docs:
            path=route(doc)[1];actual=api.get(path);saved=record['objects'].get(path) if record else None
            if actual is None:
                if saved and saved.get('uid'):raise InvalidRequestError('an owned Flux resource was deleted; explicit recovery is required')
                results.append((doc,None,False));continue
            if not record or not saved:raise InvalidRequestError('preexisting central Flux resource is not owned by this journal')
            if not isinstance(saved.get('nonce'),str) or len(saved['nonce'])!=32:raise InvalidRequestError('central Flux object intent binding is absent')
            desired=desired_resource(doc,self.bundle.digest,saved['nonce'])
            meta=actual.get('metadata',{});uid=meta.get('uid')
            if not isinstance(uid,str) or not uid or not resource_matches(actual,desired) or (saved.get('uid') and saved['uid']!=uid):raise InvalidRequestError('central Flux resource ownership or approved specification drifted')
            if meta.get('deletionTimestamp'):raise InvalidRequestError('owned central Flux resource is being deleted')
            if doc['kind']=='ClusterRole' and (actual.get('aggregationRule') or any(k.startswith('rbac.authorization.k8s.io/aggregate-to-') for k in meta.get('labels',{}))):
                raise InvalidRequestError('central Flux role must not aggregate into tenant permissions')
            if doc['kind']=='Deployment':
                pod=actual['spec']['template']['spec']
                if any(pod.get(k) for k in ('initContainers','ephemeralContainers','hostNetwork','hostPID','hostIPC')):
                    raise InvalidRequestError('central Flux pod authority differs from approved controllers')
                for container in pod['containers']:
                    security=container.get('securityContext',{})
                    if security.get('privileged') or security.get('capabilities',{}).get('add'):
                        raise InvalidRequestError('central Flux controller privileges were expanded')
            saved['uid']=uid;saved['state']='OBSERVED';results.append((doc,actual,ready(actual)))
        if record:journal.save()
        return results

    def advance(self,api,journal):
        import secrets
        rows=self.observe(api,journal)
        record=journal.state.get('centralFluxInstall')
        if not record:
            record={'bundleSha256':self.bundle.digest,'nonce':secrets.token_hex(16),'objects':{},'state':'PENDING'}
            journal.state['centralFluxInstall']=record;journal.save()
        # One native create per reconcile. All resources are observed first;
        # namespaces and established CRDs block controller creation until ready.
        for doc,actual,is_ready in rows:
            if actual is not None:
                if not is_ready:return False
                continue
            collection,path=route(doc)
            saved=record['objects'].setdefault(path,{'nonce':secrets.token_hex(16)})
            if not isinstance(saved.get('nonce'),str) or len(saved['nonce'])!=32:raise InvalidRequestError('central Flux object intent binding is absent')
            saved['state']='SUBMITTING';journal.save()
            try:api.create(collection,desired_resource(doc,self.bundle.digest,saved['nonce']))
            except InvalidRequestError:
                record['objects'][path]['state']='UNKNOWN';journal.save();raise
            record['objects'][path]['state']='SUBMITTED';journal.save()
            return False
        record['state']='OBSERVED_READY';journal.save();return True

    def inspect(self,api,journal):
        record=journal.state.get('centralFluxInstall',{})
        return record.get('state')=='OBSERVED_READY' and all(actual is not None and is_ready for _,actual,is_ready in self.observe(api,journal))
