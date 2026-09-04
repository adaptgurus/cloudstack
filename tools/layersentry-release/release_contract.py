#!/usr/bin/env python3
"""Build and verify the LayerSentry UI release-contract foundation."""

import argparse
import gzip
import hashlib
import json
import os
import re
import sys
import tarfile
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = "1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,63}$")
EPOCH_RE = re.compile(r"^[0-9]+$")
MAX_ARTIFACT_BYTES = 256 * 1024 * 1024
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 20000
MAX_JSON_BYTES = 16 * 1024 * 1024
MAX_EXTENDED_HEADER_BYTES = 1024 * 1024


class ContractError(Exception):
    pass


def sha256(path):
    require_regular_file(path, "digest input")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    reject_symlinks(path, "JSON output")
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise ContractError(message)


def reject_symlinks(path, label):
    # Check before resolve() erases link evidence, including linked parents.
    path = Path(path).absolute()
    require(not any(part.is_symlink() for part in (path, *path.parents)),
            f"{label} must not use symlinks")


def require_regular_file(path, label):
    reject_symlinks(path, label)
    require(path.is_file(), f"{label} is missing or not a regular file")


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON contains duplicate keys")
        result[key] = value
    return result


def safe_name(name, field):
    require(isinstance(name, str) and name == os.path.basename(name), f"unsafe {field}")
    require(name not in ("", ".", ".."), f"invalid {field}")
    return name


def load_json(path, label):
    try:
        require_regular_file(path, label)
        with path.open("rb") as stream:
            content = stream.read(MAX_JSON_BYTES + 1)
        require(len(content) <= MAX_JSON_BYTES, f"{label} exceeds JSON size policy")
        return json.loads(content.decode("utf-8"), object_pairs_hook=unique_json_object)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractError(f"invalid {label}: {error}") from error


def build_contract(args):
    require_regular_file(Path(args.artifact), "artifact")
    reject_symlinks(Path(args.output_dir), "output directory")
    artifact = Path(args.artifact).resolve()
    output = Path(args.output_dir).resolve()
    package_lock_path = Path(args.package_lock)
    require(artifact.is_file(), "artifact is missing")
    require(artifact.parent == output, "artifact must be directly inside output-dir")
    require(COMMIT_RE.fullmatch(args.source_commit), "invalid source commit")
    require(VERSION_RE.fullmatch(args.version), "invalid release version")
    require(EPOCH_RE.fullmatch(args.source_epoch), "invalid source epoch")
    package_lock = load_json(package_lock_path, "package lock")
    dependencies = package_lock.get("dependencies")
    require(isinstance(dependencies, dict), "package lock has no dependency map")
    components = []
    for name, dependency in sorted(dependencies.items()):
        version = dependency.get("version") if isinstance(dependency, dict) else None
        if isinstance(version, str) and version:
            components.append({"type": "library", "name": name, "version": version})

    artifact_digest = sha256(artifact)
    lock_digest = sha256(package_lock_path)
    sbom_path = output / "layersentry-ui.sbom.cdx.json"
    provenance_path = output / "layersentry-ui.provenance.json"
    manifest_path = output / "release-manifest.json"
    write_json(sbom_path, {
        "bomFormat": "CycloneDX", "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{artifact_digest[:8]}-{artifact_digest[8:12]}-{artifact_digest[12:16]}-{artifact_digest[16:20]}-{artifact_digest[20:32]}",
        "version": 1,
        "metadata": {"component": {"type": "application", "name": "layersentry-ui", "version": args.version}},
        "components": components,
    })
    write_json(provenance_path, {
        "schemaVersion": SCHEMA_VERSION,
        "subject": {"name": artifact.name, "sha256": artifact_digest},
        "source": {"repository": "https://github.com/adaptgurus/cloudstack", "commit": args.source_commit},
        "builder": {"identity": os.environ.get("LAYERSENTRY_BUILDER_ID", "local-untrusted-builder"),
                    "node": os.environ.get("LAYERSENTRY_NODE_VERSION", "unknown"),
                    "npm": os.environ.get("LAYERSENTRY_NPM_VERSION", "unknown"),
                    "sourceDateEpoch": int(args.source_epoch)},
        "materials": [{"name": "ui/package-lock.json", "sha256": lock_digest}],
    })
    write_json(manifest_path, {
        "schemaVersion": SCHEMA_VERSION,
        "release": {"version": args.version, "channel": "candidate", "status": "unsigned"},
        "cloudstack": {"version": "4.22.1.1"},
        "source": {"repository": "https://github.com/adaptgurus/cloudstack", "commit": args.source_commit},
        "compatibility": {"rockyLinux": ["9"], "java": ["17"]},
        "artifacts": [{"name": artifact.name, "mediaType": "application/gzip", "sha256": artifact_digest, "size": artifact.stat().st_size}],
        "metadata": {"sbom": {"name": sbom_path.name, "format": "CycloneDX", "sha256": sha256(sbom_path)},
                     "provenance": {"name": provenance_path.name, "sha256": sha256(provenance_path)}},
        "signature": {"requiredForProduction": True, "status": "unsigned"},
        "policies": {"productionSourceMaps": False},
    })
    reject_symlinks(output / "SHA256SUMS", "checksum output")
    (output / "SHA256SUMS").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in (artifact, sbom_path, provenance_path, manifest_path)), encoding="ascii")


