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

"""Operator-only native CloudStack bootstrap with durable observe-before-retry.

A completed native job is infrastructure evidence only. RKE2 formation is
verified separately through the trusted guest transport; no release flag is
promoted by this module.
"""
from __future__ import annotations

import base64
import fcntl
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import urllib.parse
from datetime import timedelta, timezone
from uuid import UUID, uuid5

from controller.cloudstack import CloudStackClient
from controller.model import InvalidRequestError

READS = {
    'listProjects', 'listZones', 'listNetworks', 'listServiceOfferings',
    'listTemplates', 'listPublicIpAddresses', 'listLoadBalancerRules',
    'listLoadBalancerRuleInstances', 'listFirewallRules', 'listVirtualMachines', 'listHosts', 'queryAsyncJobResult',
}
MUTATIONS = {'deployVirtualMachine', 'createLoadBalancerRule', 'assignToLoadBalancerRule', 'createFirewallRule'}
SAFE_NAME = re.compile(r'^[a-z][a-z0-9-]{0,35}[a-z0-9]$')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def protected_file(value, *, private=True):
    path = Path(value)
    try:
        info = path.lstat()
    except OSError:
        raise InvalidRequestError('required bootstrap file is unavailable') from None
    forbidden = 0o077 if private else 0o022
    if not path.is_absolute() or path.resolve() != path or not stat.S_ISREG(info.st_mode) or info.st_mode & forbidden:
        raise InvalidRequestError('bootstrap file type or permissions are unsafe')
    if info.st_size > 1024 * 1024:
        raise InvalidRequestError('bootstrap file exceeds size limit')
    return path


def validate_plan(value):
    keys = {'bootstrapId', 'name', 'projectId', 'zoneId', 'networkId', 'serviceOfferingId', 'templateId', 'publicIpId', 'hostIds', 'apiSourceCidrs'}
    if not isinstance(value, dict) or set(value) != keys:
        raise InvalidRequestError('bootstrap plan fields do not match schema')
    result = dict(value)
    for key in keys - {'name', 'hostIds', 'apiSourceCidrs'}:
        try:
            result[key] = str(UUID(value[key]))
        except (ValueError, TypeError, AttributeError):
            raise InvalidRequestError('bootstrap identifiers must be UUIDs') from None
    if not SAFE_NAME.fullmatch(value.get('name', '')):
        raise InvalidRequestError('bootstrap name must be a bounded DNS name')
    hosts = value['hostIds']
    if not isinstance(hosts, list) or len(hosts) != 3:
        raise InvalidRequestError('management bootstrap requires exactly three control-plane hosts')
    try:
        result['hostIds'] = [str(UUID(item)) for item in hosts]
    except (ValueError, TypeError, AttributeError):
        raise InvalidRequestError('bootstrap host identifiers must be UUIDs') from None
    import ipaddress
    cidrs = value['apiSourceCidrs']
    if not isinstance(cidrs, list) or not 1 <= len(cidrs) <= 16:
        raise InvalidRequestError('explicit operator API source CIDRs are required')
    try:
        normalized = [ipaddress.IPv4Network(cidr, strict=True) for cidr in cidrs]
    except (ValueError, TypeError):
        raise InvalidRequestError('operator API source CIDRs must be exact IPv4 networks') from None
    if any(cidr.prefixlen < 24 for cidr in normalized):
        raise InvalidRequestError('operator API source ranges must be /24 or narrower')
    result['apiSourceCidrs'] = sorted({str(cidr) for cidr in normalized})
    return result


