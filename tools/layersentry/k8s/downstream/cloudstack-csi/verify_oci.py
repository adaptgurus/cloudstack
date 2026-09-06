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


INDEX = 'application/vnd.oci.image.index.v1+json'
MANIFEST = 'application/vnd.oci.image.manifest.v1+json'
SCANNER = 'ae4f3b554449e7e25548e7d8ccc029d17357348e30c6e3df01b92bc93654d6a9'


def verify_provenance(document, component, source_commit):
    approved = json.loads((Path(__file__).parent / 'manifest.json').read_text())
    upstream = approved['upstreamCommit']
    predicate = document.get('predicate', {})
    definition = predicate.get('buildDefinition', {})
    external = definition.get('externalParameters', {})
    request = external.get('request', {})
    expected_ldflags = (f'-s -w -X main.version=3.0.2-layersentry.{source_commit} '
        f'-X github.com/cloudstack/cloudstack-csi-driver/pkg/driver.driverVersion=3.0.2-layersentry.{source_commit} '
        f'-X github.com/cloudstack/cloudstack-csi-driver/pkg/driver.gitCommit={upstream}')
    expected_vcs = {'localdir:context': '.', 'localdir:dockerfile': 'cmd/' + component,
                    'revision': upstream, 'source': approved['upstreamRepository'].removesuffix('.git')}
    actual_vcs = predicate.get('runDetails', {}).get('metadata', {}).get('buildkit_metadata', {}).get('vcs')
    root_args = request.get('root', {}).get('request', {}).get('args', {})
    if (document.get('predicateType') != 'https://slsa.dev/provenance/v1'
            or actual_vcs != expected_vcs
            or external.get('configSource', {}).get('path') != 'Dockerfile'
            or request.get('frontend') != 'dockerfile.v0'
            or request.get('args', {}).get('build-arg:LDFLAGS') != expected_ldflags
            or root_args.get('build-arg:LDFLAGS') != expected_ldflags
            or any(root_args.get('vcs:' + key) != value for key, value in expected_vcs.items())):
        raise VerificationError('provenance does not bind the exact source, build arguments and Dockerfile')
    dependencies = definition.get('resolvedDependencies', [])
    expected = {}
    for name, digest in (('docker/buildkit-syft-scanner', SCANNER),
                         ('alpine', approved['buildImages']['runtime'].split('@sha256:')[1]),
                         ('golang', approved['buildImages']['builder'].split('@sha256:')[1])):
        expected[f'pkg:docker/{name}?digest=sha256:{digest}&platform=linux%2Famd64'] = {'sha256': digest}
    if (not isinstance(dependencies, list) or len(dependencies) != len(expected)
            or any(not isinstance(item, dict) or item.get('uri') not in expected
                   or item.get('digest') != expected[item['uri']] for item in dependencies)
            or len({item['uri'] for item in dependencies}) != len(expected)):
        raise VerificationError('provenance base/scanner dependency closure differs from approved inputs')
    return {'upstreamCommit': upstream, 'layersentryCommit': source_commit,
            'dockerfileDirectory': 'cmd/' + component, 'dependencyCount': len(expected),
            'predicateType': document['predicateType'], 'unsigned': True}


