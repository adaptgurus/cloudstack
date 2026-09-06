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

"""Fail-closed evaluator for destructive Workstream E0 evidence.

The live runner produces the input report; this module never performs a
CloudStack or Kubernetes mutation. A transport-successful run cannot become
LIVE_VERIFIED unless every required case includes its case-specific evidence.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence


EXPECTED_SOURCE = {
    "cloudstack": "4.22.1.1",
    "capc_commit": "7521b14a31e6c46f81f16aae3738a27c08ad063f",
    "capc_patch_sha256": "6d3fc88ccf986bd025fc6d714ec7b4fa19d0c2afe6f10c50ef02a198286cea74",
    "cloudstack_csi_commit": "a84477e922d62b82387ab55134fafc9c0b5aaf64",
    "cloudstack_csi_patch_sha256": "64853e92e82f4a6e5e298b9d114a1522aea21d04f84c02e1667079c54d4f9635",
}

REQUIRED_CASES = (
    "endpoint-6443-reconcile",
    "endpoint-9345-reconcile",
    "pvc-survives-machine-delete",
    "pvc-survives-rollout",
    "pvc-survives-scale-down",
    "pvc-survives-remediation",
    "nodedisk-retain-replacement",
    "nodedisk-delete-replacement",
    "csi-project-create",
    "csi-cross-project-denied",
    "csi-attach-detach-idempotent",
    "csi-snapshot-restore",
    "csi-expand-idempotent",
    "csi-delete-idempotent",
)

DATA_SURVIVAL_CASES = {
    "pvc-survives-machine-delete",
    "pvc-survives-rollout",
    "pvc-survives-scale-down",
    "pvc-survives-remediation",
    "csi-snapshot-restore",
}
IDEMPOTENCY_CASES = {
    "endpoint-6443-reconcile",
    "endpoint-9345-reconcile",
    "csi-attach-detach-idempotent",
    "csi-expand-idempotent",
    "csi-delete-idempotent",
}
_SECRET_KEY = re.compile(r"(password|secret|token|private.?key|api.?key)", re.IGNORECASE)


class QualificationError(ValueError):
    """The evidence report is incomplete, unsafe or inconsistent."""


def _secret_paths(value: Any, path: str = "$") -> list[str]:
    found = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            child = f"{path}.{key}"
            if _SECRET_KEY.search(str(key)):
                found.append(child)
            found.extend(_secret_paths(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_secret_paths(nested, f"{path}[{index}]"))
    return found


def evaluate(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic status and blockers for one E0 report."""

    blockers: list[str] = []
    leaked = _secret_paths(report)
    if leaked:
        blockers.append("secret-bearing fields are prohibited: " + ", ".join(leaked))

    source = report.get("source")
    if not isinstance(source, Mapping):
        blockers.append("source identity is missing")
    else:
        for key, expected in EXPECTED_SOURCE.items():
            if source.get(key) != expected:
                blockers.append(f"source.{key} does not match the qualified release candidate")

    environment = report.get("environment")
    if not isinstance(environment, Mapping):
        blockers.append("environment identity is missing")
    else:
        if environment.get("os_family") != "Rocky Linux" or environment.get("os_major") != 9:
            blockers.append("destructive qualification must run on Rocky Linux 9")
        for field in ("run_id", "artifact_id", "project_id", "zone_id"):
            if not environment.get(field):
                blockers.append(f"environment.{field} is missing")

    cases = report.get("cases")
    by_id: dict[str, Mapping[str, Any]] = {}
    if not isinstance(cases, Sequence) or isinstance(cases, (str, bytes)):
        blockers.append("cases must be an array")
    else:
        for case in cases:
            if not isinstance(case, Mapping) or not case.get("id"):
                blockers.append("case without an id")
                continue
            case_id = str(case["id"])
            if case_id in by_id:
                blockers.append(f"duplicate case: {case_id}")
                continue
            by_id[case_id] = case

    for case_id in REQUIRED_CASES:
        case = by_id.get(case_id)
        if case is None:
            blockers.append(f"missing case: {case_id}")
            continue
        if case.get("status") != "PASS":
            blockers.append(f"{case_id} is not PASS")
        evidence = case.get("evidence")
        if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item for item in evidence):
            blockers.append(f"{case_id} has no durable evidence references")
        if case_id in DATA_SURVIVAL_CASES:
            before = case.get("data_sha256_before")
            after = case.get("data_sha256_after")
            if not before or before != after:
                blockers.append(f"{case_id} does not prove identical data before/after")
        if case_id in IDEMPOTENCY_CASES:
            if not isinstance(case.get("attempts"), int) or case["attempts"] < 2:
                blockers.append(f"{case_id} requires at least two attempts")
            if not isinstance(case.get("mutations"), int) or case["mutations"] > 1:
                blockers.append(f"{case_id} replayed more than one mutation")

    denied = by_id.get("csi-cross-project-denied")
    if denied is not None and denied.get("actual") != "DENIED":
        blockers.append("csi-cross-project-denied did not fail closed")
    retained = by_id.get("nodedisk-retain-replacement")
    if retained is not None and retained.get("same_volume_id") is not True:
        blockers.append("retained node disk did not preserve its exact volume ID")
    deleted = by_id.get("nodedisk-delete-replacement")
    if deleted is not None and deleted.get("old_volume_absent") is not True:
        blockers.append("delete-policy node disk old volume remains or is unproven")

    return {
        "status": "LIVE_VERIFIED" if not blockers else "NOT_TESTED",
        "qualified": not blockers,
        "blockers": blockers,
        "required_cases": list(REQUIRED_CASES),
    }


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        result = evaluate(report)
    except (OSError, json.JSONDecodeError, QualificationError) as exc:
        result = {"status": "NOT_TESTED", "qualified": False, "blockers": [str(exc)]}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["qualified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