class BoundedArchiveReader:
    """Bound decompressed bytes, including PAX/GNU headers hidden by tarfile."""

    def __init__(self, stream):
        self.stream = stream
        self.total = 0

    def read(self, size):
        data = self.stream.read(min(size, MAX_EXPANDED_BYTES - self.total + 1))
        self.total += len(data)
        require(self.total <= MAX_EXPANDED_BYTES, "artifact exceeds expanded-size policy")
        return data


class StrictTarInfo(tarfile.TarInfo):
    @classmethod
    def frombuf(cls, buf, encoding, errors):
        return cls._frombuf(buf, encoding, errors)

    @classmethod
    def _frombuf(cls, buf, encoding, errors, **kwargs):
        # Patched Python releases parse internal headers through _frombuf;
        # older Python 3.9 releases call the public frombuf directly.
        try:
            parse = getattr(super(), "_frombuf", super().frombuf)
            member = parse(buf, encoding, errors, **kwargs)
        except tarfile.EOFHeaderError:
            raise  # A zero block is the valid tar terminator.
        except tarfile.HeaderError as error:
            # TarFile.next otherwise treats invalid/truncated later headers as EOF.
            raise ContractError("invalid artifact archive header") from error
        require(member.size >= 0, "artifact member has negative size")
        if member.type in (tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.SOLARIS_XHDTYPE,
                           tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK):
            require(member.size <= MAX_EXTENDED_HEADER_BYTES,
                    "artifact extended header exceeds size policy")
        return member


def validate_archive(path):
    require_regular_file(path, "artifact")
    try:
        with gzip.open(path, "rb") as compressed:
            reader = BoundedArchiveReader(compressed)
            with tarfile.open(fileobj=reader, mode="r|", tarinfo=StrictTarInfo) as archive:
                names = {}
                expanded_files = 0
                for count, member in enumerate(archive, 1):
                    require(count <= MAX_ARCHIVE_MEMBERS, "artifact exceeds member-count policy")
                    name = PurePosixPath(member.name)
                    require(member.name and not name.is_absolute() and ".." not in name.parts
                            and "\\" not in member.name, "unsafe artifact archive path")
                    normalized = str(name)
                    require(normalized not in names, "artifact contains duplicate normalized path")
                    require(member.type in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE)
                            and member.sparse is None, "artifact contains link/device or unsupported member type")
                    require(member.size >= 0 and member.size <= MAX_MEMBER_BYTES,
                            "artifact member exceeds size policy")
                    require(not member.isdir() or member.size == 0, "artifact directory has file data")
                    require(normalized != "." or member.isdir(), "artifact root must be a directory")
                    require(not member.isfile() or not member.name.endswith("/"),
                            "artifact file has directory path")
                    expanded_files += member.size
                    require(expanded_files <= MAX_EXPANDED_BYTES, "artifact exceeds expanded-size policy")
                    names[normalized] = member.isdir()
                    require(not normalized.endswith((".map", ".map.gz")), "artifact contains source map")
                require(names, "artifact archive is empty")
                for required in ("index.html", "config.json"):
                    require(required in names and not names[required], f"artifact has no regular root {required}")
                for name in names:
                    require(all(names.get(str(parent), True) for parent in PurePosixPath(name).parents),
                            "artifact contains file/directory path conflict")
                # Continue through tar padding and gzip trailers. Reading via the
                # tar stream also includes any bytes it already buffered.
                while True:
                    padding = archive.fileobj.read(64 * 1024)
                    if not padding:
                        break
                    require(not any(padding), "artifact contains data after tar terminator")
    except (tarfile.TarError, OSError, EOFError, RecursionError) as error:
        raise ContractError(f"invalid artifact archive: {error}") from error


