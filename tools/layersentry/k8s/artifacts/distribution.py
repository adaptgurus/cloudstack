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

"""Deterministic inventory of the existing systemd/filesystem runtime payload.

No installer or deployment is implemented here. Runtime credentials/configuration
are deliberately excluded; the release contract and artifact locks are separate
inputs. This receipt does not qualify host Python or Gunicorn packages.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def payload_paths(root):
    return sorted([*root.glob('controller/*.py'), *root.glob('systemd/*'),
                   root/'layersentry_k8s_policy.py', root/'layersentry_k8s_controller.py'])


def inventory(root):
    rows = []
    for path in payload_paths(root):
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o022:
            raise ValueError('unsafe runtime payload')
        relative = str(path.relative_to(root))
        target = '/etc/systemd/system/'+path.name if relative.startswith('systemd/') else '/usr/lib/layersentry/k8s/'+relative
        rows.append({'path':relative, 'installedPath':target, 'mode':'0644',
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return rows


def tree_sha(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def verify(root, receipt):
    rows = inventory(root)
    if rows != receipt.get('files') or tree_sha(rows) != receipt.get('treeSha256'):
        raise ValueError('runtime distribution content differs from receipt')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path)
    parser.add_argument('--source-commit')
    parser.add_argument('--verify', type=Path)
    args = parser.parse_args()
    if args.verify:
        verify(args.root, json.loads(args.verify.read_text()))
        print('DISTRIBUTION_TREE_VERIFIED')
        return
    if not args.output or not re.fullmatch('[0-9a-f]{40}', args.source_commit or ''):
        parser.error('--output and exact --source-commit are required')
    rows = inventory(args.root)
    # The claimed source commit must contain exactly the runtime bytes inventoried.
    for row in rows:
        data = subprocess.check_output(['git','-C',str(args.root),'show',
            args.source_commit+':tools/layersentry/k8s/'+row['path']])
        if hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('runtime differs from claimed source commit')
    receipt = {'schemaVersion':'1.0','sourceCommit':args.source_commit,
               'distribution':'systemd-filesystem','files':rows,'treeSha256':tree_sha(rows),
               'runtimeDependencyLock':{'path':'tools/layersentry/k8s/artifacts/runtime-dependencies.json',
                   'sha256':hashlib.sha256((args.root/'artifacts/runtime-dependencies.json').read_bytes()).hexdigest()},
               'runtimeIdentity':json.loads((args.root/'artifacts/runtime-dependencies.json').read_text()).get('identity', {}),
               'releaseMetadata':'Install the release manifest and referenced artifact locks from the exact release commit separately; never copy runtime credentials from Git.'}
    args.output.write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['treeSha256'])

if __name__ == '__main__':
    main()
