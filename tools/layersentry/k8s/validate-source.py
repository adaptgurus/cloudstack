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

"""Deterministic source gate for the LayerSentry K8s ownership surface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import py_compile
import re
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
DOWNSTREAM = ROOT / "downstream"
ALLOWED_STATUS = {
    "DESIGN_DEFINED",
    "SOURCE_COMPLETE",
    "CI_VERIFIED",
    "LIVE_VERIFIED",
    "PRODUCTION_CERTIFIED",
    "PARTIAL",
    "PENDING",
    "BLOCKED",
    "UNKNOWN",
    "NOT_TESTED",
}
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ValidationError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if key in obj:
                raise ValidationError(f"duplicate JSON key {key!r} in {path}")
            obj[key] = value
        return obj

    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationError(f"invalid JSON {path}: {exc}") from exc


def validate_python() -> int:
    count = 0
    for path in sorted(ROOT.rglob("*.py")):
        py_compile.compile(str(path), doraise=True)
        count += 1
    return count


def validate_json() -> int:
    count = 0
    for path in sorted(ROOT.rglob("*.json")):
        load_json(path)
        count += 1
    return count


def validate_downstream_manifests() -> int:
    count = 0
    for manifest_path in sorted(DOWNSTREAM.glob("*/manifest.json")):
        manifest = load_json(manifest_path)
        if not isinstance(manifest, dict):
            raise ValidationError(f"manifest must be an object: {manifest_path}")
        if manifest.get("schemaVersion") != "1.0":
            raise ValidationError(f"unsupported manifest schema: {manifest_path}")
        if not isinstance(manifest.get("component"), str) or not manifest["component"].strip():
            raise ValidationError(f"manifest component missing: {manifest_path}")
        repository = manifest.get("upstreamRepository")
        if not isinstance(repository, str) or not repository.startswith("https://github.com/"):
            raise ValidationError(f"upstream repository must be pinned to HTTPS GitHub URL: {manifest_path}")
        commit = manifest.get("upstreamCommit")
        if not isinstance(commit, str) or not SHA40.fullmatch(commit):
            raise ValidationError(f"invalid upstream commit: {manifest_path}")
        patches = manifest.get("patches")
        if not isinstance(patches, list) or not patches:
            raise ValidationError(f"manifest has no patches: {manifest_path}")
        for patch in patches:
            if not isinstance(patch, dict):
                raise ValidationError(f"patch entry must be an object: {manifest_path}")
            rel = patch.get("path")
            expected = patch.get("sha256")
            if not isinstance(rel, str) or Path(rel).name != rel or rel in {".", ".."}:
                raise ValidationError(f"unsafe patch path {rel!r}: {manifest_path}")
            if not isinstance(expected, str) or not SHA256.fullmatch(expected):
                raise ValidationError(f"invalid patch sha256 for {rel!r}: {manifest_path}")
            patch_path = manifest_path.parent / rel
            if not patch_path.is_file():
                raise ValidationError(f"patch missing: {patch_path}")
            actual = hashlib.sha256(patch_path.read_bytes()).hexdigest()
            if actual != expected:
                raise ValidationError(
                    f"patch digest mismatch: {patch_path} expected={expected} actual={actual}"
                )
        status = manifest.get("status")
        if status not in ALLOWED_STATUS:
            raise ValidationError(f"invalid manifest status {status!r}: {manifest_path}")
        count += 1
    if count == 0:
        raise ValidationError("no downstream manifests found")
    return count


def validate_release_candidate() -> None:
    path = ROOT / "release-candidate-lane-b.json"
    data = load_json(path)
    if not isinstance(data, dict):
        raise ValidationError("release candidate must be a JSON object")
    required = {
        "schemaVersion",
        "status",
        "cloudstack",
        "capi",
        "capc",
        "caprke2",
        "rke2",
        "kubernetes",
        "architecture",
        "hardGates",
        "productionRestrictions",
        "sourceOfTruth",
    }
    missing = sorted(required - data.keys())
    if missing:
        raise ValidationError(f"release candidate missing keys: {', '.join(missing)}")
    if data.get("status") not in ALLOWED_STATUS:
        raise ValidationError(f"invalid release candidate status: {data.get('status')!r}")
    hard_gates = data.get("hardGates")
    if not isinstance(hard_gates, dict) or not hard_gates:
        raise ValidationError("release candidate hardGates must be a non-empty object")
    bad_gates = sorted(key for key, value in hard_gates.items() if not isinstance(value, bool))
    if bad_gates:
        raise ValidationError(f"hard gates must be boolean: {', '.join(bad_gates)}")
    architecture = data.get("architecture")
    for key in ("infrastructureOwner", "machineOwner", "rke2Owner", "packageOwner"):
        if not isinstance(architecture, dict) or not architecture.get(key):
            raise ValidationError(f"release candidate architecture missing {key}")
    source_paths = data.get("sourceOfTruth")
    if not isinstance(source_paths, list) or not source_paths:
        raise ValidationError("release candidate sourceOfTruth must be non-empty")
    for rel in source_paths:
        if not isinstance(rel, str) or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValidationError(f"unsafe sourceOfTruth path: {rel!r}")
        if not (REPO / rel).is_file():
            raise ValidationError(f"sourceOfTruth path does not exist: {rel}")


def validate_yaml_if_present() -> int:
    paths = sorted([*ROOT.rglob("*.yml"), *ROOT.rglob("*.yaml")])
    if not paths:
        return 0
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise ValidationError("PyYAML is required because K8s YAML files are present") from exc
    for path in paths:
        try:
            list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except Exception as exc:  # PyYAML exposes multiple parser exception classes.
            raise ValidationError(f"invalid YAML {path}: {exc}") from exc
    return len(paths)


def validate_systemd_units() -> int:
    count = 0
    for path in sorted((ROOT / "systemd").glob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if "\x00" in text:
            raise ValidationError(f"NUL byte in systemd unit: {path}")
        if "[Unit]" not in text:
            raise ValidationError(f"systemd unit missing [Unit]: {path}")
        if path.suffix == ".service":
            if "[Service]" not in text or "ExecStart=" not in text:
                raise ValidationError(f"service missing [Service]/ExecStart: {path}")
            if re.search(r"^ExecStart=.*(?:/bin/(?:ba)?sh\s+-c\b)", text, flags=re.MULTILINE):
                raise ValidationError(f"shell-interpolated ExecStart is forbidden: {path}")
        elif path.suffix == ".timer" and "[Timer]" not in text:
            raise ValidationError(f"timer missing [Timer]: {path}")
        count += 1
    return count


def run_tests() -> None:
    suites = [ROOT, DOWNSTREAM]
    for suite in suites:
        proc = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(suite), "-p", "test_*.py"],
            cwd=str(suite),
            env={**dict(__import__("os").environ), "PYTHONPATH": str(suite)},
            check=False,
        )
        if proc.returncode != 0:
            raise ValidationError(f"unit tests failed under {suite}")


def main() -> int:
    try:
        python_count = validate_python()
        json_count = validate_json()
        manifest_count = validate_downstream_manifests()
        validate_release_candidate()
        yaml_count = validate_yaml_if_present()
        unit_count = validate_systemd_units()
        run_tests()
    except (ValidationError, py_compile.PyCompileError, OSError) as exc:
        print(f"K8S_SOURCE_VALIDATION_FAIL {exc}", file=sys.stderr)
        return 1
    print(
        "K8S_SOURCE_VALIDATION_OK "
        f"python={python_count} json={json_count} manifests={manifest_count} "
        f"yaml={yaml_count} systemd={unit_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
