"""Offline ownership, credential and completed-resume checks; no guest execution."""
import base64
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from bootstrap.credentials import ManagementCredentials, sanitized_kubeconfig
from bootstrap.native import protected_file, validate_plan
from bootstrap.transport import _GUEST_KUBECONFIG
from bootstrap_management import reconcile
from controller.model import InvalidRequestError
import test_management_bootstrap as fixtures
from test_management_bootstrap import IDS, PLAN


def kubeconfig():
    cert = base64.b64encode(b'-----BEGIN CERTIFICATE-----\nfixture\n-----END CERTIFICATE-----').decode()
    key = base64.b64encode(b'-----BEGIN PRIVATE KEY-----\nfixture\n-----END PRIVATE KEY-----').decode()
    return {'apiVersion': 'v1', 'kind': 'Config', 'clusters': [{'name': 'local', 'cluster': {'server': 'https://127.0.0.1:6443', 'certificate-authority-data': cert}}],
            'users': [{'name': 'admin', 'user': {'client-certificate-data': cert, 'client-key-data': key}}],
            'contexts': [{'name': 'default', 'context': {'cluster': 'local', 'user': 'admin'}}], 'current-context': 'default'}


class TemporaryForwardingTests(unittest.TestCase):
    setUp = fixtures.BootstrapTests.setUp
    tearDown = fixtures.BootstrapTests.tearDown
    vm = fixtures.BootstrapTests.vm

    def row(self, *, firewall=False):
        result = {'id': IDS[14 if firewall else 13], 'protocol': 'tcp', 'ipaddressid': PLAN['publicIpId'], 'networkid': PLAN['networkId'], 'state': 'Active'}
        if firewall:
            result.update(startport='2201', endport='2201', cidrlist='192.0.2.50/32')
        else:
            result.update(publicport='2201', publicendport='2201', privateport='22', privateendport='22', virtualmachineid=self.native.vm_id(1), vmguestip='192.0.2.1')
        return result

    def setup_row(self, row, *, firewall=False):
        key = 'ssh-firewall-1' if firewall else 'ssh-forward-1'
        self.journal.state['operations'][key] = {'state': 'OBSERVED', 'resourceId': row['id']}
        self.native.transport_inventory = Mock(return_value=[row])
        self.native.observe_vm = Mock(return_value=self.vm())

    def test_existing_exact_foreign_rule_is_never_adopted(self):
        self.native.transport_inventory = Mock(return_value=[self.row()])
        with self.assertRaises(InvalidRequestError):
            self.native.observe_transport(1)
        self.client.call.assert_not_called()

    def test_owned_forward_rejects_vm_ip_port_and_resource_drift(self):
        for field, value in [('virtualmachineid', IDS[18]), ('vmguestip', '203.0.113.22'), ('privateport', '23'), ('id', IDS[18])]:
            row = self.row()
            self.setup_row(row)
            row[field] = value
            with self.subTest(field=field), self.assertRaises(InvalidRequestError):
                self.native.observe_transport(1)

    def test_firewall_rejects_wider_sources_and_port_ranges(self):
        for changes in [{'cidrlist': '0.0.0.0/0'}, {'startport': '2200'}, {'endport': '2203'}]:
            row = self.row(firewall=True)
            self.setup_row(row, firewall=True)
            row.update(changes)
            with self.subTest(changes=changes), self.assertRaises(InvalidRequestError):
                self.native.observe_transport(1, firewall=True)

    def test_ambiguous_delete_is_never_replayed(self):
        self.setup_row(self.row(firewall=True), firewall=True)
        self.client.call.side_effect = TimeoutError()
        self.assertFalse(self.native.delete_transport_rule(1, firewall=True))
        self.client.reset_mock()
        self.assertFalse(self.native.delete_transport_rule(1, firewall=True))
        self.client.call.assert_not_called()
        self.native.transport_inventory.return_value = []
        self.assertTrue(self.native.delete_transport_rule(1, firewall=True))

    def test_cleanup_never_deletes_before_credentials_are_verified(self):
        with self.assertRaises(InvalidRequestError):
            self.native.cleanup_transport()
        self.client.call.assert_not_called()

    def test_completed_bootstrap_cannot_reopen_forwarding(self):
        self.journal.state['credentialsEscrowed'] = {'sha256': 'a'*64}
        with self.assertRaises(InvalidRequestError):
            self.native.ensure_transport([self.vm(i) for i in (1,2,3)])
        self.client.call.assert_not_called()

    def test_runner_ssh_requires_exact_approved_addresses(self):
        for cidrs in [['192.0.2.0/24'], ['198.51.100.1/32'], []]:
            with self.subTest(cidrs=cidrs), self.assertRaises(InvalidRequestError):
                validate_plan({**PLAN, 'sshSourceCidrs': cidrs})


