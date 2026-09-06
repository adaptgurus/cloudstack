#!/usr/bin/env python3
"""Export only the SSH Ed25519 public key across the confined QGA read boundary."""
import base64
import os
from pathlib import Path
import stat
import struct
import tempfile

SOURCE = Path('/etc/ssh/ssh_host_ed25519_key.pub')
DESTINATION = Path('/usr/share/layersentry/node-image/ssh_host_ed25519_key.pub')


def public_key(text):
    if len(text) > 4096 or '\x00' in text or len(text.strip().splitlines()) != 1:
        raise ValueError('bounded single-line SSH public key required')
    fields = text.split()
    if len(fields) < 2 or fields[0] != 'ssh-ed25519':
        raise ValueError('Ed25519 public key required')
    blob = base64.b64decode(fields[1], validate=True)
    prefix = struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32)
    if len(blob) != len(prefix) + 32 or not blob.startswith(prefix):
        raise ValueError('invalid Ed25519 public wire encoding')
    return 'ssh-ed25519 ' + base64.b64encode(blob).decode() + '\n'


def export():
    if os.geteuid() != 0:
        raise ValueError('root-owned exporter required')
    descriptor = os.open(SOURCE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'r') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0 or info.st_nlink != 1 or info.st_mode & 0o022 or info.st_size > 4096:
            raise ValueError('trusted root-owned public source required')
        data = public_key(source.read(4097))
    parent = DESTINATION.parent
    for directory in [parent, *parent.parents]:
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid != 0 or info.st_mode & 0o022:
            raise ValueError('trusted export directory ancestry required')
    descriptor, name = tempfile.mkstemp(prefix='.ssh-public-', dir=parent)
    try:
        with os.fdopen(descriptor, 'w') as output:
            output.write(data)
            output.flush()
            os.fchmod(output.fileno(), 0o644)
            os.fsync(output.fileno())
        os.replace(name, DESTINATION)
    finally:
        Path(name).unlink(missing_ok=True)


if __name__ == '__main__':
    export()
