#!/usr/bin/env python3
"""Render review-only native CSI objects offline; never connects to Kubernetes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import yaml

ROOT = Path(__file__).resolve().parent
NAMESPACE = 'layersentry-cloudstack-csi'
SECRET = 'cloudstack-project-credentials'
DRIVER_REPOSITORY = 'registry.invalid/layersentry/cloudstack-csi-driver'
SYNCER_REPOSITORY = 'registry.invalid/layersentry/cloudstack-csi-sc-syncer'
METADATA = '/run/cloud-init/instance-data.json'
SIDECARS = {'external-provisioner': 'csi-provisioner', 'external-attacher': 'csi-attacher',
            'external-resizer': 'csi-resizer', 'liveness-probe': 'livenessprobe',
            'node-driver-registrar': 'csi-node-driver-registrar'}


class InvalidBundle(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise InvalidBundle(message)


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def json_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def locked_inputs(root=ROOT):
    lock = json.loads((root / 'inputs.lock.json').read_text())
    chart = root / 'chart'
    actual = {str(p.relative_to(chart)) for p in chart.rglob('*') if p.is_file()}
    require(actual == set(lock['chartFiles']), 'chart file inventory differs')
    for name, digest in lock['chartFiles'].items():
        path = chart / name
        require(not path.is_symlink() and sha(path) == digest, 'chart content differs: ' + name)
    require(sha(root.parent / 'artifact-lock.json') == lock['artifactLockSha256'], 'artifact lock differs')
    artifact = json.loads((root.parent / 'artifact-lock.json').read_text())
    require(artifact['upstreamCommit'] == lock['upstreamCommit'], 'upstream source differs')
    promotion = root / 'registry-evidence' / 'promotion-images.yaml'
    require(sha(promotion) == lock['promotionSource']['sha256'], 'promotion source differs')
    promotion_map = {item['name']: item['dmap'] for item in yaml.safe_load(promotion.read_text())}
    for item in lock['sidecars']:
        require(item['tag'] in promotion_map[item['name']].get(item['indexDigest'], []), 'promotion tag/digest differs')
        for name, digest in item['metadataFiles'].items():
            require(sha(root / 'registry-evidence' / name) == digest, 'registry metadata differs: ' + name)
        def metadata(kind):
            return json.loads((root / 'registry-evidence' / (item['name'] + '-' + kind + '.json')).read_text())
        index, runtime, config = metadata('index'), metadata('amd64'), metadata('config')
        descriptors = [d for d in index['manifests'] if d.get('platform') == {'os': 'linux', 'architecture': 'amd64'}]
        require(len(descriptors) == 1 and descriptors[0]['digest'] == item['runtimeManifestDigest'], 'amd64 descriptor differs')
        require(descriptors[0]['size'] == (root / 'registry-evidence' / (item['name'] + '-amd64.json')).stat().st_size,
                'runtime descriptor size differs')
        require(runtime['config']['digest'] == item['configDigest'] and runtime['layers'] == item['layers'], 'runtime closure differs')
        require(runtime['config']['size'] == (root / 'registry-evidence' / (item['name'] + '-config.json')).stat().st_size,
                'config descriptor size differs')
        require(config['os'] == 'linux' and config['architecture'] == 'amd64', 'config platform differs')
        require(item['metadataFiles'][item['name'] + '-index.json'] == item['indexDigest'].removeprefix('sha256:')
                and item['metadataFiles'][item['name'] + '-amd64.json'] == item['runtimeManifestDigest'].removeprefix('sha256:')
                and item['metadataFiles'][item['name'] + '-config.json'] == item['configDigest'].removeprefix('sha256:'),
                'registry graph digest binding differs')
    require({x['name'] for x in lock['sidecars']} == set(SIDECARS.values()), 'sidecar inventory differs')
    require(all(value is False for value in lock['qualification'].values()), 'review bundle cannot qualify deployment')
    return lock, artifact


def values():
    return {'fullnameOverride': 'cloudstack-csi', 'syncer': {'enabled': False},
            'secret': {'enabled': True, 'create': False, 'name': SECRET, 'hostMount': False},
            'node': {'metadataSource': 'cloud-init', 'kubeletPath': '/var/lib/kubelet',
                     'nodeSelector': {'kubernetes.io/arch': 'amd64'}},
            'controller': {'nodeSelector': {'kubernetes.io/arch': 'amd64'}}}


def helm_objects(helm, lock, root=ROOT):
    require(sha(helm) == lock['helm']['binarySha256'], 'Helm binary differs from pinned tool')
    with tempfile.TemporaryDirectory(prefix='layersentry-csi-render-') as work:
        work = Path(work)
        (work / 'values.json').write_bytes(json_bytes(values()))
        # No inherited plugin, kubeconfig, helm configuration or network-backed dependency update.
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(work), 'LANG': 'C.UTF-8',
               'HELM_CACHE_HOME': str(work / 'cache'), 'HELM_CONFIG_HOME': str(work / 'config'),
               'HELM_DATA_HOME': str(work / 'data'), 'KUBECONFIG': str(work / 'absent')}
        result = subprocess.run([str(helm.resolve()), 'template', 'cloudstack-csi', str(root / 'chart'),
                                 '--namespace', NAMESPACE, '--kube-version', '1.36.4',
                                 '--values', str(work / 'values.json')], env=env,
                                check=True, capture_output=True, timeout=60)
    require(len(result.stdout) < 1024 * 1024, 'unexpectedly large Helm output')
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def overlay(objects, lock, artifact):
    objects = copy.deepcopy(objects)
    sidecars = {x['name']: x for x in lock['sidecars']}
    driver = DRIVER_REPOSITORY + '@' + artifact['images']['cloudstack-csi-driver']['imageManifestDigest']
    for obj in objects:
        if obj['kind'] not in {'Deployment', 'DaemonSet'}:
            continue
        pod = obj['spec']['template']['spec']
        for container in pod['containers']:
            name = container['name']
            if name in {'cloudstack-csi-controller', 'cloudstack-csi-node'}:
                require(container['image'] == 'ghcr.io/cloudstack/cloudstack-csi-driver:' + lock['chartAppVersion'],
                        'unexpected upstream driver reference')
                container['image'] = driver
            else:
                require(name in SIDECARS, 'unexpected container')
                item = sidecars[SIDECARS[name]]
                require(container['image'] == item['registry'] + ':' + item['tag'], 'upstream sidecar version differs')
                container['image'] = item['registry'] + '@' + item['runtimeManifestDigest']
            for mount in container.get('volumeMounts', []):
                if mount['name'] == 'cloud-config':
                    mount['readOnly'] = True
                if mount['name'] == 'cloud-init-dir':
                    require(mount['mountPath'] == '/run/cloud-init', 'metadata mount differs')
                    mount.update(mountPath=METADATA, readOnly=True)
        for volume in pod['volumes']:
            if volume['name'] == 'cloud-init-dir':
                require(volume['hostPath'] == {'path': '/run/cloud-init', 'type': 'Directory'}, 'metadata volume differs')
                volume['hostPath'] = {'path': METADATA, 'type': 'File'}
            if volume['name'] == 'cloud-config':
                volume['secret'].update(defaultMode=0o440, items=[{'key': 'cloud-config', 'path': 'cloud-config'}])
    namespace = {'apiVersion': 'v1', 'kind': 'Namespace', 'metadata': {'name': NAMESPACE, 'labels': {
        'app.kubernetes.io/managed-by': 'layersentry',
        'pod-security.kubernetes.io/enforce': 'privileged',
        'pod-security.kubernetes.io/enforce-version': 'v1.36'}}}
    return [namespace] + objects


def validate(objects, lock, artifact):
    allowed = {'Namespace', 'ServiceAccount', 'ClusterRole', 'ClusterRoleBinding', 'Role',
               'RoleBinding', 'Deployment', 'DaemonSet', 'CSIDriver'}
    identities = set()
    sidecars = {x['name']: x for x in lock['sidecars']}
    wanted_driver = DRIVER_REPOSITORY + '@' + artifact['images']['cloudstack-csi-driver']['imageManifestDigest']
    workloads = []
    for obj in objects:
        kind, meta = obj['kind'], obj['metadata']
        require(kind in allowed, 'unexpected resource kind')
        identity = (kind, meta.get('namespace', ''), meta['name'])
        require(identity not in identities, 'duplicate resource')
        identities.add(identity)
        if kind in {'Role', 'RoleBinding', 'ServiceAccount', 'Deployment', 'DaemonSet'}:
            require(meta.get('namespace') == NAMESPACE, 'namespace escape')
        else:
            require('namespace' not in meta, 'cluster resource has namespace')
        require('syncer' not in meta['name'], 'syncer must remain disabled')
        for rule in obj.get('rules', []):
            require(not any('*' in str(value) for value in rule.values()), 'wildcard RBAC')
            require('secrets' not in rule.get('resources', []), 'Secret API grant')
        if kind.endswith('Binding'):
            require(obj['roleRef']['name'] != 'cluster-admin', 'cluster-admin binding')
            require(all(s['kind'] == 'ServiceAccount' and s['namespace'] == NAMESPACE
                        and s['name'] in {'cloudstack-csi-controller', 'cloudstack-csi-node'}
                        for s in obj['subjects']), 'foreign RBAC subject')
        if kind not in {'Deployment', 'DaemonSet'}:
            continue
        workloads.append(kind)
        pod = obj['spec']['template']['spec']
        require(pod['nodeSelector'] == {'kubernetes.io/os': 'linux', 'kubernetes.io/arch': 'amd64'}, 'platform selector differs')
        require(not any(pod.get(key) for key in ('hostNetwork', 'hostPID', 'hostIPC', 'initContainers', 'ephemeralContainers')), 'unexpected host or init access')
        containers = {x['name']: x for x in pod['containers']}
        expected = ({'cloudstack-csi-controller', 'external-provisioner', 'external-attacher', 'external-resizer', 'liveness-probe'}
                    if kind == 'Deployment' else {'cloudstack-csi-node', 'node-driver-registrar', 'liveness-probe'})
        require(set(containers) == expected and len(containers) == len(pod['containers']), 'container inventory differs')
        for name, container in containers.items():
            wanted = wanted_driver if name.startswith('cloudstack-csi-') else sidecars[SIDECARS[name]]['registry'] + '@' + sidecars[SIDECARS[name]]['runtimeManifestDigest']
            require(container['image'] == wanted, 'image digest differs')
            require(not container.get('envFrom') and not any(e['name'] == 'NODE_ID' for e in container.get('env', [])), 'untrusted identity/environment override')
        volumes = {x['name']: x for x in pod['volumes']}
        require(volumes['cloud-config'] == {'name': 'cloud-config', 'secret': {'secretName': SECRET, 'defaultMode': 0o440,
                'items': [{'key': 'cloud-config', 'path': 'cloud-config'}]}}, 'credential reference differs')
        if kind == 'DaemonSet':
            require(volumes['cloud-init-dir']['hostPath'] == {'path': METADATA, 'type': 'File'}, 'metadata source differs')
            mount = next(m for m in containers['cloudstack-csi-node']['volumeMounts'] if m['name'] == 'cloud-init-dir')
            require(mount == {'name': 'cloud-init-dir', 'mountPath': METADATA, 'readOnly': True}, 'metadata mount is not read-only exact file')
    require(sorted(workloads) == ['DaemonSet', 'Deployment'], 'controller/node workload missing')
    require(('Namespace', '', NAMESPACE) in identities, 'namespace missing')
    require(('CSIDriver', '', 'csi.cloudstack.apache.org') in identities, 'CSI driver missing')


def render(helm, root=ROOT):
    lock, artifact = locked_inputs(root)
    objects = overlay(helm_objects(helm, lock, root), lock, artifact)
    validate(objects, lock, artifact)
    return objects, lock, artifact


def write_bundle(output, objects, lock, artifact):
    output.mkdir(parents=True, exist_ok=False)
    manifests = yaml.safe_dump_all(objects, sort_keys=False).encode()
    (output / 'review-manifests.yaml').write_bytes(manifests)
    images = [{'component': name, 'runtimeDigest': item['imageManifestDigest'], 'indexDigest': item['imageIndexDigest'],
               'plannedReference': (DRIVER_REPOSITORY if name == 'cloudstack-csi-driver' else SYNCER_REPOSITORY) + '@' + item['imageManifestDigest'],
               'registryReference': None, 'archive': item['archivePath'], 'archiveSha256': item['archiveSha256'],
               'enabled': name == 'cloudstack-csi-driver', 'signatureVerified': False}
              for name, item in artifact['images'].items()]
    images += [{'component': item['name'], 'runtimeDigest': item['runtimeManifestDigest'], 'indexDigest': item['indexDigest'],
                'registryReference': item['registry'] + '@' + item['runtimeManifestDigest'], 'enabled': True,
                'signatureVerified': False, 'provenanceVerified': False} for item in lock['sidecars']]
    receipt = {'schemaVersion': '1.0', 'artifactType': 'layersentry-native-csi-review-bundle',
               'status': 'SOURCE_COMPLETE', 'deployable': False, 'namespace': NAMESPACE, 'secretReference': SECRET,
               'inputsSha256': sha(ROOT / 'inputs.lock.json'), 'artifactLockSha256': lock['artifactLockSha256'],
               'manifestSha256': hashlib.sha256(manifests).hexdigest(), 'objectCount': len(objects),
               'qualification': lock['qualification'], 'images': images}
    (output / 'bundle.json').write_bytes(json_bytes(receipt))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--helm', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(write_bundle(args.output, *render(args.helm)), sort_keys=True))


if __name__ == '__main__':
    main()
