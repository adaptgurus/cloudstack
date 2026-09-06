#!/usr/bin/env python3
"""Run all DR integrity checks with mandatory real QEMU and pinned native fixtures."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest


NATIVE_FILES = {
    "dr_recovery_acceptance.py": "085d179822fb94e6bc7e19a0623fb3d127d57bd813df0a6d6965e875657942c3",
    "test_dr_recovery_acceptance.py": "e14b828a4444ece4c8f2d8da14c99b2af21f0215499f63cf1f7840ccc9ff20dc",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary = {"schema": 1, "scope": "LOCAL_DR_INTEGRITY", "runtime_mutation": False,
               "rocky_acceptance": "NOT_TESTED", "python": platform.python_version(),
               "passed": False}
    try:
        native = Path(os.environ["LAYERSENTRY_NATIVE_ACCEPTANCE_DIR"])
        for filename, expected in NATIVE_FILES.items():
            if hashlib.sha256((native / filename).read_bytes()).hexdigest() != expected:
                raise ValueError("native fixture source hash mismatch")
        summary["native_fixture_sha256"] = NATIVE_FILES
        for key in ("LAYERSENTRY_TEST_QEMU_IMG", "LAYERSENTRY_TEST_QEMU_IO"):
            executable = Path(os.environ[key])
            if not executable.is_absolute() or not executable.is_file():
                raise ValueError("explicit real QEMU executable required")
            command = subprocess.run([str(executable), "--version"], check=True, capture_output=True,
                                     text=True, timeout=10)
            summary[key] = {"version": command.stdout.splitlines()[0],
                            "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest()}
        root = Path(__file__).resolve().parents[3]
        summary["source_commit"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True, timeout=10,
        ).stdout.strip()
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent), pattern="test_dr*.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        summary.update(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                       skipped=len(result.skipped), unexpected_successes=len(result.unexpectedSuccesses),
                       expected_failures=len(result.expectedFailures))
        summary["passed"] = (result.wasSuccessful() and result.testsRun >= 39 and not result.skipped
                             and not result.expectedFailures)
    except Exception as error:
        # Test preflight diagnostics contain no caller paths, command output or credentials.
        summary["preflight_error_type"] = type(error).__name__
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
