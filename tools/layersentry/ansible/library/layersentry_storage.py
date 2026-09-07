#!/usr/bin/python3
# Copyright 2026 LayerSentry contributors
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
from typing import Dict, Iterable, List, Set, Tuple

from ansible.module_utils.basic import AnsibleModule

NAME_RE = re.compile(r"^ls_[a-z0-9_]{1,48}$")
SIZE_RE = re.compile(r"^([1-9][0-9]*[MGT]|100%FREE)$")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$")
ALLOWED_PURPOSES = {
    "database-data", "database-wal", "database-logs", "database-backup",
    "application-data", "application-logs", "cache", "temporary",
}
ALLOWED_ROOTS = (
    "/data", "/srv", "/opt/layersentry-data", "/var/lib/pgsql",
    "/var/lib/mysql", "/var/lib/redis", "/var/lib/valkey",
    "/var/lib/layersentryd/apps", "/var/lib/tomcat", "/var/www/html",
    "/var/log/layersentry-services",
)


def run(argv: List[str], ok: Iterable[int] = (0,), timeout: int = 120) -> Tuple[int, str, str]:
    proc = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        timeout=timeout,
        check=False,
    )
    if proc.returncode not in set(ok):
        raise RuntimeError("command failed rc=%d: %s" % (proc.returncode, argv[0]))
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def clean_mount(path: str) -> str:
    if not path or not os.path.isabs(path) or os.path.normpath(path) != path:
        raise ValueError("mount point must be canonical absolute path")
    if not any(path == root or path.startswith(root + os.sep) for root in ALLOWED_ROOTS):
        raise ValueError("mount point is outside approved LayerSentry roots")
    return path


def real_block(device: str, require_by_id: bool = True) -> str:
    if require_by_id and not device.startswith("/dev/disk/by-"):
        raise ValueError("attached device must use /dev/disk/by-* identity")
    real = os.path.realpath(device)
    st = os.stat(real)
    if not stat.S_ISBLK(st.st_mode):
        raise ValueError("storage target is not a block device")
    return real


def ancestry(device: str) -> Set[str]:
    out: Set[str] = set()
    cur = os.path.realpath(device)
    for _ in range(32):
        if not cur or cur in out:
            break
        out.add(cur)
        _, parent, _ = run(["/usr/bin/lsblk", "-nro", "PKNAME", cur], ok=(0, 1))
        parent = parent.strip()
        if not parent:
            break
        if not parent.startswith("/"):
            parent = "/dev/" + parent
        cur = os.path.realpath(parent)
    return out


def root_ancestry() -> Set[str]:
    _, source, _ = run(["/usr/bin/findmnt", "-nro", "SOURCE", "/"])
    if not source:
        raise RuntimeError("cannot determine root filesystem source")
    return ancestry(source)


def reject_os_device(device: str, root_anc: Set[str]) -> str:
    real = real_block(device, True)
    if ancestry(real).intersection(root_anc):
        raise ValueError("refusing OS/root/root-parent device %s" % device)
    return real


def fs_type(device: str) -> str:
    rc, out, _ = run(["/usr/sbin/blkid", "-s", "TYPE", "-o", "value", device], ok=(0, 2))
    return "" if rc == 2 else out.strip()


def fs_uuid(device: str) -> str:
    _, out, _ = run(["/usr/sbin/blkid", "-s", "UUID", "-o", "value", device])
    if not out or any(c.isspace() for c in out) or "/" in out:
        raise RuntimeError("invalid filesystem UUID")
    return out


