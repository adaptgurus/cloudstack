#!/usr/bin/env python3
"""Lint LayerSentry RBAC matrices and emit secret-safe NOT_TESTED evidence.

Live execution is intentionally separate: the integration runner must resolve
role credentials and foreign-object fixtures at runtime. This source gate makes
the contract machine-readable without accepting credentials in files or CLI
arguments.
"""

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

ROLES = {"platform_admin", "department_admin", "department_user", "read_only"}
KINDS = {"direct_url", "api", "api_object"}
EXPECTATIONS = {
    "allowed", "api_allowed", "denied_or_redirected", "api_denied",
    "api_denied_or_empty",
}
MUTATING_PREFIXES = (
    "add", "assign", "associate", "attach", "authorize", "create", "delete",
    "deploy", "destroy", "disable", "enable", "expunge", "migrate", "reboot",
    "recover", "remove", "reset", "restart", "restore", "revoke", "start",
    "stop", "update", "upload",
)
SECRET_KEY = re.compile(r"(authorization|cookie|password|secret|session|token)", re.I)
SECRET_VALUE = re.compile(
    r"(?i)(apikey|signature|sessionkey|token|password|secret)=([^&\s]+)"
)


class MatrixError(ValueError):
    pass


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SECRET_KEY.search(str(key)) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return SECRET_VALUE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
    return value


def validate_matrix(matrix: dict[str, Any]) -> None:
    if matrix.get("schema_version") != 1:
        raise MatrixError("schema_version must be 1")
    if not isinstance(matrix.get("suite_id"), str) or not matrix["suite_id"]:
        raise MatrixError("suite_id must be a non-empty string")
    roles = matrix.get("roles")
    if not isinstance(roles, list) or set(roles) != ROLES:
        raise MatrixError("roles must contain the four LayerSentry V1 roles exactly")
    tests = matrix.get("tests")
    if not isinstance(tests, list) or not tests:
        raise MatrixError("tests must be a non-empty list")

    ids: set[str] = set()
    coverage = {(test.get("role"), test.get("kind")) for test in tests if isinstance(test, dict)}
    for index, test in enumerate(tests):
        if not isinstance(test, dict):
            raise MatrixError(f"tests[{index}] must be an object")
        test_id = test.get("id")
        if not isinstance(test_id, str) or not test_id or test_id in ids:
            raise MatrixError(f"tests[{index}].id must be non-empty and unique")
        ids.add(test_id)
        if test.get("role") not in ROLES or test.get("kind") not in KINDS:
            raise MatrixError(f"{test_id}: invalid role or kind")
        if test.get("expect") not in EXPECTATIONS:
            raise MatrixError(f"{test_id}: invalid expectation")
        if test["kind"] == "direct_url":
            path = test.get("path")
            if not isinstance(path, str) or not path.startswith("/") or "://" in path:
                raise MatrixError(f"{test_id}: path must be a relative absolute-path")
        else:
            command = test.get("command")
            if not isinstance(command, str) or not command:
                raise MatrixError(f"{test_id}: API command is required")
            if command.lower().startswith(MUTATING_PREFIXES):
                raise MatrixError(f"{test_id}: mutating API commands are forbidden in the R1 matrix")
            if not isinstance(test.get("params"), dict):
                raise MatrixError(f"{test_id}: params must be an object")

    for role in ROLES - {"platform_admin"}:
        if (role, "direct_url") not in coverage:
            raise MatrixError(f"missing direct_url negative for {role}")
        if not ({(role, "api"), (role, "api_object")} & coverage):
            raise MatrixError(f"missing direct API negative for {role}")
        if (role, "api_object") not in coverage:
            raise MatrixError(f"missing object-ID tampering negative for {role}")
    if not any(test["role"] == "platform_admin" for test in tests):
        raise MatrixError("missing platform_admin positive control")


def git_commit(root: pathlib.Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return result.stdout.strip()


def not_tested_evidence(matrix: dict[str, Any], source_commit: str) -> dict[str, Any]:
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    empty_hash = hashlib.sha256(b"").hexdigest()
    return {
        "schema_version": 1,
        "suite_id": matrix["suite_id"],
        "source_commit": source_commit,
        "target": {"environment": "not-supplied", "base_url_sha256": empty_hash},
        "started_at": now,
        "finished_at": now,
        "status": "NOT_TESTED",
        "results": [
            {
                "id": test["id"], "kind": test["kind"], "role": test["role"],
                "expected": test["expect"], "actual": "not_executed",
                "passed": False, "response_sha256": empty_hash,
            }
            for test in matrix["tests"]
        ],
        "cleanup": "not_required_read_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix", type=pathlib.Path)
    parser.add_argument("--emit-not-tested", type=pathlib.Path)
    args = parser.parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    validate_matrix(matrix)
    if args.emit_not_tested:
        root = pathlib.Path(__file__).resolve().parents[3]
        evidence = redact(not_tested_evidence(matrix, git_commit(root)))
        args.emit_not_tested.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"validated {len(matrix['tests'])} tests in {matrix['suite_id']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MatrixError, json.JSONDecodeError, OSError, subprocess.CalledProcessError) as error:
        print(f"validation failed: {error}", file=sys.stderr)
        raise SystemExit(2)
