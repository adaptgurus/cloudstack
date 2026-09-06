#!/usr/bin/env python3
"""Assemble a public immutable first-plane bundle; never publish or install it."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

import yaml
from bundle import sha256, verify_oci

ROOT = Path(__file__).resolve().parent
PROVIDERS = [
    ('cluster-api','CoreProvider','v1.13.5','cluster-api','core-components.yaml','capi-system'),
    ('rke2','BootstrapProvider','v0.25.2','bootstrap-rke2','bootstrap-components.yaml','rke2-bootstrap-system'),
    ('rke2','ControlPlaneProvider','v0.25.2','control-plane-rke2','control-plane-components.yaml','rke2-control-plane-system'),
    ('cloudstack','InfrastructureProvider','v0.6.1','infrastructure-cloudstack','infrastructure-components.yaml','capc-system'),
]


def command(args, *, timeout=300):
    result = subprocess.run(args,capture_output=True,timeout=timeout,check=False)
    if result.returncode:raise ValueError('public artifact command failed: '+args[0])
    return result.stdout


def asset(item, path):
    if path.exists():
        if sha256(path)!=item['sha256']:raise ValueError('existing public asset checksum differs')
        return
    release=json.loads(command(['gh','api','repos/'+item['repository']+'/releases/tags/'+item['version']]))
    match=[a for a in release['assets'] if a['name']==item['name']]
    if len(match)!=1:raise ValueError('exact release asset is absent or ambiguous')
    raw=command(['gh','api','-H','Accept: application/octet-stream','repos/'+item['repository']+'/releases/assets/'+str(match[0]['id'])],timeout=300)
    if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('upstream release asset checksum mismatch')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)


def concrete(text):
    # These exact public release assets are hash-verified before transformation.
    text=re.sub(r'\$\{[A-Z][A-Z0-9_]*:=([^}]+)\}',lambda match:match[1],text)
    if '${' in text or '$(' in text:raise ValueError('unresolved provider variable')
    return text


def prepare(output, *, downstream_dir):
    lock=json.loads((ROOT/'inputs.lock.json').read_text())
    output.mkdir(parents=True,exist_ok=True)
    work=output/'source';work.mkdir(exist_ok=True)
    assets={}
    for item in lock['assets']:
        key=(item['repository'],item['name'])
        path=work/item['repository'].split('/')[-1]/item['name']
        asset(item,path);assets[key]=path
    crane=lock['crane'];archive=work/'crane.tar.gz'
    asset({**crane,'version':crane['version']},archive)
    with tarfile.open(archive) as tar:
        member=tar.getmember('crane')
        if not member.isfile() or member.size>100*1024**2:raise ValueError('invalid pinned crane executable')
        raw=tar.extractfile(member).read()
    if hashlib.sha256(raw).hexdigest()!=crane['binarySha256']:raise ValueError('crane executable checksum mismatch')
    executable=work/'crane';executable.write_bytes(raw);executable.chmod(0o755)
    bundle=output/'bundle';bundle.mkdir(exist_ok=True)
    (bundle/'images').mkdir(exist_ok=True);(bundle/'bin').mkdir(exist_ok=True)
    shutil.copyfile(assets[('kubernetes-sigs/cluster-api','clusterctl-linux-amd64')],bundle/'bin/clusterctl')
    (bundle/'bin/clusterctl').chmod(0o755)
    images=[]
    replacements={}
    for index,item in enumerate(lock['images']):
        file=f'images/upstream-{index}.oci.tar';target=bundle/file
        if not target.exists():
            layout=work/f'upstream-{index}.oci'
            if not layout.exists():
                command([str(executable),'pull','--format=oci','--annotate-ref',item['image'],str(layout)],timeout=600)
            temporary=target.with_suffix('.partial')
            with tarfile.open(temporary,'w') as archive:
                for path in sorted(layout.rglob('*')):
                    if path.is_symlink():raise ValueError('unsafe OCI layout path')
                    if not path.is_file():continue
                    name=str(path.relative_to(layout))
                    if name not in ('index.json','oci-layout') and not re.fullmatch(r'blobs/sha256/[a-f0-9]{64}',name):raise ValueError('unexpected OCI layout file')
                    info=tarfile.TarInfo(name);info.size=path.stat().st_size;info.mode=0o644
                    with path.open('rb') as stream:archive.addfile(info,stream)
            os.replace(temporary,target)
        verify_oci(target,item['image'])
        images.append({'image':item['image'],'file':file,'sha256':sha256(target),'activate':True})
        replacements[item['source']]=item['image']
    downstream={}
    for item in lock['downstream']['components']:
        component=item['component'];source=downstream_dir/component
        archive=source/f'{component}.oci.tar';binding=item['componentBinding']
        if sha256(archive)!=item['archiveSha256']:raise ValueError('downstream archive differs from qualified hosted artifact')
        verify_oci(archive,binding['image'])
        file=f'images/{component}.oci.tar';shutil.copyfile(archive,bundle/file)
        images.append({'image':binding['image'],'file':file,'sha256':sha256(bundle/file),'activate':component=='capc'})
        manifest=source/binding['manifest']
        if sha256(manifest)!=binding['manifestSha256']:raise ValueError('downstream manifest differs from qualified hosted artifact')
        downstream[component]=manifest
    deployments=[];crds=[];namespaces=[];providers=[]
    for name,kind,version,label,filename,namespace in PROVIDERS:
        repository='kubernetes-sigs/cluster-api' if name=='cluster-api' else ('rancher/cluster-api-provider-rke2' if name=='rke2' else 'kubernetes-sigs/cluster-api-provider-cloudstack')
        source=downstream['capc'] if name=='cloudstack' else assets[(repository,filename)]
        target=bundle/'repositories'/label/version;target.mkdir(parents=True,exist_ok=True)
        text=concrete(source.read_text())
        for before,after in replacements.items():text=text.replace(before,after)
        docs=[item for item in yaml.safe_load_all(text) if item]
        for item in docs:
            if item['kind']=='Deployment':
                containers=item['spec']['template']['spec']['containers']
                for container in containers:container['imagePullPolicy']='IfNotPresent'
                deployments.append({'name':item['metadata']['name'],'namespace':namespace,'images':{c['name']:c['image'] for c in containers},'provider':label})
            if item['kind']=='CustomResourceDefinition':crds.append({'name':item['metadata']['name'],'versions':[v['name'] for v in item['spec']['versions'] if v['served']]})
            if item['kind']=='Namespace':namespaces.append(item['metadata']['name'])
        (target/filename).write_text(yaml.safe_dump_all(docs,sort_keys=False))
        shutil.copyfile(assets[(repository,'metadata.yaml')],target/'metadata.yaml')
        providers.append({'name':name,'type':kind,'version':version,'label':label,'namespace':namespace,'file':str((target/filename).relative_to(bundle))})
    certdir=bundle/'repositories/cert-manager/v1.21.1';certdir.mkdir(parents=True,exist_ok=True)
    text=assets[('cert-manager/cert-manager','cert-manager.yaml')].read_text()
    for before,after in replacements.items():text=text.replace(before,after)
    docs=[item for item in yaml.safe_load_all(text) if item]
    for item in docs:
        if item['kind']=='Deployment':
            containers=item['spec']['template']['spec']['containers']
            for container in containers:container['imagePullPolicy']='IfNotPresent'
            deployments.append({'name':item['metadata']['name'],'namespace':'cert-manager','images':{c['name']:c['image'] for c in containers},'provider':'cert-manager'})
        if item['kind']=='CustomResourceDefinition':crds.append({'name':item['metadata']['name'],'versions':[v['name'] for v in item['spec']['versions'] if v['served']]})
        if item['kind']=='Namespace':namespaces.append(item['metadata']['name'])
    (certdir/'cert-manager.yaml').write_text(yaml.safe_dump_all(docs,sort_keys=False))
    # CCM remains available but unactivated; its existing qualification gate is false.
    shutil.copyfile(downstream['cloudstack-ccm'],bundle/'cloud-controller-manager.yaml')
    files={str(path.relative_to(bundle)):{'sha256':sha256(path),'size':path.stat().st_size} for path in sorted(bundle.rglob('*')) if path.is_file() and path.name!='bundle.json'}
    value={'schemaVersion':'1.0','status':'SOURCE_COMPLETE','productionCertified':False,'rke2Version':'v1.36.4+rke2r1',
           'files':files,'images':images,'providers':providers,'deployments':deployments,'crds':crds,'namespaceNames':sorted(set(namespaces)),
           'sourceLockSha256':sha256(ROOT/'inputs.lock.json')}
    (bundle/'bundle.json').write_text(json.dumps(value,indent=2)+'\n')
    print(json.dumps({'status':'SOURCE_COMPLETE','bundleManifestSha256':sha256(bundle/'bundle.json'),'productionCertified':False}))
    return bundle


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--downstream-dir',type=Path,required=True)
    args=parser.parse_args();prepare(args.output.resolve(),downstream_dir=args.downstream_dir.resolve())