def verify(archive, docker_inspect, component, source_commit):
    if component not in {'cloudstack-csi-driver', 'cloudstack-csi-sc-syncer'} or not re.fullmatch('[a-f0-9]{40}', source_commit):
        raise VerificationError('invalid component or LayerSentry source commit')
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

    roots = index.get('manifests', [])
    if index.get('schemaVersion') != 2 or len(roots) != 1 or roots[0].get('mediaType') != INDEX:
        raise VerificationError('expected one retained OCI index, not a detached runtime manifest')
    root_digest = roots[0].get('digest')
    root = blobs.get(root_digest, (0, None))[1]
    if not isinstance(root, dict) or root.get('schemaVersion') != 2 or root.get('mediaType') != INDEX:
        raise VerificationError('invalid retained OCI index document')
    children = root.get('manifests', [])
    if len(children) != 2 or any(child.get('mediaType') != MANIFEST for child in children):
        raise VerificationError('expected one runtime and one attestation manifest')
    runtime_refs = [child for child in children if child.get('platform') == {'architecture': 'amd64', 'os': 'linux'}]
    attest_refs = [child for child in children if child.get('platform') == {'architecture': 'unknown', 'os': 'unknown'}]
    if len(runtime_refs) != 1 or len(attest_refs) != 1:
        raise VerificationError('OCI descriptor platform differs from linux/amd64 qualification')
    if attest_refs[0].get('annotations', {}) != {
        'vnd.docker.reference.digest': runtime_refs[0].get('digest'),
        'vnd.docker.reference.type': 'attestation-manifest',
    }:
        raise VerificationError('attestation manifest is not bound to the runtime descriptor')
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
    if image_digest != runtime_refs[0]['digest'] or reachable != set(blobs):
        raise VerificationError('OCI runtime descriptor differs or unreferenced blobs remain')
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
            if 'sbom' in attestations: raise VerificationError('duplicate SBOM attestation')
            attestations['sbom'] = {'digest': digest, 'document': document}
        elif predicate_type.startswith('https://slsa.dev/provenance/'):
            if 'provenance' in attestations: raise VerificationError('duplicate provenance attestation')
            attestations['provenance'] = {'digest': digest, 'document': document}
    if set(attestations) != {'sbom', 'provenance'}:
        raise VerificationError('SBOM or provenance attestation absent')
    attestation_manifest = blobs[attest_refs[0]['digest']][1]
    attestation_layers = attestation_manifest.get('layers', [])
    if (len(attestation_layers) != 2
            or any(layer.get('mediaType') != 'application/vnd.in-toto+json' for layer in attestation_layers)
            or {layer.get('digest') for layer in attestation_layers} != {entry['digest'] for entry in attestations.values()}):
        raise VerificationError('attestation index does not retain the exact SBOM and provenance layers')
    provenance_binding = verify_provenance(attestations['provenance']['document'], component, source_commit)
    return {
        'status': 'CI_VERIFIED', 'scope': 'OCI identity, attestation binding and isolated build smoke tests',
        'productionCertified': False, 'liveVerified': False, 'signed': False,
        'layersentrySourceCommit': source_commit, 'component': component,
        'archiveSha256': archive_hash.hexdigest(), 'archiveSizeBytes': archive.stat().st_size,
        'imageIndexDigest': root_digest, 'platform': 'linux/amd64',
        'provenanceSourceBinding': provenance_binding, 'imageManifestDigest': image_digest,
        'imageConfigDigest': config_digest, 'attestations': attestations,
    }



def verify_artifact_binding(result, lock):
    if (lock.get('schemaVersion') != '1.0' or lock.get('artifactType') != 'layersentry-csi-build-closure'
            or lock.get('layersentrySourceCommit') != result['layersentrySourceCommit']
            or lock.get('upstreamCommit') != result['provenanceSourceBinding']['upstreamCommit']):
        raise VerificationError('artifact lock source or schema differs from verified OCI evidence')
    expected = lock.get('images', {}).get(result['component'], {})
    for key in ('archiveSha256', 'archiveSizeBytes', 'imageIndexDigest', 'imageManifestDigest',
                'imageConfigDigest', 'platform', 'provenanceSourceBinding'):
        if expected.get(key) != result.get(key):
            raise VerificationError('verified OCI ' + key + ' differs from retained artifact lock')
    observed = {kind: {'digest': item['digest'], 'predicateType': item['document']['predicateType']}
                for kind, item in result['attestations'].items()}
    if expected.get('attestations') != observed:
        raise VerificationError('verified OCI attestation closure differs from retained artifact lock')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--inspect', type=Path, required=True)
    parser.add_argument('--component', choices=['cloudstack-csi-driver', 'cloudstack-csi-sc-syncer'], required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--artifact-lock', type=Path, help='also enforce the manifest-approved retained artifact lock')
    args = parser.parse_args()
    result = verify(args.archive, json.loads(args.inspect.read_text()), args.component, args.source_commit)
    if args.artifact_lock is not None:
        approved = json.loads((Path(__file__).parent / 'manifest.json').read_text())['buildArtifact']['sha256']
        with args.artifact_lock.open('rb') as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != approved:
            raise VerificationError('artifact lock differs from the downstream manifest approval')
        verify_artifact_binding(result, json.loads(raw))
        result['artifactLockSha256'] = approved
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'attestations'}, sort_keys=True))


if __name__ == '__main__':
    main()
