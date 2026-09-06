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

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Tuple


class ControllerError(RuntimeError):
    """Safe controller error suitable for mapping at the BFF boundary."""


class AuthorizationError(ControllerError):
    pass


class AuthenticationError(AuthorizationError):
    """The caller did not present a currently valid upstream identity."""


class ConflictError(ControllerError):
    pass


class NotFoundError(ControllerError):
    pass


class InvalidRequestError(ControllerError):
    pass


class AmbiguousMutationError(ControllerError):
    """A mutating API timed out or returned an unknowable outcome."""


class OperationStatus(str, Enum):
    REQUESTED = "REQUESTED"
    VALIDATING = "VALIDATING"
    RUNNING = "RUNNING"
    READY = "READY"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    DELETING = "DELETING"
    DELETED = "DELETED"


TERMINAL_STATUSES = {OperationStatus.READY, OperationStatus.FAILED, OperationStatus.DELETED}


@dataclass(frozen=True)
class Actor:
    subject: str
    account_id: str
    domain_id: str
    project_ids: Tuple[str, ...] = ()
    roles: Tuple[str, ...] = ()
    capabilities: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Operation:
    id: str
    idempotency_key: str
    request_sha256: str
    kind: str
    target_name: str
    project_id: str
    actor_subject: str
    status: OperationStatus
    step_index: int
    request: Mapping[str, Any]
    plan: Tuple[Mapping[str, Any], ...]
    resources: Mapping[str, Any] = field(default_factory=dict)
    last_error: Optional[str] = None
    recovery: Optional[str] = None
    version: int = 0
    created_at: str = ""
    updated_at: str = ""

    @property
    def done(self) -> bool:
        return self.status in TERMINAL_STATUSES

    def public_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "targetName": self.target_name,
            "projectId": self.project_id,
            "status": self.status.value,
            "stepIndex": self.step_index,
            "stepCount": len(self.plan),
            "resources": dict(self.resources),
            "lastError": self.last_error,
            "recovery": self.recovery,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }
