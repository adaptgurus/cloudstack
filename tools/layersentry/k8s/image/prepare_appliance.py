#!/usr/bin/env python3
"""Copy the hosted supermin definition and add its missing SELinux package closure."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def prepare(source, output):
    if output.exists() or output.is_symlink():
        raise ValueError('refusing existing appliance directory')
    source = source.resolve(strict=True) / 'supermin.d'
    if not source.is_dir() or not (source / 'packages').is_file():
        raise ValueError('packaged supermin definition required')
    # Preserve packaged definitions; supermin accepts additional package lists
    # and resolves dependencies from the signed installed host package cohort.
    copied = output / 'supermin.d'
    shutil.copytree(source, copied)
    with (copied / 'layersentry-selinux-packages').open('x') as stream:
        stream.write('policycoreutils\n')
    report = {'schemaVersion': '1.0', 'status': 'SOURCE_COMPLETE',
              'sourceDirectory': str(source), 'addedPackages': ['policycoreutils'],
              'capabilityVerified': False, 'definitionSha256': {}}
    for path in sorted(copied.rglob('*')):
        if path.is_file():
            report['definitionSha256'][str(path.relative_to(copied))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return report


def main():
    import guestfs
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    if args.evidence.exists() or args.evidence.is_symlink():
        raise ValueError('refusing evidence overwrite')
    handle = guestfs.GuestFS()
    try:
        path = handle.get_path()
    finally:
        handle.close()
    if ':' in path:
        raise ValueError('one packaged appliance search path required')
    result = prepare(Path(path), args.output)
    args.evidence.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
