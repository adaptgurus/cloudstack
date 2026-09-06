#!/usr/bin/env python3
"""Read-only diagnostic of the exact first CPU candidate; no guest code executes."""
import hashlib
import json
import os
from pathlib import Path
import sys

import guestfs

EXPECTED = '8ee4a820fd427abf3f00e0f55b0421c8cb9d5fa054cd84bc0aab62fc1fc4bf77'


def main():
    image, output = map(Path, sys.argv[1:])
    digest = hashlib.sha256()
    with image.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    assert digest.hexdigest() == EXPECTED and image.stat().st_size == 2673999872
    assert not output.exists()
    os.environ['LIBGUESTFS_BACKEND'] = 'direct'
    handle = guestfs.GuestFS(python_return_dict=True)
    result = {'status': 'CI_VERIFIED', 'scope': 'read-only exact candidate SELinux/QGA metadata audit',
              'imageSha256': EXPECTED, 'runtimeQualified': False, 'imageModified': False}
    try:
        handle.add_drive_opts(str(image), format='qcow2', readonly=True)
        handle.launch()
        roots = handle.inspect_os()
        assert len(roots) == 1
        for mountpoint, device in sorted(handle.inspect_get_mountpoints(roots[0]).items(), key=lambda item: len(item[0])):
            handle.mount_ro(device, mountpoint)
        result['guestfsVersion'] = handle.version()
        result['applianceSelinuxRelabelAvailable'] = handle.feature_available(['selinuxrelabel'])
        result['autorelabelExists'] = handle.exists('/.autorelabel')
        result['files'] = {}
        paths = ['/usr/lib64/ld-linux-x86-64.so.2', '/usr/bin/bash', '/usr/bin/python3', '/usr/bin/qemu-ga',
                 '/usr/lib/systemd/systemd', '/etc/sysconfig/qemu-ga', '/etc/selinux/config', '/.autorelabel']
        for path in paths:
            entry = {'exists': handle.exists(path)}
            if entry['exists']:
                entry['realPath'] = handle.realpath(path)
                entry['stat'] = handle.statns(entry['realPath'])
                try:
                    label = handle.getxattr(entry['realPath'], 'security.selinux')
                    entry['selinuxLabel'] = label.decode() if isinstance(label, bytes) else label
                except RuntimeError as error:
                    entry['selinuxLabelError'] = str(error)
            result['files'][path] = entry
        for path in ['/etc/sysconfig/qemu-ga', '/etc/selinux/config', '/etc/os-release']:
            value = handle.read_file(path)
            result[path] = value.decode() if isinstance(value, bytes) else value
        result['guestKernels'] = handle.ls('/lib/modules')
        handle.umount_all()
        handle.shutdown()
    finally:
        handle.close()
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
