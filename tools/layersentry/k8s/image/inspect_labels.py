#!/usr/bin/env python3
"""Require real appliance relabel support and inspect sealed guest labels read-only."""
import argparse
import json
import os
from pathlib import Path


CRITICAL = {
    '/usr/lib64/ld-linux-x86-64.so.2': 'ld_so_t',
    '/usr/bin/bash': 'shell_exec_t',
    '/usr/bin/python3': 'bin_t',
    '/usr/bin/qemu-ga': 'virt_qemu_ga_exec_t',
    '/usr/lib/systemd/systemd': 'init_exec_t',
    '/usr/sbin/sshd': 'sshd_exec_t',
    '/etc/sysconfig/qemu-ga': 'etc_t',
    '/etc/selinux/config': 'selinux_config_t',
}


def validate(report):
    if not report['applianceSelinuxRelabelAvailable']:
        raise ValueError('appliance lacks setfiles/selinuxrelabel; first-boot fallback forbidden')
    if report.get('preflight'):
        return
    if report['autorelabelExists'] or report['selinuxConfig'] != 'enforcing':
        raise ValueError('offline SELinux relabel must finish with Enforcing configured')
    for path, expected in CRITICAL.items():
        actual = report['files'][path]['label'].rstrip('\x00')
        if actual != 'system_u:object_r:' + expected + ':s0':
            raise ValueError('unexpected SELinux label for ' + path + ': ' + actual)


def inspect(image=None):
    import guestfs
    os.environ['LIBGUESTFS_BACKEND'] = 'direct'
    handle = guestfs.GuestFS(python_return_dict=True)
    report = {'schemaVersion': '1.0', 'preflight': image is None,
              'runtimeQualified': False, 'imageModified': False}
    try:
        if image is not None:
            handle.add_drive_opts(str(image.resolve(strict=True)), format='qcow2', readonly=True)
        handle.launch()
        report['guestfsVersion'] = handle.version()
        report['applianceSelinuxRelabelAvailable'] = bool(handle.feature_available(['selinuxrelabel']))
        if image is not None:
            roots = handle.inspect_os()
            if len(roots) != 1:
                raise ValueError('exactly one inspected OS required')
            for mountpoint, device in sorted(handle.inspect_get_mountpoints(roots[0]).items(), key=lambda item: len(item[0])):
                handle.mount_ro(device, mountpoint)
            report['autorelabelExists'] = bool(handle.exists('/.autorelabel'))
            config = handle.read_file('/etc/selinux/config')
            if isinstance(config, bytes):
                config = config.decode()
            report['selinuxConfig'] = dict(line.split('=', 1) for line in config.splitlines() if line.startswith('SELINUX=' )).get('SELINUX')
            report['files'] = {}
            for path in CRITICAL:
                real = handle.realpath(path)
                label = handle.getxattr(real, 'security.selinux')
                report['files'][path] = {'realPath': real, 'label': label.decode() if isinstance(label, bytes) else label}
            handle.umount_all()
        handle.shutdown()
    finally:
        handle.close()
    validate(report)
    report['status'] = 'CI_VERIFIED'
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight', type=Path)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if bool(args.preflight) == bool(args.image) or bool(args.image) != bool(args.output):
        parser.error('choose --preflight OUTPUT or --image QCOW2 --output OUTPUT')
    output = args.preflight or args.output
    if output.exists() or output.is_symlink():
        raise ValueError('refusing evidence overwrite')
    result = inspect(args.image)
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
