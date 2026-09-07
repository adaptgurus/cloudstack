#!/usr/bin/python3
# Copyright 2026 LayerSentry contributors
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
from ansible.module_utils.basic import AnsibleModule

SAFE_PATH_RE = re.compile(r"^/[A-Za-z0-9._:/-]+$")
SOURCE_ROOTS = ("/data", "/srv", "/opt/layersentry-data")
TARGET_ROOTS = ("/var/lib/redis", "/var/lib/valkey", "/var/lib/pgsql")


def under(path: str, roots) -> bool:
    return any(path == root or path.startswith(root + os.sep) for root in roots)


def validate_path(path: str, roots, label: str) -> str:
    if not SAFE_PATH_RE.fullmatch(path) or not os.path.isabs(path) or os.path.normpath(path) != path or not under(path, roots):
        raise ValueError("unsafe %s path" % label)
    return path


def run(argv, ok=(0,), timeout=60):
    proc = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                          env={"PATH":"/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C.UTF-8","LC_ALL":"C.UTF-8"}, timeout=timeout, check=False)
    if proc.returncode not in ok:
        raise RuntimeError("command failed rc=%d: %s" % (proc.returncode, argv[0]))
    return proc.returncode, proc.stdout.strip()


def same_inode(source: str, target: str) -> bool:
    try:
        s = os.stat(source)
        t = os.stat(target)
    except OSError:
        return False
    return s.st_dev == t.st_dev and s.st_ino == t.st_ino


def fstab_update(source: str, target: str, present: bool) -> bool:
    path = "/etc/fstab"
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode) or st.st_mode & 0o022:
        raise RuntimeError("unsafe /etc/fstab")
    with open(path, "r", encoding="utf-8") as handle:
        old = handle.read()
    expected = "%s %s none bind,nofail,x-systemd.requires-mounts-for=%s 0 0" % (source, target, source)
    lines = []
    found = False
    changed = False
    for line in old.splitlines():
        fields = line.split()
        if len(fields) >= 2 and fields[1] == target:
            if present:
                if line.strip() != expected:
                    raise RuntimeError("bind target already owned by different fstab source")
                lines.append(expected)
                found = True
            else:
                if line.strip() != expected:
                    raise RuntimeError("refusing to remove foreign fstab entry for bind target")
                changed = True
            continue
        lines.append(line)
    if present and not found:
        lines.append(expected)
        changed = True
    if not changed:
        return False
    payload = "\n".join(lines).rstrip("\n") + "\n"
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".layersentry-fstab-", dir=directory)
    try:
        os.fchmod(fd, 0o644)
        os.write(fd, payload.encode("utf-8"))
        os.fsync(fd)
        os.close(fd); fd = -1
        os.replace(tmp, path)
        dfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    finally:
        if fd >= 0: os.close(fd)
        if os.path.exists(tmp): os.unlink(tmp)
    return True


def main():
    module = AnsibleModule(argument_spec=dict(source=dict(type="str", required=True), target=dict(type="str", required=True), state=dict(type="str", choices=["present","absent"], default="present")), supports_check_mode=False)
    try:
        source = validate_path(module.params["source"], SOURCE_ROOTS, "bind source")
        target = validate_path(module.params["target"], TARGET_ROOTS, "bind target")
        state = module.params["state"]
        sfi = os.lstat(source)
        if sfi.st_mode & stat.S_IFMT(sfi.st_mode) == stat.S_IFLNK or not stat.S_ISDIR(sfi.st_mode):
            raise RuntimeError("bind source must be a real directory")
        os.makedirs(target, mode=0o750, exist_ok=True)
        tfi = os.lstat(target)
        if stat.S_ISLNK(tfi.st_mode) or not stat.S_ISDIR(tfi.st_mode):
            raise RuntimeError("bind target must be a real directory")
        changed = False
        rc, _ = run(["/usr/bin/mountpoint", "-q", target], ok=(0,1))
        mounted = rc == 0
        if state == "present":
            if mounted and not same_inode(source, target):
                raise RuntimeError("bind target is already mounted from a different source")
            if fstab_update(source, target, True): changed = True
            if not mounted:
                run(["/usr/bin/mount", "--bind", source, target])
                changed = True
            if not same_inode(source, target):
                raise RuntimeError("bind mount identity verification failed")
        else:
            if mounted:
                if not same_inode(source, target):
                    raise RuntimeError("refusing to unmount foreign bind target")
                run(["/usr/bin/umount", target])
                changed = True
            if fstab_update(source, target, False): changed = True
        module.exit_json(changed=changed)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        module.fail_json(msg=str(exc))

if __name__ == "__main__":
    main()
