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
    out = []
    cur = os.path.realpath(device)
    for _ in range(32):
        if not cur or cur in out:
            break
        out.append(cur)
        p = subprocess.run(["/usr/bin/lsblk", "-nro", "PKNAME", cur], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False, timeout=10)
        parent = p.stdout.strip()
        if not parent:
            break
        cur = os.path.realpath(parent if parent.startswith("/") else "/dev/" + parent)
    return out


def main():
    root_source = run(["/usr/bin/findmnt", "-nro", "SOURCE", "/"])
    root_anc = set(ancestry(root_source))
    safe = []
    skipped = []
    seen = set()
    byid = Path("/dev/disk/by-id")
    if byid.is_dir():
        for p in sorted(byid.iterdir()):
            try:
                real = os.path.realpath(str(p))
                if real in seen:
                    continue
                st = os.stat(real)
                if not stat.S_ISBLK(st.st_mode):
                    continue
                seen.add(real)
                anc = ancestry(real)
                item = {"stable_id": str(p), "real_device": real, "ancestry": anc}
                if root_anc.intersection(anc):
                    item["reason"] = "os-root-ancestry"
                    skipped.append(item)
                else:
                    safe.append(item)
            except OSError:
                continue
    print(json.dumps({"root_source": root_source, "root_ancestry": sorted(root_anc), "safe_attached_devices": safe, "skipped_os_devices": skipped}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
