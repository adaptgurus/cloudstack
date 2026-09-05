#!/usr/bin/env python3
"""Convert runner observations into bounded, body-free RBAC evidence.

The browser/API adapter owns authentication and writes observations to stdin.
This process never accepts credentials, cookies, API keys, or secret-bearing
configuration. It evaluates the matrix and persists only hashes and outcomes.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sys
from typing import Any

from validate_rbac_matrix import MatrixError, validate_matrix

MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_BODY_CHARS = 1024 * 1024
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SECRET_KEY = re.compile(r"(authorization|cookie|password|secret|session|token|apikey|signature)", re.I)
# CloudStack 4.22.1.1 maps PermissionDeniedException during command
# availability checks to ApiErrorCode.UNAUTHORIZED (401). Do not broaden this
# set to parameter/account/resource/internal errors: those do not prove RBAC.
AUTHORIZATION_DENIAL_CODES = {401}


class ObservationError(ValueError):
    pass


def read_bounded_stdin() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ObservationError(f"observation input exceeds {MAX_INPUT_BYTES} bytes")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ObservationError("observation input must be an object")
    return value


def reject_secret_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if SECRET_KEY.search(str(key)):
                raise ObservationError(f"secret-bearing field forbidden at {path}.{key}")
            reject_secret_fields(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_secret_fields(item, f"{path}[{index}]")


def require_int_status(value: Any, test_id: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 100 <= value <= 599:
        raise ObservationError(f"{test_id}: http_status must be an integer from 100 to 599")
    return value


def evaluate_one(test: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    test_id = test["id"]
    status = require_int_status(observed.get("http_status"), test_id)
    body = observed.get("response_body", "")
    if not isinstance(body, str) or len(body) > MAX_BODY_CHARS:
        raise ObservationError(f"{test_id}: response_body must be a bounded string")
    result: dict[str, Any] = {
        "id": test_id,
        "kind": test["kind"],
        "role": test["role"],
        "expected": test["expect"],
        "http_status": status,
        "response_sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
    }

    if test["kind"] == "direct_url":
        accessible = observed.get("route_accessible")
        if not isinstance(accessible, bool):
            raise ObservationError(f"{test_id}: route_accessible boolean is required")
        result["actual"] = "allowed" if accessible else "denied_or_redirected"
        result["passed"] = result["actual"] == test["expect"]
    else:
        error_code = observed.get("cloudstack_error_code")
        if error_code is not None and (
            isinstance(error_code, bool)
            or not isinstance(error_code, (int, str))
            or (isinstance(error_code, str) and (not error_code.isdigit() or len(error_code) > 8))
        ):
            raise ObservationError(f"{test_id}: invalid cloudstack_error_code")
        count = observed.get("result_count")
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
            raise ObservationError(f"{test_id}: result_count must be a non-negative integer")
        normalized_error_code = int(error_code) if error_code is not None else None
        if normalized_error_code in AUTHORIZATION_DENIAL_CODES:
            actual = "api_denied"
        elif normalized_error_code is not None:
            actual = "api_error_non_authorization"
        elif count == 0 and test["kind"] == "api_object":
            actual = "api_denied_or_empty"
        else:
            actual = "api_allowed"
        expected = test["expect"]
        result["actual"] = actual
        result["passed"] = actual == expected or (expected == "api_denied_or_empty" and actual == "api_denied")
        result["cloudstack_error_code"] = normalized_error_code
    return result


def build_evidence(matrix: dict[str, Any], observations: dict[str, Any], requested_status: str) -> dict[str, Any]:
    reject_secret_fields(observations)
    if observations.get("schema_version") != 1 or observations.get("suite_id") != matrix["suite_id"]:
        raise ObservationError("observation schema_version/suite_id does not match matrix")
    source_commit = observations.get("source_commit")
    if not isinstance(source_commit, str) or not SHA_RE.fullmatch(source_commit):
        raise ObservationError("source_commit must be a lowercase 40-character Git SHA")
    target = observations.get("target")
    if not isinstance(target, dict) or set(target) != {"environment", "base_url"}:
        raise ObservationError("target must contain exactly environment and base_url")
    if not all(isinstance(target[key], str) and 0 < len(target[key]) <= 2048 for key in target):
        raise ObservationError("target values must be non-empty strings")
    raw_results = observations.get("results")
    if not isinstance(raw_results, list):
        raise ObservationError("results must be a list")
    by_id: dict[str, dict[str, Any]] = {}
    for result in raw_results:
        if not isinstance(result, dict) or not isinstance(result.get("id"), str):
            raise ObservationError("each observation result requires a string id")
        if result["id"] in by_id:
            raise ObservationError(f"duplicate observation id: {result['id']}")
        by_id[result["id"]] = result
    matrix_ids = {test["id"] for test in matrix["tests"]}
    if set(by_id) != matrix_ids:
        raise ObservationError("observation IDs must exactly match matrix IDs")

    results = [evaluate_one(test, by_id[test["id"]]) for test in matrix["tests"]]
    started = observations.get("started_at")
    finished = observations.get("finished_at")
    parsed_times = []
    for name, value in (("started_at", started), ("finished_at", finished)):
        if not isinstance(value, str):
            raise ObservationError(f"{name} is required")
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise ObservationError(f"{name} must be an ISO-8601 timestamp") from error
        if parsed.tzinfo is None:
            raise ObservationError(f"{name} must include a timezone")
        parsed_times.append(parsed)
    if parsed_times[1] < parsed_times[0]:
        raise ObservationError("finished_at cannot precede started_at")
    return {
        "schema_version": 1,
        "suite_id": matrix["suite_id"],
        "source_commit": source_commit,
        "target": {
            "environment": target["environment"],
            "base_url_sha256": hashlib.sha256(target["base_url"].encode("utf-8")).hexdigest(),
        },
        "started_at": started,
        "finished_at": finished,
        "status": requested_status if all(result["passed"] for result in results) else "PARTIAL",
        "results": results,
        "cleanup": "not_required_read_only",
    }


def write_exclusive(path: pathlib.Path, evidence: dict[str, Any]) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(evidence, stream, indent=2)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--status", required=True, choices=("CI_VERIFIED", "LIVE_VERIFIED"))
    args = parser.parse_args()
    matrix = json.loads(args.matrix.read_text(encoding="utf-8"))
    validate_matrix(matrix)
    evidence = build_evidence(matrix, read_bounded_stdin(), args.status)
    write_exclusive(args.output, evidence)
    print(f"wrote {len(evidence['results'])} body-free results to {args.output}")
    return 0 if evidence["status"] == args.status else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MatrixError, ObservationError, json.JSONDecodeError, OSError) as error:
        print(f"evaluation failed: {error}", file=sys.stderr)
        raise SystemExit(2)
