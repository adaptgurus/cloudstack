#!/usr/bin/env python3
"""Stage the reviewed CSI package closure; never resolve packages during build."""
import argparse
import hashlib
import json
import re
import shutil
import tempfile
import urllib.request
from pathlib import Path

MAX_PACKAGE_SIZE = 32 * 1024 * 1024
BASE_IMAGE = 'docker.io/library/alpine@sha256:48b0309ca019d89d40f670aa1bc06e426dc0931948452e8491e3d65087abc07d'


class LockError(ValueError):
    pass


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise LockError('duplicate lock key')
        result[key] = value
    return result


def checksums(packages):
    return ''.join(p['sha256'] + '  ' + p['file'] + '\n' for p in packages).encode()


def load_lock(path):
    lock = json.loads(path.read_text(), object_pairs_hook=unique_object)
    if lock.get('schemaVersion') != '1.0' or lock.get('runtimeImage') != BASE_IMAGE:
        raise LockError('unexpected schema or runtime base')
    if set(lock.get('architectures', {})) != {'amd64', 'arm64'}:
        raise LockError('unsupported architecture set')
    for arch, apkarch in [('amd64', 'x86_64'), ('arm64', 'aarch64')]:
        entry = lock['architectures'][arch]
        if entry.get('apkArchitecture') != apkarch or set(entry.get('profiles', {})) != {'driver', 'syncer'}:
            raise LockError('invalid architecture/profile mapping')
        for profile in entry['profiles'].values():
            packages = profile.get('packages', [])
            if not 1 <= len(packages) <= 100:
                raise LockError('invalid package count')
            names = []
            for item in packages:
                name = item.get('file', '')
                if not re.fullmatch(r'[a-z0-9][a-zA-Z0-9_.+-]*\.apk', name):
                    raise LockError('invalid package filename')
                if not re.fullmatch(r'[0-9a-f]{64}', item.get('sha256', '')):
                    raise LockError('invalid package digest')
                size = item.get('size')
                if type(size) is not int or not 0 < size <= MAX_PACKAGE_SIZE:
                    raise LockError('invalid package size')
                if item.get('url') != f'https://dl-cdn.alpinelinux.org/alpine/v3.21/main/{apkarch}/{name}':
                    raise LockError('package source outside approved Alpine release')
                names.append(name)
            if names != sorted(set(names)):
                raise LockError('duplicate or unordered packages')
            if hashlib.sha256(checksums(packages)).hexdigest() != profile.get('checksumsSha256'):
                raise LockError('checksum list differs from lock')
    return lock


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise LockError('package redirects are forbidden')


def copy_verified(stream, destination, item):
    digest = hashlib.sha256()
    remaining = item['size']
    with destination.open('xb') as output:
        while remaining:
            block = stream.read(min(1024 * 1024, remaining))
            if not block:
                raise LockError('truncated package')
            output.write(block)
            digest.update(block)
            remaining -= len(block)
        if stream.read(1):
            raise LockError('oversized package')
    if digest.hexdigest() != item['sha256']:
        raise LockError('package digest mismatch')


def prepare(lock, output, architecture, cache=None):
    # Publish a new complete directory atomically. No reuse of partial/untrusted trees.
    if output.exists() or output.is_symlink():
        raise LockError('output already exists; use a fresh staging directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.csi-apk-', dir=output.parent))
    opener = urllib.request.build_opener(NoRedirect())
    try:
        for profile, spec in lock['architectures'][architecture]['profiles'].items():
            target = staging / architecture / profile
            target.mkdir(parents=True)
            for item in spec['packages']:
                if cache is not None:
                    source = cache / architecture / profile / item['file']
                    if source.is_symlink() or not source.is_file():
                        raise LockError('missing or linked offline package')
                    stream = source.open('rb')
                else:
                    stream = opener.open(item['url'], timeout=30)
                with stream:
                    copy_verified(stream, target / item['file'], item)
            (target / 'SHA256SUMS').write_bytes(checksums(spec['packages']))
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lock', type=Path, default=Path(__file__).with_name('apk-lock.json'))
    parser.add_argument('--output', type=Path, required=True, help='fresh source/.layersentry-apk directory')
    parser.add_argument('--architecture', choices=['amd64', 'arm64'], required=True)
    parser.add_argument('--cache', type=Path, help='offline closure root; no network fallback')
    args = parser.parse_args()
    try:
        prepare(load_lock(args.lock), args.output, args.architecture, args.cache)
    except (LockError, OSError, ValueError) as exc:
        parser.exit(2, f'BLOCKED: {exc}\n')
    print('SOURCE_COMPLETE: verified package closure staged; image/runtime qualification remains required')


if __name__ == '__main__':
    main()
