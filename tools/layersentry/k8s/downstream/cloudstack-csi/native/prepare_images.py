#!/usr/bin/env python3
"""Collect locked OCI archives for review; read-only HTTPS, no publish/import/apply."""
import argparse
import hashlib
import gzip
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.request

from render import ROOT, json_bytes, locked_inputs, require, sha
sys.path.insert(0, str(ROOT.parent))
from verify_oci import verify, verify_artifact_binding


class TLSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require(newurl.startswith('https://'), 'registry redirect must retain TLS')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_blob(repository, descriptor, destination):
    require(repository.startswith('registry.k8s.io/sig-storage/'), 'unapproved registry')
    digest, size = descriptor['digest'], descriptor['size']
    require(digest.startswith('sha256:') and len(digest) == 71 and 0 < size <= 200 * 1024 * 1024, 'invalid blob descriptor')
    url = 'https://' + repository.split('/')[0] + '/v2/' + repository.split('/', 1)[1] + '/blobs/' + digest
    hashed, count, deadline = hashlib.sha256(), 0, time.monotonic() + 300
    opener = urllib.request.build_opener(TLSRedirect())
    with opener.open(url, timeout=30) as response, destination.open('xb') as output:
        require(response.geturl().startswith('https://'), 'registry response must retain TLS')
        while True:
            block = response.read(min(1024 * 1024, size - count + 1))
            if not block:
                break
            count += len(block)
            require(count <= size and time.monotonic() < deadline, 'registry transfer exceeds bound')
            hashed.update(block)
            output.write(block)
    require(count == size and 'sha256:' + hashed.hexdigest() == digest, 'registry blob content differs')


def write_archive(path, files):
    # Fixed metadata and ordering; image layers/manifests are never reencoded.
    with tarfile.open(path, 'w', format=tarfile.USTAR_FORMAT) as archive:
        for name, source in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.mode = 0o644
            if isinstance(source, Path):
                info.size = source.stat().st_size
                with source.open('rb') as stream:
                    archive.addfile(info, stream)
            else:
                info.size = len(source)
                archive.addfile(info, io.BytesIO(source))


def verify_sidecar_archive(path, item):
    """Verify tar inventory, exact OCI runtime closure and uncompressed layer diff IDs."""
    with tarfile.open(path, 'r:') as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        require(len(names) == len(set(names)) and all(member.isfile() for member in members), 'invalid OCI archive inventory')
        def raw(name):
            require(archive.getmember(name).size <= 4 * 1024 * 1024, 'oversized OCI metadata')
            return archive.extractfile(name).read()
        require(json.loads(raw('oci-layout')) == {'imageLayoutVersion': '1.0.0'}, 'invalid OCI layout')
        index = json.loads(raw('index.json'))
        require(len(index['manifests']) == 1 and index['manifests'][0]['digest'] == item['runtimeManifestDigest'], 'wrong runtime root')
        root_name = 'blobs/sha256/' + item['runtimeManifestDigest'][7:]
        runtime_raw = raw(root_name)
        require(len(runtime_raw) == index['manifests'][0]['size'], 'runtime descriptor size differs')
        require(hashlib.sha256(runtime_raw).hexdigest() == item['runtimeManifestDigest'][7:], 'runtime digest differs')
        runtime = json.loads(runtime_raw)
        require(runtime['config']['digest'] == item['configDigest'] and runtime['layers'] == item['layers'], 'runtime descriptors differ')
        config_name = 'blobs/sha256/' + item['configDigest'][7:]
        config_raw = raw(config_name)
        require(len(config_raw) == runtime['config']['size'], 'config descriptor size differs')
        require(hashlib.sha256(config_raw).hexdigest() == item['configDigest'][7:], 'config digest differs')
        config = json.loads(config_raw)
        require(config['architecture'] == 'amd64' and config['os'] == 'linux', 'wrong runtime platform')
        expected = {'oci-layout', 'index.json', root_name, config_name}
        diff_ids = []
        for descriptor in runtime['layers']:
            name = 'blobs/sha256/' + descriptor['digest'][7:]
            expected.add(name)
            require(archive.getmember(name).size == descriptor['size'], 'layer size differs')
            compressed_hash = hashlib.sha256()
            with archive.extractfile(name) as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    compressed_hash.update(chunk)
            require('sha256:' + compressed_hash.hexdigest() == descriptor['digest'], 'layer digest differs')
            require(descriptor['mediaType'].endswith('.tar.gzip') or descriptor['mediaType'].endswith('.tar+gzip'), 'unsupported layer compression')
            diff_hash, count = hashlib.sha256(), 0
            with archive.extractfile(name) as stream, gzip.GzipFile(fileobj=stream) as inflated:
                for chunk in iter(lambda: inflated.read(1024 * 1024), b''):
                    count += len(chunk)
                    require(count <= 1024 * 1024 * 1024, 'uncompressed layer exceeds bound')
                    diff_hash.update(chunk)
            diff_ids.append('sha256:' + diff_hash.hexdigest())
        require(set(names) == expected, 'orphan or missing OCI archive bytes')
        require(config['rootfs']['diff_ids'] == diff_ids, 'uncompressed layer identity differs')
    return {'runtimeDigest': item['runtimeManifestDigest'], 'layerCount': len(diff_ids), 'diffIdsVerified': True}


