# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Build pinned qualification artifacts; never deploy or certify live behavior."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent
K8S = ROOT.parent
COMPONENTS = {'caprke2-bootstrap': ('caprke2', './bootstrap', 'manager'),
              'capc': ('capc', '.', 'manager'),
              'ccm': ('cloudstack-ccm', './cmd/cloudstack-ccm', 'cloudstack-ccm'),
              'csi': ('cloudstack-csi', './cmd/cloudstack-csi-driver', 'cloudstack-csi-driver')}


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fetch_package(item, destination):
    url = item['url']
    if not url.startswith('https://dl-cdn.alpinelinux.org/alpine/v3.21/'):
        raise ValueError('APK URL is outside the locked upstream')
    if Path(item['file']).name != item['file'] or not item['file'].endswith('.apk'):
        raise ValueError('invalid APK filename')
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(item['bytes'] + 1)
    if len(data) != item['bytes'] or sha(data) != item['sha256']:
        raise ValueError('APK content differs from lock')
    (destination / item['file']).write_bytes(data)


def runtime_digest(archive):
    """Hash complete filesystem content/ownership/modes, excluding Docker host files.

    Tar order and mtimes are not runtime content. No package database, executable,
    certificate, configuration or symlink is excluded.
    """
    rows = []
    with tarfile.open(archive) as stream:
        for member in stream:
            name = member.name.removeprefix('./')
            if name in {'.dockerenv', 'etc/hostname', 'etc/hosts', 'etc/resolv.conf'}:
                continue
            content = sha(stream.extractfile(member).read()) if member.isfile() else None
            rows.append((name, member.type.decode(), member.mode, member.uid, member.gid,
                         member.linkname, content))
    return sha(json.dumps(sorted(rows), separators=(',', ':')).encode())


def build(component, output):
    folder, target, binary = COMPONENTS[component]
    manifest = K8S / 'downstream' / folder / 'manifest.json'
    spec = json.loads(manifest.read_text())
    with tempfile.TemporaryDirectory(prefix='layersentry-artifact-') as temporary:
        source = Path(temporary) / 'source'
        run(['git', 'init', '-q', str(source)])
        run(['git', '-C', str(source), 'remote', 'add', 'origin', spec['upstreamRepository']])
        run(['git', '-C', str(source), 'fetch', '--depth=1', 'origin', spec['upstreamCommit']])
        run(['git', '-C', str(source), 'checkout', '--detach', spec['upstreamCommit']])
        run(['python3', str(K8S / 'downstream/materialize.py'), '--source', str(source),
             '--manifest', str(manifest), '--apply'])
        images = spec['buildImages']
        runtime = images['runtime']
        package_lock = None
        package_layer = ''
        if component == 'csi':
            lock = ROOT / 'csi-apk-lock.json'
            package_lock = sha(lock.read_bytes())
            apks = source / 'locked-apks'
            apks.mkdir()
            for item in json.loads(lock.read_text())['packages']:
                fetch_package(item, apks)
            # Alpine verifies APK signatures against keys from the pinned base.
            # No index refresh, network package resolution or allow-untrusted.
            package_layer = ('COPY locked-apks /locked-apks\n'
                             'RUN --network=none apk add --no-network /locked-apks/*.apk '
                             '&& rm -rf /locked-apks /var/cache/apk/* /var/log/apk.log\n')
        tests = "REPO_ROOT=/src go test -p 2 ./pkg/... -ginkgo.label-filter=\"!integ\"" if component == 'capc' else 'go test -p 2 ./...'
        if component == 'caprke2-bootstrap':
            tests = 'go test -p 2 ./bootstrap/internal/cloudinit'
        dockerfile = (f'FROM {images["builder"]} AS build\n'
                      'WORKDIR /src\nENV GOTOOLCHAIN=local CGO_ENABLED=0 GOFLAGS=-mod=readonly\n'
                      'COPY go.mod go.sum ./\nRUN go mod download && go mod verify\n'
                      f'COPY . .\nRUN {tests}\n'
                      f'RUN go build -p 2 -trimpath -buildvcs=false -o /artifact {target}\n'
                      f'FROM {runtime}\n' + package_layer +
                      f'COPY --from=build /artifact /{binary}\n' +
                      ('LABEL org.opencontainers.image.source="https://github.com/adaptgurus/cloudstack"\n'
                       if component == 'caprke2-bootstrap' else
                       'LABEL org.opencontainers.image.source="https://github.com/adaptgurus/layersentry-flux-catalog"\n') +
                      ('USER 65532:65532\n' if component in {'capc', 'caprke2-bootstrap'} else '') +
                      f'ENTRYPOINT ["/{binary}"]\n')
        (source / 'Dockerfile.qualification').write_text(dockerfile)
        (source / '.dockerignore').write_text('.git\n')
        digests = []
        tag = f'layersentry-{component}:qualification'
        for attempt in (1, 2):
            run(['docker', 'build', '--no-cache', '--network=default', '--platform=linux/amd64',
                 '-f', str(source / 'Dockerfile.qualification'), '-t', tag, str(source)])
            container = run(['docker', 'create', tag], capture_output=True, text=True).stdout.strip()
            try:
                archive = Path(temporary) / f'runtime-{attempt}.tar'
                run(['docker', 'export', '-o', str(archive), container])
                digests.append(runtime_digest(archive))
            finally:
                run(['docker', 'rm', container], stdout=subprocess.DEVNULL)
        if digests[0] != digests[1]:
            raise ValueError('two clean builds produced different runtime content')
        report = {'component': component, 'sourceCommit': spec['upstreamCommit'],
                  'patches': spec['patches'], 'builder': images['builder'], 'runtime': runtime,
                  'recipeSha256': sha(dockerfile.encode()), 'apkLockSha256': package_lock,
                  'cleanBuildRuntimeDigests': digests, 'tests': tests + ' passed in both builds',
                  'liveQualified': False}
        output.mkdir(parents=True, exist_ok=True)
        (output / f'{component}.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('component', choices=COMPONENTS)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.component, args.output)
