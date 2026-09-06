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

"""Source qualification of the first-management bootstrap; no live mutation."""
import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from uuid import UUID

from bootstrap.native import Journal, NativeBootstrap, NativeCloudStackClient, validate_plan, verify_image
from bootstrap.transport import TrustedGuestTransport, _HOST_OBSERVE, _GUEST_PUBLIC_KEY, _GUEST_CONFIGURE, _GUEST_FORMATION
from bootstrap_management import ready_nodes, reconcile
from controller.cloudstack import CloudStackConfig
from controller.model import InvalidRequestError

IDS = [str(UUID(int=index)) for index in range(1, 20)]
PUBLIC = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIEpUeCj6AGhVk6sNjIU7NLidFMzpBS1FdBr1pEDkGXm1'
PLAN = dict(zip(['bootstrapId', 'projectId', 'zoneId', 'networkId', 'serviceOfferingId', 'templateId', 'publicIpId'], IDS[:7]))
PLAN.update(name='management', hostIds=IDS[7:10], apiSourceCidrs=['192.0.2.50/32'], sshSourceCidrs=['192.0.2.50/32'])


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.directory.chmod(0o700)
        self.journal = Journal(self.directory / 'journal.json', 'pinned-plan')
        self.client = Mock()
        self.native = NativeBootstrap(self.client, PLAN, {'sha256': 'a' * 64}, self.journal, PUBLIC)

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def vm(self, ordinal=1):
        return {'id': self.native.vm_id(ordinal), 'name': self.native.node_name(ordinal),
                'projectid': PLAN['projectId'], 'zoneid': PLAN['zoneId'], 'templateid': PLAN['templateId'],
                'serviceofferingid': PLAN['serviceOfferingId'], 'state': 'Running', 'hostid': PLAN['hostIds'][ordinal-1],
                'instancename': f'i-1-{ordinal}-VM', 'nic': [{'networkid': PLAN['networkId'], 'isdefault': True, 'ipaddress': f'192.0.2.{ordinal}'}]}

    def test_plan_requires_three_control_plane_hosts(self):
        with self.assertRaises(InvalidRequestError):
            validate_plan({**PLAN, 'hostIds': IDS[7:9]})
        with self.assertRaises(InvalidRequestError):
            validate_plan({**PLAN, 'userToken': 'not-allowed'})

    def test_deterministic_vm_ids_survive_process_resume(self):
        expected = self.native.vm_id(1)
        self.assertEqual(expected, NativeBootstrap(self.client, PLAN, {}, self.journal, PUBLIC).vm_id(1))
        self.assertNotEqual(expected, self.native.vm_id(2))

    def test_unknown_deployment_is_never_replayed_when_vm_is_still_absent(self):
        self.client.call.side_effect = TimeoutError('opaque transport failure')
        with self.assertRaises(InvalidRequestError):
            self.native.advance('vm-1', 'deployVirtualMachine', {}, lambda: None)
        self.client.reset_mock()
        with self.assertRaises(InvalidRequestError):
            self.native.advance('vm-1', 'deployVirtualMachine', {}, lambda: None)
        self.client.call.assert_not_called()
        self.assertEqual(self.journal.state['operations']['vm-1']['state'], 'UNKNOWN')

    def test_late_visible_vm_recovers_unknown_submission_without_replay(self):
        self.journal.state['operations']['vm-1'] = {'state': 'UNKNOWN'}
        vm = self.vm()
        self.assertEqual(self.native.advance('vm-1', 'deployVirtualMachine', {}, lambda: vm), vm)
        self.client.call.assert_not_called()
        self.assertEqual(self.journal.state['operations']['vm-1']['state'], 'OBSERVED')

    def test_completed_job_with_no_exact_resource_stays_unknown(self):
        self.journal.state['operations']['vm-1'] = {'state': 'WAITING', 'jobId': IDS[11]}
        self.client.call.return_value = {'jobstatus': 1}
        with self.assertRaises(InvalidRequestError):
            self.native.advance('vm-1', 'deployVirtualMachine', {}, lambda: None)
        self.client.call.assert_called_once_with('queryAsyncJobResult', {'jobid': IDS[11]})
        self.assertEqual(self.journal.state['operations']['vm-1']['state'], 'UNKNOWN')

    def test_job_identity_is_retained_after_resource_observation(self):
        self.journal.state['operations']['vm-1'] = {'state': 'WAITING', 'jobId': IDS[11]}
        self.native.advance('vm-1', 'deployVirtualMachine', {}, lambda: self.vm())
        self.assertEqual(self.journal.state['operations']['vm-1']['jobId'], IDS[11])

    def test_vm_project_or_host_drift_fails_closed(self):
        self.client.call.return_value = {'virtualmachine': [{**self.vm(), 'projectid': IDS[12]}]}
        with self.assertRaises(InvalidRequestError):
            self.native.observe_vm(1)
        self.client.call.return_value = {'virtualmachine': [{**self.vm(), 'hostid': IDS[12]}]}
        with self.assertRaises(InvalidRequestError):
            self.native.observe_vm(1)

    def preflight_inventory(self, drift=None):
        p = PLAN
        resources = {
            'listProjects': {'project': [{'id': p['projectId'], 'state': 'Active'}]},
            'listZones': {'zone': [{'id': p['zoneId'], 'allocationstate': 'Enabled'}]},
            'listNetworks': {'network': [{'id': p['networkId'], 'projectid': p['projectId'], 'zoneid': p['zoneId'], 'state': 'Implemented', 'type': 'Isolated', 'service': [{'name': 'Lb'}, {'name': 'Firewall'}, {'name': 'PortForwarding'}], 'gateway': '192.0.2.1', 'cidr': '192.0.2.0/24'}]},
            'listServiceOfferings': {'serviceoffering': [{'id': p['serviceOfferingId'], 'state': 'Active', 'issystem': False}]},
            'listTemplates': {'template': [{'id': p['templateId'], 'isready': True, 'hypervisor': 'KVM', 'format': 'QCOW2', 'checksum': '{SHA-256}' + 'a'*64}]},
        }
        if drift:
            command, collection, key, value = drift
            resources[command][collection][0][key] = value
        def call(command, params):
            if command == 'listPublicIpAddresses':
                return {'publicipaddress': [{'id': p['publicIpId'], 'projectid': p['projectId'], 'zoneid': p['zoneId'], 'state': 'Allocated', 'ipaddress': '198.51.100.10', 'associatednetworkid': p['networkId'], 'issourcenat': True}]}
            if command == 'listHosts':
                return {'host': [{'id': params['id'], 'zoneid': p['zoneId'], 'state': 'Up', 'resourcestate': 'Enabled', 'hypervisor': 'KVM', 'ipaddress': '203.0.113.1'}]}
            return resources[command]
        return call

    def test_preflight_binds_every_native_input_and_rejects_image_or_network_drift(self):
        self.client.call.side_effect = self.preflight_inventory()
        self.assertFalse(self.native.preflight()['productionCertified'])
        self.assertIn('198.51.100.10/32', self.native.allowed_cidrs)
        for drift in [('listTemplates', 'template', 'checksum', 'bad'), ('listNetworks', 'network', 'projectid', IDS[12]), ('listNetworks', 'network', 'vpcid', IDS[12]), ('listNetworks', 'network', 'cidr', '10.42.0.0/24')]:
            self.client.call.side_effect = self.preflight_inventory(drift)
            with self.assertRaises(InvalidRequestError):
                self.native.preflight()
        self.assertTrue(all(call.args[0].startswith('list') for call in self.client.call.call_args_list))

    def test_broad_management_source_cidrs_are_rejected(self):
        with self.assertRaises(InvalidRequestError):
            validate_plan({**PLAN, 'apiSourceCidrs': ['0.0.0.0/0']})

    def test_existing_world_open_firewall_is_not_adopted(self):
        self.native.allowed_cidrs = ['192.0.2.50/32']
        self.client.call.return_value = {'firewallrule': [{'id': IDS[13], 'protocol': 'tcp', 'startport': '6443', 'endport': '6443', 'cidrlist': '0.0.0.0/0', 'state': 'Active'}]}
        with self.assertRaises(InvalidRequestError):
            self.native.observe_firewall(6443)

    def test_lb_creation_never_auto_opens_the_public_firewall(self):
        self.native.allowed_cidrs = ['192.0.2.50/32']
        self.client.call.side_effect = lambda command, params: {'loadbalancerrule': []} if command == 'listLoadBalancerRules' else {'jobid': IDS[11]}
        self.native.ensure_endpoints([self.vm()])
        creates = [call.args[1] for call in self.client.call.call_args_list if call.args[0] == 'createLoadBalancerRule']
        self.assertEqual(len(creates), 2)
        self.assertTrue(all(params['openfirewall'] is False for params in creates))
        self.assertTrue(all('cidrlist' not in params for params in creates))

    def test_native_userdata_contains_only_public_key_and_no_join_secret(self):
        calls = []
        def call(command, params):
            calls.append((command, params))
            return {'virtualmachine': []} if command == 'listVirtualMachines' else {'jobid': IDS[11]}
        self.client.call.side_effect = call
        self.native.ensure_nodes()
        creates = [params for command, params in calls if command == 'deployVirtualMachine']
        self.assertEqual(len(creates), 3)
        for params in creates:
            decoded = base64.b64decode(params['userdata']).decode()
            self.assertIn(PUBLIC, decoded)
            self.assertNotIn('token', decoded.lower())
            self.assertNotIn('PRIVATE KEY', decoded)
            self.assertEqual(params['projectid'], PLAN['projectId'])
        self.assertNotIn('userdata', self.journal.path.read_text())
        self.assertNotIn(PUBLIC, self.journal.path.read_text())

    def test_another_journal_writer_is_rejected(self):
        with self.assertRaises(InvalidRequestError):
            Journal(self.journal.path, 'pinned-plan')

    def test_resume_with_changed_identity_is_rejected(self):
        self.journal.close()
        with self.assertRaises(InvalidRequestError):
            Journal(self.journal.path, 'different-plan')

    def test_symlink_journal_is_rejected(self):
        self.journal.close()
        target = self.directory / 'target'
        self.journal.path.rename(target)
        self.journal.path.symlink_to(target)
        with self.assertRaises(InvalidRequestError):
            Journal(self.journal.path, 'pinned-plan')

    def test_unowned_lb_backend_is_rejected(self):
        rule = {'id': IDS[13]}
        self.native.observe_rule = lambda port: rule
        self.native.observe_firewall = lambda port: rule
        self.native.allowed_cidrs = PLAN['apiSourceCidrs']
        self.client.call.return_value = {'loadbalancerruleinstance': [{'id': IDS[14]}]}
        with self.assertRaises(InvalidRequestError):
            self.native.ensure_endpoints([self.vm()])

    def test_signed_client_rejects_transport_override_and_unapproved_command(self):
        key = self.directory / 'key'; key.write_text('runtime-key'); key.chmod(0o600)
        client = NativeCloudStackClient(CloudStackConfig('https://example.test/client/api', key, key))
        with self.assertRaises(InvalidRequestError):
            client._signed_query('deployVirtualMachine', {'command': 'destroyVirtualMachine'})
        with self.assertRaises(InvalidRequestError):
            client._signed_query('destroyVirtualMachine', {})
        self.assertIn('command=deployVirtualMachine', client._signed_query('deployVirtualMachine', {'customid': IDS[0]}))


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.key = self.file('key', 'runtime-private-test-value')
        self.token = self.file('token', 'a' * 64)
        self.known = self.file('known', '192.0.2.10 ' + PUBLIC)
        self.host_id = IDS[7]
        self.host = {'id': self.host_id, 'ipaddress': '192.0.2.10'}
        self.hosts = {self.host_id: {'address': '192.0.2.10', 'user': 'root', 'keyFile': str(self.key), 'knownHostsFile': str(self.known)}}
        self.runner = Mock(return_value=subprocess.CompletedProcess([], 0, PUBLIC.encode(), b''))
        self.transport = TrustedGuestTransport(self.hosts, self.key, self.token, runner=self.runner)
        self.vm = {'id': IDS[10], 'hostid': self.host_id, 'instancename': 'i-1-1-VM', 'nic': [{'isdefault': True, 'ipaddress': '192.0.2.11'}]}
        self.transport.bind_endpoints({IDS[10+i]: {'address': '198.51.100.10', 'port': 2201+i} for i in range(3)})
        self.runner.reset_mock()

    def file(self, name, data):
        path = self.directory / name; path.write_text(data); path.chmod(0o600)
        return path

    def tearDown(self):
        self.temp.cleanup()

    def test_embedded_programs_compile_without_execution(self):
        for index, source in enumerate((_HOST_OBSERVE, _GUEST_PUBLIC_KEY, _GUEST_CONFIGURE, _GUEST_FORMATION)):
            compile(source, f'guest-source-{index}', 'exec')
        self.assertNotIn("p['guestReadScript']", _HOST_OBSERVE)

    def test_live_host_binding_precedes_ssh(self):
        with self.assertRaises(InvalidRequestError):
            self.transport.observe_guest_host_key(self.vm, {**self.host, 'ipaddress': '192.0.2.99'})
        self.runner.assert_not_called()

    def test_guest_host_key_change_is_rejected(self):
        self.runner.return_value = subprocess.CompletedProcess([], 0, json.dumps({'hostKey': PUBLIC}).encode(), b'')
        self.transport.observe_guest_host_key(self.vm, self.host)
        self.runner.return_value = subprocess.CompletedProcess([], 0, json.dumps({'hostKey': PUBLIC[:-2] + 'AB'}).encode(), b'')
        with self.assertRaises(InvalidRequestError):
            self.transport.observe_guest_host_key(self.vm, self.host)

    def test_token_travels_only_in_guest_ssh_stdin(self):
        self.runner.side_effect = [subprocess.CompletedProcess([], 0, json.dumps({'hostKey': PUBLIC}).encode(), b''), subprocess.CompletedProcess([], 0, b'{"configured":true}', b'')]
        result = self.transport.configure(self.vm, self.host, '192.0.2.100', 'management-cp1', seed=True, peer_ips=['192.0.2.11','192.0.2.12','192.0.2.13'], gateway='192.0.2.1')
        self.assertTrue(result['configured'])
        host_call, guest_call = self.runner.call_args_list
        self.assertNotIn('a' * 64, repr(host_call))
        self.assertNotIn('a' * 64, repr(guest_call.args))
        self.assertEqual(json.loads(guest_call.kwargs['input'])['token'], 'a' * 64)
        self.assertIn('StrictHostKeyChecking=yes', guest_call.args[0])
        self.assertIn('GlobalKnownHostsFile=/dev/null', guest_call.args[0])
        self.assertIn('root@198.51.100.10', guest_call.args[0])
        self.assertNotIn('root@192.0.2.11', guest_call.args[0])
        self.assertEqual(guest_call.args[0][guest_call.args[0].index('-p') + 1], '2201')

    def test_token_rotation_during_resume_is_not_silently_accepted(self):
        self.token.write_text('b' * 64)
        with self.assertRaises(InvalidRequestError):
            self.transport.configure(self.vm, self.host, '192.0.2.100', 'management-cp1', seed=True, peer_ips=[], gateway='192.0.2.1')
        self.runner.assert_not_called()

    def test_sensitive_subprocess_errors_are_not_returned(self):
        self.runner.return_value = subprocess.CompletedProcess([], 1, b'', b'secret value must not escape')
        with self.assertRaisesRegex(InvalidRequestError, 'sensitive diagnostics withheld') as result:
            self.transport.observe_guest_host_key(self.vm, self.host)
        self.assertNotIn('secret value', str(result.exception))


