#!/usr/bin/python3
# Copyright 2026 LayerSentry contributors
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import argparse
import json
import os
import pwd
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path


def run(argv, **kw):
    return subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, check=False, timeout=120, **kw)


def block_type(device: str) -> str:
    p = run(["/usr/bin/lsblk", "-dnro", "TYPE", device])
    values = [line.strip() for line in p.stdout.splitlines() if line.strip()]
    if p.returncode != 0 or len(values) != 1:
        raise RuntimeError("cannot prove block-device type for %s" % device)
    return values[0]


def root_top_disk() -> str:
    p = run(["/usr/bin/findmnt", "-nro", "SOURCE", "/"])
    if p.returncode != 0 or not p.stdout.strip():
        raise RuntimeError("cannot discover root source")
    q = run(["/usr/bin/lsblk", "-s", "-nrpo", "PATH", p.stdout.strip()])
    if q.returncode != 0:
        raise RuntimeError("cannot prove root block-device ancestry")
    ancestry = []
    for raw in q.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        real = os.path.realpath(raw)
        if real and real not in ancestry:
            ancestry.append(real)
    if not ancestry:
        raise RuntimeError("root block-device ancestry is empty")
    disks = [device for device in ancestry if block_type(device) == "disk"]
    if len(disks) != 1:
        raise RuntimeError("cannot uniquely prove top whole root disk: found=%d" % len(disks))
    return disks[0]


def stable_id_for(real: str) -> str:
    root = Path("/dev/disk/by-id")
    candidates = []
    for p in root.iterdir():
        try:
            if os.path.realpath(str(p)) == real:
                candidates.append(str(p))
        except OSError:
            pass
    preferred = [p for p in candidates if any(Path(p).name.startswith(x) for x in ("wwn-", "scsi-", "nvme-", "virtio-"))]
    if preferred:
        return sorted(preferred)[0]
    if candidates:
        return sorted(candidates)[0]
    raise RuntimeError("root disk has no /dev/disk/by-id identity; cannot execute product-level root-disk negative safely")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen-address", required=True)
    ap.add_argument("--allowed-cidr", required=True)
    ap.add_argument("--release", choices=["16", "17"], default="17")
    args = ap.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError("root is required for acceptance setup")
    root_disk = root_top_disk()
    sid = stable_id_for(root_disk)
    fi = os.stat(root_disk)
    if not stat.S_ISBLK(fi.st_mode):
        raise RuntimeError("discovered root parent is not a block device")
    req = {
        "schema_version": 1,
        "request_id": str(uuid.uuid4()),
        "service_id": str(uuid.uuid4()),
        "operation_id": str(uuid.uuid4()),
        "idempotency_key": str(uuid.uuid4()),
        "category": "database",
        "provider": "postgresql",
        "release_line": args.release,
        "topology": "standalone",
        "lvm": [{
            "name": "ls_root_negative",
            "devices": [sid],
            "initialize_pvs": True,
            "confirm_pv_initialize": True,
            "logical_volumes": [{"name": "ls_root_negative", "size": "1G", "mount_point": "/data/root-negative", "purpose": "database-data", "filesystem": "xfs", "format": True, "confirm_format": True}],
        }],
        "network": {"listen_address": args.listen_address, "port": 5432, "allowed_cidrs": [args.allowed_cidr]},
        "maintenance": {"mode": "manual", "auto_patch": False, "release_line_locked": True},
        "backup": {"enabled": False},
        "secret_refs": {"admin_password": "secret://00000000000000000000000000000000"},
    }
    layersentry = pwd.getpwnam("layersentry")
    fd, path = tempfile.mkstemp(prefix="root-negative-", suffix=".json", dir="/run/layersentryd")
    try:
        os.fchmod(fd, 0o600); os.fchown(fd, layersentry.pw_uid, layersentry.pw_gid)
        os.write(fd, json.dumps(req, separators=(",", ":")).encode("utf-8")); os.fsync(fd); os.close(fd); fd = -1
        proc = run(["/usr/sbin/runuser", "-u", "layersentry", "--", "/usr/bin/layersentryd", "plan-file", path])
        if proc.returncode == 0:
            raise RuntimeError("CRITICAL: product accepted OS/root disk for destructive LVM plan")
        text = (proc.stdout + "\n" + proc.stderr).lower()
        if "root" not in text and "os/" not in text:
            raise RuntimeError("plan failed, but root-disk rejection was not proven: %s" % text[-1000:])
        print("ROOT_DISK_NEGATIVE_OK stable_id=%s real=%s mutation_started=false" % (sid, root_disk))
    finally:
        if fd >= 0:
            os.close(fd)
        try: os.unlink(path)
        except FileNotFoundError: pass


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ROOT_DISK_NEGATIVE_FAIL %s" % exc, file=os.sys.stderr)
        raise SystemExit(1)
