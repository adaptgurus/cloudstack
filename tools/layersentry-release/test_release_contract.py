#!/usr/bin/env python3

import importlib.util
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

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
        args = type("Args", (), {"artifact": str(self.artifact), "output_dir": str(self.bundle),
                                  "package_lock": str(self.lock), "version": "1.0.0",
                                  "source_commit": "a" * 40, "source_epoch": "1"})
        release_contract.build_contract(args)

    def tearDown(self):
        shutil.rmtree(self.temp)

    def _write_archive(self):
        with tarfile.open(self.artifact, "w:gz") as archive:
            for path in sorted(self.dist.iterdir()):
                archive.add(path, arcname=path.name)

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


if __name__ == "__main__":
    unittest.main()
