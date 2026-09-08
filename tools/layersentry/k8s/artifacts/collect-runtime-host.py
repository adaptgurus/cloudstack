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

"""Observation only. Run on the dedicated Rocky 9 controller acceptance host.

Usage: /usr/bin/python3 -I -B collect-runtime-host.py --dedicated-controller-host
Writes sanitized JSON to stdout only. Does not install packages or qualify a host.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import sysconfig

sys.dont_write_bytecode = True
NEVRA = '%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}'


def query(argv):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=20,
                           env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'LC_ALL': 'C'})
        return p.returncode, p.stdout[:262144]
    except (OSError, subprocess.TimeoutExpired):
        return -1, ''


def file_hash(path):
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError('file exceeds observation limit')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def tree_hash(path, exclude=()):
    rows = []
    symlinks = 0
    for item in sorted(path.rglob('*')):
        relative = item.relative_to(path)
        if any(part in {'__pycache__', *exclude} for part in relative.parts) or item.suffix == '.pyc':
            continue
        if item.is_symlink():
            symlinks += 1
            # Never follow package/stdlib symlinks into unrelated host files.
            rows.append([str(relative), 'symlink', hashlib.sha256(os.readlink(item).encode()).hexdigest()])
        elif item.is_file():
            rows.append([str(relative), oct(item.stat().st_mode & 0o777), file_hash(item)])
    return hashlib.sha256(json.dumps(rows, separators=(',', ':')).encode()).hexdigest(), len(rows), symlinks


def rpm_owner(path):
    code, value = query(['rpm', '-qf', '--qf', NEVRA, str(path)])
    return value.strip() if code == 0 else None


def rpm_header(nevra):
    if not nevra:
        return None
    code, value = query(['rpm', '-q', '--qf', '%{SHA256HEADER}', nevra])
    value = value.strip()
    return value if code == 0 and re.fullmatch('[0-9a-f]{64}', value) else None


def distribution_observation(name):
    dist = metadata.distribution(name)
    rows = []
    owners = set()
    missing = 0
    for entry in sorted(dist.files or [], key=str):
        path = Path(dist.locate_file(entry))
        if path.suffix == '.pyc' or '__pycache__' in path.parts:
            continue
        # RECORD may name entry points outside site-packages; only system prefixes
        # are acceptable on this /usr/bin/python3 systemd host.
        if not str(path.resolve()).startswith(('/usr/', '/lib/', '/lib64/')):
            missing += 1
            continue
        if path.is_symlink() or not path.is_file():
            missing += 1
            continue
        rows.append({'path': str(entry), 'sha256': file_hash(path)})
    if dist.files:
        owner = rpm_owner(Path(dist.locate_file(dist.files[0])))
        if owner:
            owners.add(owner)
    installer = (dist.read_text('INSTALLER') or '').strip()
    if installer not in ('pip', 'rpm', ''):
        installer = 'OTHER'
    direct = dist.read_text('direct_url.json')
    archive_hash = None
    if direct:
        value = json.loads(direct).get('archive_info', {})
        candidate = value.get('hashes', {}).get('sha256')
        if isinstance(candidate, str) and re.fullmatch('[0-9a-f]{64}', candidate):
            archive_hash = candidate
    # Never expose direct_url.json URLs, credentials or raw package metadata.
    return dist, {'name': dist.metadata['Name'], 'version': dist.version,
        'installedContentSha256': hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'fileCount': len(rows), 'unverifiedFiles': missing,
        'rpmNevra': sorted(owners), 'rpmHeaderSha256': {n: rpm_header(n) for n in sorted(owners)}, 'installer': installer or ('rpm' if owners else 'UNKNOWN'),
        'wheelOrSourceArchiveSha256': archive_hash,
        'installationSource': 'RPM ownership' if owners else 'pip metadata; archive hash may require owner-supplied wheel',
        'installedRecordSha256': hashlib.sha256((dist.read_text('RECORD') or '').encode()).hexdigest() if dist.read_text('RECORD') else None,
        'files': rows}


def dependency_observations():
    try:
        from packaging.requirements import Requirement
    except ImportError:
        Requirement = None
    pending = ['gunicorn']
    seen = set()
    result, missing, inactive = [], [], []
    while pending:
        name = pending.pop()
        canonical = re.sub('[-_.]+', '-', name).lower()
        if canonical in seen:
            continue
        seen.add(canonical)
        if len(seen) > 128:
            raise ValueError('dependency count exceeds observation limit')
        try:
            dist, row = distribution_observation(name)
        except metadata.PackageNotFoundError:
            missing.append(canonical)
            continue
        result.append(row)
        for raw in dist.requires or []:
            if Requirement is None:
                missing.append('dependency-marker-parser-unavailable')
                break
            req = Requirement(raw)
            if req.marker is None or req.marker.evaluate({'extra': ''}):
                pending.append(req.name)
            else:
                inactive.append(req.name)
    return {'packages': result, 'missing': sorted(set(missing)),
            'inactiveOptionalDependencies': sorted(set(inactive)),
            'dependencyMetadataClosureObserved': not missing and all(r['fileCount'] and not r['unverifiedFiles'] for r in result)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dedicated-controller-host', action='store_true')
    args = parser.parse_args()
    if not args.dedicated_controller_host or not sys.flags.isolated:
        parser.error('use /usr/bin/python3 -I -B and --dedicated-controller-host on the selected acceptance host')
    os_release = Path('/etc/os-release').read_text()
    fields = {}
    for line in os_release.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            if key in {'ID', 'VERSION_ID', 'NAME', 'PRETTY_NAME'}:
                fields[key] = value.strip('"')
    code, architecture = query(['uname', '-m'])
    code_ip, addresses = query(['ip', '-j', '-4', 'addr', 'show'])
    host_refused = '10.10.10.14' in addresses or code_ip != 0
    for service in ('cloudstack-agent', 'rke2-server', 'rke2-agent'):
        code_unit, text = query(['systemctl', 'show', service+'.service', '--property=LoadState', '--value'])
        host_refused |= code_unit < 0 or text.strip() not in {'not-found', ''}
    if (fields.get('ID') != 'rocky' or fields.get('VERSION_ID', '').split('.')[0] != '9'
            or code != 0 or architecture.strip() != 'x86_64' or host_refused
            or 'microsoft' in platform.release().lower()
            or Path('/.dockerenv').exists() or Path('/run/.containerenv').exists()):
        print(json.dumps({'status': 'REFUSED', 'reason': 'Host does not meet dedicated Rocky 9 controller acceptance contract'}))
        return 2
    python = Path('/usr/bin/python3')
    if Path(sys.executable).resolve() != python.resolve():
        raise ValueError('unexpected interpreter')
    stdlib = Path(sysconfig.get_path('stdlib'))
    stdlib_sha, stdlib_files, stdlib_links = tree_hash(stdlib, ('site-packages', 'dist-packages'))
    code, python_version = query(['/usr/bin/python3', '--version'])
    code_pip, pip_output = query(['/usr/bin/python3', '-I', '-B', '-m', 'pip', 'show', 'gunicorn'])
    pip_fields = {}
    if code_pip == 0:
        for line in pip_output.splitlines():
            key, sep, value = line.partition(':')
            if sep and key in {'Name', 'Version', 'Location', 'Requires'}:
                pip_fields[key] = value.strip()
    gunicorn = {'status': 'NOT_INSTALLED'}
    spec = importlib.util.find_spec('gunicorn')
    if spec and spec.origin:
        module = Path(spec.origin)
        if str(module.resolve()).startswith(('/usr/', '/lib/', '/lib64/')):
            tree, count, links = tree_hash(module.parent)
            gunicorn = {'version': metadata.version('gunicorn'), 'modulePath': str(module.parent),
                        'moduleTreeSha256': tree, 'moduleFileCount': count, 'unverifiedSymlinks': links, 'rpmNevra': rpm_owner(module), 'rpmHeaderSha256': rpm_header(rpm_owner(module))}
    report = {'schemaVersion': '1.0', 'status': 'OBSERVED_NOT_QUALIFIED',
        'host': {'name': platform.node(), 'dedicatedControllerOperatorAttestation': True},
        'osRelease': fields, 'osReleaseSha256': file_hash(Path('/etc/os-release')),
        'architecture': architecture.strip(),
        'python': {'path': str(python), 'resolvedPath': str(python.resolve()), 'sha256': file_hash(python),
            'rpmNevra': rpm_owner(python), 'rpmHeaderSha256': rpm_header(rpm_owner(python)), 'versionCommand': python_version.strip() if code == 0 else 'UNKNOWN',
            'implementation': sys.implementation.name, 'version': platform.python_version(),
            'stdlibPath': str(stdlib), 'stdlibTreeSha256': stdlib_sha, 'stdlibFileCount': stdlib_files, 'unverifiedStdlibSymlinks': stdlib_links},
        'gunicorn': gunicorn, 'gunicornPipShow': pip_fields, 'dependencies': dependency_observations(),
        'packageArchiveIdentityNote': 'Installed tree/NEVRA are observations. Missing original wheel/RPM artifact hashes must be supplied before pinning.',
        'systemChanges': False, 'packagesInstalled': False}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'status': 'UNKNOWN', 'errorType': type(exc).__name__}))
        raise SystemExit(2)
