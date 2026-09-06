#!/usr/bin/env python3
"""Real, same-host libvirt capture acceptance on one explicitly retained CPU fixture."""
from __future__ import annotations

import argparse
import base64
from dataclasses import asdict
import grp
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import signal
import sys
import time
import uuid
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent / 'k8s/image'))
import boot_qga_acceptance as boot
from dr_file_replication import FileCatalog, FileDisk, FilePlan, QcowTools
from dr_libvirt_capture import FileReplicationEngine
from dr_replication import Repository, ReplicationError
from dr_replication_transport import MountedTransport

PREFIX = Path('/var/lib/libvirt/images')
STAGES = {'FULL': 0x31, 'INC1': 0x52, 'INC2': 0}
MARKER_BYTES = 1024 * 1024


def save(path, value):
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('x', encoding='utf-8') as stream:
        os.chmod(temporary, 0o600)
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def fixture(path, connection):
    record = boot.load_ownership(path)
    check(record.get('retainForDrQualification') is True, 'CPU fixture was not explicitly retained for DR')
    domain = connection.lookupByUUIDString(record['domainUuid'])
    check(domain.UUIDString() == record['domainUuid'] and domain.name() == record['domainName'], 'fixture identity mismatch')
    check(domain.isActive() == 1, 'retained CPU fixture must be running')
    xml = ET.fromstring(domain.XMLDesc(0))
    check(not xml.findall('./devices/interface'), 'fixture must have no NIC')
    writable = [disk for disk in xml.findall('./devices/disk') if disk.get('device') == 'disk' and disk.find('readonly') is None]
    check(len(writable) == 1, 'fixture must have exactly one writable disk')
    disk = writable[0]
    check(disk.get('type') == 'file' and disk.find('driver').get('type') == 'qcow2'
          and disk.find('source').get('file') == record['diskPath']
          and disk.find('target').get('dev') == 'vda', 'fixture disk binding changed')
    check(not domain.listAllCheckpoints(0) and domain.snapshotNum(0) == 0, 'fresh checkpoint-free fixture required; do not replay a prior run')
    return record, domain


def qga_python(identity, script, arguments=(), timeout=120):
    process = boot.agent(identity, {'execute': 'guest-exec', 'arguments': {
        'path': '/usr/bin/python3', 'arg': ['-c', script, *arguments], 'capture-output': True}})
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = boot.agent(identity, {'execute': 'guest-exec-status', 'arguments': {'pid': process['pid']}})
        if status.get('exited'):
            check(not status.get('out-truncated') and not status.get('err-truncated'), 'QGA output truncated')
            stdout = base64.b64decode(status.get('out-data', ''), validate=True).decode()
            stderr = base64.b64decode(status.get('err-data', ''), validate=True).decode()
            check(status.get('exitcode') == 0, 'guest command failed: ' + stdout + stderr)
            return json.loads(stdout)
        time.sleep(1)
    raise TimeoutError('QGA command timeout; mutation is not replayed')


def marker(identity, stage, *, write):
    check(stage in STAGES, 'invalid marker stage')
    script = r'''
import hashlib,json,os,pathlib,sys
stage,operation=sys.argv[1:]
values={'FULL':0x31,'INC1':0x52,'INC2':0}
assert stage in values and operation in ['write','read']
root=pathlib.Path('/var/tmp/layersentry-dr-qualification')
if operation=='write':
 root.mkdir(mode=0o700,exist_ok=True)
 assert not root.is_symlink() and root.stat().st_uid==0
 assert root.stat().st_dev==pathlib.Path('/').stat().st_dev, 'marker must be on captured root filesystem'
 for name,data in [('stage.txt',(stage+'\n').encode()),('payload.bin',bytes([values[stage]])*(1024*1024))]:
  path=root/name
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
  with os.fdopen(fd,'wb') as stream:
   stream.write(data);stream.flush();os.fsync(stream.fileno())
 fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
 os.fsync(fd);os.close(fd);os.sync()
data=(root/'payload.bin').read_bytes()
actual=(root/'stage.txt').read_text().strip()
assert actual==stage and data==bytes([values[stage]])*(1024*1024)
print(json.dumps({'stage':actual,'sizeBytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'allZero':not any(data)},sort_keys=True))
'''
    result = qga_python(identity, script, [stage, 'write' if write else 'read'])
    check(result == {'stage': stage, 'sizeBytes': MARKER_BYTES,
                     'sha256': hashlib.sha256(bytes([STAGES[stage]]) * MARKER_BYTES).hexdigest(),
                     'allZero': STAGES[stage] == 0}, 'guest marker result mismatch')
    return result


