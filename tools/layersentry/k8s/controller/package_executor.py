"""Bounded native package reconciliation; Flux remains the Helm lifecycle owner."""
from __future__ import annotations

from .flux_resources import desired_matches,flux_ready
from .model import InvalidRequestError,NotFoundError
from .package_resources import normalize_request,build_package_resources,verify_remote_credentials
from .service import StepOutcome,StepResult


class PackageExecutor:
    def __init__(self,kubernetes,authorizer,catalog,gates):
        self.kubernetes,self.authorizer,self.catalog,self.gates=kubernetes,authorizer,catalog,gates

    def _get(self,resource):
        try:return self.kubernetes.get(resource)
        except NotFoundError:return None

    @staticmethod
    def _owned(desired,actual):
        metadata=actual.get('metadata',{})
        expected=desired['metadata']
        if metadata.get('name')!=expected['name'] or metadata.get('namespace')!=expected['namespace'] or not desired_matches(expected['labels'],metadata.get('labels',{})) or not desired_matches(expected['annotations'],metadata.get('annotations',{})):
            raise InvalidRequestError('package resource ownership or immutable request binding changed')
        if not desired_matches(desired['spec'],actual.get('spec',{})):
            raise InvalidRequestError('package desired state drifted; automatic retarget/upgrade is prohibited')

    def _context(self,actor,request,action):
        request=normalize_request(request)
        self.authorizer.require(actor,'kubernetes.package.'+action,request['projectId'])
        if not self.gates.kubernetes_ready():raise InvalidRequestError('central Flux/base Kubernetes live qualification is incomplete')
        entry=self.catalog.resolve(request['package'],request['version'],request['profile'])
        if entry['stateful'] and not self.gates.stateful_ready():raise InvalidRequestError('stateful package E0 data-safety/restore gates are closed')
        if entry['requiredHostCapabilities']:raise InvalidRequestError('selected package requires a qualified node-image capability rollout before installation')
        cluster=self.kubernetes.get({'apiVersion':'cluster.x-k8s.io/v1beta2','kind':'Cluster','metadata':{'namespace':request['namespace'],'name':request['clusterName']}})
        metadata=cluster.get('metadata',{});labels=metadata.get('labels',{})
        if metadata.get('name')!=request['clusterName'] or metadata.get('namespace')!=request['namespace'] or labels.get('layersentry.io/managed')!='true' or labels.get('layersentry.io/project')!=request['projectId'] or metadata.get('deletionTimestamp'):
            raise InvalidRequestError('package target is not the exact live owned CAPI cluster')
        uid=metadata.get('uid')
        generation=metadata.get('generation')
        conditions=cluster.get('status',{}).get('conditions',[])
        if type(generation) is not int or not any(c.get('type') in ('Available','Ready') and c.get('status')=='True' and c.get('observedGeneration')==generation for c in conditions):
            raise InvalidRequestError('package target CAPI cluster has no current readiness observation')
        verify_remote_credentials(self.kubernetes,cluster,request['projectId'])
        resources=build_package_resources(request,entry,self.catalog.digest,uid)
        return request,entry,uid,resources

    @staticmethod
    def _ready(source,release,digest):
        return (source is not None and release is not None and flux_ready(source) and flux_ready(release)
                and source.get('status',{}).get('artifact',{}).get('revision')==digest
                and release.get('status',{}).get('lastAttemptedRevisionDigest')==digest)

    def reconcile(self,actor,request,*,inspect_only=False):
        request,entry,uid,resources=self._context(actor,request,'read' if inspect_only else 'install')
        for dependency in entry['dependsOn']:
            dependency_entry=self.catalog.resolve(dependency['package'],dependency['version'],dependency['profile'])
            refs=build_package_resources({**request,**dependency},dependency_entry,self.catalog.digest,uid)
            actual=[self._get(ref) for ref in refs]
            for ref,row in zip(refs,actual):
                if row is not None:self._owned(ref,row)
            if not self._ready(*actual,dependency_entry['chartDigest']):
                return StepResult(StepOutcome.PENDING,detail='waiting for the exact qualified package dependency')
        actual=[self._get(ref) for ref in resources]
        for ref,row in zip(resources,actual):
            if row is not None:self._owned(ref,row)
        if self._ready(*actual,entry['chartDigest']):
            return StepResult(StepOutcome.CONVERGED,{'package':{'name':entry['package'],'version':entry['version'],'chartDigest':entry['chartDigest'],'clusterUid':uid}},'native Flux reports exact current-generation package readiness')
        if inspect_only:return StepResult(StepOutcome.PENDING,detail='package is absent or not current-generation Ready')
        for ref,row in zip(resources,actual):
            if row is None:
                self.kubernetes.create(ref)
                return StepResult(StepOutcome.PENDING,detail='native Flux desired object submitted; readiness is pending')
            if row.get('metadata',{}).get('deletionTimestamp'):
                return StepResult(StepOutcome.PENDING,detail='owned package is being deleted; no replacement submitted')
            if not flux_ready(row):
                return StepResult(StepOutcome.PENDING,detail='waiting for native Flux source/controller readiness')
        return StepResult(StepOutcome.PENDING,detail='waiting for exact chart revision observation')

    def delete(self,actor,request):
        request,entry,uid,resources=self._context(actor,request,'delete')
        if entry['stateful']:
            raise InvalidRequestError('stateful uninstall requires the separately verified retention/backup workflow')
        if not entry['uninstallQualified']:
            raise InvalidRequestError('package uninstall/retention has not been qualified')
        identity={key:entry[key] for key in ('package','version','profile')}
        for dependent in self.catalog.entries.values():
            if identity not in dependent['dependsOn']:continue
            refs=build_package_resources({**request,**{key:dependent[key] for key in identity}},dependent,self.catalog.digest,uid)
            if any(self._get(ref) is not None for ref in refs):
                raise InvalidRequestError('another package still depends on this package; uninstall is blocked')
        # Native Helm finalization must finish before its immutable source is
        # removed. No finalizer removal, PVC deletion, or remote kubectl exists.
        for ref in reversed(resources):
            row=self._get(ref)
            if row is None:continue
            self._owned(ref,row)
            if not row.get('metadata',{}).get('deletionTimestamp'):self.kubernetes.delete_observed(row)
            return StepResult(StepOutcome.PENDING,detail='waiting for native Helm/source deletion observation')
        return StepResult(StepOutcome.CONVERGED,{'package':{'name':entry['package'],'state':'DELETED'}},'both owned Flux resources are absent')

    def observe_ambiguous(self,actor,request,*,deleting=False):
        # Native resources retain immutable request/cluster bindings. Reconcile
        # reads before any apply; delete also uses UID/resourceVersion fences.
        return self.delete(actor,request) if deleting else self.reconcile(actor,request)
