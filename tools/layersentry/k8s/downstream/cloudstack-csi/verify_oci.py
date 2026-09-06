#!/usr/bin/env python3
"""Check OCI content, smoke-image identity and retained SBOM/provenance subjects."""
import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path


class VerificationError(ValueError):
    pass


def verify(archive, docker_inspect, component, source_commit):
    blobs = {}
    archive_hash = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            archive_hash.update(block)
    with tarfile.open(archive) as tar:
        seen = set()
        for member in tar:
            if member.isdir():
                continue
            if not member.isfile() or member.name in seen:
                raise VerificationError('duplicate or non-regular OCI member')
            seen.add(member.name)
            if member.name in ('index.json', 'oci-layout'):
                if member.size > 1024 * 1024:
                    raise VerificationError('oversized OCI index')
                tar.extractfile(member).read()
                continue
            if not re.fullmatch(r'blobs/sha256/[a-f0-9]{64}', member.name) or member.size > 512 * 1024 * 1024:
                raise VerificationError('invalid or oversized OCI blob')
            digest = hashlib.sha256()
            stream = tar.extractfile(member)
            content = bytearray() if member.size <= 32 * 1024 * 1024 else None
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
                if content is not None:
                    content.extend(block)
            sha = digest.hexdigest()
            if member.name != 'blobs/sha256/' + sha:
                raise VerificationError('OCI blob digest mismatch')
            try:
                document = json.loads(content) if content is not None else None
            except (UnicodeDecodeError, json.JSONDecodeError):
                document = None
            blobs['sha256:' + sha] = (member.size, document)
        index = json.load(tar.extractfile('index.json'))
        if json.load(tar.extractfile('oci-layout')).get('imageLayoutVersion') != '1.0.0':
            raise VerificationError('unsupported OCI layout')

    reachable = set()
    def walk(descriptor):
        digest = descriptor.get('digest')
        if digest not in blobs or descriptor.get('size') != blobs[digest][0]:
            raise VerificationError('missing blob or descriptor size mismatch')
        if digest in reachable:
            return
        reachable.add(digest)
        document = blobs[digest][1]
        if isinstance(document, dict):
            for child in document.get('manifests', []):
                walk(child)
            if document.get('schemaVersion') == 2 and 'layers' in document:
                walk(document['config'])
            for child in document.get('layers', []):
                walk(child)
    for descriptor in index.get('manifests', []):
        walk(descriptor)
    images = []
    for digest in reachable:
        document = blobs[digest][1]
        if isinstance(document, dict) and document.get('schemaVersion') == 2 and 'config' in document and 'layers' in document:
            config_digest = document['config']['digest']
            config = blobs[config_digest][1]
            if config.get('architecture') == 'amd64' and config.get('os') == 'linux':
                images.append((digest, config_digest, config))
    if len(images) != 1:
        raise VerificationError('expected exactly one linux/amd64 runtime image')
    image_digest, config_digest, config = images[0]
    if len(docker_inspect) != 1 or docker_inspect[0].get('Id') != config_digest:
        raise VerificationError('smoke-tested Docker image differs from retained OCI image')
    if config.get('config', {}).get('Entrypoint') != ['/' + component]:
        raise VerificationError('unexpected image entrypoint')
    attestations = {}
    for digest in reachable:
        document = blobs[digest][1]
        if not isinstance(document, dict) or 'predicateType' not in document:
            continue
        if not any(s.get('digest', {}).get('sha256') == image_digest.split(':')[1] for s in document.get('subject', [])):
            raise VerificationError('attestation subject differs from runtime image')
        predicate_type = document['predicateType']
        if predicate_type == 'https://spdx.dev/Document':
            if not document.get('predicate', {}).get('packages'):
                raise VerificationError('SBOM contains no packages')
            attestations['sbom'] = {'digest': digest, 'document': document}
        elif predicate_type.startswith('https://slsa.dev/provenance/'):
            attestations['provenance'] = {'digest': digest, 'document': document}
    if set(attestations) != {'sbom', 'provenance'}:
        raise VerificationError('SBOM or provenance attestation absent')
    if not re.fullmatch('[a-f0-9]{40}', source_commit):
        raise VerificationError('invalid LayerSentry source commit')
    return {
        'status': 'CI_VERIFIED', 'scope': 'OCI identity, attestation binding and isolated build smoke tests',
        'productionCertified': False, 'liveVerified': False, 'signed': False,
        'layersentrySourceCommit': source_commit, 'component': component,
        'archiveSha256': archive_hash.hexdigest(), 'imageManifestDigest': image_digest,
        'imageConfigDigest': config_digest, 'attestations': attestations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--inspect', type=Path, required=True)
    parser.add_argument('--component', choices=['cloudstack-csi-driver', 'cloudstack-csi-sc-syncer'], required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.archive, json.loads(args.inspect.read_text()), args.component, args.source_commit)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'attestations'}, sort_keys=True))


if __name__ == '__main__':
    main()