def collect(output, artifact_directory, fetch=download_blob):
    lock, artifact = locked_inputs()
    output.mkdir(parents=True, exist_ok=False)
    evidence = output / 'registry-evidence'
    shutil.copytree(ROOT / 'registry-evidence', evidence)
    shutil.copy2(ROOT / 'inputs.lock.json', output / 'inputs.lock.json')
    shutil.copy2(ROOT.parent / 'artifact-lock.json', output / 'artifact-lock.json')
    records = []
    # Verify copied bytes, including actual unsigned SLSA predicate and complete index/SBOM closure.
    for component, item in artifact['images'].items():
        source = artifact_directory / item['archivePath']
        require(source.is_file() and source.stat().st_size == item['archiveSizeBytes'], 'retained artifact size differs')
        destination = output / item['archivePath']
        shutil.copyfile(source, destination)
        inspect = json.loads((artifact_directory / (component + '-inspect.json')).read_text())
        result = verify(destination, inspect, component, artifact['layersentrySourceCommit'])
        verify_artifact_binding(result, artifact)
        (output / (component + '-verification.json')).write_bytes(json_bytes(result))
        records.append({'component': component, 'archive': destination.name, 'sha256': sha(destination),
                        'runtimeDigest': item['imageManifestDigest'], 'fullRetainedIndex': True})
    # A sidecar archive contains the selected amd64 runtime only; the original multi-platform
    # index and unverified signature manifest stay alongside it as public registry evidence.
    with tempfile.TemporaryDirectory(prefix='layersentry-csi-blobs-') as temp:
        cache = Path(temp)
        for item in lock['sidecars']:
            runtime_path = evidence / (item['name'] + '-amd64.json')
            runtime = json.loads(runtime_path.read_text())
            index = json.loads((evidence / (item['name'] + '-index.json')).read_text())
            descriptor = next(d for d in index['manifests'] if d['digest'] == item['runtimeManifestDigest'])
            files = {'oci-layout': b'{"imageLayoutVersion":"1.0.0"}\n',
                     'index.json': json_bytes({'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.index.v1+json',
                                              'manifests': [descriptor]}),
                     'blobs/sha256/' + item['runtimeManifestDigest'][7:]: runtime_path,
                     'blobs/sha256/' + item['configDigest'][7:]: evidence / (item['name'] + '-config.json')}
            for layer in runtime['layers']:
                blob = cache / layer['digest'][7:]
                if not blob.exists():
                    fetch(item['registry'], layer, blob)
                require(blob.stat().st_size == layer['size'] and sha(blob) == layer['digest'][7:], 'cached layer differs')
                files['blobs/sha256/' + layer['digest'][7:]] = blob
            destination = output / (item['name'] + '.oci.tar')
            write_archive(destination, files)
            verification = verify_sidecar_archive(destination, item)
            (output / (item['name'] + '-verification.json')).write_bytes(json_bytes(verification))
            records.append({'component': item['name'], 'archive': destination.name, 'sha256': sha(destination),
                            'runtimeDigest': item['runtimeManifestDigest'], 'fullRetainedIndex': False,
                            'signatureVerified': False, 'provenanceVerified': False})
    receipt = {'schemaVersion': '1.0', 'artifactType': 'layersentry-native-csi-image-collection',
               'status': 'SOURCE_COMPLETE', 'deployable': False, 'signed': False,
               'registryPublished': False, 'qualification': lock['qualification'], 'archives': records,
               'inputsSha256': sha(ROOT / 'inputs.lock.json')}
    # Completion receipt is written last. Partial output after failure is never a completed bundle.
    (output / 'images.json').write_bytes(json_bytes(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-directory', type=Path, required=True, help='exact retained driver/syncer OCI + Docker inspect files')
    parser.add_argument('--output', type=Path, required=True, help='new private output directory')
    args = parser.parse_args()
    print(json.dumps(collect(args.output, args.artifact_directory), sort_keys=True))


if __name__ == '__main__':
    main()
