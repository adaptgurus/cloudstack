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

"""Fixed QGA public-host-key observation, then strictly verified guest SSH.

Only public SSH host keys cross QGA. RKE2 secrets travel in SSH stdin and are
stored only in the guest's mode-0600 runtime configuration.
"""
from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from uuid import UUID

from controller.model import InvalidRequestError
from .native import protected_file

_GUEST_PUBLIC_KEY = '''import json,os,stat
p='/etc/ssh/ssh_host_ed25519_key.pub'
s=os.lstat(p)
if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_gid != 0 or s.st_mode & 0o022 or s.st_size > 4096: raise SystemExit(2)
print(json.dumps({'hostKey':open(p).read().strip()}))
'''

_HOST_OBSERVE = '''import base64,json,subprocess,sys,time,uuid
p=json.load(sys.stdin)
if set(p) != {'vmId','instanceName'}: raise SystemExit(2)
vmid=str(uuid.UUID(p['vmId']))
name=p['instanceName']
if subprocess.run(['virsh','domuuid',name],capture_output=True,text=True,timeout=15,check=True).stdout.strip() != vmid: raise SystemExit(3)
def qga(value):
 r=subprocess.run(['virsh','qemu-agent-command',vmid,json.dumps(value)],capture_output=True,text=True,timeout=15,check=True)
 return json.loads(r.stdout)['return']
r=qga({'execute':'guest-exec','arguments':{'path':'/usr/bin/python3','arg':['-c',GUEST_READ_SCRIPT],'capture-output':True}})
for i in range(30):
 s=qga({'execute':'guest-exec-status','arguments':{'pid':r['pid']}})
 if s.get('exited'):
  if s.get('exitcode') != 0: raise SystemExit(4)
  result=base64.b64decode(s.get('out-data',''),validate=True)
  if len(result)>4096: raise SystemExit(5)
  sys.stdout.buffer.write(result)
  break
 time.sleep(1)
else: raise SystemExit(6)
'''

_HOST_OBSERVE = _HOST_OBSERVE.replace('GUEST_READ_SCRIPT', repr(_GUEST_PUBLIC_KEY))

_GUEST_CONFIGURE = '''import ipaddress,json,os,subprocess,sys,tempfile
p=json.load(sys.stdin)
if set(p) != {'name','endpoint','token','seed','version','peerIps','gateway'}: raise SystemExit(2)
if p['version'] != 'v1.36.4+rke2r1': raise SystemExit(3)
v=subprocess.run(['/usr/local/bin/rke2','--version'],capture_output=True,text=True,timeout=15,check=True).stdout
if p['version'] not in v: raise SystemExit(4)
if subprocess.run(['getenforce'],capture_output=True,text=True,timeout=10,check=True).stdout.strip() != 'Enforcing': raise SystemExit(5)
peers=[str(ipaddress.IPv4Address(value)) for value in p['peerIps']]
if len(peers)!=3 or len(set(peers))!=3: raise SystemExit(9)
gateway=str(ipaddress.IPv4Address(p['gateway']))
ssh_source=str(ipaddress.IPv4Address(os.environ.get('SSH_CONNECTION','').split()[0]))
if subprocess.run(['systemctl','is-active','--quiet','firewalld'],timeout=10).returncode: raise SystemExit(10)
changed=False
def firewall(*args):
 global changed
 query=[arg.replace('--add-rich-rule=', '--query-rich-rule=').replace('--add-source=', '--query-source=') for arg in args]
 if query!=list(args):
  persistent=subprocess.run(['firewall-cmd','--permanent',*query],capture_output=True,timeout=10).returncode==0
  runtime=subprocess.run(['firewall-cmd',*query],capture_output=True,timeout=10).returncode==0
  if persistent and runtime: return
 r=subprocess.run(['firewall-cmd','--permanent',*args],capture_output=True,timeout=20)
 if r.returncode: raise SystemExit(11)
 changed=True
for source in sorted(set(peers+[gateway,ssh_source])):
 ports=[22] if source==ssh_source else []
 if source in peers+[gateway]: ports += [6443,9345]
 if source in peers: ports += [2379,2380,10250]
 for port in sorted(set(ports)):
  firewall('--add-rich-rule=rule family="ipv4" source address="'+source+'/32" port port="'+str(port)+'" protocol="tcp" accept')
 if source in peers:
  firewall('--add-rich-rule=rule family="ipv4" source address="'+source+'/32" port port="8472" protocol="udp" accept')
# Dedicated management pod network only; these are not customer workload nodes.
firewall('--zone=trusted','--add-source=10.42.0.0/16')
if subprocess.run(['firewall-cmd','--permanent','--query-service=ssh'],capture_output=True,timeout=10).returncode==0:
 firewall('--remove-service=ssh')
if changed and subprocess.run(['firewall-cmd','--reload'],capture_output=True,timeout=20).returncode: raise SystemExit(12)
config={'token' :p['token'],'tls-san':[p['endpoint']],'node-name':p['name'],'cni':'canal','cluster-cidr':'10.42.0.0/16','service-cidr':'10.43.0.0/16','write-kubeconfig-mode':'0600','selinux':True}
if not p['seed']: config['server']='https://'+p['endpoint']+':9345'
path='/etc/rancher/rke2/config.yaml'
os.makedirs(os.path.dirname(path),mode=0o700,exist_ok=True)
encoded=json.dumps(config,sort_keys=True).encode()
if os.path.lexists(path):
 if os.path.islink(path) or os.stat(path).st_mode & 0o077: raise SystemExit(6)
 if open(path,'rb').read() != encoded: raise SystemExit(7)
else:
 fd,tmp=tempfile.mkstemp(dir=os.path.dirname(path),prefix='.layersentry-')
 with os.fdopen(fd,'wb') as f: f.write(encoded);f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
r=subprocess.run(['systemctl','enable','--now','rke2-server'],capture_output=True,timeout=120)
if r.returncode: raise SystemExit(8)
print(json.dumps({'configured':True}))
'''

