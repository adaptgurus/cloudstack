#!/usr/bin/python3
# Copyright 2026 LayerSentry contributors
# Licensed under the Apache License, Version 2.0

from __future__ import annotations

import base64
import os
import subprocess
from ansible.module_utils.basic import AnsibleModule

CLIENTS = {"mysql": "/usr/bin/mysql", "mariadb": "/usr/bin/mariadb"}


def run_bootstrap(provider: str, password_b64: str) -> None:
    try:
        secret = bytearray(base64.b64decode(password_b64, validate=True))
    except Exception as exc:
        raise ValueError("invalid administrator secret encoding") from exc
    try:
        if len(secret) < 12 or len(secret) > 1024:
            raise ValueError("database administrator password length outside 12..1024 bytes")
        secret.decode("utf-8", errors="strict")
        hexpw = bytes(secret).hex()
        sql = (
            "SET @ls_pw = CONVERT(0x%s USING utf8mb4);\n"
            "SET @ls_q = CONCAT(\"CREATE USER IF NOT EXISTS 'layersentry_admin'@'%%' IDENTIFIED BY \" , QUOTE(@ls_pw));\n"
            "PREPARE ls_s FROM @ls_q; EXECUTE ls_s; DEALLOCATE PREPARE ls_s;\n"
            "SET @ls_q = CONCAT(\"ALTER USER 'layersentry_admin'@'%%' IDENTIFIED BY \" , QUOTE(@ls_pw), \" REQUIRE SSL\");\n"
            "PREPARE ls_s FROM @ls_q; EXECUTE ls_s; DEALLOCATE PREPARE ls_s;\n"
            "GRANT ALL PRIVILEGES ON *.* TO 'layersentry_admin'@'%%' WITH GRANT OPTION;\n"
            "FLUSH PRIVILEGES;\n"
        ) % hexpw
        if provider == "mysql":
            sql += "ALTER USER 'root'@'localhost' IDENTIFIED WITH auth_socket;\n"
        env = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        proc = subprocess.run(
            [CLIENTS[provider], "--protocol=socket", "--user=root"],
            input=sql.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, timeout=120, check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError("local database bootstrap failed rc=%d" % proc.returncode)
    finally:
        for i in range(len(secret)):
            secret[i] = 0


def main() -> None:
    module = AnsibleModule(
        argument_spec=dict(
            provider=dict(type="str", required=True, choices=sorted(CLIENTS)),
            password_b64=dict(type="str", required=True, no_log=True),
        ),
        supports_check_mode=False,
        no_log=True,
    )
    try:
        run_bootstrap(module.params["provider"], module.params["password_b64"])
        module.exit_json(changed=True)
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        module.fail_json(msg=str(exc))


if __name__ == "__main__":
    main()