def verify_contract(args):
    reject_symlinks(Path(args.bundle_dir), "bundle directory")
    bundle = Path(args.bundle_dir).resolve()
    require(bundle.is_dir(), "bundle directory is missing")
    manifest = load_json(bundle / "release-manifest.json", "release manifest")
    require(manifest.get("schemaVersion") == SCHEMA_VERSION, "unsupported manifest schema")
    release = manifest.get("release", {})
    require(VERSION_RE.fullmatch(release.get("version", "")) is not None, "invalid release version")
    require(release.get("channel") == "candidate" and release.get("status") == "unsigned",
            "unsupported release state")
    require(manifest.get("cloudstack", {}).get("version") == "4.22.1.1", "incompatible CloudStack version")
    require(manifest.get("compatibility", {}).get("rockyLinux") == ["9"], "incompatible Rocky Linux profile")
    commit = manifest.get("source", {}).get("commit", "")
    require(COMMIT_RE.fullmatch(commit) is not None, "invalid manifest source commit")
    if args.expected_source_commit:
        require(commit == args.expected_source_commit, "source commit mismatch")
    require(manifest.get("policies", {}).get("productionSourceMaps") is False, "source-map policy mismatch")
    signature = manifest.get("signature", {})
    require(signature.get("requiredForProduction") is True, "production signature policy missing")
    # Detached-signature verification is deliberately not implemented in this
    # foundation. Never trust a self-asserted manifest status as authentication.
    require(args.allow_unsigned and signature.get("status") == "unsigned",
            "release is not cryptographically signature-verified")
    artifacts = manifest.get("artifacts")
    require(isinstance(artifacts, list) and len(artifacts) == 1, "manifest must contain one UI artifact")
    artifact = artifacts[0]
    name = safe_name(artifact.get("name"), "artifact name")
    digest = artifact.get("sha256")
    require(isinstance(digest, str) and SHA256_RE.fullmatch(digest), "invalid artifact digest")
    path = bundle / name
    require_regular_file(path, "artifact")
    require(path.stat().st_size <= MAX_ARTIFACT_BYTES, "artifact exceeds size policy")
    require(path.stat().st_size == artifact.get("size"), "artifact size mismatch")
    require(sha256(path) == digest, "artifact digest mismatch")
    for field in ("sbom", "provenance"):
        record = manifest.get("metadata", {}).get(field, {})
        metadata_name = safe_name(record.get("name"), f"{field} name")
        metadata_digest = record.get("sha256")
        require(isinstance(metadata_digest, str) and SHA256_RE.fullmatch(metadata_digest), f"invalid {field} digest")
        metadata_path = bundle / metadata_name
        require_regular_file(metadata_path, field)
        require(metadata_path.is_file() and sha256(metadata_path) == metadata_digest, f"{field} digest mismatch")
    sbom = load_json(bundle / manifest["metadata"]["sbom"]["name"], "SBOM")
    require(sbom.get("bomFormat") == "CycloneDX" and sbom.get("specVersion") == "1.5", "unsupported SBOM")
    provenance = load_json(bundle / manifest["metadata"]["provenance"]["name"], "provenance")
    require(provenance.get("subject", {}).get("sha256") == digest, "provenance subject mismatch")
    require(provenance.get("source", {}).get("commit") == commit, "provenance source mismatch")
    validate_archive(path)


def parser():
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    for name in ("version", "source-commit", "source-epoch", "artifact", "package-lock", "output-dir"):
        build.add_argument(f"--{name}", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--bundle-dir", required=True)
    verify.add_argument("--expected-source-commit")
    verify.add_argument("--allow-unsigned", action="store_true")
    return root


def main():
    args = parser().parse_args()
    try:
        build_contract(args) if args.command == "build" else verify_contract(args)
    except ContractError as error:
        print(f"release contract rejected: {error}", file=sys.stderr)
        return 1
    print(f"release contract {args.command} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