_GUEST_FORMATION = '''import json,ssl,socket,subprocess,sys
p=json.load(sys.stdin)
args=['/var/lib/rancher/rke2/bin/kubectl','--kubeconfig','/etc/rancher/rke2/rke2.yaml','--request-timeout=15s']
if p.get('throughEndpoint'): args += ['--server=https://'+p['endpoint']+':6443']
r=subprocess.run(args+['get','nodes','-o','json'],capture_output=True,text=True,timeout=20)
if r.returncode: print(json.dumps({'ready':False,'nodes':[]}));raise SystemExit(0)
items=json.loads(r.stdout).get('items',[])
result=[]
for n in items:
 m=n.get('metadata',{});s=n.get('status',{})
 result.append({'name':m.get('name'),'version':s.get('nodeInfo',{}).get('kubeletVersion'),'controlPlane':'node-role.kubernetes.io/control-plane' in m.get('labels',{}),'ready':any(c.get('type')=='Ready' and c.get('status')=='True' for c in s.get('conditions',[]))})
endpoint=False
if p.get('throughEndpoint'):
 try:
  context=ssl.create_default_context(cafile='/var/lib/rancher/rke2/server/tls/server-ca.crt')
  with socket.create_connection((p['endpoint'],9345),timeout=10) as sock:
   with context.wrap_socket(sock,server_hostname=p['endpoint']): endpoint=True
 except (OSError,ssl.SSLError): pass
print(json.dumps({'ready':True,'nodes':result,'endpoint9345Tls':endpoint}))
'''


_GUEST_KUBECONFIG = '''import json,subprocess,sys
p=json.load(sys.stdin)
if p != {}: raise SystemExit(2)
r=subprocess.run(['/var/lib/rancher/rke2/bin/kubectl','--kubeconfig','/etc/rancher/rke2/rke2.yaml','config','view','--raw','--flatten','--minify','-o','json'],capture_output=True,timeout=20)
if r.returncode or len(r.stdout)>262144: raise SystemExit(3)
sys.stdout.buffer.write(r.stdout)
'''


