"""Bind sealed NAS replicas to the established native recovery adapter.

Status: NOT_TESTED. No entry point, scheduler, automatic failover or deployment.
The integration host imports its reviewed, pinned Cozystack
``dr_recovery_acceptance`` module and supplies it explicitly. No downloaded code
or caller-selected module path is loaded here.
"""

from __future__ import annotations

import contextlib
import datetime
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Iterator

from dr_replication import BackupDisk, BackupIdentity, NasReplicator, fingerprint, identifier, require
from dr_state_machine import (
    DrPolicy, DurableDrStore, OperationState, OperationType, ProtectionPlan,
    ProviderCapability, ProviderDescriptor, ProviderFamily, RecoveryPoint,
    RecoveryPointKind, RecoveryRequest, SitePair, ValidationError,
    request_fingerprint,
)


class NativeNasRecoveryProvider:
    """One request-bound provider instance, rebuilt from durable request data.

    Authorize is an integration-owned server-side check for the exact request,
    plan, account, VM and backup. Route verification must establish that native
    recovery reads this DR-local replica, including its repository identity.
    Neither callback may be derived from a browser-supplied boolean.
    """

    def __init__(self, *, native, api, fixture: dict, request: RecoveryRequest,
                 plan: ProtectionPlan, site_pair: SitePair, point: RecoveryPoint,
                 replicator: NasReplicator, journal_root: Path,
                 authorize: Callable, verify_repository_route: Callable,
                 verify_test_isolation: Callable | None = None,
                 enabled: bool = False):
        self.native, self.api = native, api
        # Own a canonical copy so another caller cannot mutate native parameters.
        self.fixture = json.loads(json.dumps(fixture))
        self.request, self.plan, self.site_pair, self.point = request, plan, site_pair, point
        self.replicator, self.journal_root = replicator, journal_root
        self.authorize, self.verify_repository_route = authorize, verify_repository_route
        self.verify_test_isolation = verify_test_isolation
        self._enabled = enabled is True
        self._mutation_guard = None
        self._prepared_receipt = None
        self.native.fixture_check(self.fixture)
        self._validate_binding()

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            family=ProviderFamily.CLOUDSTACK_NATIVE,
            capabilities=frozenset({ProviderCapability.SELECTED_RECOVERY_POINT,
                                    ProviderCapability.TEST_RECOVERY}),
            implementation_id="cloudstack-4.22.1.1-nas-selected-replica-v1",
            enabled=self._enabled,
        )

    def _validate_binding(self) -> None:
        self.site_pair.validate()
        DrPolicy.validate_selected_recovery_point(self.request, self.plan, self.point)
        identifier(self.request.operation_id)
        f = self.fixture
        require(self.point.kind is RecoveryPointKind.NATIVE_BACKUP
                and self.point.provider is ProviderFamily.CLOUDSTACK_NATIVE, "NATIVE_BACKUP_REQUIRED")
        require(self.point.application_consistent is False, "APPLICATION_CONSISTENCY_EVIDENCE_REQUIRED")
        require(self.request.operation_type in {OperationType.TEST_RECOVERY, OperationType.RECOVERY},
                "NATIVE_FAILOVER_NOT_IMPLEMENTED")
        require(self.site_pair.enabled is True and self.plan.site_pair_id == self.site_pair.id
                and self.request.site_pair_id == self.site_pair.id, "SITE_PAIR_DISABLED_OR_MISMATCH")
        require(self.site_pair.source_site_id == f["source_zone_id"]
                and self.site_pair.recovery_site_id == f["destination_zone_id"], "FIXTURE_SITE_MISMATCH")
        require(self.plan.workload_ids == (f["source_vm_id"],), "SINGLE_VM_PLAN_REQUIRED")
        require(self.request.recovery_group_id is None and self.plan.recovery_group_id is None,
                "RECOVERY_GROUP_EXECUTOR_REQUIRED")
        # The account/workload determine the lock, not an arbitrary caller key.
        require(self.request.lease_resource == "native-nas:" + f["account_id"] + ":" + f["source_vm_id"],
                "CANONICAL_WORKLOAD_LEASE_REQUIRED")
        require(callable(self.authorize) and callable(self.verify_repository_route), "TRUSTED_INTEGRATION_GUARDS_REQUIRED")
        if self.request.operation_type is OperationType.TEST_RECOVERY:
            require(callable(self.verify_test_isolation), "TEST_NETWORK_ISOLATION_VERIFIER_REQUIRED")
        labels = [label for label, item in f["points"].items() if item["backup_id"] == self.point.provider_reference]
        require(len(labels) == 1, "SELECTED_BACKUP_NOT_IN_FIXTURE")
        self.label = labels[0]

    def _authorize(self) -> None:
        self._validate_binding()
        DrPolicy.validate_provider(self.request, self.descriptor)
        require(self.authorize(self.request, self.plan, self.fixture) is True, "DR_OPERATION_UNAUTHORIZED")

    def _read_identity(self) -> BackupIdentity:
        f = self.fixture
        backup = self.native.one(self.api, "listBackups", "backup", self.point.provider_reference)
        self.native.owner_check(backup, f)
        require(backup.get("status") == "BackedUp"
                and backup.get("virtualmachineid") == f["source_vm_id"]
                and backup.get("zoneid") == f["source_zone_id"]
                and backup.get("backupofferingid") == f["offering_id"], "BACKUP_BINDING_CHANGED")
        volumes = backup.get("volumes")
        if isinstance(volumes, str):
            require(len(volumes) <= 65536, "VOLUME_METADATA_TOO_LARGE")
            volumes = json.loads(volumes)
        require(isinstance(volumes, list) and 1 <= len(volumes) <= 64, "BACKUP_DISKS_REQUIRED")
        disks = []
        for volume in volumes:
            require(isinstance(volume, dict) and type(volume.get("deviceId")) is int, "INVALID_VOLUME_METADATA")
            device = volume["deviceId"]
            expected_type = "ROOT" if device == 0 else "DATADISK"
            require(volume.get("type") == expected_type and isinstance(volume.get("path"), str), "INVALID_VOLUME_METADATA")
            disks.append(BackupDisk(device, volume.get("uuid"), expected_type.lower() + "." + volume["path"] + ".qcow2"))
        require({str(disk.device_id) for disk in disks} == set(f["points"][self.label]["disk_hashes"]),
                "BACKUP_DISK_MEMBERSHIP_CHANGED")
        created = datetime.datetime.strptime(backup["created"], "%Y-%m-%dT%H:%M:%S%z")
        identity = BackupIdentity(
            plan_id=self.plan.id, account_id=f["account_id"], domain_id=f["domain_id"],
            workload_id=f["source_vm_id"], source_site_id=f["source_zone_id"],
            recovery_site_id=f["destination_zone_id"], repository_id=f["repository_id"],
            offering_id=f["offering_id"], backup_id=self.point.provider_reference,
            external_id=backup.get("externalid"), captured_at_epoch=int(created.timestamp()),
            disks=tuple(sorted(disks, key=lambda disk: disk.device_id)),
        )
        identity.validate()
        require(identity.captured_at_epoch == self.point.created_at_epoch, "RECOVERY_POINT_TIMESTAMP_MISMATCH")
        return identity

    def _replication_guard(self, expected: BackupIdentity) -> None:
        self._authorize()
        require(self._read_identity() == expected, "BACKUP_METADATA_CHANGED")

    def replicate(self) -> dict:
        """Explicitly copy this selected completed backup; never create a backup."""
        self._authorize()
        self.native.preflight(self.api, self.fixture)
        identity = self._read_identity()
        return self.replicator.replicate(identity, guard=self._replication_guard)

    def preflight(self) -> dict:
        self._authorize()
        self.native.preflight(self.api, self.fixture)
        identity = self._read_identity()
        receipt = self.replicator.verify(identity)
        self._replication_guard(identity)
        require(self.verify_repository_route(self.request, identity, receipt) is True,
                "DR_LOCAL_REPOSITORY_ROUTE_UNVERIFIED")
        self._check_test_isolation()
        return receipt

    def _check_test_isolation(self) -> None:
        if self.request.operation_type is OperationType.TEST_RECOVERY:
            require(self.verify_test_isolation(self.request, self.fixture) is True,
                    "TEST_NETWORK_ISOLATION_UNVERIFIED")

    @contextlib.contextmanager
    def _journal(self, *, create: bool) -> Iterator:
        root = self.journal_root
        require(root.is_absolute() and root.resolve() == root and root.is_dir(), "PRIVATE_JOURNAL_ROOT_REQUIRED")
        info = root.stat()
        require(info.st_uid == os.geteuid() and not info.st_mode & 0o077, "PRIVATE_JOURNAL_ROOT_REQUIRED")
        folder = root / self.request.operation_id
        if create:
            try:
                folder.mkdir(mode=0o700)
                fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except FileExistsError:
                pass
        else:
            require(folder.is_dir() and not folder.is_symlink() and (folder / "journal.json").is_file(),
                    "SUBMISSION_JOURNAL_MISSING_NO_REPLAY")
        binding = {"fixture": self.fixture, "request_fingerprint": request_fingerprint(self.request),
                   "plan": asdict(self.plan), "site_pair": asdict(self.site_pair), "point": asdict(self.point)}
        # The native journal uses JSON; enums in these records are str subclasses.
        journal = self.native.Journal(folder, binding, self.api.endpoint)
        try:
            yield journal
        finally:
            journal.close()

    def submit(self, request: RecoveryRequest, recovery_point: RecoveryPoint | None) -> str:
        require(request == self.request and recovery_point == self.point, "BOUND_REQUEST_MISMATCH")
        require(callable(self._mutation_guard), "COORDINATOR_LEASE_REQUIRED")
        receipt = self._prepared_receipt or self.preflight()
        require(0 <= int(time.time()) - receipt["verified_at_epoch"] <= 300, "REPLICA_VERIFICATION_EXPIRED")
        require(receipt["identity"] == self._read_identity().payload(), "BACKUP_METADATA_CHANGED")
        f = self.fixture
        name = "dr-" + self.request.operation_id + "-" + self.label
        params = {"backupid": self.point.provider_reference, "zoneid": f["destination_zone_id"],
                  "networkids": ",".join(mapping["destination"] for mapping in f["network_map"]),
                  "account": f["account"], "domainid": f["domain_id"], "name": name,
                  "templateid": f["template_id"], "serviceofferingid": f["service_offering_id"],
                  "startvm": "false", "preserveip": "false"}

        def guarded_api(command, **values):
            if command == "createVMFromBackup":
                require(values == params, "NATIVE_MUTATION_PARAMETER_MISMATCH")
                self._authorize()
                self._check_test_isolation()
                self._mutation_guard()
            else:
                require(command == "queryAsyncJobResult", "UNEXPECTED_NATIVE_API_COMMAND")
            return self.api(command, **values)

        with self._journal(create=True) as journal:
            binding = {"manifest_sha256": receipt["manifest_sha256"], "identity": receipt["identity"]}
            previous = journal.data.get("replica")
            require(previous is None or previous == binding, "REPLICA_JOURNAL_BINDING_MISMATCH")
            journal.data["replica"] = binding
            journal.save()
            # Reuse the authoritative intent/async implementation. It fails closed
            # if an earlier call may have been submitted without receiving a job ID.
            self.native.submit_once(guarded_api, journal, "selected", "createVMFromBackup", params, True)
        return self.request.operation_id

    def reconcile(self, provider_operation_reference: str) -> str:
        """Only query the recorded job/clone. Never resubmit or start a VM."""
        require(provider_operation_reference == self.request.operation_id, "PROVIDER_REFERENCE_MISMATCH")
        self._authorize()
        with self._journal(create=False) as journal:
            operation = journal.data["operations"].get("selected")
            require(operation is not None and operation.get("command") == "createVMFromBackup"
                    and operation.get("params", {}).get("backupid") == self.point.provider_reference,
                    "RECORDED_NATIVE_OPERATION_MISSING_OR_MISMATCH")
            if operation.get("state") == "FAILED":
                return "FAILED"
            # Always refresh even a previously completed journal result, so a
            # replaced/deleted clone is not treated as a current success.
            if operation.get("state") != "COMPLETE":
                try:
                    status = self.native.reconcile(self.api, operation, journal)
                except self.native.GateError:
                    if operation.get("state") == "FAILED":
                        return "FAILED"
                    raise
                if status == "PENDING":
                    return "PENDING"
            self.native.vm_check(self.api, operation["vm_id"], operation["params"]["name"], self.fixture)
            return "COMPLETE"

    def evidence(self) -> dict:
        self._authorize()
        with self._journal(create=False) as journal:
            operation = journal.data["operations"].get("selected", {})
            return {"provider_operation_reference": self.request.operation_id,
                    "backup_id": self.point.provider_reference, "job_id": operation.get("job_id"),
                    "vm_id": operation.get("vm_id"), "provider_state": operation.get("state", "UNKNOWN"),
                    "replica_manifest_sha256": journal.data.get("replica", {}).get("manifest_sha256"),
                    "guest_data": "NOT_TESTED", "application": "NOT_TESTED", "e2e": "NOT_TESTED"}