class ImageAttestationTests(unittest.TestCase):
    def test_real_signature_and_runtime_evidence_are_required(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            key, public, signature, attestation = [directory / item for item in ('key.pem', 'public.pem', 'signature', 'image.json')]
            subprocess.run(['openssl', 'genpkey', '-algorithm', 'ED25519', '-out', str(key)], capture_output=True, check=True)
            subprocess.run(['openssl', 'pkey', '-in', str(key), '-pubout', '-out', str(public)], capture_output=True, check=True)
            value = {'schemaVersion': '1.0', 'artifactType': 'layersentry-rke2-node-image', 'templateId': PLAN['templateId'], 'os': 'rocky9', 'architecture': 'amd64', 'rke2Version': 'v1.36.4+rke2r1', 'qualificationStatus': 'LIVE_VERIFIED', 'rke2Installed': True, 'qemuGuestAgentInstalled': True, 'sshEnabled': True, 'selinuxEnforcing': True, 'sha256': 'a'*64, 'qualificationEvidenceSha256': 'b'*64}
            attestation.write_text(json.dumps(value))
            subprocess.run(['openssl', 'pkeyutl', '-sign', '-inkey', str(key), '-rawin', '-in', str(attestation), '-out', str(signature)], capture_output=True, check=True)
            self.assertEqual(verify_image(attestation, signature, public, PLAN['templateId'])['sha256'], 'a'*64)
            value['qualificationStatus'] = 'NOT_TESTED'
            attestation.write_text(json.dumps(value))
            with self.assertRaises(InvalidRequestError):
                verify_image(attestation, signature, public, PLAN['templateId'])
            subprocess.run(['openssl', 'pkeyutl', '-sign', '-inkey', str(key), '-rawin', '-in', str(attestation), '-out', str(signature)], capture_output=True, check=True)
            with self.assertRaises(InvalidRequestError):
                verify_image(attestation, signature, public, PLAN['templateId'])


class FormationTests(unittest.TestCase):
    def test_readiness_requires_exact_version_three_names_roles_and_ready(self):
        nodes = [{'name': f'cp{i}', 'ready': True, 'controlPlane': True, 'version': 'v1.36.4+rke2r1'} for i in (1,2,3)]
        self.assertTrue(ready_nodes({'nodes': nodes}, ['cp1','cp2','cp3']))
        self.assertFalse(ready_nodes({'nodes': nodes + [nodes[0]]}, ['cp1','cp2','cp3']))
        nodes[2]['ready'] = False
        self.assertFalse(ready_nodes({'nodes': nodes}, ['cp1','cp2','cp3']))

    def test_seed_readiness_precedes_every_join(self):
        native = Mock()
        native.journal.state = {}
        native.preflight.return_value = {'independentHostPlacement': False}
        native.hosts = {'host': {}}
        native.endpoint = '198.51.100.10'
        native.gateway = '192.0.2.1'
        native.ensure_nodes.return_value = [{'id': str(index), 'hostid': 'host', 'state': 'Running', 'nic': [{'isdefault': True, 'ipaddress': f'192.0.2.{index}'}]} for index in (11,12,13)]
        native.ensure_endpoints.return_value = True
        native.node_name.side_effect = lambda ordinal: f'cp{ordinal}'
        transport = Mock()
        transport.formation.return_value = {'ready': False, 'nodes': []}
        result = reconcile(native, transport, Mock())
        self.assertEqual(result['stage'], 'SEED_RKE2_STARTUP')
        self.assertEqual(transport.configure.call_count, 1)
        self.assertTrue(transport.configure.call_args.kwargs['seed'])

    def test_inspection_never_calls_native_mutations_or_guest_configuration(self):
        native = Mock()
        native.journal.state = {}
        native.preflight.return_value = {'independentHostPlacement': False}
        native.hosts = {'host': {}}
        native.endpoint = '192.0.2.100'
        native.observe_vm.return_value = {'id': 'vm', 'hostid': 'host', 'state': 'Running', 'nic': [{'isdefault': True, 'ipaddress': '192.0.2.11'}]}
        native.node_name.side_effect = lambda ordinal: f'cp{ordinal}'
        transport = Mock()
        transport.formation.return_value = {'ready': False, 'nodes': []}
        result = reconcile(native, transport, Mock(), inspect_only=True)
        self.assertEqual(result['status'], 'PENDING')
        native.ensure_nodes.assert_not_called()
        native.ensure_endpoints.assert_not_called()
        transport.configure.assert_not_called()


if __name__ == '__main__':
    unittest.main()