def verify_image(attestation_path, signature_path, public_key_path, template_id):
    """Verify an operator-trusted release key; the attestation is never self-trusted."""
    attestation = protected_file(attestation_path, private=False)
    signature = protected_file(signature_path, private=False)
    key = protected_file(public_key_path, private=False)
    result = subprocess.run([
        'openssl', 'pkeyutl', '-verify', '-pubin', '-inkey', str(key), '-rawin',
        '-in', str(attestation), '-sigfile', str(signature),
    ], capture_output=True, timeout=15, check=False)
    if result.returncode:
        raise InvalidRequestError('node-image attestation signature verification failed')
    try:
        value = json.loads(attestation.read_bytes())
    except (ValueError, UnicodeError):
        raise InvalidRequestError('node-image attestation is invalid') from None
    required = {
        'schemaVersion': '1.0', 'artifactType': 'layersentry-rke2-node-image',
        'templateId': template_id, 'os': 'rocky9', 'architecture': 'amd64',
        'rke2Version': 'v1.36.4+rke2r1', 'qualificationStatus': 'LIVE_VERIFIED',
        'rke2Installed': True, 'qemuGuestAgentInstalled': True, 'sshEnabled': True,
        'selinuxEnforcing': True,
    }
    if not isinstance(value, dict) or any(value.get(k) != v for k, v in required.items()):
        raise InvalidRequestError('qualified node-image facts do not match the bootstrap contract')
    for field in ('sha256', 'qualificationEvidenceSha256'):
        if not re.fullmatch(r'[0-9a-f]{64}', value.get(field, '')):
            raise InvalidRequestError('node-image artifact/evidence digest is missing')
    return value