class NativeRecoveryCoordinator:
    """Drive existing durable states up to a verified stopped native clone.

    Completion requires an application/recovery integration that is outside
    native clone creation. This coordinator cannot switch traffic, fence,
    promote, fail back or advance automatic failover.
    """

    def __init__(self, store: DurableDrStore, provider: NativeNasRecoveryProvider):
        self.store, self.provider = store, provider

    def advance(self) -> dict:
        p, store = self.provider, self.store
        p._authorize()
        request = p.request
        record = store.begin_operation(request)
        if record.state in {OperationState.COMPLETED, OperationState.BLOCKED, OperationState.FAILED}:
            return {"state": record.state.value, "operation_id": record.operation_id}
        if record.state is OperationState.RECONCILIATION_REQUIRED:
            # Read-only provider evidence can help an operator. No transition or
            # fresh lease authorizes replay from this terminal safety state.
            return {"state": record.state.value, "provider_state": p.reconcile(request.operation_id),
                    "operation_id": request.operation_id, "evidence": p.evidence()}
        # Hashing large immutable replicas happens before the short mutation lease.
        # Reconciliation never requires a new source copy or another submission.
        if record.state in {OperationState.REQUESTED, OperationState.LEASE_ACQUIRED, OperationState.PRECHECKED}:
            p._prepared_receipt = p.preflight()
        lease = store.acquire_lease(request.lease_resource, request.operation_id, 300, actor=request.requested_by)

        def guard():
            store.assert_lease(request.operation_id, lease.token)

        def move(state: OperationState, **extra):
            return store.transition(request.operation_id, state, actor=request.requested_by,
                                    lease_token=lease.token, **extra)

        p._mutation_guard = guard
        try:
            record = store.get_operation(request.operation_id)
            if record.state is OperationState.LEASE_ACQUIRED:
                record = move(OperationState.PRECHECKED)
            if record.state is OperationState.PRECHECKED:
                move(OperationState.MUTATION_SUBMITTED, event_type="NATIVE_SUBMISSION_INTENT",
                     details={"provider_operation_reference": request.operation_id,
                              "backup_id": p.point.provider_reference})
                try:
                    p.submit(request, p.point)
                except Exception:
                    # The authoritative native journal retains any actual job ID.
                    # Do not expose provider exception text or replay the mutation.
                    store.mark_ambiguous_mutation(request.operation_id, actor=request.requested_by,
                                                 lease_token=lease.token,
                                                 provider_operation_reference=request.operation_id,
                                                 reason="Inspect native journal and exact async job; no automatic replay")
                    raise ValidationError("NATIVE_SUBMISSION_RECONCILIATION_REQUIRED") from None
            record = store.get_operation(request.operation_id)
            if record.state in {OperationState.MUTATION_SUBMITTED, OperationState.MUTATION_PENDING}:
                try:
                    state = p.reconcile(request.operation_id)
                except Exception:
                    # Transport/query uncertainty is not a failed create. Preserve
                    # the durable pending state for read-only reconciliation.
                    return {"state": record.state.value, "operation_id": request.operation_id,
                            "provider_state": "UNKNOWN", "retry": "QUERY_ONLY"}
                if state == "PENDING":
                    if record.state is OperationState.MUTATION_SUBMITTED:
                        record = move(OperationState.MUTATION_PENDING, details=p.evidence())
                elif state == "FAILED":
                    record = move(OperationState.FAILED, error_code="NATIVE_ASYNC_FAILED", details=p.evidence())
                elif state == "COMPLETE":
                    record = move(OperationState.VALIDATING_DESTINATION, details=p.evidence())
                else:
                    raise ValidationError("INVALID_NATIVE_PROVIDER_STATE")
            return {"state": record.state.value, "operation_id": request.operation_id,
                    "evidence": p.evidence(), "next_gate": "DESTINATION_AND_GUEST_APPLICATION_VALIDATION"}
        finally:
            p._mutation_guard = None
            p._prepared_receipt = None
            # Expired leases must not be silently reacquired simply for cleanup.
            # They naturally expire; valid leases can be safely released.
            from dr_state_machine import LeaseRequired
            try:
                store.release_lease(request.lease_resource, request.operation_id, lease.token,
                                    actor=request.requested_by)
            except LeaseRequired:
                pass