class LostAckOnce(MountedTransport):
    """Lose the first ACK only after the real destination has durably committed."""
    def __init__(self, catalog):
        super().__init__(catalog)
        self.dropped_receipt = None

    def send(self, manifest, source_folder):
        receipt = super().send(manifest, source_folder)
        if self.dropped_receipt is None:
            self.dropped_receipt = receipt
            raise ReplicationError('QUALIFICATION_ACK_DROPPED_AFTER_COMMIT')
        return receipt


def checkpoints(domain):
    return sorted(checkpoint.getName() for checkpoint in domain.listAllCheckpoints(0))


def receipt_identity(receipt):
    return {key: receipt[key] for key in ['state', 'epoch_id', 'manifest_sha256', 'chain_length', 'captured_at_epoch', 'bytes']}


def run_acceptance(args):
    import libvirt
    check(re.fullmatch(r'[a-f0-9]{40}', args.source_commit or '') is not None, 'exact reviewed source commit required')
    check(boot.run(['getenforce']).strip() == 'Enforcing', 'host SELinux must be Enforcing')
    check(args.libvirt_version >= 7002000 and args.qemu_version >= 4002000, 'explicit supported provider pins required')
    connection = libvirt.open('qemu:///system')
    check(connection is not None, 'local libvirt unavailable')
    work = None
    evidence_created = False
    recovered = []
    result = {'status': 'NOT_TESTED', 'scope': 'same-host networkless libvirt QCOW2 provider acceptance',
              'productionQualified': False, 'nativeCloudStackRecoveryTested': False,
              'crossSiteTransportTested': False, 'failoverTested': False, 'multiDiskTested': False,
              'rke2Started': False, 'phases': []}
    try:
        check(connection.getLibVersion() == args.libvirt_version and connection.getVersion() == args.qemu_version,
              'libvirt/QEMU version pin mismatch')
        source, domain = fixture(args.ownership_manifest, connection)
        check(not args.evidence.exists() and not args.evidence.is_symlink(), 'evidence directory must be new')
        args.evidence.mkdir(mode=0o700, parents=True)
        evidence_created = True
        identity = str(uuid.uuid4())
        work = PREFIX / ('layersentry-drqc-' + identity)
        work.mkdir(mode=0o750)
        qemu_uid, qemu_gid = pwd.getpwnam('qemu').pw_uid, grp.getgrnam('qemu').gr_gid
        os.chown(work, 0, qemu_gid)
        for name in ['state', 'capture', 'repository', 'restore']:
            (work / name).mkdir(mode=0o750 if name == 'capture' else 0o700)
        os.chown(work / 'capture', 0, qemu_gid)
        virtual_size = domain.blockInfo('vda', 0)[0]
        check(0 < virtual_size <= 128 * 1024**3, 'fixture disk size outside bounded scope')
        plan = FilePlan(plan_id=identity, tenant_id=str(uuid.uuid4()), workload_id=source['domainUuid'],
                        source_site_id=str(uuid.uuid4()), recovery_site_id=str(uuid.uuid4()), repository_id=str(uuid.uuid4()),
                        domain_uuid=source['domainUuid'], domain_name=source['domainName'],
                        disks=(FileDisk('vda', str(uuid.uuid4()), source['diskPath'], virtual_size),),
                        libvirt_version=args.libvirt_version, qemu_version=args.qemu_version,
                        max_chain=4, retention_count=3, minimum_retention_seconds=0, max_points=8,
                        capture_timeout=600, transfer_timeout=900, max_bytes=virtual_size * 2 + 1024**3)
        plan.validate()
        ownership = {'schemaVersion': '1.0', 'workspaceUuid': identity, 'workspace': str(work),
                     'sourceOwnershipManifest': str(args.ownership_manifest), 'sourceDomainUuid': source['domainUuid'],
                     'sourceImageSha256': source['sourceSha256'], 'recoveredDomains': [], 'finished': False}
        save(work / 'ownership.json', ownership)
        save(work / 'repository/.layersentry-repository.json', {'schema': 1, 'site_id': plan.recovery_site_id, 'repository_id': plan.repository_id})
        save(work / 'plan.json', asdict(plan))
        boot.run(['restorecon', '-RF', str(work)])
        tools = QcowTools(Path('/usr/bin/qemu-img'), args.qemu_version)
        tools.check_version(time.monotonic() + 30)
        catalog = FileCatalog(Repository(work / 'repository', plan.recovery_site_id, plan.repository_id), plan)
        transport = MountedTransport(catalog)

        def engine(selected=transport):
            return FileReplicationEngine(plan, work / 'state', work / 'capture', selected,
                                         qemu_uid=qemu_uid, qemu_gid=qemu_gid, qemu_img=Path('/usr/bin/qemu-img'))

        result.update({'sourceImageSha256': source['sourceSha256'], 'sourceDomainUuid': source['domainUuid'],
                       'sourceCommit': args.source_commit,
                       'workspace': str(work), 'libvirtVersion': args.libvirt_version, 'qemuVersion': args.qemu_version,
                       'testPlan': asdict(plan), 'testIdentityScope': 'local qualification UUIDs, not CloudStack site/resource IDs'})
        points = {}
        for stage in STAGES:
            started = time.monotonic()
            expected = marker(source['domainUuid'], stage, write=True)
            epoch = str(uuid.uuid4())
            points[stage] = epoch
            mode = 'FULL' if stage == 'FULL' else 'INCREMENTAL'
            if stage == 'INC1':
                lost = LostAckOnce(catalog)
                writer = engine(lost)
                try:
                    writer.replicate(epoch, mode=mode)
                except ReplicationError as error:
                    check(str(error) == 'QUALIFICATION_ACK_DROPPED_AFTER_COMMIT', 'unexpected capture/transfer failure')
                else:
                    raise AssertionError('lost ACK injection did not fire')
                check(lost.dropped_receipt is not None, 'ACK was not lost after a real commit')
                before = checkpoints(domain)
                state = writer.status()
                check(state['head']['epoch_id'] == points['FULL'] and state['active_epoch'] == epoch
                      and state['active_state'] == 'TRANSFERRING', 'source cursor advanced without ACK')
                committed = catalog.verify(epoch)
                receipt = engine().replicate(epoch, mode=mode, allow_capture=False)
                check(receipt_identity(receipt) == receipt_identity(committed) and checkpoints(domain) == before,
                      'ACK resume changed capture lineage')
                result['lostAck'] = {'stateBeforeResume': state, 'destinationCommitted': True,
                                     'captureProhibitedDuringResume': True, 'checkpointCountUnchanged': True}
            else:
                receipt = engine().replicate(epoch, mode=mode)
            check(receipt['state'] == 'COMMITTED' and receipt['chain_length'] == len(points), 'capture chain receipt mismatch')
            check(checkpoints(domain) == sorted('lsdr-' + item for item in points.values()), 'unexpected provider checkpoints')
            check(engine().status()['head']['epoch_id'] == epoch, 'acknowledged source head mismatch')
            phase = {'stage': stage, 'epochId': epoch, 'marker': expected, 'receipt': receipt,
                     'elapsedSeconds': round(time.monotonic() - started, 3)}
            result['phases'].append(phase)
            save(args.evidence / 'progress.json', result)

        before_checkpoints = checkpoints(domain)
        repeated = engine().replicate(points['FULL'], mode='FULL', allow_capture=False)
        check(receipt_identity(repeated) == receipt_identity(result['phases'][0]['receipt']), 'completed epoch replay changed receipt')
        check(engine().status()['head']['epoch_id'] == points['INC2'] and checkpoints(domain) == before_checkpoints,
              'completed epoch replay rewound cursor or recaptured')
        try:
            engine().replicate(points['INC2'], mode='FULL', allow_capture=False)
        except ReplicationError as error:
            check(str(error) == 'EPOCH_MODE_CONFLICT', 'unexpected negative case result')
        else:
            raise AssertionError('conflicting epoch mode was accepted')
        check(checkpoints(domain) == before_checkpoints and catalog.listing()['total'] == 3, 'negative case mutated provider/catalog')
        result['idempotency'] = {'oldCompletedEpochReplayPassed': True, 'sourceHeadUnchanged': True,
                                 'negativeModeConflict': 'EPOCH_MODE_CONFLICT', 'providerCheckpointsUnchanged': True}
        sealed_before = {stage: receipt_identity(catalog.verify(epoch)) for stage, epoch in points.items()}
        result['recoveries'] = []
        for stage in ['INC2', 'INC1']:
            started = time.monotonic()
            materialized = catalog.materialize(points[stage], work / 'restore', tools)
            disk = materialized['disks'][0]
            image = Path(materialized['output_directory']) / 'disks' / disk['filename']
            boot_evidence = args.evidence / ('recovery-' + stage.lower())
            boot.boot(argparse.Namespace(image=image, sha256=disk['sha256'], evidence=boot_evidence,
                                         retain_for_dr_qualification=True))
            recovery_record = json.loads((boot_evidence / 'ownership.json').read_text())
            recovery_manifest = Path(recovery_record['diskPath']).parent / 'ownership.json'
            recovered.append(recovery_manifest)
            ownership['recoveredDomains'].append({'domainUuid': recovery_record['domainUuid'], 'ownershipManifest': str(recovery_manifest)})
            save(work / 'ownership.json', ownership)
            actual = marker(recovery_record['domainUuid'], stage, write=False)
            boot.cleanup(recovery_manifest)
            recovered.remove(recovery_manifest)
            result['recoveries'].append({'stage': stage, 'epochId': points[stage], 'materialization': materialized,
                                         'guestMarker': actual, 'guestBootAndQgaPassed': True, 'ownedRuntimeRemoved': True,
                                         'elapsedSeconds': round(time.monotonic() - started, 3)})
            save(args.evidence / 'progress.json', result)
        sealed_after = {stage: receipt_identity(catalog.verify(epoch)) for stage, epoch in points.items()}
        check(sealed_before == sealed_after, 'retained replica changed during recovery')
        check(marker(source['domainUuid'], 'INC2', write=False)['allZero'], 'protected source data changed during recovery')
        check(boot.run(['getenforce']).strip() == 'Enforcing', 'host SELinux changed')
        result.update({'status': 'LIVE_VERIFIED', 'retainedReplicaIntegrityUnchanged': True,
                       'retainedReceipts': sealed_after, 'sourceFixtureRetained': True,
                       'qualificationLimits': ['same-host mounted transport', 'one writable disk', 'crash consistency',
                                               'no native CloudStack recovery/import', 'no failover/failback/fencing',
                                               'no RKE2 start or Kubernetes/storage qualification']})
    except BaseException as error:
        result.update({'status': 'PARTIAL', 'failureType': type(error).__name__, 'failure': str(error),
                       'captureReplay': 'PROHIBITED_WITHOUT_RECONCILIATION'})
        raise
    finally:
        cleanup_failures = []
        for path in recovered:
            try:
                boot.cleanup(path)
            except BaseException as error:
                cleanup_failures.append({'ownershipManifest': str(path), 'failure': str(error)})
        if cleanup_failures:
            result['cleanupFailures'] = cleanup_failures
            result['status'] = 'PARTIAL'
        if work is not None and (work / 'ownership.json').exists():
            ownership['finished'] = True
            save(work / 'ownership.json', ownership)
            result['ownershipManifest'] = str(work / 'ownership.json')
            # Journals contain only scoped IDs, file hashes and provider state.
            journal_evidence = args.evidence / 'journals'
            journal_evidence.mkdir(mode=0o700, exist_ok=True)
            for index, path in enumerate(sorted((work / 'state').rglob('*.json'))):
                check(index < 100 and not path.is_symlink() and path.stat().st_size <= 1024**2, 'journal evidence outside bounded scope')
                destination = journal_evidence / path.relative_to(work / 'state')
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
        if evidence_created:
            save(args.evidence / 'result.json', result)
        connection.close()
    check(result['status'] == 'LIVE_VERIFIED', 'capture acceptance did not fully pass')
    print(json.dumps(result, sort_keys=True))


