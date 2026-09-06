"""Native Flux OCI chart and remote HelmRelease resources, with fixed tenancy."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from .flux_resources import bounded_name
from .package_catalog import NAME,VERSION
from .model import InvalidRequestError


def normalize_request(request):
    fields={'clusterName','namespace','projectId','package','version','profile'}
    if not isinstance(request,dict) or set(request)!=fields:raise InvalidRequestError('package request fields differ from schema')
    if any(not isinstance(request[key],str) or not NAME.fullmatch(request[key]) for key in fields-{'version'}):
        raise InvalidRequestError('package target identity is invalid')
    if not isinstance(request['version'],str) or not VERSION.fullmatch(request['version']):
        raise InvalidRequestError('package version must be exact')
    return dict(request)


def verify_remote_credentials(kubernetes,cluster,project_id):
    """Bind native CAPRKE2's credential owner without reading credential bytes."""
    metadata=cluster['metadata'];namespace=metadata['namespace'];name=metadata['name'];uid=metadata.get('uid')
    ref=cluster.get('spec',{}).get('controlPlaneRef',{})
    if ref.get('apiGroup')!='controlplane.cluster.x-k8s.io' or ref.get('kind')!='RKE2ControlPlane' or not isinstance(ref.get('name'),str) or not NAME.fullmatch(ref['name']):
        raise InvalidRequestError('remote package target has no native RKE2 control-plane reference')
    plane=kubernetes.get({'apiVersion':'controlplane.cluster.x-k8s.io/v1beta2','kind':'RKE2ControlPlane','metadata':{'namespace':namespace,'name':ref['name']}})
    pm=plane.get('metadata',{});labels=pm.get('labels',{})
    if pm.get('namespace')!=namespace or pm.get('name')!=ref['name'] or not pm.get('uid') or pm.get('deletionTimestamp') or labels.get('layersentry.io/project')!=project_id or labels.get('layersentry.io/managed')!='true':
        raise InvalidRequestError('remote control-plane ownership differs from the selected project')
    if not any(o.get('kind')=='Cluster' and o.get('name')==name and o.get('uid')==uid and str(o.get('apiVersion','')).startswith('cluster.x-k8s.io/') for o in pm.get('ownerReferences',[])):
        raise InvalidRequestError('remote control-plane belongs to another Cluster incarnation')
    secret=kubernetes.get_capi_kubeconfig_metadata(namespace,name);sm=secret.get('metadata',{})
    if sm.get('namespace')!=namespace or sm.get('name')!=name+'-kubeconfig' or sm.get('deletionTimestamp'):
        raise InvalidRequestError('native kubeconfig metadata identity differs')
    if not any(o.get('kind')=='RKE2ControlPlane' and o.get('name')==ref['name'] and o.get('uid')==pm['uid'] and o.get('controller') is True and str(o.get('apiVersion','')).startswith('controlplane.cluster.x-k8s.io/') for o in sm.get('ownerReferences',[])):
        raise InvalidRequestError('native kubeconfig is not controlled by the exact RKE2 control plane')


def build_package_resources(request,entry,catalog_digest,cluster_uid):
    request=normalize_request(request)
    if not isinstance(cluster_uid,str) or not cluster_uid or len(cluster_uid)>128:raise InvalidRequestError('observed CAPI cluster UID is required')
    binding=hashlib.sha256(json.dumps({'request':request,'catalog':catalog_digest,'clusterUid':cluster_uid},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    name=bounded_name(request['clusterName'],entry['package'])
    labels={'layersentry.io/managed':'true','layersentry.io/project':request['projectId'],'layersentry.io/cluster':request['clusterName'],'layersentry.io/package':entry['package']}
    metadata={'name':name,'namespace':request['namespace'],'labels':labels,'annotations':{'layersentry.io/package-binding':binding,'layersentry.io/cluster-uid':cluster_uid}}
    source={'apiVersion':'source.toolkit.fluxcd.io/v1','kind':'OCIRepository','metadata':deepcopy(metadata),'spec':{
        'interval':'10m','timeout':'2m','url':entry['chartUrl'],'ref':{'digest':entry['chartDigest']},
        'layerSelector':{'mediaType':'application/vnd.cncf.helm.chart.content.v1.tar+gzip','operation':'copy'}}}
    release={'apiVersion':'helm.toolkit.fluxcd.io/v2','kind':'HelmRelease','metadata':deepcopy(metadata),'spec':{
        'interval':'5m','timeout':'10m','releaseName':name,'targetNamespace':entry['targetNamespace'],'storageNamespace':entry['targetNamespace'],
        'kubeConfig':{'secretRef':{'name':request['clusterName']+'-kubeconfig','key':'value'}},
        'chartRef':{'kind':'OCIRepository','name':name},'values':deepcopy(entry['values']),
        'install':{'createNamespace':True,'crds':'Create','remediation':{'retries':0}},
        'upgrade':{'crds':'Skip','remediation':{'retries':0}},
        'uninstall':{'deletionPropagation':'foreground','disableWait':False},
        'driftDetection':{'mode':'enabled'},
        'dependsOn':[{'name':bounded_name(request['clusterName'],dep['package'])} for dep in entry['dependsOn']]}}
    return source,release
