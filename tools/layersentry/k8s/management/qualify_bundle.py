#!/usr/bin/env python3
"""Hosted-only immutable bundle generation/import qualification, without a cluster."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time

import yaml

from management.bundle import Bundle, sha256, retain_archive
from management.install import clusterctl_config, clusterctl_env

ROOT = Path(__file__).resolve().parent


def run(argv, *, timeout=300, env=None):
    result = subprocess.run(argv, capture_output=True, timeout=timeout, check=False, env=env)
    if result.returncode:
        # Only public build inputs reach this command. Bounded diagnostics are
        # useful here; the runtime installer deliberately discards diagnostics.
        raise RuntimeError('public qualification command failed: '+str(argv[0])+'\n'+result.stderr.decode(errors='replace')[-4000:])
    return result.stdout


def generate(bundle, output):
    config = output/'clusterctl.json'
    config.write_text(json.dumps(clusterctl_config(bundle)))
    generated = []
    for provider in bundle.value['providers']:
        flag = {'CoreProvider':'--core','BootstrapProvider':'--bootstrap','ControlPlaneProvider':'--control-plane','InfrastructureProvider':'--infrastructure'}[provider['type']]
        raw = run([str(bundle.file('bin/clusterctl')), 'generate', 'provider', flag, provider['name']+':'+provider['version'], '--config', str(config)], env=clusterctl_env(output))
        docs = [row for row in yaml.safe_load_all(raw) if row]
        actual = {(row['metadata']['namespace'], row['metadata']['name']):{c['name']:c['image'] for c in row['spec']['template']['spec']['containers']} for row in docs if row['kind']=='Deployment'}
        expected = {(d['namespace'],d['name']):d['images'] for d in bundle.value['deployments'] if d['provider']==provider['label']}
        if actual != expected:
            raise ValueError('native clusterctl generation changed controller identity/image binding')
        path=output/(provider['label']+'.yaml');path.write_bytes(raw)
        generated.append({'provider':provider['label'],'sha256':sha256(path),'size':len(raw)})
    return generated


def native_import(bundle, source, output):
    if os.environ.get('GITHUB_ACTIONS') != 'true' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted':
        raise ValueError('native import qualification is restricted to a disposable GitHub-hosted runner')
    lock=json.loads((ROOT/'qualification-tools.lock.json').read_text())
    crane=source/'crane'
    if sha256(crane)!=json.loads((ROOT/'inputs.lock.json').read_text())['crane']['binarySha256']:
        raise ValueError('qualification crane binary differs from pin')
    runtime=source/'runtime.tar'
    run([str(crane),'export','--platform','linux/amd64',lock['runtimeImage'],str(runtime)],timeout=600)
    binaries=output/'bin';binaries.mkdir()
    with tarfile.open(runtime) as archive:
        for name in ('containerd','ctr','runc','containerd-shim-runc-v2'):
            member=archive.getmember('bin/'+name)
            if not member.isfile() or member.size>150*1024**2:raise ValueError('unsafe pinned runtime binary')
            path=binaries/name;path.write_bytes(archive.extractfile(member).read());path.chmod(0o755)
    version=run([str(binaries/'containerd'),'--version']).decode().strip()
    if lock['expectedContainerdVersion'] not in version:raise ValueError('native containerd version differs from exact RKE2 runtime')
    # Root-owned containerd state is confined to disposable hosted-runner temp;
    # it is never mixed into the user-owned exported artifact tree.
    daemon_root=Path(tempfile.mkdtemp(prefix='layersentry-native-containerd-',dir=os.environ['RUNNER_TEMP']))
    socket=str(daemon_root/'socket')
    config=daemon_root/'config.toml'
    config.write_text('version = 3\ndisabled_plugins = ["io.containerd.cri.v1.images", "io.containerd.cri.v1.runtime"]\n')
    env={**os.environ,'PATH':str(binaries)+':/usr/bin:/bin'}
    log=(output/'containerd.log').open('wb')
    daemon=subprocess.Popen(['sudo','-n','--',str(binaries/'containerd'),'--config',str(config),'--root',str(daemon_root/'root'),'--state',str(daemon_root/'state'),'--address',socket],stdout=log,stderr=log,env=env)
    ctr=['sudo','-n','--',str(binaries/'ctr'),'--address',socket,'--namespace','k8s.io']
    try:
        deadline=time.monotonic()+30
        while not Path(socket).exists():
            if daemon.poll() is not None or time.monotonic()>deadline:raise RuntimeError('isolated containerd did not start')
            time.sleep(0.2)
        observations=[];transfer_probe=None
        for attempt in range(3):
            for item in bundle.value['images']:
                repository=item['image'].split('@')[0]
                flags=[] if attempt==0 else ['--local']
                run(ctr+['images','import',*flags,'--all-platforms','--digests','--base-name',repository,str(bundle.file(item['file']))],timeout=300)
            rows=run(ctr+['images','list']).decode().splitlines()
            actual={row.split()[0]:row.split()[2] for row in rows[1:] if len(row.split())>=3}
            expected={item['image']:item['image'].split('@')[1] for item in bundle.value['images']}
            missing=[name for name,digest in expected.items() if actual.get(name)!=digest]
            if attempt==0:
                # Diagnose the old transfer-API path without using it as a pass
                # gate. Runtime now explicitly uses native local import.
                transfer_probe={'missingExactNames':missing,'observedImages':actual}
                print(json.dumps({'scope':'transfer-API naming diagnostic','missingExactNames':missing,'observedImages':actual}))
                continue
            if missing:raise ValueError('native local import lost required exact image index names: '+json.dumps({'missing':missing,'actual':actual}))
            observations.append({'attempt':attempt,'mode':'native-local','exactImages':expected})
        return {'runtimeImage':lock['runtimeImage'],'containerdVersion':version,'binarySha256':{path.name:sha256(path) for path in binaries.iterdir()},'transferApiProbe':transfer_probe,'imports':observations}
    finally:
        daemon.terminate()
        try:daemon.wait(timeout=20)
        except subprocess.TimeoutExpired:daemon.kill();daemon.wait(timeout=10)
        log.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,required=True)
    args=parser.parse_args();prepared=args.prepared.resolve()
    bundle=Bundle(prepared/'bundle',sha256(prepared/'bundle/bundle.json'))
    with tempfile.TemporaryDirectory(prefix='layersentry-management-qualification-') as directory:
        output=Path(directory)
        generated=generate(bundle,output)
        imported=native_import(bundle,prepared/'source',output)
    value=bundle.value;value['status']='CI_VERIFIED'
    manifest=bundle.root/'bundle.json';manifest.write_text(json.dumps(value,indent=2)+'\n')
    # GitHub ZIP artifacts discard executable modes. Preserve the usable
    # clusterctl mode inside a deterministic tar, never as loose ZIP files.
    retained=prepared/'management-provider-bundle.tar'
    retain_archive(bundle,retained)
    evidence={'schemaVersion':'1.0','scope':'hosted source, native provider generation and exact RKE2 containerd import/reimport only',
              'status':'CI_VERIFIED','liveVerified':False,'productionCertified':False,'signed':False,
              'sourceCommit':os.environ['GITHUB_SHA'],'workflowRunId':os.environ['GITHUB_RUN_ID'],
              'bundleManifestSha256':sha256(manifest),'bundleArchiveSha256':sha256(retained),'inputLockSha256':sha256(ROOT/'inputs.lock.json'),
              'generatedProviders':generated,'nativeImport':imported}
    (prepared/'qualification.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'status':evidence['status'],'bundleManifestSha256':evidence['bundleManifestSha256'],'liveVerified':False,'productionCertified':False}))


if __name__=='__main__':main()
