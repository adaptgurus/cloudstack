#!/usr/bin/env python3
"""Hosted-only CSI OCI import/reimport qualification using the exact RKE2 runtime."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request
import zipfile

from render import ROOT, DRIVER_REPOSITORY, SYNCER_REPOSITORY, json_bytes, locked_inputs, require, sha, render, write_bundle
from prepare_images import TLSRedirect, collect


def command(argv, timeout=300):
    result = subprocess.run(argv, capture_output=True, timeout=timeout)
    require(result.returncode == 0, 'public qualification command failed: ' + str(argv[0]) + '\n' + result.stderr.decode(errors='replace')[-4000:])
    return result.stdout


def asset(url, expected, destination, max_size):
    opener = urllib.request.build_opener(TLSRedirect())
    count, hashed, deadline = 0, hashlib.sha256(), time.monotonic() + 300
    with opener.open(url, timeout=30) as response, destination.open('xb') as stream:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            count += len(block)
            require(count <= max_size and time.monotonic() < deadline, 'public tool asset exceeds bounds')
            stream.write(block)
            hashed.update(block)
    require(hashed.hexdigest() == expected, 'tool asset digest differs')


def executable(archive_path, member_name, target, expected):
    with tarfile.open(archive_path) as archive:
        members = [item for item in archive.getmembers() if item.name == member_name]
        require(len(members) == 1 and members[0].isfile() and members[0].size <= 150 * 1024 * 1024, 'unsafe executable archive member')
        raw = archive.extractfile(members[0]).read()
    require(hashlib.sha256(raw).hexdigest() == expected, 'native executable digest differs')
    target.write_bytes(raw)
    target.chmod(0o755)


def retained_artifact(output, artifact):
    workflow = artifact['workflow']
    prefix = 'repos/' + workflow['repository'] + '/actions/'
    run = json.loads(command(['gh', 'api', prefix + 'runs/' + str(workflow['runId'])]))
    require(run['conclusion'] == 'success' and run['status'] == 'completed'
            and run['head_sha'] == workflow['sourceCommit'] and run['path'] == workflow['path'], 'retained build workflow binding differs')
    identity = artifact['githubArtifact']
    metadata = json.loads(command(['gh', 'api', prefix + 'artifacts/' + str(identity['id'])]))
    require(metadata['name'] == identity['name'] and metadata['size_in_bytes'] == identity['sizeBytes']
            and not metadata['expired'] and metadata['workflow_run']['id'] == workflow['runId'], 'retained artifact identity differs')
    archive_path = output / 'retained.zip'
    with archive_path.open('xb') as stream:
        result = subprocess.run(['gh', 'api', prefix + 'artifacts/' + str(identity['id']) + '/zip'], stdout=stream, stderr=subprocess.PIPE, timeout=300)
    require(result.returncode == 0 and sha(archive_path) == identity['sha256'], 'retained artifact ZIP digest differs')
    directory = output / 'retained'
    directory.mkdir()
    with zipfile.ZipFile(archive_path) as archive:
        for component, image in artifact['images'].items():
            for name in (image['archivePath'], component + '-inspect.json'):
                matches = [member for member in archive.infolist() if member.filename == name]
                require(len(matches) == 1 and matches[0].file_size <= 64 * 1024 * 1024, 'unsafe retained artifact entry')
                with archive.open(matches[0]) as source, (directory / name).open('xb') as target:
                    shutil.copyfileobj(source, target)
    return directory


def runtime_envelope(source, target, image):
    """Expose the locked runtime at OCI top level without changing any image blob."""
    require(sha(source) == image['archiveSha256'], 'retained archive changed before runtime binding')
    with tarfile.open(source, 'r:') as archive:
        top = json.load(archive.extractfile('index.json'))
        require(len(top['manifests']) == 1 and top['manifests'][0]['digest'] == image['imageIndexDigest'], 'original index differs')
        inner = json.load(archive.extractfile('blobs/sha256/' + image['imageIndexDigest'][7:]))
        runtime = [item for item in inner['manifests'] if item['digest'] == image['imageManifestDigest']]
        require(len(runtime) == 1 and runtime[0]['platform'] == {'architecture': 'amd64', 'os': 'linux'}, 'runtime selector differs')
        # Keep the original attestation index reachable, but don't reuse its historical tag.
        retained = {key: value for key, value in top['manifests'][0].items() if key != 'annotations'}
        envelope = json_bytes({'schemaVersion': 2, 'mediaType': 'application/vnd.oci.image.index.v1+json',
                               'manifests': [retained, runtime[0]]})
        with tarfile.open(target, 'w', format=tarfile.USTAR_FORMAT) as output:
            for member in sorted(archive.getmembers(), key=lambda item: item.name):
                if member.isdir():
                    continue
                require(member.isfile(), 'non-file in already verified OCI archive')
                info = tarfile.TarInfo(member.name)
                info.mode = 0o644
                info.size = len(envelope) if member.name == 'index.json' else member.size
                with io.BytesIO(envelope) if member.name == 'index.json' else archive.extractfile(member) as stream:
                    output.addfile(info, stream)
    require(sha(source) == image['archiveSha256'], 'original archive changed during binding')
    return {'originalArchiveSha256': image['archiveSha256'], 'runtimeEnvelopeSha256': sha(target),
            'retainedIndexDigest': image['imageIndexDigest'], 'runtimeDigest': image['imageManifestDigest'],
            'imageBlobsModified': False}


def expected_images(lock, artifact):
    records = []
    for component, image in artifact['images'].items():
        repository = DRIVER_REPOSITORY if component == 'cloudstack-csi-driver' else SYNCER_REPOSITORY
        records.append({'component': component, 'repository': repository, 'reference': repository + '@' + image['imageManifestDigest'],
                        'digest': image['imageManifestDigest'], 'archive': image['archivePath'],
                        'retainedIndexDigest': image['imageIndexDigest']})
    for image in lock['sidecars']:
        records.append({'component': image['name'], 'repository': image['registry'],
                        'reference': image['registry'] + '@' + image['runtimeManifestDigest'],
                        'digest': image['runtimeManifestDigest'], 'archive': image['name'] + '.oci.tar'})
    return records


def verify_rows(raw, expected):
    lines = raw.decode().splitlines()
    require(lines and lines[0].split()[:3] == ['REF', 'TYPE', 'DIGEST'], 'unexpected ctr image list schema')
    actual = {}
    for line in lines[1:]:
        fields = line.split()
        require(len(fields) >= 3 and fields[0] not in actual, 'ambiguous ctr image row')
        actual[fields[0]] = fields[2]
    for item in expected:
        require(actual.get(item['reference']) == item['digest'], 'native runtime name/descriptor differs: ' + item['component'])
        if 'retainedIndexDigest' in item:
            require(actual.get(item['repository'] + '@' + item['retainedIndexDigest']) == item['retainedIndexDigest'], 'retained index name/descriptor differs')
    return {item['reference']: actual[item['reference']] for item in expected}


def native_import(images, binaries, output, lock, artifact, runtime_lock):
    require(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted',
            'native import qualification requires a disposable GitHub-hosted runner')
    for name, expected in runtime_lock['binarySha256'].items():
        require(sha(binaries / name) == expected, 'RKE2 runtime executable differs')
    version = command([str(binaries / 'containerd'), '--version']).decode().strip()
    require(version == runtime_lock['expectedContainerdVersionOutput'], 'exact RKE2 containerd version differs')
    work = Path(tempfile.mkdtemp(prefix='layersentry-csi-containerd-', dir=os.environ['RUNNER_TEMP']))
    config = work / 'config.toml'
    config.write_text('version = 3\ndisabled_plugins = ["io.containerd.cri.v1.images", "io.containerd.cri.v1.runtime"]\n')
    socket = str(work / 'socket')
    log = (output / 'containerd.log').open('wb')
    env = {**os.environ, 'PATH': str(binaries) + ':/usr/bin:/bin'}
    envelopes = {}
    for component, image in artifact['images'].items():
        target = output / (component + '.runtime-envelope.oci.tar')
        envelopes[component] = runtime_envelope(images / image['archivePath'], target, image)
    daemon = subprocess.Popen(['sudo', '-n', '--', str(binaries / 'containerd'), '--config', str(config),
                               '--root', str(work / 'root'), '--state', str(work / 'state'), '--address', socket],
                              stdout=log, stderr=log, env=env)
    ctr = ['sudo', '-n', '--', str(binaries / 'ctr'), '--address', socket, '--namespace', 'k8s.io']
    expected = expected_images(lock, artifact)
    observations = []
    try:
        deadline = time.monotonic() + 30
        while not Path(socket).exists():
            require(daemon.poll() is None and time.monotonic() < deadline, 'private containerd failed to start')
            time.sleep(0.2)
        # No registry resolution, workload execution or external runtime socket is used.
        for attempt in (1, 2):
            for item in expected:
                command(ctr + ['images', 'import', '--local', '--all-platforms', '--digests',
                               '--label', 'io.cri-containerd.image=managed', '--base-name', item['repository'],
                               str(images / item['archive'])])
                if item['component'] in envelopes:
                    command(ctr + ['images', 'import', '--local', '--all-platforms', '--digests',
                                   '--label', 'io.cri-containerd.image=managed', '--base-name', item['repository'],
                                   str(output / (item['component'] + '.runtime-envelope.oci.tar'))])
            rows = command(ctr + ['images', 'list'])
            (output / ('import-' + str(attempt) + '.txt')).write_bytes(rows)
            bindings = verify_rows(rows, expected)
            # Prove exact named targets are also readable content; retain both original
            # CSI index documents in the content store, including attestations.
            checked = []
            for item in expected:
                for digest in [item['digest']] + ([item['retainedIndexDigest']] if 'retainedIndexDigest' in item else []):
                    raw = command(ctr + ['content', 'get', digest])
                    require('sha256:' + hashlib.sha256(raw).hexdigest() == digest, 'containerd content digest differs')
                    checked.append(digest)
            observations.append({'attempt': attempt, 'mode': 'native-local', 'exactRuntimeImages': bindings,
                                 'contentDigestsVerified': checked})
        return {'containerdVersion': version, 'runtimeImage': runtime_lock['runtimeImage'],
                'binarySha256': runtime_lock['binarySha256'], 'imports': observations, 'runtimeEnvelopes': envelopes,
                'criPodExecutionVerified': False, 'liveNodePreloadVerified': False}
    finally:
        daemon.terminate()
        try:
            daemon.wait(timeout=20)
        except subprocess.TimeoutExpired:
            daemon.kill()
            daemon.wait(timeout=10)
        log.close()
        (output / 'cleanup.json').write_bytes(json_bytes({'privateDaemonStopped': daemon.poll() is not None,
            'scope': 'owned isolated hosted-runner daemon only; no lab runtime', 'privateStatePath': str(work),
            'stateDisposition': 'retained only on ephemeral hosted runner; not uploaded'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted', 'hosted runner required')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    source.mkdir()
    lock, artifact = locked_inputs()
    runtime_lock = json.loads((ROOT / 'qualification-tools.lock.json').read_text())
    helm_archive = source / 'helm.tar.gz'
    asset(lock['helm']['url'], lock['helm']['archiveSha256'], helm_archive, 64 * 1024 * 1024)
    helm = source / 'helm'
    executable(helm_archive, 'linux-amd64/helm', helm, lock['helm']['binarySha256'])
    crane_item = runtime_lock['crane']
    crane_archive = source / 'crane.tar.gz'
    asset('https://github.com/' + crane_item['repository'] + '/releases/download/' + crane_item['version'] + '/' + crane_item['name'],
          crane_item['sha256'], crane_archive, 64 * 1024 * 1024)
    crane = source / 'crane'
    executable(crane_archive, 'crane', crane, crane_item['binarySha256'])
    runtime = source / 'runtime.tar'
    command([str(crane), 'export', '--platform', 'linux/amd64', runtime_lock['runtimeImage'], str(runtime)], timeout=600)
    binaries = source / 'bin'
    binaries.mkdir()
    for name, expected in runtime_lock['binarySha256'].items():
        executable(runtime, 'bin/' + name, binaries / name, expected)
    retained = retained_artifact(source, artifact)
    collection = collect(output / 'images', retained)
    objects, _, _ = render(helm)
    review = write_bundle(output / 'review', objects, lock, artifact)
    os.environ['LAYERSENTRY_TEST_HELM'] = str(helm)
    tests = subprocess.run([os.sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT), '-p', 'test_*.py', '-v'], capture_output=True, timeout=120)
    (output / 'tests.txt').write_bytes(tests.stdout + tests.stderr)
    require(tests.returncode == 0 and b'skipped=' not in tests.stderr, 'native source/render tests did not all pass')
    imported = native_import(output / 'images', binaries, output, lock, artifact, runtime_lock)
    receipt = {'schemaVersion': '1.0', 'status': 'CI_VERIFIED', 'scope': 'offline native CSI artifact import/reimport only',
               'sourceCommit': os.environ.get('GITHUB_SHA'), 'runId': os.environ.get('GITHUB_RUN_ID'),
               'deployable': False, 'signatureVerified': False, 'registryPublished': False,
               'qualification': lock['qualification'], 'images': collection, 'reviewBundle': review, 'nativeImport': imported,
               'airgapCandidate': {'runtimeNamesVerified': True, 'imagePullPolicy': 'IfNotPresent',
                                   'requiresExactPreloadOnEveryWorkloadNode': True, 'liveNodePreloadVerified': False}}
    (output / 'qualification.json').write_bytes(json_bytes(receipt))
    print(json.dumps({'status': receipt['status'], 'scope': receipt['scope'], 'imports': len(imported['imports'])}))


if __name__ == '__main__':
    main()
