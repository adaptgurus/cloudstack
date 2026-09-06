#!/usr/bin/env python3
"""LayerSentry operator DC/DR replication CLI. Source status: NOT_TESTED.

No command is a deployment instruction. Mutations require --execute and enabled
operator configuration. CloudStack still owns VM import, networking and startup.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
from pathlib import Path

from dr_file_replication import FileCatalog, FilePlan, QcowTools, absolute_path, secure_root
from dr_libvirt_capture import FileReplicationEngine
from dr_replication import Repository, ReplicationError, fingerprint, identifier, read_json, require
from dr_replication_transport import MountedTransport, SshTransport, receive_one, write_frame


def configuration(path: str) -> tuple[dict, FilePlan]:
    config_path = absolute_path(path)
    with secure_root(config_path.parent, private=False) as parent:
        value = read_json(parent, config_path.name)
    require(value.get("schema") == 1 and type(value.get("enabled")) is bool, "INVALID_CONFIGURATION_SCHEMA")
    plan = FilePlan.from_dict(value.get("plan"))
    plan.validate()
    return value, plan


def catalog(config: dict, plan: FilePlan) -> FileCatalog:
    require(config.get("role") == "receiver" and set(config) == {
        "schema", "enabled", "role", "plan", "destination_root", "allowed_scope_sha256", "qemu_img",
    }, "INVALID_RECEIVER_CONFIGURATION")
    require(config["allowed_scope_sha256"] == fingerprint(plan.scope()), "PINNED_RECEIVER_SCOPE_REQUIRED")
    return FileCatalog(Repository(absolute_path(config["destination_root"]), plan.recovery_site_id, plan.repository_id), plan)


def source(config: dict, plan: FilePlan) -> FileReplicationEngine:
    require(config.get("role") == "source" and set(config) == {
        "schema", "enabled", "role", "plan", "state_root", "capture_root", "qemu_uid", "qemu_gid", "qemu_img", "transport",
    }, "INVALID_SOURCE_CONFIGURATION")
    target = config["transport"]
    require(isinstance(target, dict), "INVALID_TRANSPORT_CONFIGURATION")
    if target.get("kind") == "mounted":
        require(set(target) == {"kind", "destination_root"}, "INVALID_TRANSPORT_CONFIGURATION")
        replica = FileCatalog(Repository(absolute_path(target["destination_root"]), plan.recovery_site_id, plan.repository_id), plan)
        transport = MountedTransport(replica)
    else:
        require(target.get("kind") == "ssh" and set(target) == {
            "kind", "host", "user", "port", "identity_file", "known_hosts",
        }, "INVALID_TRANSPORT_CONFIGURATION")
        transport = SshTransport(plan, host=target["host"], user=target["user"], port=target["port"],
                                 identity_file=absolute_path(target["identity_file"]), known_hosts=absolute_path(target["known_hosts"]))
    return FileReplicationEngine(plan, absolute_path(config["state_root"]), absolute_path(config["capture_root"]), transport,
                                 qemu_uid=config["qemu_uid"], qemu_gid=config["qemu_gid"], qemu_img=absolute_path(config["qemu_img"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("inspect", "status", "capture", "resume", "tick", "abandon",
                                             "receive", "list", "verify", "materialize", "retention", "retire"))
    parser.add_argument("--config", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--epoch")
    parser.add_argument("--mode", choices=("AUTO", "FULL", "INCREMENTAL"), default="AUTO")
    parser.add_argument("--output-root")
    parser.add_argument("--catalog-sha256")
    parser.add_argument("--pin", action="append", default=[])
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    receiver = args.command == "receive"
    try:
        config, plan = configuration(args.config)
        mutating = args.command in {"capture", "resume", "tick", "abandon", "receive", "materialize", "retire"}
        require(not mutating or (args.execute and config["enabled"]), "EXPLICIT_EXECUTION_AND_ENABLED_CONFIG_REQUIRED")
        if args.command in {"capture", "resume", "abandon", "verify", "materialize"}:
            require(args.epoch is not None, "EXPLICIT_EPOCH_REQUIRED")
            identifier(args.epoch)
        if receiver:
            def expired(_number, _frame):
                raise ReplicationError("RECEIVER_DEADLINE_EXCEEDED")
            signal.signal(signal.SIGALRM, expired)
            signal.setitimer(signal.ITIMER_REAL, plan.transfer_timeout)
            receive_one(catalog(config, plan), sys.stdin.buffer, sys.stdout.buffer)
            signal.setitimer(signal.ITIMER_REAL, 0)
            return 0
        if args.command == "inspect":
            # Offline configuration identity only; no provider inspection/claim.
            result = {"scope_sha256": fingerprint(plan.scope()), "enabled": config["enabled"],
                      "plan_id": plan.plan_id, "source_status": "NOT_TESTED"}
        elif args.command in {"status", "capture", "resume", "tick", "abandon"}:
            engine = source(config, plan)
            if args.command == "status":
                result = engine.status()
            elif args.command == "tick":
                result = engine.tick()
            elif args.command == "abandon":
                result = engine.abandon(args.epoch)
            else:
                result = engine.replicate(args.epoch, mode=args.mode, allow_capture=args.command == "capture")
        else:
            replica = catalog(config, plan)
            if args.command == "list":
                result = replica.listing(offset=args.offset, limit=args.limit)
            elif args.command == "verify":
                result = replica.verify(args.epoch)
            elif args.command == "materialize":
                require(args.output_root is not None, "PRIVATE_RESTORE_ROOT_REQUIRED")
                result = replica.materialize(args.epoch, absolute_path(args.output_root),
                                             QcowTools(absolute_path(config["qemu_img"]), plan.qemu_version))
            elif args.command == "retention":
                result = replica.retention(pinned=tuple(args.pin))
            else:
                require(args.catalog_sha256 is not None, "EXPLICIT_CATALOG_DIGEST_REQUIRED")
                result = replica.retire(args.catalog_sha256, pinned=tuple(args.pin))
        print(json.dumps(result, sort_keys=True))
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, ReplicationError) else "INVALID_INPUT_OR_PROVIDER_IO"
        result = {"state": "ERROR", "reason": code, "verification": "NOT_TESTED"}
        if receiver:
            signal.setitimer(signal.ITIMER_REAL, 0)
            try:
                write_frame(sys.stdout.buffer, result)
            except (OSError, ReplicationError):
                pass
        else:
            print(json.dumps(result, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
