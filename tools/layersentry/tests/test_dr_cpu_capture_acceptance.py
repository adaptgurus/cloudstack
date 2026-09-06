import argparse
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dr_cpu_capture_acceptance as acceptance


class CaptureFixtureGuards(unittest.TestCase):
    def fixture(self, *, network=False):
        identity = str(uuid.uuid4())
        record = {'domainUuid': identity, 'domainName': 'layersentry-cpuqc-' + identity,
                  'diskPath': '/var/lib/libvirt/images/layersentry-cpuqc-' + identity + '/runtime.qcow2',
                  'retainForDrQualification': True}
        xml = '<domain><devices><disk type="file" device="disk"><driver type="qcow2"/><source file="' + record['diskPath'] + '"/><target dev="vda"/></disk>'
        if network:
            xml += '<interface type="network"/>'
        xml += '</devices></domain>'
        domain = Mock()
        domain.UUIDString.return_value = identity
        domain.name.return_value = record['domainName']
        domain.isActive.return_value = 1
        domain.XMLDesc.return_value = xml
        domain.listAllCheckpoints.return_value = []
        domain.snapshotNum.return_value = 0
        connection = Mock()
        connection.lookupByUUIDString.return_value = domain
        return record, domain, connection

    def test_unretained_fixture_is_rejected_before_libvirt_lookup(self):
        record, _, connection = self.fixture()
        record['retainForDrQualification'] = False
        with patch.object(acceptance.boot, 'load_ownership', return_value=record):
            with self.assertRaises(ValueError):
                acceptance.fixture(Path('/unused'), connection)
        connection.lookupByUUIDString.assert_not_called()

    def test_networked_or_used_fixture_is_rejected_before_capture(self):
        for network in [True, False]:
            record, domain, connection = self.fixture(network=network)
            if not network:
                domain.listAllCheckpoints.return_value = [Mock()]
            with patch.object(acceptance.boot, 'load_ownership', return_value=record):
                with self.assertRaises(ValueError):
                    acceptance.fixture(Path('/unused'), connection)
            domain.backupBegin.assert_not_called()

    def test_exact_fresh_fixture_is_accepted_without_mutation(self):
        record, domain, connection = self.fixture()
        with patch.object(acceptance.boot, 'load_ownership', return_value=record):
            self.assertEqual((record, domain), acceptance.fixture(Path('/unused'), connection))
        domain.backupBegin.assert_not_called()

    def test_lost_ack_follows_destination_commit_and_is_one_shot(self):
        catalog = Mock()
        receipt = {'state': 'COMMITTED', 'epoch_id': str(uuid.uuid4())}
        catalog.receive_local.return_value = receipt
        transport = acceptance.LostAckOnce(catalog)
        with self.assertRaisesRegex(acceptance.ReplicationError, 'QUALIFICATION_ACK_DROPPED_AFTER_COMMIT'):
            transport.send({'manifest': 'fixture'}, 17)
        catalog.receive_local.assert_called_once_with({'manifest': 'fixture'}, 17)
        self.assertEqual(receipt, transport.dropped_receipt)
        self.assertEqual(receipt, transport.send({'manifest': 'fixture'}, 17))

    def test_existing_evidence_is_never_overwritten_on_refusal(self):
        record, domain, connection = self.fixture()
        connection.getLibVersion.return_value = 11010000
        connection.getVersion.return_value = 10001000
        provider = Mock()
        provider.open.return_value = connection
        with tempfile.TemporaryDirectory() as temporary:
            evidence = Path(temporary)
            previous = evidence / 'result.json'
            previous.write_text('preserve existing evidence')
            args = argparse.Namespace(source_commit='a' * 40, libvirt_version=11010000,
                                      qemu_version=10001000, ownership_manifest=Path('/unused'), evidence=evidence)
            with patch.dict(sys.modules, {'libvirt': provider}), \
                    patch.object(acceptance.boot, 'run', return_value='Enforcing'), \
                    patch.object(acceptance, 'fixture', return_value=(record, domain)):
                with self.assertRaisesRegex(ValueError, 'evidence directory must be new'):
                    acceptance.run_acceptance(args)
            self.assertEqual('preserve existing evidence', previous.read_text())
        connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
