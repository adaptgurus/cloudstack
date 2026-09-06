#!/usr/bin/env python3
"""Provider-neutral LayerSentry DR state, journal, lease and safety contracts.

Status: NOT_TESTED.

This module is intentionally source-only. It does not start a scheduler, call a
replication provider, mutate CloudStack core database/API contracts, switch
traffic, fence a source, or execute failover by itself. It provides the durable
control-plane primitives required for later DR orchestration while preserving
provider implementations behind capability contracts.

The existing native CloudStack backup/recovery adapter remains the authoritative
implementation for ``createVMFromBackup`` recovery. This module does not
reimplement that API path; callers integrate it through ``RecoveryProvider``.

Safety invariants:
* recovery workflows that consume a recovery point must name it explicitly;
* idempotency keys are bound to an immutable request fingerprint;
* post-lease state changes require the matching live exclusive lease;
* ambiguous provider mutation outcomes become RECONCILIATION_REQUIRED and are
  never silently replayed by this state machine;
* automatic failover is fail-closed unless witness/quorum, source fencing,
  no-dual-writer proof, safe provider promotion, destination/application
  validation and traffic-switch readiness are all proven at the required stage;
* provider-specific low-RPO implementations are capability-gated.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Optional, Protocol, Sequence


class DrError(RuntimeError):
    """Base error for DR control-plane contracts."""


class ValidationError(DrError):
    """A DR object or request violates a control-plane invariant."""


class StateTransitionError(DrError):
    """The requested durable operation-state transition is invalid."""


class IdempotencyConflict(DrError):
    """An idempotency key was reused with a different immutable request."""


class LeaseConflict(DrError):
    """An exclusive lease is currently owned by another operation."""


class LeaseRequired(DrError):
    """A mutating transition was attempted without the matching live lease."""


class CapabilityError(DrError):
    """The selected provider does not advertise a required capability."""


class AutoFailoverIneligible(DrError):
    """Automatic failover was requested without every mandatory safety proof."""


class OperationType(str, Enum):
    TEST_RECOVERY = "TEST_RECOVERY"
    RECOVERY = "RECOVERY"
    PLANNED_FAILOVER = "PLANNED_FAILOVER"
    FAILBACK = "FAILBACK"
    AUTO_FAILOVER = "AUTO_FAILOVER"


class OperationState(str, Enum):
    REQUESTED = "REQUESTED"
    LEASE_ACQUIRED = "LEASE_ACQUIRED"
    PRECHECKED = "PRECHECKED"
    MUTATION_SUBMITTED = "MUTATION_SUBMITTED"
    MUTATION_PENDING = "MUTATION_PENDING"
    VALIDATING_DESTINATION = "VALIDATING_DESTINATION"
    VALIDATING_APPLICATION = "VALIDATING_APPLICATION"
    TRAFFIC_SWITCH_PENDING = "TRAFFIC_SWITCH_PENDING"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


class RecoveryPointKind(str, Enum):
    NATIVE_BACKUP = "NATIVE_BACKUP"
    HOT_REPLICA = "HOT_REPLICA"


class ProviderFamily(str, Enum):
    CLOUDSTACK_NATIVE = "CLOUDSTACK_NATIVE"
    LINSTOR_DRBD = "LINSTOR_DRBD"
    CEPH_RBD = "CEPH_RBD"
    SAN_ARRAY = "SAN_ARRAY"
    LIBVIRT_BACKUP = "LIBVIRT_BACKUP"


class ProviderCapability(str, Enum):
    SELECTED_RECOVERY_POINT = "SELECTED_RECOVERY_POINT"
    TEST_RECOVERY = "TEST_RECOVERY"
    HOT_REPLICATION = "HOT_REPLICATION"
    PLANNED_FAILOVER = "PLANNED_FAILOVER"
    REVERSE_REPLICATION = "REVERSE_REPLICATION"
    FAILBACK = "FAILBACK"
    SAFE_PROMOTION = "SAFE_PROMOTION"
    SOURCE_FENCING = "SOURCE_FENCING"
    NO_DUAL_WRITER_PROOF = "NO_DUAL_WRITER_PROOF"
    DESTINATION_VALIDATION = "DESTINATION_VALIDATION"
    APPLICATION_VALIDATION = "APPLICATION_VALIDATION"
    CONSISTENCY_GROUPS = "CONSISTENCY_GROUPS"
    TRAFFIC_SWITCH = "TRAFFIC_SWITCH"


@dataclass(frozen=True)
class SitePair:
    id: str
    source_site_id: str
    recovery_site_id: str
    enabled: bool = True

    def validate(self) -> None:
        _require_values(self.id, self.source_site_id, self.recovery_site_id)
        if self.source_site_id == self.recovery_site_id:
            raise ValidationError("source and recovery sites must be different")


@dataclass(frozen=True)
class NetworkMapping:
    id: str
    site_pair_id: str
    source_network_id: str
    recovery_network_id: str

    def validate(self) -> None:
        _require_values(
            self.id,
            self.site_pair_id,
            self.source_network_id,
            self.recovery_network_id,
        )
        if self.source_network_id == self.recovery_network_id:
            raise ValidationError("source and recovery networks must be different")


@dataclass(frozen=True)
class IpMapping:
    id: str
    site_pair_id: str
    source_address: str
    recovery_address: str
    mode: str = "STATIC"

    def validate(self) -> None:
        _require_values(
            self.id, self.site_pair_id, self.source_address, self.recovery_address
        )
        if self.mode not in {"STATIC", "RESERVE", "REMAP"}:
            raise ValidationError(f"unsupported IP mapping mode: {self.mode}")


@dataclass(frozen=True)
class RecoveryGroup:
    id: str
    name: str
    ordered_workload_ids: tuple[str, ...]

    def validate(self) -> None:
        _require_values(self.id, self.name)
        if not self.ordered_workload_ids:
            raise ValidationError("a recovery group requires at least one workload")
        if any(not value.strip() for value in self.ordered_workload_ids):
            raise ValidationError("recovery group workload IDs must be non-empty")
        if len(set(self.ordered_workload_ids)) != len(self.ordered_workload_ids):
            raise ValidationError("a recovery group cannot contain duplicate workloads")


@dataclass(frozen=True)
class ProtectionPlan:
    id: str
    site_pair_id: str
    provider: ProviderFamily
    workload_ids: tuple[str, ...]
    recovery_group_id: Optional[str] = None
    network_mapping_ids: tuple[str, ...] = ()
    ip_mapping_ids: tuple[str, ...] = ()
    automatic_failover_enabled: bool = False

    def validate(self) -> None:
        _require_values(self.id, self.site_pair_id)
        if not self.workload_ids or any(not value.strip() for value in self.workload_ids):
            raise ValidationError("a protection plan requires non-empty workload IDs")
        if len(set(self.workload_ids)) != len(self.workload_ids):
            raise ValidationError("duplicate workload IDs are not allowed")


@dataclass(frozen=True)
class RecoveryPoint:
    id: str
    protection_plan_id: str
    provider: ProviderFamily
    kind: RecoveryPointKind
    provider_reference: str
    created_at_epoch: int
    application_consistent: bool = False

    def validate(self) -> None:
        _require_values(self.id, self.protection_plan_id, self.provider_reference)
        if self.created_at_epoch <= 0:
            raise ValidationError("recovery point creation time must be positive")


@dataclass(frozen=True)
class ProviderDescriptor:
    family: ProviderFamily
    capabilities: frozenset[ProviderCapability]
    implementation_id: str
    enabled: bool = False

    def validate(self) -> None:
        _require_values(self.implementation_id)

    def require(self, required: Iterable[ProviderCapability]) -> None:
        if not self.enabled:
            raise CapabilityError(
                f"provider {self.family.value} is not enabled for DR orchestration"
            )
        missing = sorted(
            capability.value for capability in set(required) - set(self.capabilities)
        )
        if missing:
            raise CapabilityError(
                f"provider {self.family.value} lacks required capabilities: "
                + ", ".join(missing)
            )


@dataclass(frozen=True)
class RecoveryRequest:
    operation_id: str
    idempotency_key: str
    operation_type: OperationType
    site_pair_id: str
    protection_plan_id: str
    provider: ProviderFamily
    lease_resource: str
    requested_by: str
    recovery_point_id: Optional[str] = None
    recovery_group_id: Optional[str] = None
    isolated_test_network: bool = False

    def validate(self) -> None:
        _require_values(
            self.operation_id,
            self.idempotency_key,
            self.site_pair_id,
            self.protection_plan_id,
            self.lease_resource,
            self.requested_by,
        )
        if self.operation_type in {
            OperationType.TEST_RECOVERY,
            OperationType.RECOVERY,
            OperationType.FAILBACK,
        } and not self.recovery_point_id:
            raise ValidationError(
                f"{self.operation_type.value} requires an explicit recovery_point_id"
            )
        if self.operation_type is OperationType.TEST_RECOVERY and not self.isolated_test_network:
            raise ValidationError("test recovery must use an isolated test network")
        if self.operation_type is OperationType.AUTO_FAILOVER and self.isolated_test_network:
            raise ValidationError("automatic failover cannot target an isolated test network")


@dataclass(frozen=True)
class AutoFailoverProof:
    """Stage evidence. Booleans must represent independently verified evidence."""

    witness_quorum: bool = False
    source_fenced: bool = False
    no_dual_writer: bool = False
    provider_safe_promotion: bool = False
    destination_validated: bool = False
    application_validated: bool = False
    traffic_switch_ready: bool = False


@dataclass(frozen=True)
class OperationRecord:
    operation_id: str
    idempotency_key: str
    request_fingerprint: str
    operation_type: OperationType
    state: OperationState
    provider: ProviderFamily
    site_pair_id: str
    protection_plan_id: str
    recovery_group_id: Optional[str]
    recovery_point_id: Optional[str]
    lease_resource: str
    requested_by: str
    created_at_epoch: int
    updated_at_epoch: int
    error_code: Optional[str]
    error_message: Optional[str]


@dataclass(frozen=True)
class LeaseRecord:
    resource_key: str
    operation_id: str
    token: str
    expires_at_epoch: int
    updated_at_epoch: int


@dataclass(frozen=True)
class JournalEvent:
    sequence: int
    operation_id: str
    state: OperationState
    event_type: str
    actor: str
    details: Mapping[str, Any]
    created_at_epoch: int


class RecoveryProvider(Protocol):
    """Capability-gated provider contract; provider implementations live elsewhere."""

    @property
    def descriptor(self) -> ProviderDescriptor:
        ...

    def submit(self, request: RecoveryRequest, recovery_point: Optional[RecoveryPoint]) -> str:
        """Submit one provider mutation and return its provider-operation reference."""
        ...

    def reconcile(self, provider_operation_reference: str) -> str:
        """Read provider state without blindly replaying an ambiguous mutation."""
        ...


_REQUIRED_CAPABILITIES: dict[OperationType, frozenset[ProviderCapability]] = {
    OperationType.TEST_RECOVERY: frozenset(
        {ProviderCapability.SELECTED_RECOVERY_POINT, ProviderCapability.TEST_RECOVERY}
    ),
    OperationType.RECOVERY: frozenset({ProviderCapability.SELECTED_RECOVERY_POINT}),
    OperationType.PLANNED_FAILOVER: frozenset(
        {
            ProviderCapability.PLANNED_FAILOVER,
            ProviderCapability.SAFE_PROMOTION,
            ProviderCapability.SOURCE_FENCING,
            ProviderCapability.NO_DUAL_WRITER_PROOF,
            ProviderCapability.DESTINATION_VALIDATION,
            ProviderCapability.APPLICATION_VALIDATION,
        }
    ),
    OperationType.FAILBACK: frozenset(
        {
            ProviderCapability.FAILBACK,
            ProviderCapability.REVERSE_REPLICATION,
            ProviderCapability.SAFE_PROMOTION,
            ProviderCapability.SOURCE_FENCING,
            ProviderCapability.NO_DUAL_WRITER_PROOF,
            ProviderCapability.DESTINATION_VALIDATION,
            ProviderCapability.APPLICATION_VALIDATION,
        }
    ),
    OperationType.AUTO_FAILOVER: frozenset(
        {
            ProviderCapability.SAFE_PROMOTION,
            ProviderCapability.SOURCE_FENCING,
            ProviderCapability.NO_DUAL_WRITER_PROOF,
            ProviderCapability.DESTINATION_VALIDATION,
            ProviderCapability.APPLICATION_VALIDATION,
            ProviderCapability.TRAFFIC_SWITCH,
        }
    ),
}


_ALLOWED_TRANSITIONS: dict[OperationState, frozenset[OperationState]] = {
    OperationState.REQUESTED: frozenset({OperationState.BLOCKED, OperationState.FAILED}),
    OperationState.LEASE_ACQUIRED: frozenset(
        {OperationState.PRECHECKED, OperationState.BLOCKED, OperationState.FAILED}
    ),
    OperationState.PRECHECKED: frozenset(
        {OperationState.MUTATION_SUBMITTED, OperationState.BLOCKED, OperationState.FAILED}
    ),
    OperationState.MUTATION_SUBMITTED: frozenset(
        {
            OperationState.MUTATION_PENDING,
            OperationState.VALIDATING_DESTINATION,
            OperationState.RECONCILIATION_REQUIRED,
            OperationState.FAILED,
        }
    ),
    OperationState.MUTATION_PENDING: frozenset(
        {
            OperationState.VALIDATING_DESTINATION,
            OperationState.RECONCILIATION_REQUIRED,
            OperationState.FAILED,
        }
    ),
    OperationState.VALIDATING_DESTINATION: frozenset(
        {
            OperationState.VALIDATING_APPLICATION,
            OperationState.BLOCKED,
            OperationState.FAILED,
        }
    ),
    OperationState.VALIDATING_APPLICATION: frozenset(
        {
            OperationState.TRAFFIC_SWITCH_PENDING,
            OperationState.COMPLETED,
            OperationState.BLOCKED,
            OperationState.FAILED,
        }
    ),
    OperationState.TRAFFIC_SWITCH_PENDING: frozenset(
        {
            OperationState.COMPLETED,
            OperationState.RECONCILIATION_REQUIRED,
            OperationState.FAILED,
        }
    ),
    OperationState.COMPLETED: frozenset(),
    OperationState.BLOCKED: frozenset(),
    OperationState.FAILED: frozenset(),
    OperationState.RECONCILIATION_REQUIRED: frozenset(),
}

_TERMINAL_STATES = frozenset(
    {
        OperationState.COMPLETED,
        OperationState.BLOCKED,
        OperationState.FAILED,
        OperationState.RECONCILIATION_REQUIRED,
    }
)


class DrPolicy:
    """Pure validation helpers; no provider mutation or scheduling side effects."""

    @staticmethod
    def required_capabilities(operation_type: OperationType) -> frozenset[ProviderCapability]:
        return _REQUIRED_CAPABILITIES[operation_type]

    @classmethod
    def validate_provider(cls, request: RecoveryRequest, provider: ProviderDescriptor) -> None:
        request.validate()
        provider.validate()
        if request.provider is not provider.family:
            raise CapabilityError(
                f"request provider {request.provider.value} does not match "
                f"descriptor {provider.family.value}"
            )
        provider.require(cls.required_capabilities(request.operation_type))

    @staticmethod
    def validate_selected_recovery_point(
        request: RecoveryRequest,
        plan: ProtectionPlan,
        recovery_point: Optional[RecoveryPoint],
    ) -> None:
        request.validate()
        plan.validate()
        if request.protection_plan_id != plan.id:
            raise ValidationError("request protection plan does not match supplied plan")
        if request.provider is not plan.provider:
            raise ValidationError("request provider does not match protection plan provider")
        if request.recovery_point_id is None:
            return
        if recovery_point is None:
            raise ValidationError("explicit recovery_point_id has no matching recovery point")
        recovery_point.validate()
        if recovery_point.id != request.recovery_point_id:
            raise ValidationError("supplied recovery point does not match selected ID")
        if recovery_point.protection_plan_id != plan.id:
            raise ValidationError("recovery point belongs to a different protection plan")
        if recovery_point.provider is not plan.provider:
            raise ValidationError("recovery point provider differs from protection plan provider")

    @classmethod
    def validate_auto_failover_plan(
        cls,
        record: OperationRecord,
        plan: ProtectionPlan,
        provider: ProviderDescriptor,
    ) -> None:
        if record.operation_type is not OperationType.AUTO_FAILOVER:
            raise ValidationError("automatic-failover policy used for a non-auto operation")
        plan.validate()
        provider.validate()
        if not plan.automatic_failover_enabled:
            raise AutoFailoverIneligible("protection plan has automatic failover disabled")
        if record.protection_plan_id != plan.id or record.site_pair_id != plan.site_pair_id:
            raise AutoFailoverIneligible("operation does not match the protection plan/site pair")
        if record.provider is not plan.provider or record.provider is not provider.family:
            raise AutoFailoverIneligible("operation, plan and provider families do not match")
        provider.require(cls.required_capabilities(OperationType.AUTO_FAILOVER))

    @staticmethod
    def auto_failover_blockers(
        target_state: OperationState,
        proof: AutoFailoverProof,
    ) -> tuple[str, ...]:
        required: list[tuple[str, bool]] = []
        if target_state in {
            OperationState.PRECHECKED,
            OperationState.MUTATION_SUBMITTED,
            OperationState.MUTATION_PENDING,
            OperationState.VALIDATING_DESTINATION,
            OperationState.VALIDATING_APPLICATION,
            OperationState.TRAFFIC_SWITCH_PENDING,
            OperationState.COMPLETED,
        }:
            required.extend(
                [
                    ("witness/quorum not proven", proof.witness_quorum),
                    ("source fencing not proven", proof.source_fenced),
                    ("no-dual-writer proof missing", proof.no_dual_writer),
                ]
            )
        if target_state in {
            OperationState.VALIDATING_DESTINATION,
            OperationState.VALIDATING_APPLICATION,
            OperationState.TRAFFIC_SWITCH_PENDING,
            OperationState.COMPLETED,
        }:
            required.append(
                ("provider-safe promotion not proven", proof.provider_safe_promotion)
            )
        if target_state in {
            OperationState.VALIDATING_APPLICATION,
            OperationState.TRAFFIC_SWITCH_PENDING,
            OperationState.COMPLETED,
        }:
            required.append(("destination validation missing", proof.destination_validated))
        if target_state in {
            OperationState.TRAFFIC_SWITCH_PENDING,
            OperationState.COMPLETED,
        }:
            required.append(("application validation missing", proof.application_validated))
            required.append(("traffic switch readiness not proven", proof.traffic_switch_ready))
        return tuple(message for message, passed in required if not passed)


class DurableDrStore:
    """SQLite-backed durable source primitive for LayerSentry DR state.

    The database is LayerSentry-owned and must not point at or modify CloudStack
    core tables. Distributed production deployment still requires an approved
    shared/transactional backend and runtime validation; this source is not a
    production certification claim.
    """

    def __init__(self, database_path: str) -> None:
        if not database_path or not database_path.strip():
            raise ValidationError("database_path is required")
        self._database_path = database_path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def initialize(self) -> None:
        schema = """
        CREATE TABLE IF NOT EXISTS dr_objects (
            object_type TEXT NOT NULL,
            object_id TEXT NOT NULL,
            revision INTEGER NOT NULL,
            payload_json TEXT NOT NULL,
            updated_at_epoch INTEGER NOT NULL,
            PRIMARY KEY (object_type, object_id)
        );

        CREATE TABLE IF NOT EXISTS dr_operations (
            operation_id TEXT PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            request_fingerprint TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            state TEXT NOT NULL,
            provider TEXT NOT NULL,
            site_pair_id TEXT NOT NULL,
            protection_plan_id TEXT NOT NULL,
            recovery_group_id TEXT,
            recovery_point_id TEXT,
            lease_resource TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL,
            updated_at_epoch INTEGER NOT NULL,
            error_code TEXT,
            error_message TEXT
        );

        CREATE TABLE IF NOT EXISTS dr_operation_journal (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            operation_id TEXT NOT NULL,
            state TEXT NOT NULL,
            event_type TEXT NOT NULL,
            actor TEXT NOT NULL,
            details_json TEXT NOT NULL,
            created_at_epoch INTEGER NOT NULL,
            FOREIGN KEY (operation_id) REFERENCES dr_operations(operation_id)
        );

        CREATE INDEX IF NOT EXISTS dr_operation_journal_operation_idx
            ON dr_operation_journal(operation_id, sequence);

        CREATE TABLE IF NOT EXISTS dr_leases (
            resource_key TEXT PRIMARY KEY,
            operation_id TEXT NOT NULL,
            token TEXT NOT NULL,
            expires_at_epoch INTEGER NOT NULL,
            updated_at_epoch INTEGER NOT NULL,
            FOREIGN KEY (operation_id) REFERENCES dr_operations(operation_id)
        );
        """
        with self._connect() as connection:
            connection.executescript(schema)

    def put_object(self, object_type: str, object_id: str, payload: Any) -> int:
        _require_values(object_type, object_id)
        payload_json = _canonical_json(payload)
        now = _epoch_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT revision FROM dr_objects WHERE object_type=? AND object_id=?",
                (object_type, object_id),
            ).fetchone()
            revision = 1 if row is None else int(row["revision"]) + 1
            connection.execute(
                """
                INSERT INTO dr_objects(object_type, object_id, revision, payload_json, updated_at_epoch)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(object_type, object_id) DO UPDATE SET
                    revision=excluded.revision,
                    payload_json=excluded.payload_json,
                    updated_at_epoch=excluded.updated_at_epoch
                """,
                (object_type, object_id, revision, payload_json, now),
            )
            connection.commit()
            return revision
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_object(self, object_type: str, object_id: str) -> Optional[Mapping[str, Any]]:
        _require_values(object_type, object_id)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT revision, payload_json, updated_at_epoch
                FROM dr_objects WHERE object_type=? AND object_id=?
                """,
                (object_type, object_id),
            ).fetchone()
        if row is None:
            return None
        return {
            "revision": int(row["revision"]),
            "payload": json.loads(str(row["payload_json"])),
            "updated_at_epoch": int(row["updated_at_epoch"]),
        }

    def begin_operation(self, request: RecoveryRequest) -> OperationRecord:
        request.validate()
        fingerprint = request_fingerprint(request)
        now = _epoch_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM dr_operations WHERE idempotency_key=?",
                (request.idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing["request_fingerprint"] != fingerprint:
                    raise IdempotencyConflict(
                        "idempotency key already belongs to a different immutable request"
                    )
                connection.commit()
                return _operation_from_row(existing)

            if connection.execute(
                "SELECT 1 FROM dr_operations WHERE operation_id=?", (request.operation_id,)
            ).fetchone() is not None:
                raise IdempotencyConflict("operation_id already exists")

            connection.execute(
                """
                INSERT INTO dr_operations(
                    operation_id, idempotency_key, request_fingerprint,
                    operation_type, state, provider, site_pair_id,
                    protection_plan_id, recovery_group_id, recovery_point_id,
                    lease_resource, requested_by, created_at_epoch, updated_at_epoch
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request.operation_id,
                    request.idempotency_key,
                    fingerprint,
                    request.operation_type.value,
                    OperationState.REQUESTED.value,
                    request.provider.value,
                    request.site_pair_id,
                    request.protection_plan_id,
                    request.recovery_group_id,
                    request.recovery_point_id,
                    request.lease_resource,
                    request.requested_by,
                    now,
                    now,
                ),
            )
            self._append_journal_in_tx(
                connection,
                request.operation_id,
                OperationState.REQUESTED,
                "OPERATION_CREATED",
                request.requested_by,
                {"request_fingerprint": fingerprint},
                now,
            )
            row = connection.execute(
                "SELECT * FROM dr_operations WHERE operation_id=?", (request.operation_id,)
            ).fetchone()
            connection.commit()
            assert row is not None
            return _operation_from_row(row)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_operation(self, operation_id: str) -> Optional[OperationRecord]:
        _require_values(operation_id)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM dr_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
        return None if row is None else _operation_from_row(row)

    def acquire_lease(
        self,
        resource_key: str,
        operation_id: str,
        ttl_seconds: int,
        *,
        actor: str,
    ) -> LeaseRecord:
        _require_values(resource_key, operation_id, actor)
        if ttl_seconds <= 0:
            raise ValidationError("lease ttl_seconds must be positive")
        now = _epoch_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            operation = connection.execute(
                "SELECT state, lease_resource FROM dr_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if operation is None:
                raise ValidationError("cannot lease an unknown operation")
            current_state = OperationState(str(operation["state"]))
            if current_state in _TERMINAL_STATES:
                raise LeaseConflict(f"cannot lease terminal operation {current_state.value}")
            if operation["lease_resource"] != resource_key:
                raise ValidationError("lease resource differs from operation request")

            existing = connection.execute(
                "SELECT * FROM dr_leases WHERE resource_key=?", (resource_key,)
            ).fetchone()
            if existing is not None and int(existing["expires_at_epoch"]) > now:
                if existing["operation_id"] != operation_id:
                    raise LeaseConflict(
                        f"resource {resource_key} is leased by another operation"
                    )
                token = str(existing["token"])
            else:
                token = secrets.token_urlsafe(32)

            expires = now + ttl_seconds
            connection.execute(
                """
                INSERT INTO dr_leases(resource_key, operation_id, token, expires_at_epoch, updated_at_epoch)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(resource_key) DO UPDATE SET
                    operation_id=excluded.operation_id,
                    token=excluded.token,
                    expires_at_epoch=excluded.expires_at_epoch,
                    updated_at_epoch=excluded.updated_at_epoch
                """,
                (resource_key, operation_id, token, expires, now),
            )
            if current_state is OperationState.REQUESTED:
                connection.execute(
                    "UPDATE dr_operations SET state=?, updated_at_epoch=? WHERE operation_id=?",
                    (OperationState.LEASE_ACQUIRED.value, now, operation_id),
                )
                current_state = OperationState.LEASE_ACQUIRED
                event_type = "LEASE_ACQUIRED"
            else:
                event_type = "LEASE_RENEWED"
            self._append_journal_in_tx(
                connection,
                operation_id,
                current_state,
                event_type,
                actor,
                {"resource_key": resource_key, "expires_at_epoch": expires},
                now,
            )
            connection.commit()
            return LeaseRecord(resource_key, operation_id, token, expires, now)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def renew_lease(
        self,
        resource_key: str,
        operation_id: str,
        token: str,
        ttl_seconds: int,
        *,
        actor: str,
    ) -> LeaseRecord:
        _require_values(resource_key, operation_id, token, actor)
        if ttl_seconds <= 0:
            raise ValidationError("lease ttl_seconds must be positive")
        now = _epoch_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_lease_in_tx(connection, resource_key, operation_id, token, now)
            expires = now + ttl_seconds
            connection.execute(
                """
                UPDATE dr_leases SET expires_at_epoch=?, updated_at_epoch=?
                WHERE resource_key=? AND operation_id=? AND token=?
                """,
                (expires, now, resource_key, operation_id, token),
            )
            state_row = connection.execute(
                "SELECT state FROM dr_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            assert state_row is not None
            self._append_journal_in_tx(
                connection,
                operation_id,
                OperationState(str(state_row["state"])),
                "LEASE_RENEWED",
                actor,
                {"resource_key": resource_key, "expires_at_epoch": expires},
                now,
            )
            connection.commit()
            return LeaseRecord(resource_key, operation_id, token, expires, now)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def release_lease(
        self,
        resource_key: str,
        operation_id: str,
        token: str,
        *,
        actor: str,
    ) -> None:
        _require_values(resource_key, operation_id, token, actor)
        now = _epoch_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            self._assert_lease_in_tx(connection, resource_key, operation_id, token, now)
            state_row = connection.execute(
                "SELECT state FROM dr_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            assert state_row is not None
            connection.execute(
                "DELETE FROM dr_leases WHERE resource_key=? AND operation_id=? AND token=?",
                (resource_key, operation_id, token),
            )
            self._append_journal_in_tx(
                connection,
                operation_id,
                OperationState(str(state_row["state"])),
                "LEASE_RELEASED",
                actor,
                {"resource_key": resource_key},
                now,
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def assert_lease(self, operation_id: str, token: str) -> LeaseRecord:
        _require_values(operation_id, token)
        now = _epoch_now()
        with self._connect() as connection:
            operation = connection.execute(
                "SELECT lease_resource FROM dr_operations WHERE operation_id=?",
                (operation_id,),
            ).fetchone()
            if operation is None:
                raise LeaseRequired("operation does not exist")
            return self._assert_lease_in_tx(
                connection,
                str(operation["lease_resource"]),
                operation_id,
                token,
                now,
            )

    def transition(
        self,
        operation_id: str,
        new_state: OperationState,
        *,
        actor: str,
        lease_token: Optional[str] = None,
        event_type: str = "STATE_TRANSITION",
        details: Optional[Mapping[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> OperationRecord:
        """Advance a non-automatic operation.

        AUTO_FAILOVER cannot use this generic path beyond a pre-lease BLOCKED or
        FAILED decision; it must use ``transition_auto_failover`` so required
        evidence cannot be bypassed accidentally.
        """
        return self._transition(
            operation_id,
            new_state,
            actor=actor,
            lease_token=lease_token,
            event_type=event_type,
            details=details,
            error_code=error_code,
            error_message=error_message,
            auto_plan=None,
            auto_provider=None,
            auto_proof=None,
        )

    def transition_auto_failover(
        self,
        operation_id: str,
        new_state: OperationState,
        *,
        actor: str,
        lease_token: str,
        plan: ProtectionPlan,
        provider: ProviderDescriptor,
        proof: AutoFailoverProof,
        event_type: str = "AUTO_FAILOVER_STATE_TRANSITION",
        details: Optional[Mapping[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> OperationRecord:
        _require_values(lease_token)
        return self._transition(
            operation_id,
            new_state,
            actor=actor,
            lease_token=lease_token,
            event_type=event_type,
            details=details,
            error_code=error_code,
            error_message=error_message,
            auto_plan=plan,
            auto_provider=provider,
            auto_proof=proof,
        )

    def _transition(
        self,
        operation_id: str,
        new_state: OperationState,
        *,
        actor: str,
        lease_token: Optional[str],
        event_type: str,
        details: Optional[Mapping[str, Any]],
        error_code: Optional[str],
        error_message: Optional[str],
        auto_plan: Optional[ProtectionPlan],
        auto_provider: Optional[ProviderDescriptor],
        auto_proof: Optional[AutoFailoverProof],
    ) -> OperationRecord:
        _require_values(operation_id, actor, event_type)
        now = _epoch_now()
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM dr_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            if row is None:
                raise ValidationError("operation does not exist")
            record = _operation_from_row(row)
            current = record.state
            if new_state not in _ALLOWED_TRANSITIONS[current]:
                raise StateTransitionError(
                    f"invalid DR transition {current.value} -> {new_state.value}"
                )

            if current is not OperationState.REQUESTED:
                if not lease_token:
                    raise LeaseRequired(
                        f"transition from {current.value} requires the exclusive lease token"
                    )
                self._assert_lease_in_tx(
                    connection,
                    record.lease_resource,
                    operation_id,
                    lease_token,
                    now,
                )

            if record.operation_type is OperationType.AUTO_FAILOVER:
                if current is OperationState.REQUESTED and new_state in {
                    OperationState.BLOCKED,
                    OperationState.FAILED,
                }:
                    pass
                else:
                    if auto_plan is None or auto_provider is None or auto_proof is None:
                        raise AutoFailoverIneligible(
                            "automatic failover requires the dedicated evidence-gated transition path"
                        )
                    DrPolicy.validate_auto_failover_plan(record, auto_plan, auto_provider)
                    blockers = DrPolicy.auto_failover_blockers(new_state, auto_proof)
                    if blockers:
                        raise AutoFailoverIneligible("; ".join(blockers))
            elif any(value is not None for value in (auto_plan, auto_provider, auto_proof)):
                raise ValidationError("automatic-failover evidence supplied to non-auto operation")

            connection.execute(
                """
                UPDATE dr_operations
                SET state=?, updated_at_epoch=?, error_code=?, error_message=?
                WHERE operation_id=?
                """,
                (new_state.value, now, error_code, error_message, operation_id),
            )
            event_details: dict[str, Any] = dict(details or {})
            event_details["previous_state"] = current.value
            if error_code:
                event_details["error_code"] = error_code
            if record.operation_type is OperationType.AUTO_FAILOVER:
                event_details["auto_failover_evidence_gate"] = "PASSED"
            self._append_journal_in_tx(
                connection,
                operation_id,
                new_state,
                event_type,
                actor,
                event_details,
                now,
            )
            updated = connection.execute(
                "SELECT * FROM dr_operations WHERE operation_id=?", (operation_id,)
            ).fetchone()
            connection.commit()
            assert updated is not None
            return _operation_from_row(updated)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def mark_ambiguous_mutation(
        self,
        operation_id: str,
        *,
        actor: str,
        lease_token: str,
        provider_operation_reference: str,
        reason: str,
    ) -> OperationRecord:
        """Fail closed after an uncertain provider mutation; never replay it here."""
        _require_values(provider_operation_reference, reason)
        record = self.get_operation(operation_id)
        if record is None:
            raise ValidationError("operation does not exist")
        if record.operation_type is OperationType.AUTO_FAILOVER:
            raise AutoFailoverIneligible(
                "ambiguous auto-failover mutation requires explicit reconciliation; "
                "generic retry/transition is prohibited"
            )
        return self.transition(
            operation_id,
            OperationState.RECONCILIATION_REQUIRED,
            actor=actor,
            lease_token=lease_token,
            event_type="AMBIGUOUS_PROVIDER_MUTATION",
            details={
                "provider_operation_reference": provider_operation_reference,
                "retry_policy": "FAIL_CLOSED_NO_AUTOMATIC_REPLAY",
            },
            error_code="AMBIGUOUS_PROVIDER_MUTATION",
            error_message=reason,
        )

    def list_journal(self, operation_id: str) -> Sequence[JournalEvent]:
        _require_values(operation_id)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT sequence, operation_id, state, event_type, actor,
                       details_json, created_at_epoch
                FROM dr_operation_journal
                WHERE operation_id=? ORDER BY sequence ASC
                """,
                (operation_id,),
            ).fetchall()
        return tuple(
            JournalEvent(
                sequence=int(row["sequence"]),
                operation_id=str(row["operation_id"]),
                state=OperationState(str(row["state"])),
                event_type=str(row["event_type"]),
                actor=str(row["actor"]),
                details=json.loads(str(row["details_json"])),
                created_at_epoch=int(row["created_at_epoch"]),
            )
            for row in rows
        )

    def _assert_lease_in_tx(
        self,
        connection: sqlite3.Connection,
        resource_key: str,
        operation_id: str,
        token: str,
        now: int,
    ) -> LeaseRecord:
        row = connection.execute(
            """
            SELECT resource_key, operation_id, token, expires_at_epoch, updated_at_epoch
            FROM dr_leases WHERE resource_key=?
            """,
            (resource_key,),
        ).fetchone()
        if row is None:
            raise LeaseRequired("no exclusive lease exists for the operation resource")
        if row["operation_id"] != operation_id or not secrets.compare_digest(
            str(row["token"]), token
        ):
            raise LeaseRequired("exclusive lease is owned by a different operation/token")
        if int(row["expires_at_epoch"]) <= now:
            raise LeaseRequired("exclusive lease has expired")
        return LeaseRecord(
            resource_key=str(row["resource_key"]),
            operation_id=str(row["operation_id"]),
            token=str(row["token"]),
            expires_at_epoch=int(row["expires_at_epoch"]),
            updated_at_epoch=int(row["updated_at_epoch"]),
        )

    @staticmethod
    def _append_journal_in_tx(
        connection: sqlite3.Connection,
        operation_id: str,
        state: OperationState,
        event_type: str,
        actor: str,
        details: Mapping[str, Any],
        now: int,
    ) -> None:
        connection.execute(
            """
            INSERT INTO dr_operation_journal(
                operation_id, state, event_type, actor, details_json, created_at_epoch
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (operation_id, state.value, event_type, actor, _canonical_json(details), now),
        )


def request_fingerprint(request: RecoveryRequest) -> str:
    request.validate()
    canonical = _canonical_json(request)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _operation_from_row(row: sqlite3.Row) -> OperationRecord:
    return OperationRecord(
        operation_id=str(row["operation_id"]),
        idempotency_key=str(row["idempotency_key"]),
        request_fingerprint=str(row["request_fingerprint"]),
        operation_type=OperationType(str(row["operation_type"])),
        state=OperationState(str(row["state"])),
        provider=ProviderFamily(str(row["provider"])),
        site_pair_id=str(row["site_pair_id"]),
        protection_plan_id=str(row["protection_plan_id"]),
        recovery_group_id=_optional_str(row["recovery_group_id"]),
        recovery_point_id=_optional_str(row["recovery_point_id"]),
        lease_resource=str(row["lease_resource"]),
        requested_by=str(row["requested_by"]),
        created_at_epoch=int(row["created_at_epoch"]),
        updated_at_epoch=int(row["updated_at_epoch"]),
        error_code=_optional_str(row["error_code"]),
        error_message=_optional_str(row["error_message"]),
    )


def _optional_str(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def _require_values(*values: str) -> None:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValidationError("required DR identifiers/values must be non-empty strings")


def _epoch_now() -> int:
    return int(time.time())


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _to_jsonable(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        converted = [_to_jsonable(item) for item in value]
        return sorted(converted, key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (tuple, list)):
        return [_to_jsonable(item) for item in value]
    return value
