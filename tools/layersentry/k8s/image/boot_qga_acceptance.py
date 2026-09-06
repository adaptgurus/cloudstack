#!/usr/bin/env python3
"""Bounded networkless Rocky candidate boot. Does not qualify a production template."""
import argparse
import base64
import grp
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

PREFIX = Path('/var/lib/libvirt/images')
LOG_ROOT = Path('/var/log/libvirt/qemu')
URI = 'qemu:///system'


def run(argv, timeout=60):
    try:
        return subprocess.check_output(argv, timeout=timeout, text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as error:
        # These fixed image/libvirt commands carry no credentials. Preserve the
        # bounded causal diagnostic rather than only their numeric exit status.
        raise RuntimeError(json.dumps({'command': Path(argv[0]).name, 'returnCode': error.returncode,
                                       'output': (error.output or '')[-16384:]})) from error
    except subprocess.TimeoutExpired as error:
        output = error.output or ''
        if isinstance(output, bytes):
            output = output.decode(errors='replace')
        raise TimeoutError(json.dumps({'command': Path(argv[0]).name, 'timeoutSeconds': timeout,
                                       'output': output[-16384:]})) from error


def virsh(*args, timeout=60):
    return run(['virsh', '--connect', URI, *args], timeout)


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def xml_for(manifest):
    root = ET.Element('domain', type='kvm')
    for tag, value in [('name', manifest['domainName']), ('uuid', manifest['domainUuid'])]:
        ET.SubElement(root, tag).text = value
    ET.SubElement(root, 'memory', unit='MiB').text = '4096'
    ET.SubElement(root, 'vcpu').text = '2'
    os_node = ET.SubElement(root, 'os')
    ET.SubElement(os_node, 'type', arch='x86_64', machine='q35').text = 'hvm'
    ET.SubElement(os_node, 'boot', dev='hd')
    features = ET.SubElement(root, 'features')
    ET.SubElement(features, 'acpi')
    ET.SubElement(features, 'apic')
    ET.SubElement(root, 'cpu', mode='host-passthrough', check='none')
    ET.SubElement(root, 'on_poweroff').text = 'destroy'
    ET.SubElement(root, 'on_reboot').text = 'restart'
    ET.SubElement(root, 'on_crash').text = 'destroy'
    devices = ET.SubElement(root, 'devices')
    disk = ET.SubElement(devices, 'disk', type='file', device='disk')
    ET.SubElement(disk, 'driver', name='qemu', type='qcow2', cache='none')
    ET.SubElement(disk, 'source', file=manifest['diskPath'])
    ET.SubElement(disk, 'target', dev='vda', bus='virtio')
    seed = ET.SubElement(devices, 'disk', type='file', device='cdrom')
    ET.SubElement(seed, 'driver', name='qemu', type='raw')
    ET.SubElement(seed, 'source', file=manifest['seedPath'])
    ET.SubElement(seed, 'target', dev='sda', bus='sata')
    ET.SubElement(seed, 'readonly')
    ET.SubElement(devices, 'controller', type='virtio-serial', index='0')
    channel = ET.SubElement(devices, 'channel', type='unix')
    ET.SubElement(channel, 'target', type='virtio', name='org.qemu.guest_agent.0')
    serial = ET.SubElement(devices, 'serial', type='pty')
    ET.SubElement(serial, 'log', file=manifest['consolePath'], append='off')
    ET.SubElement(serial, 'target', port='0')
    return ET.tostring(root, encoding='unicode')


def load_ownership(path):
    if path.is_symlink() or path.name != 'ownership.json':
        raise ValueError('invalid ownership manifest path')
    record = json.loads(path.read_text())
    identity = str(uuid.UUID(record['domainUuid']))
    expected = PREFIX / ('layersentry-cpuqc-' + identity)
    if path.parent != expected or path.parent.is_symlink() or path.resolve() != expected / 'ownership.json':
        raise ValueError('ownership workspace is outside the exact generated prefix')
    if path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
        raise ValueError('ownership manifest must be private and root-owned')
    if record['domainName'] != 'layersentry-cpuqc-' + identity:
        raise ValueError('domain name/UUID mismatch')
    for key, name in [('diskPath', 'runtime.qcow2'), ('seedPath', 'seed.iso')]:
        if record[key] != str(expected / name) or (expected / name).is_symlink():
            raise ValueError('owned artifact path mismatch')
    log = LOG_ROOT / (record['domainName'] + '-console.log')
    if record['consolePath'] != str(log) or log.is_symlink():
        raise ValueError('owned console log path mismatch')
    if not re.fullmatch(r'[a-f0-9]{64}', record['sourceSha256']):
        raise ValueError('invalid source digest')
    return record


def cleanup(path):
    record = load_ownership(path)
    identity = record['domainUuid']
    # List all domains first: a connection failure must never be mistaken for absence.
    present = identity in virsh('list', '--all', '--uuid').splitlines()
    if present:
        actual = ET.fromstring(virsh('dumpxml', identity))
        if actual.findtext('uuid') != identity or actual.findtext('name') != record['domainName']:
            raise ValueError('live domain identity differs from ownership')
        source = actual.find("./devices/disk[@device='disk']/source")
        if source is None or source.get('file') != record['diskPath'] or actual.findall('./devices/interface'):
            raise ValueError('live domain disk/network differs from ownership')
        virsh('shutdown', identity)
        deadline = time.monotonic() + 60
        while identity in virsh('list', '--uuid').splitlines() and time.monotonic() < deadline:
            time.sleep(2)
        if identity in virsh('list', '--uuid').splitlines():
            virsh('destroy', identity)
        if identity in virsh('list', '--all', '--uuid').splitlines():
            raise ValueError('owned domain was unexpectedly persistent; manual review required')
    Path(record['consolePath']).unlink(missing_ok=True)
    shutil.rmtree(path.parent)


def agent(identity, command):
    result = json.loads(virsh('qemu-agent-command', identity, '--timeout', '5', json.dumps(command), timeout=10))
    if 'error' in result:
        raise RuntimeError('guest agent command failed: ' + json.dumps(result['error']))
    return result['return']


def guest_checks(identity):
    script = r'''
set -euo pipefail
timeout 180 cloud-init status --wait >/tmp/layersentry-cloud-init-status
python3 - <<'PY'
import hashlib,json,pathlib,subprocess
def cmd(*args): return subprocess.check_output(args,text=True).strip()
def state(unit,verb):
 p=subprocess.run(['systemctl',verb,unit],text=True,capture_output=True)
 return p.stdout.strip()
root=pathlib.Path('/')
osdata=dict(line.split('=',1) for line in (root/'etc/os-release').read_text().splitlines() if '=' in line)
result={'os':osdata['ID'].strip('"'),'osVersion':osdata['VERSION_ID'].strip('"'),
 'selinux':cmd('getenforce'),'rke2Version':cmd('/usr/local/bin/rke2','--version'),
 'services':{u:{'active':state(u,'is-active'),'enabled':state(u,'is-enabled')} for u in ['qemu-guest-agent','sshd','firewalld','rke2-server','rke2-agent']},
 'machineIdGenerated':len((root/'etc/machine-id').read_text().strip())==32,
 'sshHostEd25519PublicKey':(root/'etc/ssh/ssh_host_ed25519_key.pub').read_text().strip(),
 'rootAuthorizedKeysEmpty':not (root/'root/.ssh/authorized_keys').exists() or not (root/'root/.ssh/authorized_keys').read_text().strip(),
 'clusterConfigAbsent':not (root/'etc/rancher/rke2/config.yaml').exists(),
 'serverStateAbsent':not (root/'var/lib/rancher/rke2/server').exists(),
 'interfaces':sorted(p.name for p in (root/'sys/class/net').iterdir()),
 'cloudInitStatus':(root/'tmp/layersentry-cloud-init-status').read_text().strip(),
 'sshdSettings':dict(line.split(' ',1) for line in cmd('sshd','-T').splitlines()),
 'inputLockSha256':hashlib.sha256((root/'usr/share/layersentry/node-image/inputs.lock.json').read_bytes()).hexdigest()}
assert result['os']=='rocky' and result['osVersion']=='9.8'
assert result['selinux']=='Enforcing'
assert 'v1.36.4+rke2r1' in result['rke2Version']
for u in ['qemu-guest-agent','sshd','firewalld']: assert result['services'][u]['active']=='active',u
for u in ['rke2-server','rke2-agent']: assert result['services'][u]=={'active':'inactive','enabled':'disabled'},u
for key in ['machineIdGenerated','rootAuthorizedKeysEmpty','clusterConfigAbsent','serverStateAbsent']: assert result[key],key
assert result['interfaces']==['lo']
assert result['sshHostEd25519PublicKey'].startswith('ssh-ed25519 ')
assert result['sshdSettings']['passwordauthentication']=='no'
assert result['sshdSettings']['kbdinteractiveauthentication']=='no'
assert result['sshdSettings']['permitrootlogin'] in ['prohibit-password','without-password']
assert result['sshdSettings']['pubkeyauthentication']=='yes'
print(json.dumps(result,sort_keys=True))
PY
'''
    process = agent(identity, {'execute': 'guest-exec', 'arguments': {'path': '/bin/bash', 'arg': ['-c', script], 'capture-output': True}})
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        status = agent(identity, {'execute': 'guest-exec-status', 'arguments': {'pid': process['pid']}})
        if status.get('exited'):
            if status.get('out-truncated') or status.get('err-truncated'):
                raise ValueError('guest output was truncated')
            stdout = base64.b64decode(status.get('out-data', ''), validate=True).decode()
            stderr = base64.b64decode(status.get('err-data', ''), validate=True).decode()
            if status.get('exitcode') != 0:
                raise RuntimeError('guest checks failed: ' + stdout + stderr)
            return json.loads(stdout)
        time.sleep(2)
    raise TimeoutError('guest checks exceeded 240 seconds')


def boot(args):
    if not re.fullmatch(r'[a-f0-9]{64}', args.sha256 or ''):
        raise ValueError('exact lowercase SHA-256 required')
    image = args.image.resolve(strict=True)
    if not image.is_file() or digest(image) != args.sha256:
        raise ValueError('candidate image SHA-256 mismatch')
    info = json.loads(run(['qemu-img', 'info', '--output=json', str(image)]))
    format_data = info.get('format-specific', {}).get('data', {})
    if info.get('format') != 'qcow2' or info.get('backing-filename') or info.get('encrypted') or format_data.get('data-file') or format_data.get('encrypt') or not 0 < info.get('virtual-size', 0) <= 128 * 1024**3:
        raise ValueError('candidate must be standalone unencrypted QCOW2 up to 128 GiB')
    run(['qemu-img', 'check', '-f', 'qcow2', str(image)], timeout=180)
    if run(['getenforce']).strip() != 'Enforcing':
        raise ValueError('host SELinux must remain Enforcing')
    if LOG_ROOT.resolve(strict=True) != LOG_ROOT or LOG_ROOT.stat().st_uid != 0 or LOG_ROOT.stat().st_mode & 0o022:
        raise ValueError('native libvirt log directory must be trusted and root-owned')
    virsh('list', '--all', '--uuid')
    iso = shutil.which('xorriso') or shutil.which('genisoimage')
    if not iso:
        raise ValueError('xorriso or genisoimage required for NoCloud CIDATA')
    if args.evidence.exists() or args.evidence.is_symlink():
        raise ValueError('refusing existing evidence directory')
    args.evidence.mkdir(mode=0o700, parents=True)
    identity = str(uuid.uuid4())
    work = PREFIX / ('layersentry-cpuqc-' + identity)
    console_path = LOG_ROOT / (work.name + '-console.log')
    if console_path.exists() or console_path.is_symlink():
        raise ValueError('refusing existing console log overwrite')
    work.mkdir(mode=0o750)
    os.chown(work, 0, grp.getgrnam('qemu').gr_gid)
    record = {'schemaVersion': '1.0', 'domainUuid': identity, 'domainName': work.name,
              'sourceSha256': args.sha256, 'sourcePath': str(image),
              'diskPath': str(work / 'runtime.qcow2'), 'seedPath': str(work / 'seed.iso'),
              'consolePath': str(console_path), 'networkInterfaces': 0, 'firmware': 'bios',
              'productionQualified': False, 'retainForDrQualification': False}
    ownership = work / 'ownership.json'
    ownership.write_text(json.dumps(record, indent=2) + '\n')
    ownership.chmod(0o600)
    passed = False
    try:
        run(['cp', '--reflink=auto', '--sparse=always', str(image), record['diskPath']], timeout=300)
        if digest(Path(record['diskPath'])) != args.sha256:
            raise ValueError('runtime copy digest mismatch')
        seed = work / 'seed'
        seed.mkdir(mode=0o700)
        (seed / 'meta-data').write_text('instance-id: ' + work.name + '\nlocal-hostname: layersentry-cpuqc\n')
        (seed / 'user-data').write_text('#cloud-config\nssh_pwauth: false\ndisable_root: false\n')
        run([iso, *(['-as', 'mkisofs'] if Path(iso).name == 'xorriso' else []), '-output', record['seedPath'], '-volid', 'cidata', '-joliet', '-rock', str(seed)])
        for key in ['diskPath', 'seedPath']:
            os.chown(record[key], 0, grp.getgrnam('qemu').gr_gid)
            os.chmod(record[key], 0o640)
        run(['restorecon', '-RF', str(work)])
        xml = work / 'domain.xml'
        xml.write_text(xml_for(record))
        (args.evidence / 'domain-request.xml').write_text(xml.read_text())
        (args.evidence / 'source-image-info.json').write_text(json.dumps(info, indent=2) + '\n')
        virsh('create', str(xml))
        deadline = time.monotonic() + 300
        while True:
            try:
                agent(identity, {'execute': 'guest-ping'})
                break
            except (subprocess.SubprocessError, RuntimeError):
                if time.monotonic() >= deadline:
                    raise TimeoutError('QGA unavailable after 300 seconds')
                time.sleep(5)
        actual = ET.fromstring(virsh('dumpxml', identity))
        if actual.findall('./devices/interface'):
            raise ValueError('network interface unexpectedly attached')
        facts = guest_checks(identity)
        (args.evidence / 'guest-checks.json').write_text(json.dumps(facts, indent=2) + '\n')
        (args.evidence / 'domain-actual.xml').write_text(ET.tostring(actual, encoding='unicode'))
        passed = True
        record['retainForDrQualification'] = bool(args.retain_for_dr_qualification)
        ownership.write_text(json.dumps(record, indent=2) + '\n')
        report = {'status': 'LIVE_VERIFIED', 'scope': 'networkless Rocky CPU image boot and QGA',
                  'sourceSha256': args.sha256, 'domainUuid': identity,
                  'ownershipManifest': str(ownership) if args.retain_for_dr_qualification else None,
                  'productionQualified': False, 'joinTested': False, 'storageTested': False,
                  'sshConnectivityTested': False, 'rke2Started': False}
        (args.evidence / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, sort_keys=True))
    except BaseException as error:
        (args.evidence / 'failure.txt').write_text(str(error) + '\n')
        raise
    finally:
        console = Path(record['consolePath'])
        if console.exists():
            # Retain at most the final 2 MiB, never an unbounded serial log.
            with console.open('rb') as stream:
                stream.seek(max(0, console.stat().st_size - 2 * 1024**2))
                (args.evidence / 'console.log').write_bytes(stream.read())
        (args.evidence / 'ownership.json').write_text(ownership.read_text())
        if not (passed and args.retain_for_dr_qualification):
            try:
                cleanup(ownership)
            except BaseException as error:
                (args.evidence / 'cleanup.json').write_text(json.dumps({
                    'status': 'UNKNOWN', 'domainUuid': identity, 'ownershipManifest': str(ownership),
                    'failure': str(error)}, indent=2) + '\n')
                if passed:
                    (args.evidence / 'result.json').write_text(json.dumps({
                        'status': 'PARTIAL', 'bootAndQgaPassed': True, 'cleanupStatus': 'UNKNOWN',
                        'productionQualified': False}, indent=2) + '\n')
                    raise
                # Preserve the original boot error; the separate cleanup receipt
                # identifies any resources requiring explicit reconciliation.
            else:
                (args.evidence / 'cleanup.json').write_text(json.dumps({
                    'status': 'LIVE_VERIFIED', 'domainUuid': identity,
                    'ownedDomainAbsent': True, 'ownedRuntimeWorkspaceRemoved': True}, indent=2) + '\n')
        else:
            (args.evidence / 'cleanup.json').write_text(json.dumps({
                'status': 'PENDING', 'reason': 'EXPLICITLY_RETAINED_FOR_DR_QUALIFICATION',
                'domainUuid': identity, 'ownershipManifest': str(ownership)}, indent=2) + '\n')


def main():
    def terminated(_signum, _frame):
        raise KeyboardInterrupt('runner termination requested; cleaning owned domain')
    signal.signal(signal.SIGTERM, terminated)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--retain-for-dr-qualification', action='store_true')
    parser.add_argument('--cleanup-manifest', type=Path)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('run through the approved root runner')
    if args.cleanup_manifest:
        if args.image or args.sha256 or args.evidence or args.retain_for_dr_qualification:
            parser.error('cleanup cannot be combined with boot arguments')
        cleanup(args.cleanup_manifest)
    else:
        if not args.image or not args.sha256 or not args.evidence:
            parser.error('--image, --sha256 and --evidence are required')
        boot(args)


if __name__ == '__main__':
    main()
