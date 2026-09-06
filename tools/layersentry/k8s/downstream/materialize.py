#!/usr/bin/env python3
"""Verify and idempotently apply a pinned LayerSentry downstream overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Sequence


class OverlayError(RuntimeError):
    """The source or overlay failed a fail-closed integrity check."""


def _run(argv: Sequence[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            list(argv),
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OverlayError(f"command failed safely: {argv[0]}") from exc
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise OverlayError(f"{argv[0]} exited {result.returncode}: {detail[:500]}")
    return result


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OverlayError("overlay manifest is unreadable or invalid") from exc
    required = {"schemaVersion", "component", "upstreamCommit", "patches"}
    if not required.issubset(manifest) or manifest["schemaVersion"] != "1.0":
        raise OverlayError("unsupported or incomplete overlay manifest")
    if not isinstance(manifest["patches"], list) or not manifest["patches"]:
        raise OverlayError("overlay manifest contains no patches")
    return manifest


def materialize(source: Path, manifest_path: Path, *, apply: bool) -> dict[str, Any]:
    source = source.resolve(strict=True)
    manifest_path = manifest_path.resolve(strict=True)
    manifest = load_manifest(manifest_path)
    # A normal clone stores .git as a directory; an isolated `git worktree`
    # stores it as a control file. Both are valid and rev-parse below remains
    # the authoritative repository check.
    if not (source / ".git").exists():
        raise OverlayError("source directory is not a Git worktree")

    head = _run(("git", "rev-parse", "HEAD"), source).stdout.strip()
    if head != manifest["upstreamCommit"]:
        raise OverlayError(f"source HEAD {head} does not match pinned upstream commit")

    results = []
    for item in manifest["patches"]:
        if not isinstance(item, dict) or set(("path", "sha256")) - set(item):
            raise OverlayError("invalid patch manifest entry")
        patch = (manifest_path.parent / item["path"]).resolve(strict=True)
        if patch.parent != manifest_path.parent:
            raise OverlayError("patch path escapes its manifest directory")
        actual_digest = _sha256(patch)
        if actual_digest != item["sha256"]:
            raise OverlayError(f"patch digest mismatch for {patch.name}")

        forward = _run(("git", "apply", "--check", str(patch)), source, check=False)
        reverse = _run(("git", "apply", "--reverse", "--check", str(patch)), source, check=False)
        if forward.returncode == 0:
            state = "APPLICABLE"
            if apply:
                _run(("git", "apply", str(patch)), source)
                state = "APPLIED"
        elif reverse.returncode == 0:
            state = "ALREADY_APPLIED"
        else:
            raise OverlayError(f"patch {patch.name} is neither applicable nor already applied")
        results.append({"patch": patch.name, "sha256": actual_digest, "state": state})

    return {
        "component": manifest["component"],
        "upstreamCommit": head,
        "mutated": bool(apply and any(item["state"] == "APPLIED" for item in results)),
        "patches": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(materialize(args.source, args.manifest, apply=args.apply), sort_keys=True))
    except OverlayError as exc:
        print(json.dumps({"error": str(exc), "status": "BLOCKED"}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
