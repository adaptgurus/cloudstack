"""Pinned-SSH or mounted-file transport for sealed epochs. Status: NOT_TESTED."""

from __future__ import annotations

import contextlib
import ipaddress
import json
import os
import re
import struct
import subprocess
import threading
from pathlib import Path

from dr_file_replication import FileCatalog, FilePlan, absolute_path, disk_chunks, secure_root
from dr_replication import CHUNK_BYTES, JSON_LIMIT, ReplicationError, canonical, fingerprint, identifier, regular_file, require


# Administrator-installed receiver and configuration. No client-supplied command,
# program path, destination path, URL, shell fragment or provider secret is sent.
REMOTE_COMMAND = "/usr/bin/python3 /opt/layersentry/dr/dr_replication_cli.py receive --config /etc/layersentry/dr/receiver.json --execute"


def read_exact(stream, size: int) -> bytes:
    require(type(size) is int and 0 <= size <= CHUNK_BYTES, "INVALID_FRAME_SIZE")
    output = bytearray()
    while len(output) < size:
        data = stream.read(size - len(output))
        require(bool(data), "TRANSFER_PEER_DISCONNECTED")
        output.extend(data)
    return bytes(output)


def read_frame(stream) -> dict:
    size = struct.unpack(">I", read_exact(stream, 4))[0]
    require(0 < size <= JSON_LIMIT, "PROTOCOL_METADATA_LIMIT")
    try:
        value = json.loads(read_exact(stream, size))
    except (ValueError, UnicodeError):
        raise ReplicationError("INVALID_PROTOCOL_METADATA") from None
    require(isinstance(value, dict), "INVALID_PROTOCOL_METADATA")
    require(value.get("state") != "ERROR", "REMOTE_OPERATION_REFUSED")
    return value


def write_frame(stream, payload: dict) -> None:
    data = canonical(payload)
    require(0 < len(data) <= JSON_LIMIT, "PROTOCOL_METADATA_LIMIT")
    stream.write(struct.pack(">I", len(data)))
    stream.write(data)
    stream.flush()


class MountedTransport:
    def __init__(self, catalog: FileCatalog):
        self.catalog = catalog

    def send(self, manifest: dict, source_folder: int) -> dict:
        return self.catalog.receive_local(manifest, source_folder)

    def verify(self, epoch_id: str) -> dict:
        return self.catalog.verify(epoch_id)


