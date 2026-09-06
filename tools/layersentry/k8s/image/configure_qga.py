#!/usr/bin/env python3
"""Extend the exact Rocky QGA policy only for trusted host-mediated bootstrap."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat

# Exact qemu-guest-agent-10.1.0-17.el9_8.5 RPM default. A package policy
# change requires review instead of silently enabling additional RPCs.
BASE = frozenset('''guest-sync-delimited guest-sync guest-ping guest-get-time guest-set-time guest-info
guest-shutdown guest-fsfreeze-status guest-fsfreeze-freeze guest-fsfreeze-freeze-list guest-fsfreeze-thaw
guest-fstrim guest-suspend-disk guest-suspend-ram guest-suspend-hybrid guest-network-get-interfaces
guest-get-vcpus guest-set-vcpus guest-get-disks guest-get-fsinfo guest-set-user-password guest-get-memory-blocks
guest-set-memory-blocks guest-get-memory-block-info guest-get-host-name guest-get-users guest-get-timezone
guest-get-osinfo guest-get-devices guest-ssh-get-authorized-keys guest-ssh-add-authorized-keys
guest-ssh-remove-authorized-keys guest-get-diskstats guest-get-cpustats guest-network-get-route guest-get-load'''.split())
EXTRA = ('guest-exec', 'guest-exec-status')


def configure(source):
    if len(source) > 16384 or '\x00' in source:
        raise ValueError('invalid QGA environment file')
    lines = source.splitlines()
    candidates = [index for index, line in enumerate(lines) if re.match(r'\s*FILTER_RPC_ARGS\s*=', line)]
    if len(candidates) != 1:
        raise ValueError('exactly one explicit QGA allowlist required')
    index = candidates[0]
    match = re.fullmatch(r'FILTER_RPC_ARGS="--allow-rpcs=([a-z0-9,-]+)"', lines[index])
    if not match:
        raise ValueError('QGA must retain a finite explicit allowlist')
    commands = match[1].split(',')
    if len(commands) != len(set(commands)) or set(commands) not in (BASE, BASE | set(EXTRA)):
        raise ValueError('QGA package policy differs from reviewed Rocky version')
    commands += [command for command in EXTRA if command not in commands]
    lines[index] = 'FILTER_RPC_ARGS="--allow-rpcs=' + ','.join(commands) + '"'
    return '\n'.join(lines) + '\n'


def main():
    path = Path('/etc/sysconfig/qemu-ga')
    info = path.lstat()
    if os.geteuid() != 0 or not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or info.st_mode & 0o022:
        raise ValueError('trusted root-owned QGA policy required')
    updated = configure(path.read_text())
    temporary = path.with_name('qemu-ga.layersentry-new')
    with temporary.open('x') as stream:
        stream.write(updated)
        stream.flush()
        os.fchmod(stream.fileno(), stat.S_IMODE(info.st_mode))
        os.fsync(stream.fileno())
    temporary.replace(path)
    print(json.dumps({'schemaVersion': '1.0', 'addedRpcs': list(EXTRA), 'allowAllRpcs': False,
                      'trustBoundary': 'authorized KVM host and LayerSentry Runner via private virtio channel',
                      'policySha256': hashlib.sha256(updated.encode()).hexdigest()}, sort_keys=True))


if __name__ == '__main__':
    main()
