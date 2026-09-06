"""Exercise the reviewed runner adapter with offline API and real disk journals."""

import datetime
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dr_native_provider import NativeNasRecoveryProvider, NativeRecoveryCoordinator
from dr_replication import CopyLimits, NasReplicator, Repository, ReplicationError
from dr_state_machine import (
    DurableDrStore, OperationType, ProtectionPlan, ProviderFamily,
    RecoveryPoint, RecoveryPointKind, RecoveryRequest, SitePair, ValidationError,
)


def uid():
    return str(uuid.uuid4())


@unittest.skipUnless(os.environ.get("LAYERSENTRY_NATIVE_ACCEPTANCE_DIR"),
                     "reviewed Cozystack native adapter test directory not provided")
class NativeBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Test-only dependency injection from a lead-reviewed local checkout.
        # The product provider never imports a caller-supplied module path.
        sys.path.insert(0, os.environ["LAYERSENTRY_NATIVE_ACCEPTANCE_DIR"])
        cls.native = importlib.import_module("dr_recovery_acceptance")
        cls.helpers = importlib.import_module("test_dr_recovery_acceptance")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="layersentry-native-binding-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = self.helpers.fixture()
        self.api = self.helpers.API(self.fixture)
        self.api.endpoint = "https://cloud.example/client/api"
        f = self.fixture
        source, destination, journal = (self.root / name for name in ("source", "destination", "journal"))
        for folder, site in ((source, f["source_zone_id"]), (destination, f["destination_zone_id"])):
            folder.mkdir(mode=0o700)
            (folder / ".layersentry-repository.json").write_text(json.dumps({
                "schema": 1, "site_id": site, "repository_id": f["repository_id"],
            }))
        journal.mkdir(mode=0o700)
        for label in ("older", "latest"):
            backup = self.api.rows[("listBackups", f["points"][label]["backup_id"])]["backup"][0]
            backup["externalid"] = "i-test-VM/" + label
            backup["volumes"] = json.dumps([
                {"deviceId": 0, "uuid": self.helpers.uid(31), "type": "ROOT", "path": "rootdisk"},
                {"deviceId": 1, "uuid": self.helpers.uid(32), "type": "DATADISK", "path": "datadisk"},
            ])
            folder = source / backup["externalid"]
            folder.mkdir(parents=True, mode=0o700)
            for name in ("root.rootdisk.qcow2", "datadisk.datadisk.qcow2"):
                (folder / name).write_bytes((label + name).encode())
        self.site_pair = SitePair(uid(), f["source_zone_id"], f["destination_zone_id"])
        self.plan = ProtectionPlan(uid(), self.site_pair.id, ProviderFamily.CLOUDSTACK_NATIVE, (f["source_vm_id"],))
        backup_id = f["points"]["older"]["backup_id"]
        created = self.api.rows[("listBackups", backup_id)]["backup"][0]["created"]
        self.point = RecoveryPoint(uid(), self.plan.id, ProviderFamily.CLOUDSTACK_NATIVE,
                                   RecoveryPointKind.NATIVE_BACKUP, backup_id,
                                   int(datetime.datetime.strptime(created, "%Y-%m-%dT%H:%M:%S%z").timestamp()))
        self.request = RecoveryRequest(uid(), uid(), OperationType.TEST_RECOVERY, self.site_pair.id,
                                       self.plan.id, ProviderFamily.CLOUDSTACK_NATIVE,
                                       "native-nas:" + f["account_id"] + ":" + f["source_vm_id"],
                                       "test-operator", recovery_point_id=self.point.id, isolated_test_network=True)
        copier = NasReplicator(Repository(source, f["source_zone_id"], f["repository_id"]),
                               Repository(destination, f["destination_zone_id"], f["repository_id"]),
                               CopyLimits(reserve_bytes=0))
        self.provider = NativeNasRecoveryProvider(
            native=self.native, api=self.api, fixture=f, request=self.request, plan=self.plan,
            site_pair=self.site_pair, point=self.point, replicator=copier, journal_root=journal,
            authorize=lambda *_: True, verify_repository_route=lambda *_: True,
            verify_test_isolation=lambda *_: True, enabled=True,
        )
        self.store = DurableDrStore(str(self.root / "dr.sqlite"))
        self.store.initialize()
        self.coordinator = NativeRecoveryCoordinator(self.store, self.provider)

    def test_selected_older_point_creates_one_stopped_clone_and_never_claims_recovery_complete(self):
        self.provider.replicate()
        result = self.coordinator.advance()
        self.assertEqual(result["state"], "VALIDATING_DESTINATION")
        self.coordinator.advance()
        mutations = self.api.mutations()
        self.assertEqual(len(mutations), 1)
        self.assertEqual(mutations[0][1]["backupid"], self.fixture["points"]["older"]["backup_id"])
        self.assertEqual(mutations[0][1]["startvm"], "false")
        self.assertEqual(result["evidence"]["e2e"], "NOT_TESTED")

    def test_ambiguous_submission_never_resubmits(self):
        self.provider.replicate()
        self.api.transport_failure = True
        with self.assertRaisesRegex(ValidationError, "RECONCILIATION_REQUIRED"):
            self.coordinator.advance()
        self.api.transport_failure = False
        with self.assertRaisesRegex(self.native.GateError, "SUBMISSION_UNCERTAIN"):
            self.coordinator.advance()
        self.assertEqual(len(self.api.mutations()), 1)

    def test_authorization_is_checked_before_replication_or_api_mutation(self):
        self.provider.authorize = lambda *_: False
        with self.assertRaisesRegex(ReplicationError, "UNAUTHORIZED"):
            self.provider.replicate()
        self.assertEqual(self.api.calls, [])

    def test_unverified_destination_repository_blocks_native_mutation(self):
        self.provider.replicate()
        self.provider.verify_repository_route = lambda *_: False
        with self.assertRaisesRegex(ReplicationError, "ROUTE_UNVERIFIED"):
            self.coordinator.advance()
        self.assertEqual(self.api.mutations(), [])

    def test_unverified_test_network_blocks_native_mutation(self):
        self.provider.replicate()
        self.provider.verify_test_isolation = lambda *_: False
        with self.assertRaisesRegex(ReplicationError, "ISOLATION_UNVERIFIED"):
            self.coordinator.advance()
        self.assertEqual(self.api.mutations(), [])


if __name__ == "__main__":
    unittest.main()
