import argparse
import hashlib
import json
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
import xml.etree.ElementTree as ET

import boot_qga_acceptance as boot


class BootAcceptanceTests(unittest.TestCase):
    def test_command_failure_preserves_bounded_causal_output(self):
        failure = subprocess.CalledProcessError(1, ['virsh'], output='x' * 20000 + 'causal libvirt error')
        with patch.object(boot.subprocess, 'check_output', side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                boot.run(['virsh', 'create', '/owned/domain.xml'])
        diagnostic = json.loads(str(caught.exception))
        self.assertEqual(1, diagnostic['returnCode'])
        self.assertEqual(16384, len(diagnostic['output']))
        self.assertTrue(diagnostic['output'].endswith('causal libvirt error'))

    def record(self):
        identity = str(uuid.uuid4())
        work = boot.PREFIX / ('layersentry-cpuqc-' + identity)
        return {'domainUuid': identity, 'domainName': work.name,
                'diskPath': str(work / 'runtime.qcow2'), 'seedPath': str(work / 'seed.iso'),
                'consolePath': str(work / 'console.log'), 'sourceSha256': 'a' * 64}

    def test_domain_is_networkless_and_binds_only_owned_disks(self):
        record = self.record()
        xml = ET.fromstring(boot.xml_for(record))
        self.assertEqual([], xml.findall('./devices/interface'))
        self.assertEqual(record['domainUuid'], xml.findtext('uuid'))
        self.assertEqual([record['diskPath'], record['seedPath']],
                         [node.get('file') for node in xml.findall('./devices/disk/source')])
        self.assertEqual('org.qemu.guest_agent.0', xml.find('./devices/channel/target').get('name'))
        self.assertEqual('q35', xml.find('./os/type').get('machine'))

    def test_ownership_rejects_path_name_mismatch_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            outside = parent / 'ownership.json'
            outside.write_text(json.dumps(self.record()))
            with self.assertRaises(ValueError):
                boot.load_ownership(outside)
            linked = parent / 'linked'
            linked.symlink_to(outside)
            with self.assertRaises(ValueError):
                boot.load_ownership(linked)

    def test_cleanup_refuses_changed_live_network_without_mutation(self):
        record = self.record()
        xml = ET.fromstring(boot.xml_for(record))
        ET.SubElement(xml.find('devices'), 'interface', type='network')
        with patch.object(boot, 'load_ownership', return_value=record), \
                patch.object(boot, 'virsh', side_effect=[record['domainUuid'] + '\n', ET.tostring(xml, encoding='unicode')]) as command, \
                patch.object(boot.shutil, 'rmtree') as remove:
            with self.assertRaises(ValueError):
                boot.cleanup(Path('/unused/ownership.json'))
            self.assertEqual(2, command.call_count)
            remove.assert_not_called()

    def test_cleanup_connection_failure_does_not_delete_owned_disk(self):
        record = self.record()
        with patch.object(boot, 'load_ownership', return_value=record), \
                patch.object(boot, 'virsh', side_effect=RuntimeError('socket unavailable')), \
                patch.object(boot.shutil, 'rmtree') as remove:
            with self.assertRaises(RuntimeError):
                boot.cleanup(Path('/unused/ownership.json'))
            remove.assert_not_called()

    def test_backed_image_rejected_before_evidence_or_domain_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'candidate'
            image.write_bytes(b'candidate')
            evidence = Path(directory) / 'evidence'
            args = argparse.Namespace(image=image, sha256=hashlib.sha256(b'candidate').hexdigest(), evidence=evidence)
            with patch.object(boot, 'run', return_value=json.dumps({'format': 'qcow2', 'backing-filename': 'other', 'virtual-size': 4096})), \
                    patch.object(boot, 'virsh') as command:
                with self.assertRaises(ValueError):
                    boot.boot(args)
                self.assertFalse(evidence.exists())
                command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
