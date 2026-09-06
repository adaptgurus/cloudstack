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

"""Bounded first-management RKE2 bootstrap; run only from the approved operator runner."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from bootstrap.native import Journal, NativeBootstrap, NativeCloudStackClient, canonical, protected_file, validate_plan, verify_image
from bootstrap.transport import TrustedGuestTransport
from controller.cloudstack import CloudStackConfig
from controller.model import InvalidRequestError


def ready_nodes(observation, names):
    rows = observation.get('nodes', [])
    if not isinstance(rows, list) or len(rows) != len(names):
        return False
    return {node.get('name') for node in rows} == set(names) and all(
        node.get('ready') is True and node.get('controlPlane') is True and node.get('version') == 'v1.36.4+rke2r1'
        for node in rows
    )


def reconcile(native, transport, *, inspect_only=False):
    preflight = native.preflight()
    transport.validate_hosts(native.hosts)
    if inspect_only:
        nodes = [native.observe_vm(index) for index in (1, 2, 3)]
    else:
        nodes = native.ensure_nodes()
    result = {'scope': 'management-rke2-bootstrap', 'status': 'PENDING', 'productionCertified': False,
              'independentHostPlacement': preflight['independentHostPlacement'],
              'virtualMachines': [{key: node.get(key) for key in ('id', 'name', 'state', 'hostid')} for node in nodes if node]}
    if any(not node or node.get('state') != 'Running' for node in nodes):
        result['stage'] = 'NATIVE_VM_CREATION'
        return result
    peer_ips = [next(nic['ipaddress'] for nic in vm['nic'] if nic.get('isdefault') is True) for vm in nodes]
    seed = nodes[0]
    host = native.hosts[seed['hostid']]
    if inspect_only:
        observation = transport.formation(seed, host, native.endpoint, through_endpoint=True)
        result['stage'] = 'FORMATION_INSPECTION'
        result['formation'] = observation
        if ready_nodes(observation, [native.node_name(i) for i in (1, 2, 3)]) and observation.get('endpoint9345Tls') is True:
            result['status'] = 'LIVE_VERIFIED'
        return result
    if not native.ensure_endpoints([seed]):
        result['stage'] = 'SEED_ENDPOINT'
        return result
    transport.configure(seed, host, native.endpoint, native.node_name(1), seed=True, peer_ips=peer_ips, gateway=native.gateway)
    seed_observation = transport.formation(seed, host, native.endpoint)
    current_names = {node.get('name') for node in seed_observation.get('nodes', []) if node.get('ready') is True}
    if native.node_name(1) not in current_names:
        result['stage'] = 'SEED_RKE2_STARTUP'
        return result
    for ordinal, node in enumerate(nodes[1:], start=2):
        transport.configure(node, native.hosts[node['hostid']], native.endpoint, native.node_name(ordinal), seed=False, peer_ips=peer_ips, gateway=native.gateway)
        observation = transport.formation(seed, host, native.endpoint)
        expected = [native.node_name(i) for i in range(1, ordinal + 1)]
        present = {row.get('name') for row in observation.get('nodes', []) if row.get('ready') is True and row.get('controlPlane') is True and row.get('version') == 'v1.36.4+rke2r1'}
        if not set(expected) <= present:
            result['stage'] = f'JOIN_CONTROL_PLANE_{ordinal}'
            return result
    if not native.ensure_endpoints(nodes):
        result['stage'] = 'HA_ENDPOINT_MEMBERSHIP'
        return result
    observation = transport.formation(seed, host, native.endpoint, through_endpoint=True)
    result['formation'] = observation
    result['stage'] = 'FORMATION_VERIFICATION'
    if ready_nodes(observation, [native.node_name(i) for i in (1, 2, 3)]) and observation.get('endpoint9345Tls') is True:
        result['status'] = 'LIVE_VERIFIED'
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'reconcile'])
    parser.add_argument('--config', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        config = json.loads(protected_file(args.config).read_bytes())
        expected = {'plan', 'image', 'cloudstack', 'journal', 'operatorKeyFile', 'tokenFile', 'hosts'}
        if not isinstance(config, dict) or set(config) != expected:
            raise InvalidRequestError('bootstrap runtime configuration fields do not match schema')
        plan = validate_plan(config['plan'])
        image = config['image']
        if set(image) != {'attestationFile', 'signatureFile', 'publicKeyFile'}:
            raise InvalidRequestError('image trust configuration is invalid')
        verified = verify_image(image['attestationFile'], image['signatureFile'], image['publicKeyFile'], plan['templateId'])
        transport = TrustedGuestTransport(config['hosts'], config['operatorKeyFile'], config['tokenFile'])
        cloud = config['cloudstack']
        if set(cloud) != {'endpoint', 'apiKeyFile', 'secretKeyFile', 'caFile'}:
            raise InvalidRequestError('CloudStack TLS configuration is invalid')
        # This bootstrap path never downgrades its credential-bearing API to HTTP.
        client = NativeCloudStackClient(CloudStackConfig(
            endpoint=cloud['endpoint'], api_key_file=protected_file(cloud['apiKeyFile']),
            secret_key_file=protected_file(cloud['secretKeyFile']), ca_file=protected_file(cloud['caFile'], private=False),
        ))
        fingerprint = hashlib.sha256(canonical({'plan': plan, 'image': verified['sha256'], 'operatorPublicKey': transport.public_key,
                                               'tokenSha256': transport.token_sha256, 'cloudstackEndpoint': cloud['endpoint']})).hexdigest()
        with Journal(config['journal'], fingerprint) as journal:
            native = NativeBootstrap(client, plan, verified, journal, transport.public_key)
            result = reconcile(native, transport, inspect_only=args.action == 'inspect')
        print(json.dumps(result, sort_keys=True))
        return 0 if result['status'] == 'LIVE_VERIFIED' else 2
    except (InvalidRequestError, OSError, ValueError, KeyError, TypeError):
        # Lower-level errors can carry a credential path or provider diagnostic.
        print(json.dumps({'status': 'BLOCKED', 'error': 'Management bootstrap did not complete; inspect the protected journal and approved runner diagnostics.', 'productionCertified': False}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
