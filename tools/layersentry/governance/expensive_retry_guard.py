#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Prevent repeated unchanged expensive CI/lab/E2E retries.

State is deliberately local under .git/layersentry-retry-guard and is never
committed. One failed attempt plus one unchanged confirmatory retry is allowed.
A third unchanged expensive attempt is blocked until a material fingerprint
input changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODULES = ("k8s", "single-os", "dr", "bootstrap", "ui")
GATE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_VALUE = 240
BLOCK_EXIT = 4


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def validate_gate(value: str) -> str:
    value = value.strip()
    if not GATE_RE.fullmatch(value):
        raise ValueError("gate must match [A-Za-z0-9][A-Za-z0-9._:-]{0,95}")
    return value


def validate_value(name: str, value: str, *, allow_empty: bool = True) -> str:
    value = value.strip()
    if not value and allow_empty:
        return ""
    if not value:
        raise ValueError(f"{name} must not be empty")
    if len(value) > MAX_VALUE or "\n" in value or "\r" in value:
        raise ValueError(f"{name} must be a single line <= {MAX_VALUE} characters")
    return value


def validate_source_sha(value: str) -> str:
    value = value.strip().lower()
    if not SHA_RE.fullmatch(value):
        raise ValueError("source SHA must be a 40-character lowercase Git SHA")
    return value


def fingerprint(fields: dict[str, str]) -> str:
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def evaluate_retry(prior: dict[str, Any] | None, current_fingerprint: str) -> tuple[bool, str]:
    if not prior:
        return True, "no_prior_failure"
    if prior.get("fingerprint") != current_fingerprint:
        return True, "material_fingerprint_changed"
    attempts = int(prior.get("attempts", 0))
    if attempts < 2:
        return True, "single_confirmatory_retry_available"
    return False, "unchanged_expensive_retry_limit_reached"


def next_failure_state(
    prior: dict[str, Any] | None,
    fields: dict[str, str],
    current_fingerprint: str,
    evidence: str,
) -> dict[str, Any]:
    attempts = 1
    if prior and prior.get("fingerprint") == current_fingerprint:
        attempts = int(prior.get("attempts", 0)) + 1
    return {
        "schemaVersion": "1.0",
        "fingerprint": current_fingerprint,
        "attempts": attempts,
        "fields": fields,
        "evidence": evidence,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }


def state_path(module: str, gate: str) -> Path:
    repo_root = Path(_git("rev-parse", "--show-toplevel"))
    raw_git_dir = Path(_git("rev-parse", "--git-dir"))
    git_dir = raw_git_dir if raw_git_dir.is_absolute() else repo_root / raw_git_dir
    gate_key = hashlib.sha256(gate.encode("utf-8")).hexdigest()[:20]
    return git_dir / "layersentry-retry-guard" / module / f"{gate_key}.json"


def load_state(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read retry state {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid retry state {path}")
    return data


def write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def build_fields(args: argparse.Namespace) -> dict[str, str]:
    source_sha = args.source_sha or _git("rev-parse", "HEAD")
    return {
        "module": args.module,
        "gate": validate_gate(args.gate),
        "sourceSha": validate_source_sha(source_sha),
        "artifactDigest": validate_value("artifact digest", args.artifact_digest),
        "environmentFingerprint": validate_value(
            "environment fingerprint", args.environment_fingerprint
        ),
        "failureSignature": validate_value("failure signature", args.failure_signature),
        "hypothesis": validate_value("hypothesis", args.hypothesis),
    }


def add_fingerprint_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--module", choices=MODULES, required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--source-sha", default="")
    parser.add_argument("--artifact-digest", default="")
    parser.add_argument("--environment-fingerprint", default="")
    parser.add_argument("--failure-signature", default="")
    parser.add_argument("--hypothesis", default="")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Block repeated unchanged expensive LayerSentry retries"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="check whether an expensive retry is allowed")
    add_fingerprint_args(check)

    record = sub.add_parser("record", help="record the result of an expensive attempt")
    add_fingerprint_args(record)
    record.add_argument("--result", choices=("fail", "pass"), required=True)
    record.add_argument("--evidence", default="")

    status = sub.add_parser("status", help="show local retry state for one gate")
    status.add_argument("--module", choices=MODULES, required=True)
    status.add_argument("--gate", required=True)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        gate = validate_gate(args.gate)
        path = state_path(args.module, gate)
        prior = load_state(path)

        if args.command == "status":
            if prior is None:
                print(f"EXPENSIVE_RETRY_STATE module={args.module} gate={gate} state=none")
            else:
                print(json.dumps(prior, indent=2, sort_keys=True))
            return 0

        fields = build_fields(args)
        current = fingerprint(fields)

        if args.command == "check":
            allowed, reason = evaluate_retry(prior, current)
            attempts = int(prior.get("attempts", 0)) if prior else 0
            if allowed:
                print(
                    f"EXPENSIVE_RETRY_ALLOWED module={args.module} gate={gate} "
                    f"reason={reason} prior_attempts={attempts} fingerprint={current}"
                )
                return 0
            print(
                f"UNCHANGED_EXPENSIVE_RETRY_BLOCKED module={args.module} gate={gate} "
                f"reason={reason} prior_attempts={attempts} fingerprint={current}",
                file=sys.stderr,
            )
            print(
                "action=change_source_artifact_environment_or_material_hypothesis_or_record_blocker",
                file=sys.stderr,
            )
            return BLOCK_EXIT

        evidence = validate_value("evidence", args.evidence)
        if args.result == "pass":
            if path.exists():
                path.unlink()
            print(f"EXPENSIVE_RETRY_CLEARED module={args.module} gate={gate} result=pass")
            return 0

        state = next_failure_state(prior, fields, current, evidence)
        write_state(path, state)
        print(
            f"EXPENSIVE_RETRY_RECORDED module={args.module} gate={gate} result=fail "
            f"attempts={state['attempts']} fingerprint={current}"
        )
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"EXPENSIVE_RETRY_GUARD_ERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
