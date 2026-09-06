"""Read a release-approved immutable package catalog; never promote its gates."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import urllib.parse

from bootstrap.native import protected_file
from .components import _unique_object
from .model import InvalidRequestError

NAME = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$')
SHA = re.compile(r'^[a-f0-9]{64}$')
VERSION = re.compile(r'^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$')
FLUX_TUPLE = {'flux':'2.9.5','sourceController':'1.9.5','helmController':'1.6.4','kustomizeController':'1.9.5'}


def entry_key(entry):
    return entry['package'],entry['version'],entry['profile']


def _public_values(value,depth=0):
    if depth>20:raise InvalidRequestError('package profile values exceed nesting bound')
    if isinstance(value,dict):
        for key,nested in value.items():
            if not isinstance(key,str):raise InvalidRequestError('package profile keys must be strings')
            if re.search(r'password|private.?key|credential|token|kubeconfig',key,re.I):
                raise InvalidRequestError('package values must not contain runtime credentials')
            if 'secret' in key.lower() and not (key.endswith('Secret') or key.endswith('SecretName')):
                raise InvalidRequestError('only logical existing Secret references belong in package profiles')
            _public_values(nested,depth+1)
    elif isinstance(value,list):
        for nested in value:_public_values(nested,depth+1)
    elif value is not None and not isinstance(value,(str,bool,int,float)):
        raise InvalidRequestError('package profile values are not JSON')
    elif isinstance(value,float) and not math.isfinite(value):
        raise InvalidRequestError('package profile numbers must be finite')


class PackageCatalog:
    def __init__(self,path,trusted_digest):
        source=protected_file(path,private=False)
        if source.stat().st_size>1024**2 or not isinstance(trusted_digest,str) or not SHA.fullmatch(trusted_digest):
            raise InvalidRequestError('package catalog input is invalid')
        raw=source.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=trusted_digest:raise InvalidRequestError('package catalog differs from approved release digest')
        value=json.loads(raw,object_pairs_hook=_unique_object)
        if not isinstance(value,dict) or set(value)!={'schemaVersion','fluxVersions','platformRegistry','packages'} or value['schemaVersion']!='1.0' or value['fluxVersions']!=FLUX_TUPLE:
            raise InvalidRequestError('package catalog/schema differs from the audited Flux tuple')
        registry=value['platformRegistry']
        if not isinstance(registry,dict) or set(registry)!={'host','bootstrapIndependent','evidenceSha256'} or registry['bootstrapIndependent'] is not True or not SHA.fullmatch(str(registry['evidenceSha256'])):
            raise InvalidRequestError('package registry bootstrap independence has not been qualified')
        entries=value['packages']
        if not isinstance(entries,list) or len(entries)>128:raise InvalidRequestError('package catalog bound exceeded')
        self.entries={};self.digest=trusted_digest
        required={'package','version','profile','chartUrl','chartDigest','targetNamespace','values','stateful','qualified','uninstallQualified','evidenceSha256','requiredHostCapabilities','dependsOn'}
        for entry in entries:
            if not isinstance(entry,dict) or set(entry)!=required:raise InvalidRequestError('package profile fields differ from schema')
            if not all(isinstance(entry[k],str) and NAME.fullmatch(entry[k]) for k in ('package','profile','targetNamespace')) or not VERSION.fullmatch(str(entry['version'])):
                raise InvalidRequestError('package identity/version is invalid')
            if not isinstance(entry['chartUrl'],str):raise InvalidRequestError('package chart URL is invalid')
            parsed=urllib.parse.urlsplit(entry['chartUrl'])
            if parsed.scheme!='oci' or parsed.netloc!=registry['host'] or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or not re.fullmatch(r'/[a-z0-9][a-z0-9/_.-]*',parsed.path) or '..' in parsed.path.split('/'):
                raise InvalidRequestError('package chart must use the independent platform OCI registry')
            if not isinstance(entry['chartDigest'],str) or not re.fullmatch(r'sha256:[a-f0-9]{64}',entry['chartDigest']):raise InvalidRequestError('package chart digest is unresolved')
            if any(type(entry[k]) is not bool for k in ('stateful','qualified','uninstallQualified')) or not SHA.fullmatch(str(entry['evidenceSha256'])):
                raise InvalidRequestError('package qualification evidence is invalid')
            if not isinstance(entry['values'],dict):raise InvalidRequestError('package values must be a release-approved object')
            _public_values(entry['values'])
            if not isinstance(entry['requiredHostCapabilities'],list) or any(not isinstance(x,str) or not NAME.fullmatch(x) for x in entry['requiredHostCapabilities']):raise InvalidRequestError('host capability requirements are invalid')
            if not isinstance(entry['dependsOn'],list) or len(entry['dependsOn'])>16:raise InvalidRequestError('package dependency bound exceeded')
            for dep in entry['dependsOn']:
                if not isinstance(dep,dict) or set(dep)!={'package','version','profile'}:raise InvalidRequestError('package dependency is invalid')
                if not all(isinstance(dep[k],str) and NAME.fullmatch(dep[k]) for k in ('package','profile')) or not isinstance(dep['version'],str) or not VERSION.fullmatch(dep['version']):raise InvalidRequestError('package dependency identity is invalid')
            if len({dep['package'] for dep in entry['dependsOn']})!=len(entry['dependsOn']):raise InvalidRequestError('multiple profiles of one dependency cannot own the same release')
            key=entry_key(entry)
            if key in self.entries:raise InvalidRequestError('duplicate package profile')
            self.entries[key]=entry
        visited=set()
        def visit(key,chain):
            if key in chain:raise InvalidRequestError('package dependency cycle')
            if key in visited:return
            if key not in self.entries:raise InvalidRequestError('package dependency is absent from catalog')
            for dep in self.entries[key]['dependsOn']:visit(entry_key(dep),chain|{key})
            visited.add(key)
        for key in self.entries:visit(key,set())

    def resolve(self,package,version,profile):
        entry=self.entries.get((package,version,profile))
        if entry is None:raise InvalidRequestError('selected package/version/profile is unavailable')
        if not entry['qualified']:raise InvalidRequestError('selected package profile has not passed native reconciliation qualification')
        return entry
