#!/usr/bin/env python3
"""Materialize the locked Rocky/RKE2 input bundle without version resolution."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import shutil
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class InputError(ValueError):
    pass


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InputError('duplicate lock key')
        result[key] = value
    return result


def files(lock):
    return [lock['baseImage'], *lock['rke2Archives'], lock['selinuxRpm'], *lock['rpmPackages']]


def load_lock(path):
    lock = json.loads(path.read_text(), object_pairs_hook=unique)
    expected = {'schemaVersion': '1.0', 'artifactType': 'layersentry-rke2-node-image-inputs', 'os': 'rocky9', 'osVersion': '9.8', 'architecture': 'amd64', 'rke2Version': 'v1.36.4+rke2r1', 'cni': 'canal'}
    if any(lock.get(k) != v for k, v in expected.items()):
        raise InputError('unsupported image tuple')
    items = files(lock)
    if not 10 < len(items) < 1000:
        raise InputError('invalid input count')
    names = set()
    for item in items:
        name = item.get('file', '')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]*', name) or name in names:
            raise InputError('invalid or duplicate input filename')
        names.add(name)
        if not re.fullmatch('[a-f0-9]{64}', item.get('sha256', '')) or type(item.get('size')) is not int or not 0 < item['size'] <= 2 * 1024**3:
            raise InputError('invalid input integrity declaration')
        url = urllib.parse.urlsplit(item.get('url', ''))
        if url.scheme != 'https' or url.username or url.password or url.query or url.fragment or url.port:
            raise InputError('invalid artifact URL')
        if url.hostname == 'download.rockylinux.org':
            if not url.path.startswith(('/pub/rocky/9/images/x86_64/', '/pub/rocky/9.8/')):
                raise InputError('Rocky input outside fixed release')
        elif url.hostname == 'github.com':
            if not url.path.startswith(('/rancher/rke2/releases/download/v1.36.4%2Brke2r1/', '/rancher/rke2-selinux/releases/download/v0.23.latest.2/')):
                raise InputError('RKE2 input outside fixed release')
        else:
            raise InputError('unapproved artifact origin')
        if url.path.split('/')[-1] != name:
            raise InputError('artifact URL/name mismatch')
    for key in lock['trust']:
        path = ROOT / 'trust' / key['file']
        if path.parent != ROOT / 'trust' or hashlib.sha256(path.read_bytes()).hexdigest() != key['sha256']:
            raise InputError('trust root digest mismatch')
    return lock


class ApprovedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != 'https' or target.hostname not in {'release-assets.githubusercontent.com', 'objects.githubusercontent.com'} or target.username or target.password or target.port:
            raise InputError('artifact redirect outside approved HTTPS CDN')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def verify_file(path, item):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != item['size']:
        raise InputError('missing, linked or wrong-size input: ' + item['file'])
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest() != item['sha256']:
        raise InputError('input digest mismatch: ' + item['file'])


def prepare(lock, output, cache=None):
    if output.exists() or output.is_symlink():
        raise InputError('output exists; use a fresh input staging directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.node-inputs-', dir=output.parent))
    def fetch(item):
        target = staging / item['file']
        if cache is not None:
            source = cache / item['file']
            verify_file(source, item)
            shutil.copyfile(source, target)
        else:
            opener = urllib.request.build_opener(ApprovedRedirect())
            req = urllib.request.Request(item['url'], headers={'User-Agent': 'curl/8.0 LayerSentry-build'})
            with opener.open(req, timeout=60) as stream, target.open('xb') as destination:
                remaining = item['size']
                while remaining:
                    block = stream.read(min(1024 * 1024, remaining))
                    if not block:
                        raise InputError('truncated input: ' + item['file'])
                    destination.write(block)
                    remaining -= len(block)
                if stream.read(1):
                    raise InputError('oversized input: ' + item['file'])
        verify_file(target, item)
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(fetch, files(lock)))
        shutil.copytree(ROOT / 'trust', staging / 'trust')
        (staging / 'inputs.lock.json').write_text(json.dumps(lock, indent=2) + '\n')
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, default=ROOT / 'cpu-rocky9-rke2-lock.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cache', type=Path, help='offline flat input directory; never falls back to networking')
    args = parser.parse_args()
    prepare(load_lock(args.lock), args.output, args.cache)
    print('SOURCE_COMPLETE: locked input bundle verified; image qualification remains NOT_TESTED')


if __name__ == '__main__':
    main()
