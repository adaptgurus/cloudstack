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

"""Read-only POC gate. Never provisions or approves a production cluster."""
import argparse
import json
from pathlib import Path

from controller.capacity import assess_capacity, discover_capacity, plan_cluster
from controller.cloudstack import CloudStackClient, CloudStackResolver
from controller.model import InvalidRequestError, NotFoundError
from controller.runtime import load_runtime_config


def read_object(path):
    with path.open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("oversized input")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("invalid input")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-config", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--host-evidence", type=Path, required=True)
    for key in ("cluster-id", "host-id", "pool-id"):
        parser.add_argument("--" + key, required=True)
    args = parser.parse_args()
    result = {"gate": "LAB_CAPACITY_PREFLIGHT", "decision": "PROVISION_BLOCKED_CAPACITY",
              "reason": "Required API/configuration/host evidence is UNKNOWN", "cluster_create_executed": False}
    try:
        config = load_runtime_config(args.runtime_config)
        resolver = CloudStackResolver(CloudStackClient(config.cloudstack), config.profile)
        resolved, plan = plan_cluster(resolver, read_object(args.request))
        snapshot = discover_capacity(resolver, resolved, args.cluster_id, args.host_id, args.pool_id)
        result.update(assess_capacity(snapshot, plan, read_object(args.host_evidence)))
    except (InvalidRequestError, NotFoundError, OSError, ValueError, TypeError, KeyError):
        # Input and native API exception bodies may contain sensitive data.
        # Diagnostic detail belongs in sanitized source tests, not live receipts.
        pass
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] == "PROVISION_ALLOWED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