class TrustedGuestTransport:
    def __init__(self, hosts, operator_key_file, token_file, *, runner=subprocess.run):
        if not isinstance(hosts, dict) or not hosts or len(hosts) > 64:
            raise InvalidRequestError('approved KVM transport host catalog is invalid')
        for host_id, host in hosts.items():
            UUID(host_id)
            if not isinstance(host, dict) or set(host) != {'address', 'user', 'keyFile', 'knownHostsFile'} or host['user'] != 'root':
                raise InvalidRequestError('approved KVM transport entry is invalid')
            ipaddress.IPv4Address(host['address'])
            protected_file(host['keyFile']); protected_file(host['knownHostsFile'], private=False)
        self.hosts = hosts
        self.operator_key = protected_file(operator_key_file)
        self.token_file = protected_file(token_file)
        self.runner = runner
        token = self.token_file.read_text().strip()
        if len(token) < 48 or len(token) > 4096 or any(ch.isspace() for ch in token):
            raise InvalidRequestError('RKE2 runtime token must be a stable strong protected value')
        self.token_sha256 = hashlib.sha256(token.encode()).hexdigest()
        self.public_key = self.run(['ssh-keygen', '-y', '-f', str(self.operator_key)], None, timeout=15).decode().strip()
        if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/]+={0,2}(?: [^\n]*)?', self.public_key):
            raise InvalidRequestError('bootstrap operator key must be Ed25519')
        self.public_key = ' '.join(self.public_key.split()[:2])
        self.known_guests = {}
        self.endpoints = {}

    def run(self, argv, value, *, timeout):
        try:
            result = self.runner(argv, input=json.dumps(value).encode() if value is not None else None, capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.SubprocessError):
            raise InvalidRequestError('trusted bootstrap transport did not complete; inspect exact node before resuming') from None
        if result.returncode or len(result.stdout) > 1024 * 1024:
            raise InvalidRequestError('trusted bootstrap transport failed; sensitive diagnostics withheld')
        return result.stdout

    @staticmethod
    def ssh_options(key, known_hosts):
        return ['ssh', '-F', '/dev/null', '-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes',
                '-o', 'StrictHostKeyChecking=yes', '-o', 'UserKnownHostsFile=' + str(known_hosts),
                '-o', 'GlobalKnownHostsFile=/dev/null', '-o', 'ConnectTimeout=10',
                '-o', 'ConnectionAttempts=1', '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
                '-i', str(key)]

    def validate_hosts(self, live_hosts):
        for host_id, live in live_hosts.items():
            if host_id not in self.hosts or self.hosts[host_id]['address'] != live.get('ipaddress'):
                raise InvalidRequestError('approved KVM transport differs from live host inventory')

    def observe_guest_host_key(self, vm, host):
        host_id = host.get('id')
        configured = self.hosts.get(host_id)
        if not configured or vm.get('hostid') != host_id:
            raise InvalidRequestError('KVM transport host is not approved for this exact VM')
        address = str(ipaddress.ip_address(host.get('ipaddress', '')))
        if configured.get('address') != address or configured.get('user') != 'root':
            raise InvalidRequestError('KVM SSH host address or operator identity differs from live CloudStack')
        instance = vm.get('instancename', '')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', instance):
            raise InvalidRequestError('native instance name is invalid')
        vm_id = str(UUID(vm['id']))
        key = protected_file(configured['keyFile'])
        known = protected_file(configured['knownHostsFile'], private=False)
        argv = self.ssh_options(key, known) + ['root@' + address, 'python3 -c ' + shlex.quote(_HOST_OBSERVE)]
        output = self.run(argv, {'vmId': vm_id, 'instanceName': instance}, timeout=90)
        try:
            host_key = json.loads(output)['hostKey']
        except (ValueError, KeyError, TypeError):
            raise InvalidRequestError('trusted guest host-key observation is invalid') from None
        fields = host_key.split()
        if len(fields) < 2 or fields[0] != 'ssh-ed25519' or not re.fullmatch(r'[A-Za-z0-9+/]+={0,2}', fields[1]):
            raise InvalidRequestError('guest SSH host key is not a valid Ed25519 public key')
        public_key = ' '.join(fields[:2])
        previous = self.known_guests.get(vm_id)
        if previous is not None and previous != public_key:
            raise InvalidRequestError('guest SSH host key changed during bootstrap')
        self.known_guests[vm_id] = public_key
        return public_key

    def bind_endpoints(self, endpoints):
        if not isinstance(endpoints, dict) or len(endpoints) != 3:
            raise InvalidRequestError('exact native temporary SSH forwarding is required')
        for vm_id, endpoint in endpoints.items():
            UUID(vm_id)
            ipaddress.IPv4Address(endpoint['address'])
            if endpoint.get('port') not in (2201, 2202, 2203):
                raise InvalidRequestError('temporary SSH port is invalid')
        self.endpoints = dict(endpoints)

    def guest_call(self, vm, host, script, payload, *, timeout=150):
        endpoint = self.endpoints.get(vm.get('id'))
        if not endpoint:
            raise InvalidRequestError('no verified native SSH forwarding for this VM')
        public_key = self.observe_guest_host_key(vm, host)
        address = str(ipaddress.IPv4Address(endpoint['address']))
        port = endpoint['port']
        with tempfile.TemporaryDirectory(prefix='layersentry-guest-trust-') as directory:
            known_hosts = Path(directory) / 'known_hosts'
            known_hosts.write_text('[' + address + ']:' + str(port) + ' ' + public_key + '\n')
            known_hosts.chmod(0o600)
            argv = self.ssh_options(self.operator_key, known_hosts) + ['-p', str(port), 'root@' + address, 'python3 -c ' + shlex.quote(script)]
            raw = self.run(argv, payload, timeout=timeout)
        try:
            result = json.loads(raw)
        except (ValueError, UnicodeError):
            raise InvalidRequestError('guest bootstrap response is invalid') from None
        if not isinstance(result, dict):
            raise InvalidRequestError('guest bootstrap response is invalid')
        return result

    def configure(self, vm, host, endpoint, name, *, seed, peer_ips, gateway):
        token = protected_file(self.token_file).read_text().strip()
        if hashlib.sha256(token.encode()).hexdigest() != self.token_sha256:
            raise InvalidRequestError('RKE2 runtime token changed during bootstrap')
        return self.guest_call(vm, host, _GUEST_CONFIGURE, {'name': name, 'endpoint': endpoint, 'token': token, 'seed': seed, 'version': 'v1.36.4+rke2r1', 'peerIps': peer_ips, 'gateway': gateway})

    def formation(self, vm, host, endpoint, *, through_endpoint=False):
        return self.guest_call(vm, host, _GUEST_FORMATION, {'endpoint': endpoint, 'throughEndpoint': through_endpoint})

    def export_credentials(self, vm, host):
        return self.guest_call(vm, host, _GUEST_KUBECONFIG, {})
