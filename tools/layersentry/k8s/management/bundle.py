"""Digest-bound immutable management bundle shared by prepare and install."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tarfile

from bootstrap.native import protected_file
from controller.model import InvalidRequestError

DIGEST = re.compile(r'^sha256:[a-f0-9]{64}$')
SHA = re.compile(r'^[a-f0-9]{64}$')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def safe_file(root, relative, *, limit=2 * 1024**3):
    if not isinstance(relative, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]{0,240}', relative) or '..' in relative.split('/'):
        raise InvalidRequestError('bundle path is invalid')
    path = root / relative
    info = path.lstat()
    if path.resolve() != path or not path.is_relative_to(root) or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o022 or info.st_uid not in (0, os.geteuid()) or info.st_nlink != 1 or info.st_size > limit:
        raise InvalidRequestError('bundle file ownership, type or size is unsafe')
    return path


def verify_oci(path, expected_image):
    """Retain the complete named index and verify every referenced OCI byte."""
    digest = expected_image.rsplit('@', 1)[-1]
    if not DIGEST.fullmatch(digest):
        raise InvalidRequestError('bundle image must use an immutable digest')
    blobs = {}
    with tarfile.open(path) as archive:
        seen = set()
        for item in archive:
            if item.isdir():continue
            if not item.isfile() or item.name in seen or item.size > 512*1024**2:
                raise InvalidRequestError('unsafe OCI archive member')
            seen.add(item.name)
            if item.name in ('index.json', 'oci-layout'):
                if item.size > 1024**2:raise InvalidRequestError('oversized OCI index')
                continue
            if not re.fullmatch(r'blobs/sha256/[a-f0-9]{64}', item.name):
                raise InvalidRequestError('unexpected OCI archive member')
            stream = archive.extractfile(item); hashed = hashlib.sha256(); raw = bytearray() if item.size < 16*1024**2 else None
            for chunk in iter(lambda: stream.read(1024*1024), b''):
                hashed.update(chunk)
                if raw is not None:raw.extend(chunk)
            if hashed.hexdigest() != item.name.rsplit('/',1)[1]:raise InvalidRequestError('OCI content digest mismatch')
            try: document = json.loads(raw) if raw is not None else None
            except (ValueError, UnicodeError):document = None
            blobs['sha256:'+hashed.hexdigest()] = (item.size,document)
        index = json.load(archive.extractfile('index.json'))
        if json.load(archive.extractfile('oci-layout')).get('imageLayoutVersion') != '1.0.0':raise InvalidRequestError('unsupported OCI layout')
    roots = index.get('manifests', [])
    if len(roots) != 1 or roots[0].get('digest') != digest:raise InvalidRequestError('OCI archive root differs from pinned image')
    visited = set()
    def walk(desc):
        key = desc.get('digest')
        if key not in blobs or desc.get('size') != blobs[key][0]:raise InvalidRequestError('OCI descriptor content is absent')
        if key in visited:return
        visited.add(key); document = blobs[key][1]
        if isinstance(document, dict):
            for child in document.get('manifests',[]):walk(child)
            if document.get('schemaVersion') == 2 and 'layers' in document:
                walk(document['config'])
                for child in document['layers']:walk(child)
    walk(roots[0])
    if not any(isinstance(blobs[key][1],dict) and blobs[key][1].get('architecture')=='amd64' and blobs[key][1].get('os')=='linux' for key in visited):
        raise InvalidRequestError('OCI archive contains no Linux amd64 runtime')


class Bundle:
    def __init__(self, directory, digest):
        self.root = Path(directory)
        if not self.root.is_absolute() or self.root.resolve() != self.root or not SHA.fullmatch(digest):
            raise InvalidRequestError('management bundle identity is invalid')
        self.digest = digest
        manifest = protected_file(self.root/'bundle.json',private=False)
        if sha256(manifest) != digest:raise InvalidRequestError('management bundle manifest digest changed')
        self.value = json.loads(manifest.read_bytes())
        expected = {'schemaVersion','status','productionCertified','rke2Version','files','images','providers','deployments','crds','namespaceNames','sourceLockSha256'}
        if set(self.value) != expected or self.value['schemaVersion']!='1.0' or self.value['status'] not in ('SOURCE_COMPLETE','CI_VERIFIED') or self.value['productionCertified'] is not False or self.value['rke2Version']!='v1.36.4+rke2r1':
            raise InvalidRequestError('management bundle qualification contract is invalid')
        lock_path = Path(__file__).with_name('inputs.lock.json')
        if self.value['sourceLockSha256'] != sha256(lock_path):
            raise InvalidRequestError('management bundle does not match the pinned source release tuple')
        lock = json.loads(lock_path.read_bytes())
        expected_images = {item['image'] for item in lock['images']} | {item['componentBinding']['image'] for item in lock['downstream']['components']}
        if {item.get('image') for item in self.value['images']} != expected_images:
            raise InvalidRequestError('management bundle image closure differs from the pinned release tuple')
        files = self.value['files']
        if not isinstance(files,dict) or not 10 <= len(files) <= 80:raise InvalidRequestError('management bundle file inventory is invalid')
        for name, item in files.items():
            path = safe_file(self.root,name)
            if not isinstance(item,dict) or set(item)!={'sha256','size'} or path.stat().st_size != item['size'] or sha256(path)!=item['sha256']:
                raise InvalidRequestError('management bundle file digest mismatch')
        images = self.value['images']
        if not isinstance(images,list) or len(images)!=8 or len({image['image'] for image in images})!=8:
            raise InvalidRequestError('management provider image closure is incomplete')
        for image in images:
            if set(image)!={'image','file','sha256','activate'} or image['file'] not in files or image['sha256']!=files[image['file']]['sha256']:
                raise InvalidRequestError('management image archive binding is invalid')
            if image['activate'] is not (not image['image'].startswith('layersentry.local/cloudstack-ccm@')):
                raise InvalidRequestError('management image activation gate differs from the approved tuple')
            verify_oci(self.root/image['file'],image['image'])
        if [(p['name'],p['type'],p['version'],p['label'],p['namespace']) for p in self.value['providers']] != [('cluster-api','CoreProvider','v1.13.5','cluster-api','capi-system'),('rke2','BootstrapProvider','v0.25.2','bootstrap-rke2','rke2-bootstrap-system'),('rke2','ControlPlaneProvider','v0.25.2','control-plane-rke2','rke2-control-plane-system'),('cloudstack','InfrastructureProvider','v0.6.1','infrastructure-cloudstack','capc-system')]:
            raise InvalidRequestError('management provider contract is incomplete')

    def file(self, name):
        if name not in self.value['files']:raise InvalidRequestError('file is outside management bundle')
        return safe_file(self.root,name)
