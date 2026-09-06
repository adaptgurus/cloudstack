"""Bounded native package reconciliation; Flux remains the Helm lifecycle owner."""
from __future__ import annotations

from copy import deepcopy
import json

from .flux_resources import desired_matches,flux_ready
from .model import InvalidRequestError,NotFoundError
from .package_resources import normalize_request,build_package_resources,verify_remote_credentials
from .service import StepOutcome,StepResult


class PackageExecutor:
    def __init__(self,kubernetes,authorizer,catalog,gates,previous_catalogs=()):
        self.kubernetes,self.authorizer,self.catalog,self.gates=kubernetes,authorizer,catalog,gates
        self.catalogs={item.digest:item for item in (catalog,*previous_catalogs)}
        if len(self.catalogs)!=1+len(previous_catalogs):
            raise InvalidRequestError('duplicate approved catalog revision')

    def _get(self,resource):
        try:return self.kubernetes.get(resource)
        except NotFoundError:return None

    @staticmethod
    def _owned(desired,actual):
        metadata=actual.get('metadata',{})
        expected=desired['metadata']
        if metadata.get('name')!=expected['name'] or metadata.get('namespace')!=expected['namespace'] or not desired_matches(expected['labels'],metadata.get('labels',{})) or not desired_matches(expected['annotations'],metadata.get('annotations',{})):
            raise InvalidRequestError('package resource ownership or immutable request binding changed')
        observed=deepcopy(actual.get('spec',{}))
        # Exact Flux 2.9.5 CRD default for OCIRepository/v1. No other
        # additional spec fields are expected for these generated resources;
        # Helm valuesFrom/postRenderers/impersonation overrides are forbidden.
        if desired['kind']=='OCIRepository' and observed.get('provider')=='generic' and 'provider' not in desired['spec']:
            observed.pop('provider')
        if json.dumps(desired['spec'],sort_keys=True,separators=(',',':')) != json.dumps(observed,sort_keys=True,separators=(',',':')):
            raise InvalidRequestError('package desired state drifted; automatic retarget/upgrade is prohibited')

    def _context(self,actor,request,action,catalog_digest=None):
        request=normalize_request(request)
        self.authorizer.require(actor,'kubernetes.package.'+action,request['projectId'])
        return self._resolve_context(request,catalog_digest)

    def _resolve_context(self,request,catalog_digest=None):
        request=normalize_request(request)
        catalog=self.catalogs.get(catalog_digest or self.catalog.digest)
        if catalog is None:raise InvalidRequestError('accepted package catalog revision is unavailable; restore its approved runtime binding')
        if not self.gates.kubernetes_ready():raise InvalidRequestError('central Flux/base Kubernetes live qualification is incomplete')
        entry=catalog.resolve(request['package'],request['version'],request['profile'])
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
        resources=build_package_resources(request,entry,catalog.digest,uid)
        return request,entry,uid,resources,catalog

    @staticmethod
    def _ready(source,release,digest):
        return (source is not None and release is not None and flux_ready(source) and flux_ready(release)
                and source.get('status',{}).get('artifact',{}).get('revision')==digest
                and release.get('status',{}).get('lastAttemptedRevisionDigest')==digest)

    def reconcile(self,actor,request,*,inspect_only=False,catalog_digest=None):
        context=self._context(actor,request,'read' if inspect_only else 'install',catalog_digest)
        return self._reconcile_context(context,inspect_only=inspect_only)

    def _missing_dependency(self,context):
        request,entry,uid,resources,catalog=context
        for dependency in entry['dependsOn']:
            dependency_entry=catalog.resolve(dependency['package'],dependency['version'],dependency['profile'])
            refs=build_package_resources({**request,**dependency},dependency_entry,catalog.digest,uid)
            actual=[self._get(ref) for ref in refs]
            for ref,row in zip(refs,actual):
                if row is not None:self._owned(ref,row)
            if not self._ready(*actual,dependency_entry['chartDigest']):
                return dependency['package']+'@'+dependency['version']+'/'+dependency['profile']
        return None

    def _require_no_dependents(self,context):
        request,entry,uid,resources,catalog=context
        identity={key:entry[key] for key in ('package','version','profile')}
        for approved in self.catalogs.values():
          for dependent in approved.entries.values():
            if identity not in dependent['dependsOn']:continue
            refs=build_package_resources({**request,**{key:dependent[key] for key in identity}},dependent,approved.digest,uid)
            if any(self._get(ref) is not None for ref in refs):
                raise InvalidRequestError('uninstall dependent package '+dependent['package']+' before this package')

    def _reconcile_context(self,context,*,inspect_only=False):
        request,entry,uid,resources,catalog=context
        missing=self._missing_dependency(context)
        if missing is not None:
            return StepResult(StepOutcome.PENDING,detail='waiting for exact qualified dependency '+missing)
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

    def delete(self,actor,request,*,catalog_digest=None):
        return self._delete_context(self._context(actor,request,'delete',catalog_digest))

    @staticmethod
    def _require_uninstall(entry):
        if entry['stateful']:
            raise InvalidRequestError('stateful uninstall requires the separately verified retention/backup workflow')
        if not entry['uninstallQualified']:
            raise InvalidRequestError('package uninstall/retention has not been qualified')

    def _delete_context(self,context):
        request,entry,uid,resources,catalog=context
        self._require_uninstall(entry)
        self._require_no_dependents(context)
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

    def prepare(self,actor,request,action,*,catalog_digest=None):
        if action not in ('install','delete'):
            raise InvalidRequestError('unsupported package operation')
        context=self._context(actor,request,action,catalog_digest)
        if action=='delete':
            self._require_uninstall(context[1])
            self._require_no_dependents(context)
        else:
            if context[4].digest!=self.catalog.digest:
                raise InvalidRequestError('new installs require the active approved catalog revision')
            missing=self._missing_dependency(context)
            if missing is not None:raise InvalidRequestError('install and qualify dependency '+missing+' before this package')
        for ref in context[3]:
            row=self._get(ref)
            if row is not None:self._owned(ref,row)
        # Persist only the immutable approval boundary, never credentials or a
        # browser session. The single worker acts on accepted durable intent.
        return {'catalogSha256':context[4].digest,'clusterUid':context[2]}

    def reconcile_operation(self,operation,step):
        action=operation.kind.removeprefix('kubernetes.package.')
        if action not in ('install','delete') or step.get('owner')!='Flux' or step.get('action')!=action:
            raise InvalidRequestError('package operation plan differs from accepted action')
        if set(operation.request)!={'packageRequest','binding'}:
            raise InvalidRequestError('package durable request differs from schema')
        request=normalize_request(operation.request['packageRequest'])
        if operation.project_id!=request['projectId'] or operation.target_name!=request['clusterName']:
            raise InvalidRequestError('package operation target differs from durable scope')
        binding=operation.request['binding']
        if not isinstance(binding,dict) or set(binding)!={'catalogSha256','clusterUid'} or binding['catalogSha256'] not in self.catalogs:
            return StepResult(StepOutcome.FAILED,detail='accepted package catalog is unavailable; restore its approved runtime binding')
        context=self._resolve_context(request,binding['catalogSha256'])
        expected={'catalogSha256':context[4].digest,'clusterUid':context[2]}
        if operation.request['binding']!=expected:
            return StepResult(StepOutcome.FAILED,detail='accepted package catalog or cluster incarnation changed; no mutation submitted')
        if action=='install':
            missing=self._missing_dependency(context)
            if missing is not None:
                return StepResult(StepOutcome.FAILED,detail='dependency readiness changed; reconcile '+missing+' before resubmission')
        return self._delete_context(context) if action=='delete' else self._reconcile_context(context)

    def catalog_status(self):
        rows=[]
        for catalog in self.catalogs.values():
          for entry in catalog.entries.values():
            blockers=[]
            if catalog.digest!=self.catalog.digest:blockers.append('Historical catalog revision is available for existing release lifecycle only')
            if not self.gates.kubernetes_ready():blockers.append('Kubernetes/central Flux live qualification is incomplete')
            if not entry['qualified']:blockers.append('Package profile has not passed native qualification')
            if entry['stateful'] and not self.gates.stateful_ready():blockers.append('Stateful data-safety and restore gates are incomplete')
            if entry['requiredHostCapabilities']:blockers.append('Qualified node capability rollout is required')
            rows.append({key:entry[key] for key in ('package','version','profile','stateful')} |
                        {'catalogSha256':catalog.digest,'available':not blockers,'blockers':blockers})
        return {'catalogSha256':self.catalog.digest,'packages':rows}