class NativeCloudStackClient(CloudStackClient):
    """Separate mutation allowlist; the existing controller preflight client stays read-only."""
    def _signed_query(self, command, params):
        if command not in READS | MUTATIONS:
            raise InvalidRequestError('native bootstrap command is not allowed')
        if any(str(key).lower() in {'apikey', 'secretkey', 'signature', 'command', 'expires', 'response', 'signatureversion'} for key in params):
            raise InvalidRequestError('native bootstrap parameters override transport fields')
        values = {
            'apikey': self._credential(self.config.api_key_file), 'command': command,
            'expires': (self.clock().astimezone(timezone.utc) + timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'response': 'json', 'signatureversion': '3',
            **{str(k): str(v).lower() if isinstance(v, bool) else str(v) for k, v in params.items()},
        }
        unsigned = '&'.join(f'{key}={urllib.parse.quote(values[key], safe="")}' for key in sorted(values)).lower()
        signature = base64.b64encode(hmac.new(self._credential(self.config.secret_key_file).encode(), unsigned.encode(), hashlib.sha1).digest()).decode()
        return urllib.parse.urlencode({**values, 'signature': signature}, quote_via=urllib.parse.quote)


class Journal:
    def __init__(self, path, fingerprint):
        self.path = Path(path)
        parent = self.path.parent
        if not parent.is_absolute() or not parent.is_dir() or parent.is_symlink() or parent.stat().st_mode & 0o077:
            raise InvalidRequestError('journal parent must be a private existing directory')
        flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW
        self.lock_fd = os.open(str(self.path) + '.lock', flags, 0o600)
        if not stat.S_ISREG(os.fstat(self.lock_fd).st_mode) or os.fstat(self.lock_fd).st_mode & 0o077:
            os.close(self.lock_fd)
            raise InvalidRequestError('journal lock permissions are unsafe')
        try:
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.lock_fd)
            raise InvalidRequestError('another bootstrap writer holds this journal') from None
        try:
            if self.path.exists() or self.path.is_symlink():
                protected_file(self.path)
                self.state = json.loads(self.path.read_bytes())
                if not isinstance(self.state, dict) or self.state.get('schemaVersion') != '1.0' or not isinstance(self.state.get('operations'), dict):
                    raise InvalidRequestError('bootstrap journal schema is invalid')
                if self.state.get('fingerprint') != fingerprint:
                    raise InvalidRequestError('bootstrap plan or runtime secret identity changed; journal cannot be reused')
            else:
                self.state = {'schemaVersion': '1.0', 'fingerprint': fingerprint, 'operations': {}}
                self.save()
        except Exception:
            self.close()
            raise

    def save(self):
        fd, name = tempfile.mkstemp(prefix='.bootstrap-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(canonical(self.state)); stream.flush(); os.fsync(stream.fileno())
            os.replace(name, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def close(self):
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class NativeBootstrap:
    def __init__(self, client, plan, image, journal, operator_public_key):
        self.client = client
        self.plan = validate_plan(plan)
        self.image = image
        self.journal = journal
        if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}', operator_public_key):
            raise InvalidRequestError('bootstrap operator must use an Ed25519 public key without comments')
        self.public_key = operator_public_key

    def exact(self, command, collection, resource_id, **extra):
        rows = self.client.call(command, {'id': resource_id, **extra}).get(collection, [])
        if not isinstance(rows, list) or len(rows) != 1 or rows[0].get('id') != resource_id:
            raise InvalidRequestError('native bootstrap resource is unavailable or ambiguous')
        return rows[0]

    def preflight(self):
        p = self.plan
        project = self.exact('listProjects', 'project', p['projectId'])
        zone = self.exact('listZones', 'zone', p['zoneId'])
        network = self.exact('listNetworks', 'network', p['networkId'], projectid=p['projectId'])
        offering = self.exact('listServiceOfferings', 'serviceoffering', p['serviceOfferingId'], zoneid=p['zoneId'])
        template = self.exact('listTemplates', 'template', p['templateId'], zoneid=p['zoneId'], templatefilter='executable')
        endpoint = self.exact('listPublicIpAddresses', 'publicipaddress', p['publicIpId'], projectid=p['projectId'])
        if project.get('state') != 'Active' or zone.get('allocationstate') != 'Enabled':
            raise InvalidRequestError('project/Site allocation prerequisites are not satisfied')
        if network.get('zoneid') != p['zoneId'] or network.get('projectid') != p['projectId'] or network.get('state') != 'Implemented':
            raise InvalidRequestError('management network is not Implemented in the exact project/Site')
        if network.get('type') != 'Isolated' or network.get('vpcid') or not {'Lb', 'Firewall'} <= {service.get('name') for service in network.get('service', [])}:
            raise InvalidRequestError('first management bootstrap requires an isolated non-VPC network with native Lb and Firewall')
        if offering.get('issystem') is True or offering.get('iscustomized') is True or offering.get('state') == 'Inactive':
            raise InvalidRequestError('management node compute profile is not a fixed active user offering')
        if template.get('isready') is not True or template.get('hypervisor') != 'KVM' or template.get('format') != 'QCOW2' or template.get('checksum') != '{SHA-256}' + self.image['sha256']:
            raise InvalidRequestError('native template is not the exact qualified Ready KVM image')
        if endpoint.get('state') != 'Allocated' or endpoint.get('projectid') != p['projectId'] or endpoint.get('zoneid') != p['zoneId'] or endpoint.get('isstaticnat') is True or endpoint.get('associatednetworkid') not in (None, p['networkId']):
            raise InvalidRequestError('management endpoint is not allocated to the exact project/Site')
        import ipaddress
        self.endpoint = str(ipaddress.IPv4Address(endpoint.get('ipaddress', '')))
        self.gateway = str(ipaddress.IPv4Address(network.get('gateway', '')))
        selected_network = ipaddress.ip_network(network.get('cidr', ''), strict=False)
        if any(selected_network.overlaps(ipaddress.ip_network(cidr)) for cidr in ('10.42.0.0/16', '10.43.0.0/16')):
            raise InvalidRequestError('management network overlaps the pinned RKE2 pod/service CIDRs')
        snat = self.client.call('listPublicIpAddresses', {'associatednetworkid': p['networkId'], 'projectid': p['projectId'], 'issourcenat': True, 'page': 1, 'pagesize': 100}).get('publicipaddress', [])
        if not isinstance(snat, list) or len(snat) != 1 or snat[0].get('associatednetworkid') != p['networkId'] or snat[0].get('projectid') != p['projectId'] or snat[0].get('state') != 'Allocated' or snat[0].get('issourcenat') is not True:
            raise InvalidRequestError('management network source NAT binding is unavailable or ambiguous')
        self.allowed_cidrs = sorted(set(p['apiSourceCidrs'] + [str(selected_network), str(ipaddress.IPv4Address(snat[0]['ipaddress'])) + '/32']))
        self.hosts = {}
        for host_id in set(p['hostIds']):
            host = self.exact('listHosts', 'host', host_id)
            if host.get('zoneid') != p['zoneId'] or host.get('state') != 'Up' or host.get('hypervisor') != 'KVM' or host.get('resourcestate') != 'Enabled':
                raise InvalidRequestError('selected KVM host is not Up and Enabled in the selected Site')
            self.hosts[host_id] = host
        return {'status': 'SOURCE_COMPLETE', 'independentHostPlacement': len(self.hosts) == 3, 'productionCertified': False}

    def vm_id(self, ordinal):
        return str(uuid5(UUID(self.plan['bootstrapId']), f'management-control-plane-{ordinal}'))

    def node_name(self, ordinal):
        return f"{self.plan['name']}-cp{ordinal}"

    def observe_vm(self, ordinal):
        p = self.plan
        rows = self.client.call('listVirtualMachines', {'id': self.vm_id(ordinal), 'projectid': p['projectId'], 'details': 'all'}).get('virtualmachine', [])
        if not isinstance(rows, list) or len(rows) > 1:
            raise InvalidRequestError('management VM lookup is ambiguous')
        if not rows:
            return None
        vm = rows[0]
        expected = {'id': self.vm_id(ordinal), 'name': self.node_name(ordinal), 'projectid': p['projectId'], 'zoneid': p['zoneId'], 'templateid': p['templateId'], 'serviceofferingid': p['serviceOfferingId']}
        if any(vm.get(k) != v for k, v in expected.items()):
            raise InvalidRequestError('management VM identity or infrastructure binding drifted')
        if vm.get('state') == 'Running' and vm.get('hostid') != p['hostIds'][ordinal - 1]:
            raise InvalidRequestError('management VM host placement drifted')
        if not any(nic.get('networkid') == p['networkId'] and nic.get('isdefault') is True for nic in vm.get('nic', [])):
            raise InvalidRequestError('management VM default network binding drifted')
        return vm

    def advance(self, key, command, params, observe):
        """One bounded native step. An ambiguous POST is never replayed automatically."""
        operations = self.journal.state['operations']
        record = operations.get(key)
        observed = observe()
        if observed:
            operations[key] = {**(record or {}), 'state': 'OBSERVED', 'resourceId': observed['id']}
            self.journal.save()
            return observed
        if record:
            job_id = record.get('jobId')
            if job_id:
                job = self.client.call('queryAsyncJobResult', {'jobid': job_id})
                if job.get('jobstatus') == 2:
                    record['state'] = 'FAILED'; self.journal.save()
                    raise InvalidRequestError('native bootstrap job failed; inspect its recorded job ID')
                if job.get('jobstatus') == 1:
                    record['state'] = 'UNKNOWN'; self.journal.save()
                    raise InvalidRequestError('native job completed but its exact resource is not observable')
                if job.get('jobstatus') != 0:
                    raise InvalidRequestError('native job returned an invalid status')
                return None
            raise InvalidRequestError('native submission outcome is UNKNOWN; inspect exact resource before any retry')
        operations[key] = {'state': 'SUBMITTING'}
        self.journal.save()
        try:
            result = self.client.call(command, params)
        except Exception:
            operations[key]['state'] = 'UNKNOWN'; self.journal.save()
            raise InvalidRequestError('native submission outcome is UNKNOWN; request was not replayed') from None
        if result.get('jobid'):
            operations[key] = {'state': 'WAITING', 'jobId': str(UUID(result['jobid']))}
        elif result.get('id'):
            operations[key] = {'state': 'WAITING', 'resourceId': str(UUID(result['id']))}
        else:
            operations[key] = {'state': 'UNKNOWN'}
        self.journal.save()
        return None

    def ensure_nodes(self):
        result = []
        for ordinal in (1, 2, 3):
            cloud_config = {'hostname': self.node_name(ordinal), 'users': [{'name': 'root', 'lock_passwd': True, 'ssh_authorized_keys': [self.public_key]}], 'ssh_pwauth': False, 'disable_root': False, 'runcmd': [['systemctl', 'enable', '--now', 'qemu-guest-agent']]}
            user_data = base64.b64encode(b'#cloud-config\n' + canonical(cloud_config)).decode()
            p = self.plan
            vm = self.advance(f'vm-{ordinal}', 'deployVirtualMachine', {
                'customid': self.vm_id(ordinal), 'name': self.node_name(ordinal), 'displayname': self.node_name(ordinal),
                'projectid': p['projectId'], 'zoneid': p['zoneId'], 'networkids': p['networkId'],
                'templateid': p['templateId'], 'serviceofferingid': p['serviceOfferingId'], 'hostid': p['hostIds'][ordinal - 1],
                'hypervisor': 'KVM', 'startvm': True, 'userdata': user_data,
            }, lambda: self.observe_vm(ordinal))
            result.append(vm)
        return result

    def observe_rule(self, port):
        rows = self.client.call('listLoadBalancerRules', {'publicipid': self.plan['publicIpId'], 'projectid': self.plan['projectId'], 'page': 1, 'pagesize': 100}).get('loadbalancerrule', [])
        if not isinstance(rows, list) or len(rows) >= 100:
            raise InvalidRequestError('load-balancer inventory is invalid or truncated')
        candidates = [row for row in rows if str(row.get('publicport')) == str(port)]
        if not candidates:
            return None
        if len(candidates) != 1:
            raise InvalidRequestError('management endpoint port ownership is ambiguous')
        rule = candidates[0]
        if rule.get('name') != f"{self.plan['name']}-{port}" or str(rule.get('privateport')) != str(port) or rule.get('publicipid') != self.plan['publicIpId'] or rule.get('protocol') != 'tcp':
            raise InvalidRequestError('management endpoint port is owned by a different rule')
        return rule if rule.get('state') == 'Active' else None

    def observe_firewall(self, port):
        import ipaddress
        rows = self.client.call('listFirewallRules', {'ipaddressid': self.plan['publicIpId'], 'page': 1, 'pagesize': 100}).get('firewallrule', [])
        if not isinstance(rows, list) or len(rows) >= 100:
            raise InvalidRequestError('management firewall inventory is invalid or truncated')
        relevant = [row for row in rows if row.get('protocol') in ('tcp', 'all') and int(row.get('startport', 0)) <= port <= int(row.get('endport', 65535))]
        if not relevant:
            return None
        if len(relevant) != 1:
            raise InvalidRequestError('management endpoint has overlapping firewall rules')
        rule = relevant[0]
        actual_cidrs = {str(ipaddress.IPv4Network(cidr.strip(), strict=True)) for cidr in rule.get('cidrlist', '').split(',')}
        if rule.get('protocol') != 'tcp' or int(rule.get('startport', 0)) != port or int(rule.get('endport', 0)) != port or actual_cidrs != set(self.allowed_cidrs):
            raise InvalidRequestError('management endpoint firewall differs from exact approved sources/port')
        return rule if rule.get('state') == 'Active' else None

    def ensure_endpoints(self, nodes):
        rules = []
        for port in (6443, 9345):
            rule = self.advance(f'lb-{port}', 'createLoadBalancerRule', {
                'name': f"{self.plan['name']}-{port}", 'publicipid': self.plan['publicIpId'],
                'publicport': port, 'privateport': port, 'algorithm': 'roundrobin', 'protocol': 'tcp',
                'networkid': self.plan['networkId'], 'openfirewall': False,
            }, lambda: self.observe_rule(port))
            if not rule:
                continue
            firewall = self.advance(f'firewall-{port}', 'createFirewallRule', {
                'ipaddressid': self.plan['publicIpId'], 'protocol': 'tcp', 'startport': port, 'endport': port,
                'cidrlist': ','.join(self.allowed_cidrs),
            }, lambda: self.observe_firewall(port))
            if not firewall:
                continue
            expected = {vm['id'] for vm in nodes}
            owned = {self.vm_id(index) for index in (1, 2, 3)}
            def observe_members():
                rows = self.client.call('listLoadBalancerRuleInstances', {'id': rule['id'], 'applied': True}).get('loadbalancerruleinstance', [])
                actual = {row['id'] for row in rows}
                if actual - owned:
                    raise InvalidRequestError('management endpoint contains an unowned backend')
                return rule if expected <= actual else None
            assigned = self.advance(f'lb-members-{port}-{len(expected)}', 'assignToLoadBalancerRule', {'id': rule['id'], 'virtualmachineids': ','.join(sorted(expected))}, observe_members)
            if assigned:
                rules.append(rule)
        return len(rules) == 2
