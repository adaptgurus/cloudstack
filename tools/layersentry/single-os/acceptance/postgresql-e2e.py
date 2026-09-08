#!/usr/bin/python3
# Copyright 2026 LayerSentry contributors
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import argparse
import http.cookiejar
import ipaddress
import json
import os
import secrets
import ssl
import stat
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DEFAULT_STATE = "/root/layersentry-postgresql-acceptance-state.json"


def fail(msg: str) -> None:
    raise RuntimeError(msg)


def run(argv, ok=(0,), timeout=120) -> str:
    p = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, check=False, timeout=timeout,
                       env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"})
    if p.returncode not in ok:
        fail("command failed rc=%d exe=%s" % (p.returncode, argv[0]))
    return p.stdout.strip()


def ancestry(device: str) -> set[str]:
    p = subprocess.run(["/usr/bin/lsblk", "-s", "-nrpo", "PATH", device], stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False, timeout=30)
    if p.returncode != 0:
        fail("cannot prove block-device ancestry for %s" % device)
    out: set[str] = set()
    for raw in p.stdout.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        real = os.path.realpath(raw)
        if real:
            out.add(real)
    if not out:
        fail("empty block-device ancestry for %s" % device)
    return out


def block_type(device: str) -> str:
    values = [line.strip() for line in run(["/usr/bin/lsblk", "-dnro", "TYPE", device]).splitlines() if line.strip()]
    if len(values) != 1:
        fail("cannot prove block-device type for %s" % device)
    return values[0]


def validate_data_device(path: str) -> None:
    if not path.startswith("/dev/disk/by-") or os.path.normpath(path) != path:
        fail("acceptance device must use a canonical /dev/disk/by-* identity")
    real = os.path.realpath(path)
    st = os.stat(real)
    if not stat.S_ISBLK(st.st_mode):
        fail("acceptance device is not a block device")
    if block_type(real) != "disk":
        fail("acceptance device must resolve to a whole disk")
    rows = [line.strip() for line in run(["/usr/bin/lsblk", "-nrpo", "PATH", real]).splitlines() if line.strip()]
    if rows != [real]:
        fail("acceptance device must be an unpartitioned whole disk")
    root = run(["/usr/bin/findmnt", "-nro", "SOURCE", "/"])
    if ancestry(root).intersection(ancestry(real)):
        fail("refusing OS/root/root-parent device")
    if subprocess.run(["/usr/bin/findmnt", "-rn", "-S", real], stdin=subprocess.DEVNULL,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=30).returncode == 0:
        fail("acceptance device is mounted")
    wipe = subprocess.run(["/usr/sbin/wipefs", "-n", real], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, check=False, timeout=30)
    if wipe.returncode != 0:
        fail("cannot inspect acceptance-device signatures")
    if wipe.stdout.strip():
        fail("acceptance device contains an existing filesystem/partition/LVM signature")
    pv = subprocess.run(["/usr/sbin/pvs", "--noheadings", "-o", "pv_name", real], stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False, timeout=30)
    if pv.returncode == 0 and pv.stdout.strip():
        fail("acceptance device is already an LVM PV")
    if pv.returncode not in (0, 5):
        fail("cannot prove acceptance device is outside LVM")
    holders = Path("/sys/class/block") / os.path.basename(real) / "holders"
    if not holders.is_dir():
        fail("cannot inspect acceptance-device holders")
    if any(holders.iterdir()):
        fail("acceptance device has active kernel holders")


def parse_size(value: str) -> int:
    if len(value) < 2 or value[-1] not in "MGT" or not value[:-1].isdigit() or int(value[:-1]) <= 0:
        fail("LVM acceptance sizes must use positive integer M/G/T values")
    return int(value[:-1]) * {"M": 1 << 20, "G": 1 << 30, "T": 1 << 40}[value[-1]]


class API:
    def __init__(self, host: str, admin_password: str):
        ipaddress.ip_address(host)
        cert = "/var/lib/layersentryd/identity/tls.crt"
        if not os.path.isfile(cert):
            fail("LayerSentry TLS certificate missing")
        ctx = ssl.create_default_context(cafile=cert)
        self.base = "https://%s:9443" % ("[%s]" % host if ":" in host else host)
        self.origin = self.base
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar), urllib.request.HTTPSHandler(context=ctx))
        self.csrf = ""
        self.admin_password = admin_password

    def request(self, method: str, path: str, body=None, mutation=False, expected=(200,)):
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if mutation:
            headers["X-CSRF-Token"] = self.csrf
            headers["Origin"] = self.origin
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=1300) as resp:
                payload = resp.read(4 << 20)
                if resp.status not in expected:
                    fail("unexpected HTTP status %d for %s" % (resp.status, path))
                return json.loads(payload or b"{}")
        except urllib.error.HTTPError as exc:
            detail = exc.read(8192).decode("utf-8", errors="replace").strip()
            fail("HTTP %d for %s: %s" % (exc.code, path, detail))

    def ensure_admin(self) -> None:
        def login() -> None:
            result = self.request("POST", "/api/v1/auth/login", {"username": "acceptance", "password": self.admin_password})
            self.csrf = result.get("csrf_token", "")
            if len(self.csrf) < 16:
                fail("login did not return CSRF proof")

        try:
            login()
            return
        except RuntimeError as login_error:
            token_path = "/var/lib/layersentryd/identity/bootstrap-token"
            if not os.path.isfile(token_path):
                raise login_error
            token = Path(token_path).read_text(encoding="utf-8").strip()
            if not token:
                raise login_error

        self.request("POST", "/api/v1/auth/bootstrap", {"token": token, "username": "acceptance", "password": self.admin_password}, expected=(201,))
        login()


