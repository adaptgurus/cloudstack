#!/usr/bin/env python3
"""Build an unqualified CPU QCOW2 offline from an integrity-checked input bundle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from prepare_inputs import ROOT, InputError, files, load_lock, verify_file


def run(argv, *, timeout=1800, stdout=None, env=None):
    return subprocess.run(argv, check=True, timeout=timeout, stdout=stdout, env=env)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def validate_binary_archive(path):
    names = set()
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            name = member.name.rstrip('/')
            parts = Path(name).parts
            if name in names or not parts or parts[0] not in {'bin', 'lib', 'share'} or '..' in parts or name.startswith('/') or not (member.isfile() or member.isdir()):
                raise InputError('unsafe RKE2 binary archive member')
            if member.size > 256 * 1024 * 1024:
                raise InputError('oversized RKE2 archive member')
            names.add(name)
    if 'bin/rke2' not in names or 'lib/systemd/system/rke2-server.service' not in names:
        raise InputError('RKE2 binary archive is incomplete')


def build(inputs, output):
    inputs = inputs.resolve(strict=True)
    if output.exists() or output.is_symlink():
        raise InputError('output already exists; refusing image overwrite')
    lock = load_lock(ROOT / 'cpu-rocky9-rke2-lock.json')
    if json.loads((inputs / 'inputs.lock.json').read_text()) != lock:
        raise InputError('staged input lock differs from source')
    for item in files(lock):
        verify_file(inputs / item['file'], item)
    for key in lock['trust']:
        if sha256(inputs / 'trust' / key['file']) != key['sha256']:
            raise InputError('staged trust key mismatch')
    for tool in ['qemu-img', 'virt-customize', 'virt-cat', 'virt-ls', 'gpg']:
        if not shutil.which(tool):
            raise InputError('required image builder tool missing: ' + tool)
    validate_binary_archive(inputs / 'rke2.linux-amd64.tar.gz')
    output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='.cpu-image-', dir=output.parent))
    env = dict(os.environ, LIBGUESTFS_BACKEND='direct')
    try:
        gpg_dir = work / 'gpg'
        gpg_dir.mkdir(mode=0o700)
        run(['gpg', '--homedir', str(gpg_dir), '--batch', '--import', str(inputs / 'trust/RPM-GPG-KEY-Rocky-9')], timeout=60)
        checksum = inputs / 'trust' / (lock['baseImage']['file'] + '.CHECKSUM')
        run(['gpg', '--homedir', str(gpg_dir), '--batch', '--verify', str(checksum) + '.asc', str(checksum)], timeout=60)
        expected_line = f"SHA256 ({lock['baseImage']['file']}) = {lock['baseImage']['sha256']}"
        if expected_line not in checksum.read_text().splitlines():
            raise InputError('signed Rocky checksum does not bind the selected base')
        image = work / 'layersentry-rke2-rocky9-amd64.qcow2'
        run(['qemu-img', 'convert', '-f', 'qcow2', '-O', 'qcow2', str(inputs / lock['baseImage']['file']), str(image)])
        payload = work / 'layersentry-node-inputs'
        payload.mkdir()
        for item in [*lock['rke2Archives'], lock['selinuxRpm'], *lock['rpmPackages']]:
            os.link(inputs / item['file'], payload / item['file'])
        shutil.copytree(inputs / 'trust', payload / 'trust')
        shutil.copyfile(inputs / 'inputs.lock.json', payload / 'inputs.lock.json')
        log = work / 'customize.log'
        with log.open('wb') as stream:
            run(['virt-customize', '--format', 'qcow2', '-a', str(image), '--no-network', '--memsize', '4096', '--smp', '2', '--copy-in', f'{payload}:/opt', '--run', str(ROOT / 'customize_guest.sh'), '--selinux-relabel'], timeout=2400, stdout=stream, env=env)
        run(['qemu-img', 'check', '-f', 'qcow2', str(image)])
        inventory = work / 'rpm-inventory.tsv'
        version = work / 'rke2-version.txt'
        for destination, guest_path in [(inventory, '/usr/share/layersentry/node-image/rpm-inventory.tsv'), (version, '/usr/share/layersentry/node-image/rke2-version.txt')]:
            with destination.open('wb') as stream:
                run(['virt-cat', '--format', 'qcow2', '-a', str(image), guest_path], timeout=180, stdout=stream, env=env)
        if 'v1.36.4+rke2r1' not in version.read_text():
            raise InputError('installed RKE2 version mismatch')
        with (work / 'qemu-image-info.json').open('wb') as stream:
            run(['qemu-img', 'info', '--output=json', str(image)], timeout=60, stdout=stream)
        # No volatile VM/template identity or invented runtime facts belong here.
        source = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True, timeout=30).strip()
        manifest = {'schemaVersion': '1.0', 'artifactType': 'layersentry-rke2-node-image', 'status': 'CI_VERIFIED', 'qualificationStatus': 'NOT_TESTED', 'sourceCommit': source, 'os': 'rocky9', 'osVersion': '9.8', 'architecture': 'amd64', 'rke2Version': lock['rke2Version'], 'cni': 'canal', 'sha256': sha256(image), 'sizeBytes': image.stat().st_size, 'inputLockSha256': sha256(ROOT / 'cpu-rocky9-rke2-lock.json'), 'rpmInventorySha256': sha256(inventory), 'rke2Installed': True, 'rke2Started': False, 'runtimeQualified': False, 'signed': False, 'templateId': None, 'qualificationEvidenceSha256': None, 'hostBootTested': False, 'joinTested': False, 'storageTested': False}
        (work / 'candidate-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        for tool in ['qemu-img', 'virt-customize', 'virt-cat']:
            with (work / (tool + '-version.txt')).open('wb') as stream:
                run([tool, '--version'], timeout=30, stdout=stream)
        shutil.rmtree(payload)
        shutil.rmtree(gpg_dir)
        work.rename(output)
        print(json.dumps(manifest, sort_keys=True))
    except BaseException:
        # Keep failure logs for diagnosis, but never publish a partial image as output.
        if (work / 'customize.log').exists():
            shutil.copyfile(work / 'customize.log', output.parent / 'failed-customize.log')
        raise
    finally:
        if work.exists():
            shutil.rmtree(work)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.inputs, args.output)


if __name__ == '__main__':
    main()
