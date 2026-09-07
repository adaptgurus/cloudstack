#!/usr/bin/python3
# Copyright 2026 LayerSentry contributors
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path


def run(argv):
    p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, timeout=30)
    if p.returncode != 0:
        raise RuntimeError("command failed: %s rc=%d" % (argv[0], p.returncode))
    return p.stdout.strip()


def ancestry(device: str):
    p = subprocess.run(
        ["/usr/bin/lsblk", "-s", "-nrpo", "PATH", device],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
        timeout=30,
    )
    if p.returncode != 0:
        raise RuntimeError("cannot prove block-device ancestry for %s" % device)
    out = []
    for raw in p.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        real = os.path.realpath(raw)
        if real and real not in out:
            out.append(real)
    if not out:
        raise RuntimeError("empty block-device ancestry for %s" % device)
    return out


def device_type(device: str) -> str:
    value = run(["/usr/bin/lsblk", "-dnro", "TYPE", device])
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    if len(lines) != 1:
        raise RuntimeError("cannot prove block-device type for %s" % device)
    return lines[0]


def main():
    root_source = run(["/usr/bin/findmnt", "-nro", "SOURCE", "/"])
    root_anc = set(ancestry(root_source))
    safe = []
    skipped = []
    seen = set()
    byid = Path("/dev/disk/by-id")
    if not byid.is_dir():
        raise RuntimeError("/dev/disk/by-id is required for stable storage acceptance")
    for p in sorted(byid.iterdir()):
        try:
            real = os.path.realpath(str(p))
            if real in seen:
                continue
            st = os.stat(real)
            if not stat.S_ISBLK(st.st_mode):
                continue
            seen.add(real)
            if device_type(real) != "disk":
                continue
            anc = ancestry(real)
            item = {"stable_id": str(p), "real_device": real, "ancestry": anc}
            if real in root_anc or root_anc.intersection(anc):
                item["reason"] = "os-root-ancestry"
                skipped.append(item)
            else:
                safe.append(item)
        except OSError:
            continue
    print(json.dumps({"root_source": root_source, "root_ancestry": sorted(root_anc), "safe_attached_devices": safe, "skipped_os_devices": skipped}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
