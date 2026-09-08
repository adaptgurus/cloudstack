# Copyright 2026 LayerSentry contributors
# Licensed under the Apache License, Version 2.0

from pathlib import Path
import unittest


class StorageSourceContractTest(unittest.TestCase):
    def test_mount_detection_requires_exact_mountpoint(self) -> None:
        module = Path(__file__).resolve().parents[1] / "library" / "layersentry_storage.py"
        source = module.read_text(encoding="utf-8")
        exact = '["/usr/bin/findmnt", "-nro", "UUID", "--mountpoint", mount_point]'
        ambiguous = '["/usr/bin/findmnt", "-nro", "UUID", "--target", mount_point]'
        self.assertIn(exact, source)
        self.assertNotIn(ambiguous, source)


if __name__ == "__main__":
    unittest.main()
