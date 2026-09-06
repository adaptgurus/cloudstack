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

import argparse
import json
import sys

from controller.components import load_release_contract
from controller.model import InvalidRequestError
from controller.runtime import build_runtime, load_runtime_config


def main() -> int:
    parser = argparse.ArgumentParser(description="LayerSentry Kubernetes controller runtime")
    parser.add_argument("--config", required=True, help="absolute runtime JSON path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check-config")
    reconcile = subparsers.add_parser("reconcile")
    reconcile.add_argument("--max-operations", type=int, default=20)
    args = parser.parse_args()
    try:
        if args.command == "check-config":
            config = load_runtime_config(args.config)
            contract = load_release_contract(config.release_manifest)
            print(json.dumps({
                "status": "READY" if contract.readiness.deployable else "BLOCKED",
                "blockers": list(contract.readiness.blockers),
            }, sort_keys=True))
            return 0 if contract.readiness.deployable else 2
        runtime = build_runtime(args.config)
        print(json.dumps(runtime.reconcile_batch(args.max_operations), sort_keys=True))
        return 0
    except (InvalidRequestError, ValueError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