def ensure_fstab(uuid: str, mount_point: str, filesystem: str) -> bool:
    path = "/etc/fstab"
    st = os.lstat(path)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode) or (st.st_mode & 0o022):
        raise RuntimeError("unsafe /etc/fstab")
    with open(path, "r", encoding="utf-8") as handle:
        old = handle.read()
    line = "UUID=%s %s %s defaults,nofail 0 2" % (uuid, mount_point, filesystem or "auto")
    for existing in old.splitlines():
        fields = existing.split()
        if len(fields) >= 2 and fields[1] == mount_point:
            if existing.strip() == line:
                return False
            raise RuntimeError("fstab mount point already owned by different source")
    directory = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=".layersentry-fstab-", dir=directory)
    try:
        os.fchmod(fd, 0o644)
        payload = old.rstrip("\n") + "\n" + line + "\n"
        os.write(fd, payload.encode("utf-8"))
        os.fsync(fd)
        os.close(fd)
        fd = -1
        os.replace(tmp, path)
        dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
    finally:
        if fd >= 0:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True


def ensure_filesystem_and_mount(device: str, item: Dict, recovery_only: bool) -> bool:
    changed = False
    mount_point = clean_mount(item["mount_point"])
    if item["purpose"] not in ALLOWED_PURPOSES:
        raise ValueError("unsupported storage purpose")
    requested_fs = item.get("filesystem") or "xfs"
    if requested_fs not in ("xfs", "ext4"):
        raise ValueError("unsupported filesystem")
    current_fs = fs_type(device)
    if not current_fs:
        if recovery_only:
            raise RuntimeError("recovery cannot recreate a missing filesystem")
        if not item.get("format") or not item.get("confirm_format"):
            raise RuntimeError("filesystem creation requires explicit format confirmation")
        if requested_fs == "xfs":
            run(["/usr/sbin/mkfs.xfs", "-f", device], timeout=300)
        else:
            run(["/usr/sbin/mkfs.ext4", "-F", device], timeout=300)
        current_fs = requested_fs
        changed = True
    elif current_fs != requested_fs:
        raise RuntimeError("existing filesystem type does not match confirmed plan")
    os.makedirs(mount_point, mode=0o750, exist_ok=True)
    os.chmod(mount_point, 0o750)
    uuid = fs_uuid(device)
    if ensure_fstab(uuid, mount_point, current_fs):
        changed = True
    rc, mounted_uuid, _ = run(["/usr/bin/findmnt", "-nro", "UUID", "--target", mount_point], ok=(0, 1))
    if rc == 0 and mounted_uuid:
        if mounted_uuid.strip() != uuid:
            raise RuntimeError("mount point is mounted from a different filesystem UUID")
    else:
        run(["/usr/bin/mount", mount_point])
        changed = True
    run(["/usr/bin/findmnt", "--verify", "--target", mount_point])
    return changed


def pvs_vg(device: str) -> str:
    rc, out, _ = run(["/usr/sbin/pvs", "--noheadings", "-o", "vg_name", device], ok=(0, 5))
    return "" if rc == 5 else out.strip()


def vg_info(vg: str) -> Tuple[bool, Set[str]]:
    rc, out, _ = run(["/usr/sbin/vgs", "--noheadings", "-o", "vg_tags", vg], ok=(0, 5))
    if rc == 5:
        return False, set()
    return True, {x.strip() for x in out.split(",") if x.strip()}


def lv_info(vg: str, lv: str) -> Tuple[bool, Set[str]]:
    rc, out, _ = run(["/usr/sbin/lvs", "--noheadings", "-o", "lv_tags", "/dev/%s/%s" % (vg, lv)], ok=(0, 5))
    if rc == 5:
        return False, set()
    return True, {x.strip() for x in out.split(",") if x.strip()}


