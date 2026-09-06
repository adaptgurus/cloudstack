"""Fixed, verified native containerd staging through the existing bootstrap transport."""
from __future__ import annotations

import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from controller.model import InvalidRequestError

_STATUS = '''import json,subprocess,sys,re
p=json.load(sys.stdin)
if set(p)!={'images'} or not isinstance(p['images'],list) or len(p['images'])!=8:raise SystemExit(2)
for image in p['images']:
 if not re.fullmatch(r'[a-z0-9][a-z0-9./_-]+@sha256:[a-f0-9]{64}',image):raise SystemExit(2)
r=subprocess.run(['/var/lib/rancher/rke2/bin/ctr','--address','/run/k3s/containerd/containerd.sock','--namespace','k8s.io','images','list'],capture_output=True,text=True,timeout=30,check=True)
if len(r.stdout)>4194304:raise SystemExit(3)
found={}
for line in r.stdout.splitlines()[1:]:
 fields=line.split()
 if fields and fields[0] in p['images']:
  if len(fields)<3 or fields[2]!=fields[0].rsplit('@',1)[1]:raise SystemExit(4)
  found[fields[0]]=fields[2]
print(json.dumps({'images':found}))
'''

_PREPARE = '''import json,os,re,stat,sys
p=json.load(sys.stdin)
if set(p)!={'bundle','archive'} or any(not re.fullmatch('[a-f0-9]{64}',p[k]) for k in p):raise SystemExit(2)
base='/var/lib/layersentry/management-bundles'
for path in ['/var/lib/layersentry',base,base+'/'+p['bundle']]:
 if not os.path.lexists(path):os.mkdir(path,0o700)
 s=os.lstat(path)
 if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or s.st_mode & 0o077:raise SystemExit(3)
path=base+'/'+p['bundle']+'/'+p['archive']+'.partial'
if os.path.lexists(path):
 s=os.lstat(path)
 if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_nlink!=1:raise SystemExit(4)
 os.unlink(path)
print(json.dumps({'prepared':True}))
'''

_IMPORT = '''import hashlib,json,os,re,stat,subprocess,sys
p=json.load(sys.stdin)
if set(p)!={'bundle','archive','image','size'}:raise SystemExit(2)
if any(not re.fullmatch('[a-f0-9]{64}',p[k]) for k in ('bundle','archive')) or not re.fullmatch(r'[a-z0-9][a-z0-9./_-]+@sha256:[a-f0-9]{64}',p['image']):raise SystemExit(2)
if not isinstance(p['size'],int) or not 0<p['size']<=2147483648:raise SystemExit(2)
base='/var/lib/layersentry/management-bundles/'+p['bundle']
s=os.lstat(base)
if not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or s.st_mode & 0o077:raise SystemExit(3)
partial=base+'/'+p['archive']+'.partial';path=base+'/'+p['archive']+'.oci.tar'
source=path if os.path.lexists(path) else partial
s=os.lstat(source)
if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_nlink!=1 or s.st_size!=p['size']:raise SystemExit(4)
h=hashlib.sha256()
with open(source,'rb') as stream:
 for block in iter(lambda:stream.read(1048576),b''):h.update(block)
if h.hexdigest()!=p['archive']:raise SystemExit(5)
if source==partial:os.chmod(source,0o600);os.replace(source,path)
cmd=['/var/lib/rancher/rke2/bin/ctr','--address','/run/k3s/containerd/containerd.sock','--namespace','k8s.io']
r=subprocess.run(cmd+['images','import','--local','--all-platforms','--digests','--base-name',p['image'].rsplit('@',1)[0],path],capture_output=True,timeout=240)
if r.returncode:raise SystemExit(6)
r=subprocess.run(cmd+['images','list'],capture_output=True,text=True,timeout=30,check=True)
if not any(len(f)>=3 and f[0]==p['image'] and f[2]==p['image'].rsplit('@',1)[1] for f in [line.split() for line in r.stdout.splitlines()[1:]]):raise SystemExit(7)
print(json.dumps({'imported':True,'image':p['image']}))
'''


class NativeImageStager:
    def __init__(self,bundle,transport,journal):
        self.bundle,self.transport,self.journal=bundle,transport,journal

    def transfer(self,vm,host,item):
        transport=self.transport
        endpoint=transport.endpoints.get(vm['id'])
        if not endpoint:raise InvalidRequestError('verified bootstrap forwarding is unavailable for image transfer')
        transport.guest_call(vm,host,_PREPARE,{'bundle':self.bundle.digest,'archive':item['sha256']})
        key=transport.observe_guest_host_key(vm,host)
        address=str(ipaddress.IPv4Address(endpoint['address']));port=endpoint['port']
        source=self.bundle.file(item['file'])
        with tempfile.TemporaryDirectory(prefix='layersentry-provider-trust-') as directory:
            known=Path(directory)/'known_hosts';known.write_text(f'[{address}]:{port} {key}\n');known.chmod(0o600)
            options=transport.ssh_options(transport.operator_key,known)[1:]
            target=f"root@{address}:/var/lib/layersentry/management-bundles/{self.bundle.digest}/{item['sha256']}.partial"
            try:
                result=transport.runner(['scp','-q','-B',*options,'-P',str(port),str(source),target],input=None,capture_output=True,timeout=300,check=False)
            except (OSError,subprocess.SubprocessError):
                raise InvalidRequestError('provider image transfer is incomplete; resume observes native state') from None
            if result.returncode:raise InvalidRequestError('provider image transfer failed; sensitive diagnostics withheld')
        payload={'bundle':self.bundle.digest,'archive':item['sha256'],'image':item['image'],'size':source.stat().st_size}
        # ctr import can exceed the small configuration call deadline; it is
        # safe to observe and retry the same immutable archive after interruption.
        return transport.guest_call(vm,host,_IMPORT,payload,timeout=300)

    def advance(self,nodes,hosts):
        """Import at most one archive per call; every call first observes all nodes."""
        images=self.bundle.value['images'];wanted=[item['image'] for item in images]
        missing=[]
        for vm in nodes:
            status=self.transport.guest_call(vm,hosts[vm['hostid']],_STATUS,{'images':wanted})
            actual=status.get('images')
            if not isinstance(actual,dict) or any(image not in wanted or digest!=image.rsplit('@',1)[1] for image,digest in actual.items()):
                raise InvalidRequestError('native containerd inventory is invalid')
            missing.extend((vm,item) for item in images if item['image'] not in actual)
        if not missing:
            self.journal.state['providerImagesImported']={'bundleSha256':self.bundle.digest,'vmIds':sorted(vm['id'] for vm in nodes)}
            self.journal.save();return True
        vm,item=missing[0]
        self.transfer(vm,hosts[vm['hostid']],item)
        return False