def cleanup_workspace(path):
    import libvirt
    check(path.name == 'ownership.json' and not path.is_symlink(), 'invalid cleanup ownership path')
    record = json.loads(path.read_text())
    identity = str(uuid.UUID(record['workspaceUuid']))
    expected = PREFIX / ('layersentry-drqc-' + identity)
    check(path.parent == expected and path.resolve() == expected / 'ownership.json'
          and record['workspace'] == str(expected), 'cleanup workspace binding mismatch')
    check(path.stat().st_uid == 0 and not path.stat().st_mode & 0o077 and record['finished'] is True,
          'unfinished or non-private cleanup ownership')
    connection = libvirt.open('qemu:///system')
    check(connection is not None, 'local libvirt unavailable')
    try:
        for identity in [record['sourceDomainUuid'], *(item['domainUuid'] for item in record['recoveredDomains'])]:
            try:
                domain = connection.lookupByUUIDString(str(uuid.UUID(identity)))
            except libvirt.libvirtError as error:
                check(error.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN, 'cannot prove owned domain absence')
            else:
                check(domain.isActive() == 0, 'shut down owned source/recovery guests before cleanup')
        shutil.rmtree(expected)
    finally:
        connection.close()


def main():
    def terminated(_signum, _frame):
        raise KeyboardInterrupt('runner terminated; preserve capture lineage for reconciliation')
    signal.signal(signal.SIGTERM, terminated)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ownership-manifest', type=Path)
    parser.add_argument('--evidence', type=Path)
    parser.add_argument('--libvirt-version', type=int)
    parser.add_argument('--qemu-version', type=int)
    parser.add_argument('--source-commit')
    parser.add_argument('--cleanup-workspace', type=Path)
    args = parser.parse_args()
    check(os.geteuid() == 0, 'approved root runner required')
    if args.cleanup_workspace:
        check(not any([args.ownership_manifest, args.evidence, args.libvirt_version, args.qemu_version, args.source_commit]), 'cleanup cannot be combined with capture')
        cleanup_workspace(args.cleanup_workspace)
    else:
        check(all([args.ownership_manifest, args.evidence, args.libvirt_version, args.qemu_version, args.source_commit]), 'all capture arguments are required')
        run_acceptance(args)


if __name__ == '__main__':
    main()