def ensure_lvm(service_id: str, groups: List[Dict], root_anc: Set[str], recovery_only: bool) -> bool:
    changed = False
    tag = "layersentry_" + service_id.replace("-", "").lower()
    for group in groups:
        vg = group.get("name", "")
        if not NAME_RE.fullmatch(vg):
            raise ValueError("LayerSentry volume group must use ls_ prefix")
        devices = group.get("devices") or []
        if not devices:
            raise ValueError("LVM group requires devices")
        for dev in devices:
            reject_os_device(dev, root_anc)
        existed, tags = vg_info(vg)
        if existed:
            if tag not in tags:
                raise RuntimeError("refusing to adopt an existing non-LayerSentry volume group")
        elif recovery_only:
            raise RuntimeError("recovery cannot recreate a missing volume group")
        else:
            for dev in devices:
                current_vg = pvs_vg(dev)
                if not current_vg:
                    if not group.get("initialize_pvs") or not group.get("confirm_pv_initialize"):
                        raise RuntimeError("PV creation requires explicit destructive confirmation")
                    run(["/usr/sbin/pvcreate", "--yes", "--force", "--force", dev], timeout=300)
                    changed = True
                elif current_vg != vg:
                    raise RuntimeError("PV is already assigned to another volume group")
            run(["/usr/sbin/vgcreate", "--addtag", tag, vg] + devices, timeout=300)
            changed = True
        if existed:
            for dev in devices:
                current_vg = pvs_vg(dev)
                if current_vg == vg:
                    continue
                if current_vg:
                    raise RuntimeError("PV is already assigned to another volume group")
                if recovery_only:
                    raise RuntimeError("recovery cannot add a missing PV to a volume group")
                if not group.get("initialize_pvs") or not group.get("confirm_pv_initialize"):
                    raise RuntimeError("new PV requires explicit destructive confirmation")
                run(["/usr/sbin/pvcreate", "--yes", "--force", "--force", dev], timeout=300)
                run(["/usr/sbin/vgextend", vg, dev], timeout=300)
                changed = True
        lvs = group.get("logical_volumes") or []
        free_seen = False
        for index, lv in enumerate(lvs):
            name = lv.get("name", "")
            size = lv.get("size", "")
            if not NAME_RE.fullmatch(name) or not SIZE_RE.fullmatch(size):
                raise ValueError("invalid LayerSentry logical volume name/size")
            if size == "100%FREE":
                if free_seen or index != len(lvs) - 1:
                    raise ValueError("100%FREE may be used once and only by final LV")
                free_seen = True
            lv_existed, lv_tags = lv_info(vg, name)
            if lv_existed and tag not in lv_tags:
                raise RuntimeError("refusing to adopt an existing non-LayerSentry logical volume")
            if not lv_existed:
                if recovery_only:
                    raise RuntimeError("recovery cannot recreate a missing logical volume")
                argv = ["/usr/sbin/lvcreate", "--addtag", tag, "-n", name]
                if size == "100%FREE":
                    argv += ["-l", "100%FREE"]
                else:
                    argv += ["-L", size]
                argv.append(vg)
                run(argv, timeout=300)
                changed = True
            if ensure_filesystem_and_mount("/dev/%s/%s" % (vg, name), lv, recovery_only):
                changed = True
    return changed


def main() -> None:
    module = AnsibleModule(
        argument_spec=dict(
            service_id=dict(type="str", required=True),
            storage=dict(type="list", elements="dict", default=[]),
            lvm=dict(type="list", elements="dict", default=[]),
            recovery_only=dict(type="bool", default=False),
        ),
        supports_check_mode=False,
    )
    service_id = module.params["service_id"]
    if not UUID_RE.fullmatch(service_id):
        module.fail_json(msg="service_id must be a canonical UUID")
    try:
        root_anc = root_ancestry()
        changed = False
        seen: Set[str] = set()
        for item in module.params["storage"]:
            device = item.get("device", "")
            if device in seen:
                raise ValueError("duplicate storage device")
            seen.add(device)
            reject_os_device(device, root_anc)
            if ensure_filesystem_and_mount(device, item, module.params["recovery_only"]):
                changed = True
        for group in module.params["lvm"]:
            for device in group.get("devices") or []:
                if device in seen:
                    raise ValueError("device assigned to both direct storage and LVM")
                seen.add(device)
        if ensure_lvm(service_id, module.params["lvm"], root_anc, module.params["recovery_only"]):
            changed = True
        module.exit_json(changed=changed, root_ancestry=sorted(root_anc))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        module.fail_json(msg=str(exc))


if __name__ == "__main__":
    main()