class ForwardedSshTests(unittest.TestCase):
    setUp = fixtures.TransportTests.setUp
    tearDown = fixtures.TransportTests.tearDown
    file = fixtures.TransportTests.file

    def test_missing_forward_cannot_fall_back_to_private_guest_ip(self):
        self.transport.endpoints = {}
        with self.assertRaises(InvalidRequestError):
            self.transport.guest_call(self.vm, self.host, _GUEST_KUBECONFIG, {})
        self.runner.assert_not_called()

    def test_export_script_compiles_without_guest_execution(self):
        compile(_GUEST_KUBECONFIG, 'kubeconfig-export', 'exec')
        self.assertIn("'--raw','--flatten','--minify'", _GUEST_KUBECONFIG)


class CredentialTests(unittest.TestCase):
    def test_only_embedded_credentials_and_fixed_endpoint_are_escrowed(self):
        value = kubeconfig()
        clean = sanitized_kubeconfig(value, '198.51.100.10')
        self.assertEqual(clean['clusters'][0]['cluster']['server'], 'https://198.51.100.10:6443')
        for field, supplied in [('exec', {'command': 'unsafe'}), ('token', 'unsafe')]:
            changed = kubeconfig(); changed['users'][0]['user'][field] = supplied
            with self.assertRaises(InvalidRequestError):
                sanitized_kubeconfig(changed, '198.51.100.10')
        value['clusters'][0]['cluster']['insecure-skip-tls-verify'] = True
        with self.assertRaises(InvalidRequestError):
            sanitized_kubeconfig(value, '198.51.100.10')

    def test_escrow_is_private_usable_json_and_never_overwrites_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = ManagementCredentials(Path(directory) / 'management.json')
            credentials.install(kubeconfig(), '198.51.100.10')
            self.assertEqual(credentials.path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(credentials.path.stat().st_nlink, 1)
            credentials.install(kubeconfig(), '198.51.100.10')
            with self.assertRaises(InvalidRequestError):
                credentials.install(kubeconfig(), '198.51.100.11')

    def test_unsafe_owner_hardlink_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / 'original'; original.write_text('x'); original.chmod(0o600)
            linked = Path(directory) / 'linked'; os.link(original, linked)
            with self.assertRaises(InvalidRequestError):
                protected_file(original)
            linked.unlink(); linked.symlink_to(original)
            with self.assertRaises(InvalidRequestError):
                protected_file(linked)
            info = original.stat()
            fake = Mock(st_mode=info.st_mode, st_uid=999999, st_nlink=1, st_size=1)
            with patch.object(Path, 'lstat', return_value=fake), self.assertRaises(InvalidRequestError):
                protected_file(original)

    def test_completed_reconcile_uses_api_without_ssh_or_vm_mutation(self):
        native, transport, credentials = Mock(), Mock(), Mock()
        native.journal.state = {'credentialsEscrowed': {'sha256': 'a'*64}, 'transportClosed': True}
        native.preflight.return_value = {'independentHostPlacement': True}
        native.hosts = {'host': {}}
        native.node_name.side_effect = lambda i: 'cp'+str(i)
        native.observe_vm.return_value = {'id': 'vm', 'hostid': 'host', 'state': 'Running', 'nic': [{'isdefault': True, 'ipaddress': '192.0.2.1'}]}
        native.cleanup_transport.return_value = True
        credentials.digest.return_value = 'a'*64
        credentials.inspect.return_value = {'nodes': [{'name': 'cp'+str(i), 'ready': True, 'controlPlane': True, 'version': 'v1.36.4+rke2r1'} for i in (1,2,3)], 'endpoint9345Tls': True}
        result = reconcile(native, transport, credentials)
        self.assertEqual(result['status'], 'LIVE_VERIFIED')
        native.ensure_nodes.assert_not_called(); native.ensure_transport.assert_not_called()
        transport.configure.assert_not_called(); transport.formation.assert_not_called(); transport.export_credentials.assert_not_called()
        credentials.digest.return_value = 'b'*64
        with self.assertRaises(InvalidRequestError):
            reconcile(native, transport, credentials)
        native.ensure_transport.assert_not_called()


if __name__ == '__main__':
    unittest.main()
