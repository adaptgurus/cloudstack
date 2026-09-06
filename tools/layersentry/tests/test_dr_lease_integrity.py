"""Deterministic local SQLite contention/lease tests; no provider or lab calls."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dr_state_machine as dr


class LeaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="dr-lease-integrity-")
        self.addCleanup(temporary.cleanup)
        self.database = str(Path(temporary.name) / "dr.sqlite")
        self.store = dr.DurableDrStore(self.database)
        self.store.initialize()
        self.clock = [100]
        clock_patch = patch.object(dr, "_epoch_now", side_effect=lambda: self.clock[0])
        clock_patch.start()
        self.addCleanup(clock_patch.stop)
        self.request = dr.RecoveryRequest(
            "operation", "idempotency", dr.OperationType.RECOVERY, "pair", "plan",
            dr.ProviderFamily.CLOUDSTACK_NATIVE, "workload", "operator",
            recovery_point_id="point",
        )
        self.store.begin_operation(self.request)

    def acquire(self, ttl=10):
        return self.store.acquire_lease("workload", "operation", ttl, actor="operator")

    def after_lock_wait(self, action):
        """Advance the clock only once the worker reaches a locked SQL operation.

        Real SQLite transactions provide contention; Events and a fake clock
        avoid sleeps, scheduler timing assumptions and long expiry waits.
        """
        entered = threading.Event()

        class ObservedConnection(sqlite3.Connection):
            def execute(connection, sql, *args, **kwargs):
                if sql == "BEGIN IMMEDIATE" or sql.startswith("SELECT lease_resource"):
                    entered.set()
                return super().execute(sql, *args, **kwargs)

        def connect():
            connection = sqlite3.connect(self.database, timeout=5, factory=ObservedConnection)
            connection.row_factory = sqlite3.Row
            return connection

        blocker = sqlite3.connect(self.database)
        blocker.execute("BEGIN EXCLUSIVE")
        try:
            with patch.object(self.store, "_connect", side_effect=connect), ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(action)
                try:
                    self.assertTrue(entered.wait(5), "worker did not reach the SQLite lock")
                    self.clock[0] = 120
                finally:
                    blocker.commit()
                return pending.result(timeout=5)
        finally:
            blocker.close()

    def test_acquisition_ttl_starts_after_database_lock_wait(self):
        lease = self.after_lock_wait(self.acquire)
        self.assertEqual(lease.expires_at_epoch, 130)
        self.assertEqual(self.store.assert_lease("operation", lease.token), lease)

    def test_transition_rejects_lease_expired_during_lock_wait(self):
        lease = self.acquire()
        before = self.store.list_journal("operation")
        with self.assertRaises(dr.LeaseRequired):
            self.after_lock_wait(lambda: self.store.transition(
                "operation", dr.OperationState.PRECHECKED,
                actor="operator", lease_token=lease.token,
            ))
        self.assertEqual(self.store.get_operation("operation").state, dr.OperationState.LEASE_ACQUIRED)
        self.assertEqual(self.store.list_journal("operation"), before)

    def test_renewal_rejects_lease_expired_during_lock_wait(self):
        lease = self.acquire()
        with self.assertRaises(dr.LeaseRequired):
            self.after_lock_wait(lambda: self.store.renew_lease(
                "workload", "operation", lease.token, 60, actor="operator",
            ))
        with self.assertRaises(dr.LeaseRequired):
            self.store.assert_lease("operation", lease.token)

    def test_release_rejects_lease_expired_during_lock_wait(self):
        lease = self.acquire()
        before = self.store.list_journal("operation")
        with self.assertRaises(dr.LeaseRequired):
            self.after_lock_wait(lambda: self.store.release_lease(
                "workload", "operation", lease.token, actor="operator",
            ))
        self.assertEqual(self.store.list_journal("operation"), before)

    def test_assertion_rejects_lease_expired_during_read_lock_wait(self):
        lease = self.acquire()
        with self.assertRaises(dr.LeaseRequired):
            self.after_lock_wait(lambda: self.store.assert_lease("operation", lease.token))

    def test_same_operation_competing_worker_cannot_take_live_token(self):
        lease = self.acquire()
        before = self.store.list_journal("operation")
        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.assertRaises(dr.LeaseConflict):
                executor.submit(self.acquire).result(timeout=5)
        self.assertEqual(self.store.assert_lease("operation", lease.token), lease)
        self.assertEqual(self.store.list_journal("operation"), before)

    def test_owner_renews_with_token_then_releases_for_sequential_resume(self):
        lease = self.acquire()
        self.clock[0] = 105
        renewed = self.store.renew_lease("workload", "operation", lease.token, 20, actor="operator")
        self.assertEqual(renewed.expires_at_epoch, 125)
        self.assertEqual(renewed.token, lease.token)
        self.store.transition("operation", dr.OperationState.PRECHECKED,
                              actor="operator", lease_token=renewed.token)
        self.store.release_lease("workload", "operation", renewed.token, actor="operator")
        resumed = self.acquire()
        self.assertNotEqual(resumed.token, renewed.token)
        self.store.transition("operation", dr.OperationState.MUTATION_SUBMITTED,
                              actor="operator", lease_token=resumed.token)

    def test_expired_token_cannot_release_or_mutate_replacement_lease(self):
        lease = self.acquire()
        self.clock[0] = 110
        replacement = self.acquire()
        self.assertNotEqual(lease.token, replacement.token)
        with self.assertRaises(dr.LeaseRequired):
            self.store.release_lease("workload", "operation", lease.token, actor="operator")
        with self.assertRaises(dr.LeaseRequired):
            self.store.transition("operation", dr.OperationState.PRECHECKED,
                                  actor="operator", lease_token=lease.token)
        self.assertEqual(self.store.assert_lease("operation", replacement.token), replacement)


if __name__ == "__main__":
    unittest.main()