def action(api: API, service_id: str, name: str, **extra):
    body = {"operation_id": str(uuid.uuid4()), "idempotency_key": str(uuid.uuid4())}
    body.update(extra)
    result = api.request("POST", "/api/v1/services/%s/%s" % (service_id, name), body, mutation=True)
    if result.get("status") != "SUCCEEDED":
        fail("%s did not succeed: %s" % (name, result.get("status")))
    return result


def sql(major: str, database: str, statement: str) -> str:
    return run(["/usr/sbin/runuser", "-u", "postgres", "--", "/usr/pgsql-%s/bin/psql" % major,
                "-XAtq", "-d", database, "-v", "ON_ERROR_STOP=1", "-c", statement], timeout=120)


def write_state(path: str, state: dict) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if os.path.lexists(path) and os.path.islink(path):
        fail("refusing symlink acceptance state")
    fd = os.open(path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, (json.dumps(state, sort_keys=True, indent=2) + "\n").encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def read_state(path: str) -> dict:
    fi = os.lstat(path)
    if stat.S_ISLNK(fi.st_mode) or not stat.S_ISREG(fi.st_mode) or fi.st_mode & 0o077 or fi.st_size > 1 << 20:
        fail("unsafe acceptance state file")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def phase_install(args, api: API) -> None:
    validate_data_device(args.device)
    requested = parse_size(args.data_size) + parse_size(args.wal_size) + parse_size(args.log_size)
    real = os.path.realpath(args.device)
    capacity = int(run(["/usr/bin/lsblk", "-bnro", "SIZE", real]).splitlines()[0])
    if requested + (512 << 20) >= capacity:
        fail("requested LVs plus safety margin do not fit selected device")

    secret_result = api.request("POST", "/api/v1/secrets", {"value": os.environ["LAYERSENTRY_ACCEPTANCE_DB_PASSWORD"]}, mutation=True, expected=(201,))
    secret_ref = secret_result.get("ref", "")
    if not secret_ref.startswith("secret://"):
        fail("secret store did not return canonical reference")

    request_id = str(uuid.uuid4()); service_id = str(uuid.uuid4()); operation_id = str(uuid.uuid4())
    lvs = [
        {"name": "ls_pgdata", "size": args.data_size, "mount_point": "/data/postgresql", "purpose": "database-data", "filesystem": "xfs", "format": True, "confirm_format": True},
        {"name": "ls_pgwal", "size": args.wal_size, "mount_point": "/data/postgresql-wal", "purpose": "database-wal", "filesystem": "xfs", "format": True, "confirm_format": True},
        {"name": "ls_pglogs", "size": args.log_size, "mount_point": "/data/postgresql-logs", "purpose": "database-logs", "filesystem": "xfs", "format": True, "confirm_format": True},
    ]
    req = {
        "schema_version": 1,
        "request_id": request_id,
        "service_id": service_id,
        "operation_id": operation_id,
        "idempotency_key": str(uuid.uuid4()),
        "category": "database",
        "provider": "postgresql",
        "release_line": args.release,
        "topology": "standalone",
        "lvm": [{"name": "ls_pg", "devices": [args.device], "initialize_pvs": True, "confirm_pv_initialize": True, "logical_volumes": lvs}],
        "network": {"listen_address": args.listen_address, "port": 5432, "allowed_cidrs": [args.allowed_cidr]},
        "maintenance": {"mode": "manual", "auto_patch": False, "release_line_locked": True},
        "backup": {"enabled": True, "schedule": "daily", "retention": 3},
        "secret_refs": {"admin_password": secret_ref},
    }
    planned = api.request("POST", "/api/v1/plans", req, mutation=True, expected=(201,))
    plan = planned.get("plan") or {}
    digest = plan.get("digest", "")
    if len(digest) != 64:
        fail("immutable plan digest missing")
    install_body = {"request": req, "confirmed_plan_digest": digest}
    installed = api.request("POST", "/api/v1/services/%s/install" % service_id, install_body, mutation=True)
    if installed.get("status") != "SUCCEEDED":
        fail("install did not succeed")
    replayed = api.request("POST", "/api/v1/services/%s/install" % service_id, install_body, mutation=True)
    if replayed.get("status") != "SUCCEEDED" or replayed.get("id") != installed.get("id") or replayed.get("id") != operation_id:
        fail("successful install replay was not idempotent")
    health = api.request("GET", "/api/v1/services/%s/health" % service_id)
    if not health.get("healthy"):
        fail("PostgreSQL health failed after install/idempotent replay")

    marker = secrets.token_hex(16)
    sql(args.release, "postgres", "DROP DATABASE IF EXISTS layersentry_acceptance")
    sql(args.release, "postgres", "CREATE DATABASE layersentry_acceptance")
    sql(args.release, "layersentry_acceptance", "CREATE TABLE marker(value text NOT NULL)")
    sql(args.release, "layersentry_acceptance", "INSERT INTO marker(value) VALUES ('%s')" % marker)

    action(api, service_id, "backup")
    backups = api.request("GET", "/api/v1/services/%s/backups" % service_id).get("backups", [])
    if not backups:
        fail("backup catalog is empty")
    backup = backups[0]
    if not backup.get("verified") or not backup.get("sha256"):
        fail("backup catalog record is not verified")
    sql(args.release, "layersentry_acceptance", "UPDATE marker SET value='mutated-after-backup'")
    action(api, service_id, "restore", backup_id=backup["id"], confirmed_backup_sha256=backup["sha256"])
    observed = sql(args.release, "layersentry_acceptance", "SELECT value FROM marker")
    if observed != marker:
        fail("restored SQL marker mismatch")
    action(api, service_id, "restart")

    write_state(args.state_file, {
        "schema": 1, "service_id": service_id, "release": args.release, "device": args.device,
        "marker": marker, "data_mount": "/data/postgresql", "wal_mount": "/data/postgresql-wal",
        "log_mount": "/data/postgresql-logs", "secret_ref": secret_ref,
    })
    print("POSTGRESQL_PHASE1_OK service_id=%s state_file=%s idempotent_replay=pass next=actual_vm_reboot_then_post-reboot" % (service_id, args.state_file))


def phase_post_reboot(args, api: API) -> None:
    state = read_state(args.state_file)
    service_id = state["service_id"]; release = state["release"]
    health = api.request("GET", "/api/v1/services/%s/health" % service_id)
    if not health.get("healthy"):
        fail("PostgreSQL health failed after real VM reboot")
    for mount in (state["data_mount"], state["wal_mount"], state["log_mount"]):
        run(["/usr/bin/mountpoint", "-q", mount])
    observed = sql(release, "layersentry_acceptance", "SELECT value FROM marker")
    if observed != state["marker"]:
        fail("database marker changed across reboot")
    action(api, service_id, "repair")
    action(api, service_id, "upgrade")
    observed = sql(release, "layersentry_acceptance", "SELECT value FROM marker")
    if observed != state["marker"]:
        fail("database marker changed across repair/upgrade")
    action(api, service_id, "restart")
    action(api, service_id, "uninstall")
    if subprocess.run(["/usr/bin/rpm", "-q", "postgresql%s-server" % release], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
        fail("PostgreSQL server RPM residue remains after uninstall")
    for mount in (state["data_mount"], state["wal_mount"], state["log_mount"]):
        run(["/usr/bin/mountpoint", "-q", mount])
    pg_version = Path(state["data_mount"]) / "data" / "PG_VERSION"
    if not pg_version.is_file():
        fail("customer PostgreSQL data was not preserved after uninstall")
    print("POSTGRESQL_PHASE2_OK service_id=%s reboot_recovery=pass repair=pass upgrade=pass uninstall_residue=pass data_preserved=pass" % service_id)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["install", "post-reboot"])
    parser.add_argument("--api-host", required=True)
    parser.add_argument("--state-file", default=DEFAULT_STATE)
    parser.add_argument("--device")
    parser.add_argument("--listen-address")
    parser.add_argument("--allowed-cidr")
    parser.add_argument("--release", choices=["16", "17"], default="17")
    parser.add_argument("--data-size", default="8G")
    parser.add_argument("--wal-size", default="2G")
    parser.add_argument("--log-size", default="1G")
    args = parser.parse_args()
    admin = os.environ.get("LAYERSENTRY_ACCEPTANCE_ADMIN_PASSWORD", "")
    if len(admin) < 12:
        fail("LAYERSENTRY_ACCEPTANCE_ADMIN_PASSWORD must be supplied at runtime and at least 12 characters")
    if args.phase == "install":
        dbpw = os.environ.get("LAYERSENTRY_ACCEPTANCE_DB_PASSWORD", "")
        if len(dbpw) < 12:
            fail("LAYERSENTRY_ACCEPTANCE_DB_PASSWORD must be supplied at runtime and at least 12 characters")
        if not args.device or not args.listen_address or not args.allowed_cidr:
            fail("install phase requires --device, --listen-address and --allowed-cidr")
        ipaddress.ip_address(args.listen_address); ipaddress.ip_network(args.allowed_cidr, strict=False)
    api = API(args.api_host, admin)
    api.ensure_admin()
    if args.phase == "install": phase_install(args, api)
    else: phase_post_reboot(args, api)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("POSTGRESQL_ACCEPTANCE_FAIL %s" % exc, file=sys.stderr)
        raise SystemExit(1)