class SshTransport:
    def __init__(self, plan: FilePlan, *, host: str, user: str, port: int,
                 identity_file: Path, known_hosts: Path):
        plan.validate()
        require(isinstance(host, str) and 0 < len(host) <= 253, "INVALID_SSH_HOST")
        try:
            ipaddress.ip_address(host)
        except ValueError:
            require(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host) is not None,
                    "INVALID_SSH_HOST")
        require(isinstance(user, str) and re.fullmatch(r"[a-z_][a-z0-9_-]{0,31}", user) is not None, "INVALID_SSH_USER")
        require(type(port) is int and 1 <= port <= 65535, "INVALID_SSH_PORT")
        self.plan, self.host, self.user, self.port = plan, host, user, port
        self.identity_file, self.known_hosts = identity_file, known_hosts

    @staticmethod
    def _trusted_file(path: Path, *, private: bool) -> None:
        absolute_path(str(path))
        with secure_root(path.parent, private=False) as parent:
            fd = regular_file(parent, path.name)
            try:
                if private:
                    require(not os.fstat(fd).st_mode & 0o077, "PRIVATE_SSH_IDENTITY_REQUIRED")
            finally:
                os.close(fd)

    @contextlib.contextmanager
    def _connection(self):
        self._trusted_file(self.identity_file, private=True)
        self._trusted_file(self.known_hosts, private=False)
        arguments = ["/usr/bin/ssh", "-F", "/dev/null", "-T", "-p", str(self.port),
                     "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                     "-o", "GlobalKnownHostsFile=/dev/null", "-o", "UserKnownHostsFile=" + str(self.known_hosts),
                     "-o", "IdentitiesOnly=yes", "-o", "PasswordAuthentication=no",
                     "-o", "KbdInteractiveAuthentication=no", "-o", "ForwardAgent=no",
                     "-o", "ClearAllForwardings=yes", "-o", "ConnectTimeout=15",
                     "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2",
                     "-i", str(self.identity_file), self.user + "@" + self.host, REMOTE_COMMAND]
        process = subprocess.Popen(arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        timer = threading.Timer(self.plan.transfer_timeout, process.kill)
        timer.daemon = True
        timer.start()
        try:
            yield process.stdin, process.stdout
            process.stdin.close()
            require(process.wait(timeout=10) == 0, "SSH_RECEIVER_FAILED")
        except (OSError, subprocess.TimeoutExpired):
            raise ReplicationError("SSH_TRANSFER_INTERRUPTED_RETRY_SEALED_EPOCH_ONLY") from None
        finally:
            timer.cancel()
            if process.poll() is None:
                process.kill()
                process.wait(timeout=10)
            process.stdout.close()
            if not process.stdin.closed:
                try:
                    process.stdin.close()
                except OSError:
                    pass

    def send(self, manifest: dict, source_folder: int) -> dict:
        from dr_file_replication import validate_manifest
        validate_manifest(manifest, self.plan)
        with self._connection() as (writer, reader):
            write_frame(writer, {"op": "PUSH", "scope_sha256": fingerprint(self.plan.scope()), "manifest": manifest})
            response = read_frame(reader)
            require(set(response) == {"state", "filenames"} and response["state"] == "NEED"
                    and isinstance(response["filenames"], list), "INVALID_RECEIVER_REQUEST")
            expected = {entry["filename"]: entry for entry in manifest["disks"]}
            names = response["filenames"]
            require(all(isinstance(name, str) and name in expected for name in names)
                    and len(names) == len(set(names)), "RECEIVER_REQUESTED_UNBOUND_FILE")
            for name in names:
                entry = expected[name]
                write_frame(writer, {"filename": name, "size": entry["size"]})
                for block in disk_chunks(source_folder, entry):
                    writer.write(block)
                writer.flush()
                require(read_frame(reader) == {"received": name}, "DISK_ACK_MISMATCH")
            receipt = read_frame(reader)
            require(receipt.get("epoch_id") == manifest["epoch_id"]
                    and receipt.get("manifest_sha256") == fingerprint(manifest), "DESTINATION_ACK_MISMATCH")
            return receipt

    def verify(self, epoch_id: str) -> dict:
        identifier(epoch_id)
        with self._connection() as (writer, reader):
            write_frame(writer, {"op": "VERIFY", "scope_sha256": fingerprint(self.plan.scope()), "epoch_id": epoch_id})
            receipt = read_frame(reader)
            require(receipt.get("epoch_id") == epoch_id and receipt.get("state") == "COMMITTED", "VERIFY_ACK_MISMATCH")
            return receipt


def receive_one(catalog: FileCatalog, reader, writer) -> None:
    """One bounded request per authenticated SSH invocation; no shell or paths."""
    request = read_frame(reader)
    require(request.get("scope_sha256") == fingerprint(catalog.plan.scope()), "PEER_PLAN_NOT_AUTHORIZED")
    if request.get("op") == "VERIFY":
        require(set(request) == {"op", "scope_sha256", "epoch_id"}, "INVALID_VERIFY_REQUEST")
        write_frame(writer, catalog.verify(identifier(request["epoch_id"])))
        return
    require(request.get("op") == "PUSH" and set(request) == {"op", "scope_sha256", "manifest"}, "RECEIVER_OPERATION_DENIED")
    with catalog.incoming(request["manifest"]) as incoming:
        missing = incoming.missing()
        write_frame(writer, {"state": "NEED", "filenames": [entry["filename"] for entry in missing]})
        for entry in missing:
            require(read_frame(reader) == {"filename": entry["filename"], "size": entry["size"]}, "UNBOUND_DISK_TRANSFER")

            def chunks():
                remaining = entry["size"]
                while remaining:
                    block = read_exact(reader, min(CHUNK_BYTES, remaining))
                    remaining -= len(block)
                    yield block

            incoming.write(entry, chunks())
            write_frame(writer, {"received": entry["filename"]})
        write_frame(writer, incoming.commit())
