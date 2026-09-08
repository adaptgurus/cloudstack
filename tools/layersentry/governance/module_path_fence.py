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

"""Fail closed when a module-writing commit crosses its owned file fence.

The checker is intentionally commit-aware. A push may contain unrelated commits
from multiple serialized module writers, but a *single commit* that touches the
K8s ownership surface may contain only K8s-owned paths.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable, Sequence

ZERO_SHA = "0" * 40


@dataclass(frozen=True)
class Fence:
    trigger_prefixes: tuple[str, ...]
    allowed_prefixes: tuple[str, ...]


# Start with the active/highest-risk source writer. Add another module only
# after its shared-file ownership can be represented without over-broad paths.
FENCES: dict[str, Fence] = {
    "k8s": Fence(
        trigger_prefixes=(
            "tools/layersentry/k8s/",
            "docs/layersentry/evidence/k8s/",
            ".github/workflows/layersentry-k8s-",
        ),
        allowed_prefixes=(
            "tools/layersentry/k8s/",
            "docs/layersentry/evidence/k8s/",
            ".github/workflows/layersentry-k8s-",
        ),
    ),
}


def normalize_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    if not value:
        raise ValueError("empty changed path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe changed path: {value}")
    normalized = path.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def matches_any(path: str, prefixes: Sequence[str]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def foreign_paths(module: str, changed_paths: Iterable[str]) -> list[str]:
    fence = FENCES[module]
    paths = [normalize_path(path) for path in changed_paths]
    if not any(matches_any(path, fence.trigger_prefixes) for path in paths):
        return []
    return sorted(path for path in paths if not matches_any(path, fence.allowed_prefixes))


def git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def commit_paths(commit: str) -> list[str]:
    parents = git("rev-list", "--parents", "-n", "1", commit).strip().split()
    if not parents:
        raise RuntimeError(f"cannot resolve commit {commit}")
    if len(parents) == 1:
        output = git("ls-tree", "-r", "--name-only", commit)
    else:
        output = git("diff", "--name-only", f"{parents[1]}..{commit}")
    return [line for line in output.splitlines() if line.strip()]


def commits_for_range(base: str, head: str) -> list[str]:
    if not head:
        raise ValueError("head SHA is required")
    if not base or base == ZERO_SHA:
        return [head]
    output = git("rev-list", "--reverse", f"{base}..{head}")
    commits = [line.strip() for line in output.splitlines() if line.strip()]
    return commits or [head]


def check_range(module: str, base: str, head: str) -> int:
    failures: list[tuple[str, list[str]]] = []
    checked = 0
    for commit in commits_for_range(base, head):
        paths = commit_paths(commit)
        if not any(matches_any(normalize_path(path), FENCES[module].trigger_prefixes) for path in paths):
            continue
        checked += 1
        foreign = foreign_paths(module, paths)
        if foreign:
            failures.append((commit, foreign))

    if failures:
        for commit, paths in failures:
            print(f"FOREIGN_MODULE_EDIT module={module} commit={commit}", file=sys.stderr)
            for path in paths:
                print(f"  forbidden_path={path}", file=sys.stderr)
        return 2

    print(f"MODULE_PATH_FENCE_OK module={module} commits_checked={checked} head={head}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--module", choices=sorted(FENCES), required=True)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return check_range(args.module, args.base, args.head)
    except (RuntimeError, ValueError) as exc:
        print(f"MODULE_PATH_FENCE_ERROR module={args.module}: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
