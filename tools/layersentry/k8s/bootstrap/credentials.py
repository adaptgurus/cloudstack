"""Protected, usable management kubeconfig escrow and direct authenticated inspection."""
from __future__ import annotations

import base64
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import stat
import tempfile

from controller.model import InvalidRequestError
from .native import canonical, protected_file


def output_path(value):
    path = Path(value)
    parent = path.parent
    info = parent.stat()
    if not path.is_absolute() or parent.resolve() != parent or not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077 or info.st_uid not in (0, os.geteuid()):
        raise InvalidRequestError('kubeconfig output needs an existing protected operator directory')
    if path.exists() or path.is_symlink():
        protected_file(path)
    return path


def sanitized_kubeconfig(value, endpoint):
    endpoint = str(ipaddress.IPv4Address(endpoint))
    if not isinstance(value, dict) or value.get('kind') != 'Config' or value.get('apiVersion') != 'v1':
        raise InvalidRequestError('management kubeconfig schema is invalid')
    clusters, users, contexts = (value.get(key, []) for key in ('clusters', 'users', 'contexts'))
    if any(not isinstance(rows, list) or len(rows) != 1 for rows in (clusters, users, contexts)):
        raise InvalidRequestError('management kubeconfig must contain exactly one flattened context')
    cluster, user, context = clusters[0]['cluster'], users[0]['user'], contexts[0]['context']
    if context.get('cluster') != clusters[0]['name'] or context.get('user') != users[0]['name'] or value.get('current-context') != contexts[0]['name']:
        raise InvalidRequestError('management kubeconfig context binding is invalid')
    if set(cluster) - {'server', 'certificate-authority-data'} or set(user) != {'client-certificate-data', 'client-key-data'}:
        raise InvalidRequestError('management kubeconfig must use only embedded CA and client certificates')
    for item in (cluster.get('certificate-authority-data'), user.get('client-certificate-data'), user.get('client-key-data')):
        try:
            decoded = base64.b64decode(item, validate=True)
            if len(decoded) > 65536 or b'-----BEGIN ' not in decoded:
                raise ValueError()
        except (ValueError, TypeError):
            raise InvalidRequestError('management kubeconfig credential encoding is invalid') from None
    # No exec/auth-provider/token/proxy/path references survive into the runtime file.
    return {'apiVersion': 'v1', 'kind': 'Config',
            'clusters': [{'name': 'management', 'cluster': {'server': 'https://' + endpoint + ':6443', 'certificate-authority-data': cluster['certificate-authority-data']}}],
            'users': [{'name': 'management-admin', 'user': dict(user)}],
            'contexts': [{'name': 'management', 'context': {'cluster': 'management', 'user': 'management-admin'}}],
            'current-context': 'management'}


class ManagementCredentials:
    def __init__(self, path):
        self.path = output_path(path)

    def read(self, endpoint):
        path = protected_file(self.path)
        value = json.loads(path.read_bytes())
        clean = sanitized_kubeconfig(value, endpoint)
        if value != clean:
            raise InvalidRequestError('escrowed management kubeconfig binding changed')
        return clean

    def digest(self):
        return hashlib.sha256(protected_file(self.path).read_bytes()).hexdigest()

    def install(self, value, endpoint):
        clean = sanitized_kubeconfig(value, endpoint)
        output_path(self.path)
        if self.path.exists():
            if self.read(endpoint) != clean:
                raise InvalidRequestError('management kubeconfig output already contains different credentials')
            return
        fd, name = tempfile.mkstemp(prefix='.management-credentials-', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(canonical(clean)); stream.flush(); os.fsync(stream.fileno())
            # Exclusive link: never overwrite a concurrently supplied credential file.
            os.link(name, self.path, follow_symlinks=False)
            os.unlink(name)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def inspect(self, endpoint):
        value = self.read(endpoint)
        cluster = value['clusters'][0]['cluster']
        user = value['users'][0]['user']
        try:
            with tempfile.TemporaryDirectory(prefix='layersentry-management-tls-') as directory:
                paths = []
                for index, encoded in enumerate((cluster['certificate-authority-data'], user['client-certificate-data'], user['client-key-data'])):
                    path = Path(directory) / str(index)
                    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(base64.b64decode(encoded, validate=True))
                    paths.append(path)
                context = ssl.create_default_context(cafile=str(paths[0]))
                context.load_cert_chain(str(paths[1]), str(paths[2]))
                connection = http.client.HTTPSConnection(endpoint, 6443, context=context, timeout=20)
                try:
                    connection.request('GET', '/api/v1/nodes', headers={'Accept': 'application/json'})
                    response = connection.getresponse()
                    raw = response.read(4 * 1024 * 1024 + 1)
                    if response.status != 200 or len(raw) > 4 * 1024 * 1024:
                        raise ValueError()
                    items = json.loads(raw)['items']
                finally:
                    connection.close()
                # RKE2 registration endpoint must use the same trusted server CA.
                with socket.create_connection((endpoint, 9345), timeout=10) as sock:
                    with context.wrap_socket(sock, server_hostname=endpoint):
                        pass
            if not isinstance(items, list) or len(items) > 100:
                raise ValueError()
            nodes = []
            for item in items:
                metadata, status = item.get('metadata', {}), item.get('status', {})
                nodes.append({'name': metadata.get('name'), 'version': status.get('nodeInfo', {}).get('kubeletVersion'),
                              'controlPlane': 'node-role.kubernetes.io/control-plane' in metadata.get('labels', {}),
                              'ready': any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in status.get('conditions', []))})
            return {'nodes': nodes, 'endpoint9345Tls': True}
        except (OSError, ValueError, KeyError, TypeError, http.client.HTTPException):
            raise InvalidRequestError('escrowed management API verification failed; temporary transport remains pending') from None
