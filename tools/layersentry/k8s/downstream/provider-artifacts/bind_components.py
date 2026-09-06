#!/usr/bin/env python3
"""Render patched provider components with an already verified OCI digest."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

DEFAULTS = {
    'CAPI_DIAGNOSTICS_ADDRESS': ':8443', 'CAPI_INSECURE_DIAGNOSTICS': 'false',
    'CAPC_CLOUDSTACKCLUSTER_CONCURRENCY': '10', 'CAPC_CLOUDSTACKMACHINE_CONCURRENCY': '10',
    'CAPC_CLOUDSTACKMACHINE_CKS_SYNC': 'false',
}


def concrete(text):
    def substitute(match):
        key, default = match.groups()
        if DEFAULTS.get(key) != default:
            raise ValueError('unexpected provider configuration variable')
        return default
    result = re.sub(r'\$\{([A-Z_]+):=([^}]+)\}', substitute, text)
    if '${' in result or '$(' in result:
        raise ValueError('unresolved provider configuration variable')
    return result


def bind(component, source, evidence, kustomize=None):
    verification = json.loads((evidence / f'{component}-verification.json').read_text())
    digest = verification['imageManifestDigest']
    if verification.get('status') != 'CI_VERIFIED' or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest):
        raise ValueError('image must pass OCI verification before manifest binding')
    image = f'layersentry.local/{component}@{digest}'
    if component == 'capc':
        patch = source / 'config/default/manager_image_patch.yaml'
        text = patch.read_text()
        old = 'localhost:5000/cluster-api-provider-cloudstack:latest'
        if text.count(old) != 1:
            raise ValueError('CAPC upstream image patch drift')
        patch.with_name('manager_image_patch_edited.yaml').write_text(text.replace(old, image))
        result = subprocess.run([str(kustomize), 'build', str(source / 'config/default')], capture_output=True, text=True, check=True, timeout=120)
        rendered = concrete(result.stdout)
        if 'ownedDataDiskID' not in rendered or 'rke2SupervisorLoadBalancerRuleID' not in rendered:
            raise ValueError('patched CAPC CRD ownership/endpoint fields absent')
        filename = 'infrastructure-components.yaml'
    elif component == 'cloudstack-ccm':
        text = (source / 'deployment.yaml').read_text()
        old = 'apache/cloudstack-kubernetes-provider:v1.2.0'
        if text.count(old) != 1:
            raise ValueError('CCM upstream image drift')
        rendered = text.replace(old, image)
        filename = 'cloud-controller-manager.yaml'
    else:
        raise ValueError('unsupported provider')
    images = re.findall(r'^\s*(?:-\s+)?image:\s*(\S+)\s*$', rendered, re.M)
    if images != [image]:
        raise ValueError('unexpected additional or unbound provider image')
    target = evidence / filename
    target.write_text(rendered)
    binding = {
        'schemaVersion': '1.0', 'component': component, 'status': 'CI_VERIFIED',
        'productionCertified': False, 'liveVerified': False, 'signed': False,
        'image': image, 'archiveSha256': verification['archiveSha256'],
        'manifest': filename, 'manifestSha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'layersentrySourceCommit': verification['layersentrySourceCommit'],
        'requirements': ['Import the retained OCI archive into every scheduled node or mirror it preserving its digest.',
                         'Install pinned CAPI core, CAPRKE2 and cert-manager dependencies before CAPC.',
                         'Provide scoped CloudStack credentials through the provider native Secret contract; no credentials are included.'],
    }
    (evidence / f'{component}-component-binding.json').write_text(json.dumps(binding, indent=2) + '\n')
    print(json.dumps(binding, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--component', choices=['capc', 'cloudstack-ccm'], required=True)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--kustomize', type=Path)
    args = parser.parse_args()
    bind(args.component, args.source.resolve(), args.evidence.resolve(), args.kustomize.resolve() if args.kustomize else None)


if __name__ == '__main__':
    main()
