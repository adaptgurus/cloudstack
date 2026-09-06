# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""SQLite-backed durable saga journal for the LayerSentry controller."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .model import ConflictError, NotFoundError, Operation, OperationStatus


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class SagaStore:
    """Durable local operation journal with optimistic concurrency.

    A production multi-replica deployment must put this behind one active
    controller or replace it with a tested transactional shared store. SQLite
    itself is not presented as a distributed coordination mechanism.
    """

    def __init__(self, path: Path | str):
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS operations (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    request_sha256 TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    target_name TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    actor_subject TEXT NOT NULL,
                    status TEXT NOT NULL,
                    step_index INTEGER NOT NULL DEFAULT 0,
                    request_json TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    resources_json TEXT NOT NULL DEFAULT '{}',
                    last_error TEXT,
                    recovery TEXT,
                    version INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS operation_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation_id TEXT NOT NULL REFERENCES operations(id),
                    status TEXT NOT NULL,
                    step_index INTEGER NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS operation_project_idx
                    ON operations(project_id, created_at);
            """)

    @staticmethod
    def _decode(row: sqlite3.Row) -> Operation:
        return Operation(
            id=row["id"], idempotency_key=row["idempotency_key"],
            request_sha256=row["request_sha256"], kind=row["kind"],
            target_name=row["target_name"], project_id=row["project_id"],
            actor_subject=row["actor_subject"], status=OperationStatus(row["status"]),
            step_index=row["step_index"], request=json.loads(row["request_json"]),
            plan=tuple(json.loads(row["plan_json"])), resources=json.loads(row["resources_json"]),
            last_error=row["last_error"], recovery=row["recovery"], version=row["version"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def create_or_get(
        self, *, idempotency_key: str, request_sha256: str, kind: str,
        target_name: str, project_id: str, actor_subject: str,
        request: Mapping[str, Any], plan: Sequence[Mapping[str, Any]],
    ) -> tuple[Operation, bool]:
        operation_id = str(uuid.uuid4())
        timestamp = _now()
        request_json = json.dumps(request, sort_keys=True, separators=(",", ":"))
        plan_json = json.dumps(list(plan), sort_keys=True, separators=(",", ":"))
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM operations WHERE idempotency_key=?", (idempotency_key,),
            ).fetchone()
            if row is not None:
                current = self._decode(row)
                if current.request_sha256 != request_sha256 or current.actor_subject != actor_subject:
                    connection.rollback()
                    raise ConflictError("idempotency key is already bound to a different request")
                connection.commit()
                return current, False
            connection.execute(
                """INSERT INTO operations
                (id,idempotency_key,request_sha256,kind,target_name,project_id,actor_subject,
                 status,step_index,request_json,plan_json,resources_json,version,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (operation_id, idempotency_key, request_sha256, kind, target_name, project_id,
                 actor_subject, OperationStatus.REQUESTED.value, 0, request_json, plan_json,
                 "{}", 0, timestamp, timestamp),
            )
            connection.execute(
                "INSERT INTO operation_events(operation_id,status,step_index,detail,created_at) VALUES(?,?,?,?,?)",
                (operation_id, OperationStatus.REQUESTED.value, 0, "request accepted", timestamp),
            )
            row = connection.execute("SELECT * FROM operations WHERE id=?", (operation_id,)).fetchone()
            connection.commit()
        return self._decode(row), True

    def get(self, operation_id: str) -> Operation:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM operations WHERE id=?", (operation_id,)).fetchone()
        if row is None:
            raise NotFoundError("operation not found")
        return self._decode(row)

    def update(
        self, operation: Operation, *, status: OperationStatus, step_index: int,
        resources: Mapping[str, Any] | None = None, last_error: str | None = None,
        recovery: str | None = None, detail: str | None = None,
    ) -> Operation:
        timestamp = _now()
        resource_json = json.dumps(
            dict(operation.resources if resources is None else resources),
            sort_keys=True, separators=(",", ":"),
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                """UPDATE operations SET status=?,step_index=?,resources_json=?,last_error=?,
                   recovery=?,version=version+1,updated_at=? WHERE id=? AND version=?""",
                (status.value, step_index, resource_json, last_error, recovery, timestamp,
                 operation.id, operation.version),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ConflictError("operation changed concurrently")
            connection.execute(
                "INSERT INTO operation_events(operation_id,status,step_index,detail,created_at) VALUES(?,?,?,?,?)",
                (operation.id, status.value, step_index, detail, timestamp),
            )
            row = connection.execute("SELECT * FROM operations WHERE id=?", (operation.id,)).fetchone()
            connection.commit()
        return self._decode(row)

    def events(self, operation_id: str) -> list[dict[str, Any]]:
        self.get(operation_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT sequence,status,step_index,detail,created_at FROM operation_events "
                "WHERE operation_id=? ORDER BY sequence", (operation_id,),
            ).fetchall()
        return [dict(row) for row in rows]
