"""Real offline QCOW sealing and crash/security checks; no libvirt/guest mutation."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dr_file_replication import FileCatalog,FileDisk,FilePlan,QcowTools,check_qcow2,secure_root
from dr_libvirt_capture import _completed_provider_receipt,_seal_completed_capture
from dr_replication import Repository,ReplicationError,fingerprint


def uid():return str(uuid.uuid4())


@unittest.skipUnless(os.environ.get('LAYERSENTRY_TEST_QEMU_IMG') and os.environ.get('LAYERSENTRY_TEST_QEMU_IO'),
                     'real offline QEMU binaries required; no synthetic reconstruction claims')
class CaptureSealingCase(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='layersentry-seal-test-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.img=os.environ['LAYERSENTRY_TEST_QEMU_IMG'];self.io=os.environ['LAYERSENTRY_TEST_QEMU_IO']
        match=re.search(r'version (\d+)\.(\d+)\.(\d+)',self.run_image('--version').decode())
        version=int(match[1])*1000000+int(match[2])*1000+int(match[3])
        self.source=self.root/'source.qcow2';self.run_image('create','-f','qcow2',str(self.source),'1048576')
        self.run_io(self.source,'write -P 0x11 0 1048576')
        self.plan=FilePlan(plan_id=uid(),tenant_id=uid(),workload_id=uid(),source_site_id=uid(),recovery_site_id=uid(),repository_id=uid(),domain_uuid=uid(),domain_name='i-test-VM',disks=(FileDisk('vda',uid(),str(self.source),1048576),),libvirt_version=11010000,qemu_version=version,max_bytes=8*1024*1024,reserve_bytes=0,minimum_retention_seconds=0,retention_count=2)
        self.tools=QcowTools(Path(self.img),version)

    def run_image(self,*args):return subprocess.run([self.img,*args],check=True,capture_output=True,timeout=30).stdout
    def run_io(self,path,command):return subprocess.run([self.io,'-f','qcow2','-c',command,str(path)],check=True,capture_output=True,timeout=30).stdout
    def folder(self,name):
        path=self.root/name;path.mkdir(mode=0o700);return path

    def capture(self,*,parent=None,proof=True):
        epoch=uid();folder=self.folder(epoch);journal=self.folder('journal-'+epoch);path=folder/'vda.qcow2'
        if parent:
            self.run_image('create','-f','qcow2','-F','qcow2','-b',str(self.source),str(path))
        else:self.run_image('convert','-f','qcow2','-O','qcow2',str(self.source),str(path))
        path.chmod(0o400)
        intent={'epoch_id':epoch,'scope_sha256':fingerprint(self.plan.scope()),'mode':'INCREMENTAL' if parent else 'FULL','parent':parent,'previous_head':parent['epoch_id'] if parent else None,'previous_captured_at_epoch':0,'requested_at_epoch':int(time.time())}
        if proof:_completed_provider_receipt(self.plan,intent,folder,journal,int(time.time()))
        return intent,folder,journal

    def seal(self,intent,folder,journal,tools=None):
        return _seal_completed_capture(self.plan,intent,folder,journal,tools or self.tools,time.monotonic()+30)

    def parent(self):return {'epoch_id':uid(),'manifest_sha256':'b'*64}

    def test_real_full_incremental_and_explicit_zero_reconstruction_preserves_sparsity(self):
        full,full_dir,full_journal=self.capture();full_manifest=self.seal(full,full_dir,full_journal)
        parent={'epoch_id':full['epoch_id'],'manifest_sha256':fingerprint(full_manifest)}
        inc,inc_dir,inc_journal=self.capture(parent=parent,proof=False);path=inc_dir/'vda.qcow2'
        path.chmod(0o600);self.run_io(path,'write -P 0x22 0 65536');self.run_io(path,'write -z 65536 65536');path.chmod(0o400)
        _completed_provider_receipt(self.plan,inc,inc_dir,inc_journal,int(time.time()))
        before=json.loads(self.run_image('map','--output=json',str(path)));blocks=path.stat().st_blocks
        # The original changes after capture. Sealing must never flatten/read it.
        self.run_io(self.source,'write -P 0x33 0 1048576')
        with secure_root(inc_dir) as fd:
            with self.assertRaisesRegex(ReplicationError,'UNSAFE_OR_UNSEALED'):check_qcow2(fd,{'filename':path.name,'virtual_bytes':1048576})
        inc_manifest=self.seal(inc,inc_dir,inc_journal)
        after=json.loads(self.run_image('map','--output=json',str(path)))
        def allocated(rows):return [{k:r[k] for k in ('start','length','data','zero','offset') if k in r} for r in rows if r.get('present') and r['depth']==0]
        self.assertEqual(allocated(before),allocated(after));self.assertEqual(path.stat().st_blocks,blocks)
        self.assertTrue(any(r.get('present') and r.get('zero') and r['start']==65536 for r in after))
        self.assertLess(path.stat().st_blocks*512,1048576)
        repository=self.folder('repository');(repository/'.layersentry-repository.json').write_text(json.dumps({'schema':1,'site_id':self.plan.recovery_site_id,'repository_id':self.plan.repository_id}))
        catalog=FileCatalog(Repository(repository,self.plan.recovery_site_id,self.plan.repository_id),self.plan)
        for manifest,folder in ((full_manifest,full_dir),(inc_manifest,inc_dir)):
            with catalog.incoming(manifest) as incoming:
                for entry in incoming.missing():incoming.write(entry,[(folder/entry['filename']).read_bytes()])
                incoming.commit()
        for manifest,expected in ((full_manifest,b'\x11'*1048576),(inc_manifest,b'\x22'*65536+b'\x00'*65536+b'\x11'*(1048576-131072))):
            output=self.folder('restore-'+manifest['epoch_id']);receipt=catalog.materialize(manifest['epoch_id'],output,self.tools)
            restored=Path(receipt['output_directory'])/'disks/vda.qcow2';raw=output/'data.raw'
            self.run_image('convert','-f','qcow2','-O','raw',str(restored),str(raw));self.assertEqual(raw.read_bytes(),expected)

    def test_detach_resumes_after_native_success_without_repeating_mutation(self):
        intent,folder,journal=self.capture(parent=self.parent());original=self.tools.detach_completed_capture
        def interrupted(path,deadline):
            original(path,deadline);raise ReplicationError('SIMULATED_COMPLETION_LOSS')
        self.tools.detach_completed_capture=Mock(side_effect=interrupted)
        with self.assertRaisesRegex(ReplicationError,'SIMULATED'):self.seal(intent,folder,journal)
        self.assertTrue((journal/'seal-vda.json').exists());self.assertFalse((journal/'capture-complete.json').exists())
        self.tools.detach_completed_capture=Mock(side_effect=AssertionError('must not replay detached metadata'))
        manifest=self.seal(intent,folder,journal);self.tools.detach_completed_capture.assert_not_called()
        self.assertEqual((folder/'vda.qcow2').stat().st_mode & 0o777,0o400)
        self.assertEqual(manifest,self.seal(intent,folder,journal))

    def test_detach_does_not_open_missing_original_backing(self):
        intent,folder,journal=self.capture(parent=self.parent());self.source.unlink()
        self.seal(intent,folder,journal)
        self.assertTrue((journal/'capture-complete.json').exists())

    def test_old_epoch_without_provider_receipt_cannot_be_salvaged(self):
        intent,folder,journal=self.capture(parent=self.parent(),proof=False)
        tools=Mock()
        with self.assertRaises(FileNotFoundError):self.seal(intent,folder,journal,tools)
        self.assertEqual(tools.mock_calls,[])

    def test_foreign_backing_and_features_rejected_before_image_parser(self):
        cases=[('path','/tmp/foreign.qcow2'),('protocol','https://example.invalid/image'),('relative','foreign.qcow2'),('crypt',None),('snapshot',None),('incompatible',None),('external-extension',None)]
        for name,value in cases:
            with self.subTest(name=name):
                intent,folder,journal=self.capture(parent=self.parent(),proof=False);path=folder/'vda.qcow2';path.chmod(0o600)
                if value:self.run_image('rebase','-u','-f','qcow2','-F','qcow2','-b',value,str(path))
                else:
                    with path.open('r+b') as stream:
                        if name=='crypt':stream.seek(32);stream.write(struct.pack('>I',1))
                        elif name=='snapshot':stream.seek(60);stream.write(struct.pack('>I',1))
                        elif name=='incompatible':stream.seek(72);stream.write(struct.pack('>Q',4))
                        else:
                            raw=stream.read(104);length=struct.unpack_from('>I',raw,100)[0];stream.seek(length);stream.write(struct.pack('>I',0x44415441))
                path.chmod(0o400);_completed_provider_receipt(self.plan,intent,folder,journal,int(time.time()))
                before=hashlib.sha256(path.read_bytes()).hexdigest();tools=Mock()
                with self.assertRaises(ReplicationError):self.seal(intent,folder,journal,tools)
                tools.check.assert_not_called();tools.detach_completed_capture.assert_not_called()
                self.assertEqual(before,hashlib.sha256(path.read_bytes()).hexdigest());self.assertFalse((journal/'capture-complete.json').exists())

    def test_changed_completion_intent_or_capture_inode_is_rejected(self):
        intent,folder,journal=self.capture(parent=self.parent());wrong={**intent,'requested_at_epoch':0};tools=Mock()
        with self.assertRaisesRegex(ReplicationError,'PROVIDER_COMPLETION_BINDING'):self.seal(wrong,folder,journal,tools)
        tools.check_version.assert_not_called()
        path=folder/'vda.qcow2';path.rename(folder/'old.qcow2');shutil.copyfile(folder/'old.qcow2',path);path.chmod(0o400)
        with self.assertRaisesRegex(ReplicationError,'COMPLETED_CAPTURE_FILE_CHANGED'):self.seal(intent,folder,journal,tools)
        tools.check.assert_not_called();tools.detach_completed_capture.assert_not_called()

    def test_changed_header_after_sealing_intent_is_not_replayed(self):
        intent,folder,journal=self.capture(parent=self.parent());self.tools.detach_completed_capture=Mock(side_effect=ReplicationError('INTERRUPTED'))
        with self.assertRaisesRegex(ReplicationError,'INTERRUPTED'):self.seal(intent,folder,journal)
        path=folder/'vda.qcow2'
        with path.open('r+b') as stream:stream.seek(65535);stream.write(b'X')
        self.tools.detach_completed_capture.reset_mock()
        with self.assertRaisesRegex(ReplicationError,'CAPTURE_HEADER_CHANGED'):self.seal(intent,folder,journal)
        self.tools.detach_completed_capture.assert_not_called()


if __name__=='__main__':unittest.main()
