#!/usr/bin/env python3

import importlib.util
import gzip
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).with_name("release_contract.py")
SPEC = importlib.util.spec_from_file_location("release_contract", MODULE_PATH)
release_contract = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_contract)


class ReleaseContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.bundle = self.temp / "bundle"
        self.dist = self.temp / "dist"
        self.bundle.mkdir()
        self.dist.mkdir()
        (self.dist / "index.html").write_text("<html></html>\n", encoding="utf-8")
        (self.dist / "config.json").write_text("{}\n", encoding="utf-8")
        (self.dist / "app.js").write_text("console.log('ok')\n", encoding="utf-8")
        self.artifact = self.bundle / "layersentry-ui-1.0.0.tar.gz"
        self._write_archive()
        self.lock = self.temp / "package-lock.json"
        self.lock.write_text(json.dumps({"dependencies": {"vue": {"version": "3.2.31"}}}), encoding="utf-8")
        self.build_args = type("Args", (), {"artifact": str(self.artifact), "output_dir": str(self.bundle),
                                  "package_lock": str(self.lock), "version": "1.0.0",
                                  "source_commit": "a" * 40, "source_epoch": "1"})
        release_contract.build_contract(self.build_args)

    def tearDown(self):
        shutil.rmtree(self.temp)

    def _write_archive(self):
        with tarfile.open(self.artifact, "w:gz") as archive:
            for path in sorted(self.dist.iterdir()):
                archive.add(path, arcname=path.name)

    def _custom_archive(self, entries):
        with tarfile.open(self.artifact, "w:gz") as archive:
            for name, kind, data in entries:
                member = tarfile.TarInfo(name)
                member.type = kind
                member.size = len(data)
                if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    member.linkname = "index.html"
                archive.addfile(member, io.BytesIO(data))

    def _refresh_digests(self):
        manifest_path = self.bundle / "release-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = release_contract.sha256(self.artifact)
        manifest["artifacts"][0].update({"sha256": digest, "size": self.artifact.stat().st_size})
        provenance_path = self.bundle / "layersentry-ui.provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["subject"]["sha256"] = digest
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
        for field in ("sbom", "provenance"):
            record = manifest["metadata"][field]
            record["sha256"] = release_contract.sha256(self.bundle / record["name"])
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def _root_entries(self):
        return [("index.html", tarfile.REGTYPE, b"<html/>"),
                ("config.json", tarfile.REGTYPE, b"{}")]

    def verify_args(self, allow_unsigned=True):
        return type("Args", (), {"bundle_dir": str(self.bundle),
                                  "expected_source_commit": "a" * 40,
                                  "allow_unsigned": allow_unsigned})

    def test_valid_unsigned_candidate_requires_explicit_override(self):
        release_contract.verify_contract(self.verify_args())
        with self.assertRaisesRegex(release_contract.ContractError, "not cryptographically signature-verified"):
            release_contract.verify_contract(self.verify_args(False))

    def test_forged_verified_status_is_rejected(self):
        manifest_path = self.bundle / "release-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["signature"]["status"] = "verified"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(release_contract.ContractError, "not cryptographically signature-verified"):
            release_contract.verify_contract(self.verify_args(False))

    def test_tampered_artifact_is_rejected(self):
        with self.artifact.open("ab") as stream:
            stream.write(b"tamper")
        with self.assertRaisesRegex(release_contract.ContractError, "size mismatch"):
            release_contract.verify_contract(self.verify_args())

    def test_tampered_sbom_is_rejected(self):
        with (self.bundle / "layersentry-ui.sbom.cdx.json").open("a", encoding="utf-8") as stream:
            stream.write("tamper")
        with self.assertRaisesRegex(release_contract.ContractError, "sbom digest mismatch"):
            release_contract.verify_contract(self.verify_args())

    def test_source_commit_mismatch_is_rejected(self):
        args = self.verify_args()
        args.expected_source_commit = "b" * 40
        with self.assertRaisesRegex(release_contract.ContractError, "source commit mismatch"):
            release_contract.verify_contract(args)

    def test_source_map_is_rejected_even_with_matching_digest(self):
        (self.dist / "app.js.map").write_text("{}", encoding="utf-8")
        self._write_archive()
        manifest_path = self.bundle / "release-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        digest = release_contract.sha256(self.artifact)
        manifest["artifacts"][0].update({"sha256": digest, "size": self.artifact.stat().st_size})
        provenance_path = self.bundle / "layersentry-ui.provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["subject"]["sha256"] = digest
        provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
        manifest["metadata"]["provenance"]["sha256"] = release_contract.sha256(provenance_path)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(release_contract.ContractError, "source map"):
            release_contract.verify_contract(self.verify_args())

    def test_duplicate_json_keys_rejected_at_all_depths(self):
        for content in ('{"a": 1, "a": 2}', '{"outer": {"a": 1, "a": 1}}'):
            with self.subTest(content=content):
                self.lock.write_text(content, encoding="utf-8")
                with self.assertRaisesRegex(release_contract.ContractError, "duplicate keys"):
                    release_contract.build_contract(self.build_args)

    def test_duplicate_metadata_keys_rejected_with_matching_digests(self):
        for filename in ("release-manifest.json", "layersentry-ui.sbom.cdx.json",
                         "layersentry-ui.provenance.json"):
            with self.subTest(filename=filename):
                path = self.bundle / filename
                original = path.read_text(encoding="utf-8")
                path.write_text(original.replace("{", '{"duplicate":1,"duplicate":2,', 1), encoding="utf-8")
                if filename != "release-manifest.json":
                    manifest_path = self.bundle / "release-manifest.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    field = "sbom" if "sbom" in filename else "provenance"
                    manifest["metadata"][field]["sha256"] = release_contract.sha256(path)
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaisesRegex(release_contract.ContractError, "duplicate keys"):
                    release_contract.verify_contract(self.verify_args())
                path.write_text(original, encoding="utf-8")
                self._refresh_digests()

    def test_symlink_bundle_and_parent_rejected(self):
        for target, suffix in ((self.bundle, ""), (self.temp, "bundle")):
            link = self.temp / "linked"
            link.symlink_to(target, target_is_directory=True)
            args = self.verify_args()
            args.bundle_dir = str(link / suffix)
            with self.assertRaisesRegex(release_contract.ContractError, "symlinks"):
                release_contract.verify_contract(args)
            link.unlink()

    def test_symlink_bundle_inputs_rejected(self):
        for filename in (self.artifact.name, "release-manifest.json", "layersentry-ui.sbom.cdx.json",
                         "layersentry-ui.provenance.json"):
            with self.subTest(filename=filename):
                path = self.bundle / filename
                original = self.temp / filename
                path.rename(original)
                path.symlink_to(original)
                with self.assertRaisesRegex(release_contract.ContractError, "symlinks"):
                    release_contract.verify_contract(self.verify_args())
                path.unlink()
                original.rename(path)

    def test_symlink_build_inputs_and_outputs_rejected(self):
        for path in (self.artifact, self.lock, self.bundle / "layersentry-ui.sbom.cdx.json",
                     self.bundle / "layersentry-ui.provenance.json", self.bundle / "release-manifest.json",
                     self.bundle / "SHA256SUMS"):
            with self.subTest(filename=path.name):
                original = path.with_name(path.name + ".original")
                path.rename(original)
                path.symlink_to(original)
                with self.assertRaisesRegex(release_contract.ContractError, "symlinks"):
                    release_contract.build_contract(self.build_args)
                path.unlink()
                original.rename(path)

    def test_directories_dot_prefixes_and_long_pax_paths_are_valid(self):
        self._custom_archive([("./", tarfile.DIRTYPE, b""),
                              ("./assets/", tarfile.DIRTYPE, b""),
                              ("./index.html", tarfile.AREGTYPE, b"<html/>"),
                              ("./config.json", tarfile.REGTYPE, b"{}"),
                              ("./assets/" + "a" * 150 + ".js", tarfile.REGTYPE, b"ok")])
        self._refresh_digests()
        release_contract.verify_contract(self.verify_args())

    def test_gnu_posix_tar_builder_layout_is_valid(self):
        result = subprocess.run(["tar", "--sort=name", "--format=posix", "--mtime=@1",
                                 "--owner=0", "--group=0", "--numeric-owner",
                                 "--pax-option=delete=atime,delete=ctime", "-C", str(self.dist),
                                 "-cf", "-", "."], check=True, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=10)
        self.artifact.write_bytes(gzip.compress(result.stdout, mtime=0))
        self._refresh_digests()
        release_contract.verify_contract(self.verify_args())

    def test_duplicate_normalized_archive_paths_rejected(self):
        for name in ("index.html", "./index.html", ".//index.html", "././index.html"):
            with self.subTest(name=name):
                self._custom_archive(self._root_entries() + [(name, tarfile.REGTYPE, b"bad")])
                self._refresh_digests()
                with self.assertRaisesRegex(release_contract.ContractError, "duplicate normalized path"):
                    release_contract.verify_contract(self.verify_args())

    def test_archive_traversal_and_absolute_paths_rejected(self):
        for name in ("../bad", "a/../../bad", "/etc/bad", "a\\..\\bad"):
            with self.subTest(name=name):
                self._custom_archive(self._root_entries() + [(name, tarfile.REGTYPE, b"")])
                with self.assertRaisesRegex(release_contract.ContractError, "unsafe artifact archive path"):
                    release_contract.validate_archive(self.artifact)

    def test_archive_links_devices_and_unknown_types_rejected(self):
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE,
                     tarfile.FIFOTYPE, tarfile.CONTTYPE, b"Z"):
            with self.subTest(kind=kind):
                self._custom_archive(self._root_entries() + [("bad", kind, b"")])
                with self.assertRaisesRegex(release_contract.ContractError, "unsupported member type"):
                    release_contract.validate_archive(self.artifact)

    def test_required_files_must_be_at_root_and_regular(self):
        for required in ("index.html", "config.json"):
            other = [entry for entry in self._root_entries() if entry[0] != required]
            for name, kind in (("nested/" + required, tarfile.REGTYPE),
                               ("not-" + required, tarfile.REGTYPE), (required, tarfile.DIRTYPE)):
                with self.subTest(name=name, kind=kind):
                    self._custom_archive(other + [(name, kind, b"")])
                    with self.assertRaisesRegex(release_contract.ContractError, "no regular root " + required):
                        release_contract.validate_archive(self.artifact)

    def test_file_directory_conflict_rejected_in_either_order(self):
        entries = [("assets", tarfile.REGTYPE, b""), ("assets/app.js", tarfile.REGTYPE, b"")]
        for extra in (entries, list(reversed(entries))):
            self._custom_archive(self._root_entries() + extra)
            with self.assertRaisesRegex(release_contract.ContractError, "file/directory path conflict"):
                release_contract.validate_archive(self.artifact)

    def test_archive_limits_accept_boundary_and_reject_excess(self):
        self._custom_archive(self._root_entries())
        expanded_size = len(gzip.decompress(self.artifact.read_bytes()))
        for constant, boundary, message in (("MAX_ARCHIVE_MEMBERS", 2, "member-count"),
                                             ("MAX_MEMBER_BYTES", 7, "member exceeds size"),
                                             ("MAX_EXPANDED_BYTES", expanded_size, "expanded-size")):
            with self.subTest(constant=constant):
                with patch.object(release_contract, constant, boundary):
                    release_contract.validate_archive(self.artifact)
                with patch.object(release_contract, constant, boundary - 1):
                    with self.assertRaisesRegex(release_contract.ContractError, message):
                        release_contract.validate_archive(self.artifact)

    def test_json_size_limit(self):
        with patch.object(release_contract, "MAX_JSON_BYTES", self.lock.stat().st_size):
            release_contract.load_json(self.lock, "package lock")
        with patch.object(release_contract, "MAX_JSON_BYTES", self.lock.stat().st_size - 1):
            with self.assertRaisesRegex(release_contract.ContractError, "JSON size policy"):
                release_contract.load_json(self.lock, "package lock")

    def test_nonzero_tar_trailing_data_rejected(self):
        expanded = gzip.decompress(self.artifact.read_bytes())
        self.artifact.write_bytes(gzip.compress(expanded + b"hidden archive"))
        with self.assertRaisesRegex(release_contract.ContractError, "data after tar terminator"):
            release_contract.validate_archive(self.artifact)

    def test_invalid_or_truncated_gzip_rejected(self):
        original = self.artifact.read_bytes()
        for data in (b"not gzip", original[:-8]):
            with self.subTest(length=len(data)):
                self.artifact.write_bytes(data)
                with self.assertRaisesRegex(release_contract.ContractError, "invalid artifact archive"):
                    release_contract.validate_archive(self.artifact)

    def test_sparse_pax_member_rejected(self):
        with tarfile.open(self.artifact, "w:gz") as archive:
            member = tarfile.TarInfo("sparse")
            member.pax_headers = {"GNU.sparse.map": "0,1", "GNU.sparse.realsize": "1000000"}
            member.size = 1
            archive.addfile(member, io.BytesIO(b"x"))
        with self.assertRaisesRegex(release_contract.ContractError, "unsupported member type"):
            release_contract.validate_archive(self.artifact)

    def test_extended_header_size_rejected_before_body_is_read(self):
        member = tarfile.TarInfo("pax")
        member.type = tarfile.XHDTYPE
        member.size = release_contract.MAX_EXTENDED_HEADER_BYTES + 1
        self.artifact.write_bytes(gzip.compress(member.tobuf()))
        with self.assertRaisesRegex(release_contract.ContractError, "extended header exceeds size"):
            release_contract.validate_archive(self.artifact)

    def test_large_declared_file_rejected_before_body_is_read(self):
        member = tarfile.TarInfo("large")
        member.size = release_contract.MAX_MEMBER_BYTES + 1
        self.artifact.write_bytes(gzip.compress(member.tobuf()))
        with self.assertRaisesRegex(release_contract.ContractError, "member exceeds size"):
            release_contract.validate_archive(self.artifact)

    def test_invalid_later_tar_header_is_not_accepted_as_eof(self):
        self._custom_archive(self._root_entries())
        expanded = gzip.decompress(self.artifact.read_bytes())
        # Each root entry occupies one header and one data block.
        for suffix in (b"invalid".ljust(512, b"x") + b"\0" * 1024, b"truncated", b""):
            with self.subTest(length=len(suffix)):
                self.artifact.write_bytes(gzip.compress(expanded[:2048] + suffix))
                with self.assertRaisesRegex(release_contract.ContractError, "invalid artifact archive header"):
                    release_contract.validate_archive(self.artifact)


if __name__ == "__main__":
    unittest.main()
