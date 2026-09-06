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

"""Strict production wiring for the E1 BFF and single active reconciler."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .auth import CloudStackCapabilityAuthorizer, CloudStackSessionAuthenticator, CloudStackSessionConfig
from .bff import BFFApplication
from .cloudstack import CloudStackClient, CloudStackConfig, CloudStackResolver, ClusterProfile
from .components import ReleaseContract, load_release_contract
from .e1_executor import E1Executor
from .flux_resources import FluxBaseline
from .kubernetes import KubernetesClient, KubernetesConfig
from .model import ConflictError, InvalidRequestError
from .service import ControllerService
from .store import SagaStore


_ROOT_KEYS = {"schemaVersion", "releaseManifest", "stateDatabase", "cloudstack", "kubernetes", "clusterProfile", "flux"}
_CLOUDSTACK_KEYS = {"endpoint", "apiKeyFile", "secretKeyFile", "caFile", "allowInsecureHttp", "trustedBrowserOrigins"}
_KUBERNETES_KEYS = {"server", "caFile", "tokenFile"}
_PROFILE_KEYS = {"namespacePrefix", "credentialSecretName", "credentialSecretNamespace", "qualifiedImages"}
_FLUX_KEYS = {"path", "sourceNamespace"}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidRequestError(f"runtime configuration contains duplicate key: {key}")
        result[key] = value
    return result


def _object(value: Any, name: str, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise InvalidRequestError(f"runtime {name} must be an object")
    unknown = sorted(set(value) - keys)
    missing = sorted(keys - set(value))
    if unknown or missing:
        raise InvalidRequestError(
            f"runtime {name} fields are invalid (missing={','.join(missing)}; unknown={','.join(unknown)})"
        )
    return value


def _absolute_file(value: Any, name: str, *, secret: bool = False) -> Path:
    if not isinstance(value, str) or not value or not Path(value).is_absolute():
        raise InvalidRequestError(f"runtime {name} must be an absolute file path")
    path = Path(value)
    if not path.is_file() or path.is_symlink():
        raise InvalidRequestError(f"runtime {name} must be an existing regular non-symlink file")
    if secret and path.stat().st_mode & 0o077:
        raise InvalidRequestError(f"runtime {name} must have mode 0600 or stricter")
    return path


@dataclass(frozen=True)
class RuntimeConfig:
    release_manifest: Path
    state_database: Path
    cloudstack: CloudStackConfig
    session: CloudStackSessionConfig
    kubernetes: KubernetesConfig
    profile: ClusterProfile
    flux_path: str
    flux_namespace: str


@dataclass(frozen=True)
class ControllerRuntime:
    config: RuntimeConfig
    contract: ReleaseContract
    store: SagaStore
    service: ControllerService
    application: BFFApplication

    def reconcile_batch(self, limit: int = 20) -> Mapping[str, int]:
        result = {"selected": 0, "advanced": 0, "conflicted": 0, "failed": 0}
        operation_ids = self.store.actionable_ids(limit)
        result["selected"] = len(operation_ids)
        for operation_id in operation_ids:
            try:
                self.service.advance(operation_id)
                result["advanced"] += 1
            except ConflictError:
                result["conflicted"] += 1
            except Exception:
                # Provider-safe detail is persisted by the service when it can
                # classify the outcome. The batch summary never emits secrets.
                try:
                    self.service.record_retryable_adapter_failure(operation_id)
                except ConflictError:
                    result["conflicted"] += 1
                else:
                    result["failed"] += 1
        return result


def load_runtime_config(path: Path | str) -> RuntimeConfig:
    config_path = Path(path)
    if not config_path.is_absolute() or not config_path.is_file() or config_path.is_symlink():
        raise InvalidRequestError("runtime configuration must be an absolute regular non-symlink file")
    if config_path.stat().st_mode & 0o022:
        raise InvalidRequestError("runtime configuration must not be group/world writable")
    try:
        root = json.loads(config_path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidRequestError("runtime configuration is unreadable or invalid") from exc
    root = _object(root, "root", _ROOT_KEYS)
    if root["schemaVersion"] != "1.0":
        raise InvalidRequestError("unsupported runtime configuration schemaVersion")
    release_manifest = _absolute_file(root["releaseManifest"], "releaseManifest")
    state_database = Path(root["stateDatabase"]) if isinstance(root["stateDatabase"], str) else Path("")
    if not state_database.is_absolute() or state_database.is_symlink() or not state_database.parent.is_dir():
        raise InvalidRequestError("runtime stateDatabase must be an absolute non-symlink path in an existing directory")
    if state_database.parent.stat().st_mode & 0o022:
        raise InvalidRequestError("runtime stateDatabase parent must not be group/world writable")
    if state_database.exists() and (not state_database.is_file() or state_database.stat().st_mode & 0o077):
        raise InvalidRequestError("runtime stateDatabase must be a regular file with mode 0600 or stricter")

    cloud = _object(root["cloudstack"], "cloudstack", _CLOUDSTACK_KEYS)
    insecure = cloud["allowInsecureHttp"]
    origins = cloud["trustedBrowserOrigins"]
    if not isinstance(insecure, bool) or not isinstance(origins, list) or not all(isinstance(item, str) for item in origins):
        raise InvalidRequestError("runtime CloudStack transport/origin settings are invalid")
    ca_file = None if cloud["caFile"] is None else _absolute_file(cloud["caFile"], "cloudstack.caFile")
    cloudstack = CloudStackConfig(
        endpoint=cloud["endpoint"],
        api_key_file=_absolute_file(cloud["apiKeyFile"], "cloudstack.apiKeyFile", secret=True),
        secret_key_file=_absolute_file(cloud["secretKeyFile"], "cloudstack.secretKeyFile", secret=True),
        ca_file=ca_file,
        allow_insecure_http=insecure,
    )
    session = CloudStackSessionConfig(
        endpoint=cloud["endpoint"], trusted_origins=tuple(origins),
        ca_file=str(ca_file) if ca_file else None, allow_insecure_http=insecure,
    )

    kubernetes = _object(root["kubernetes"], "kubernetes", _KUBERNETES_KEYS)
    kubernetes_config = KubernetesConfig(
        server=kubernetes["server"],
        ca_file=_absolute_file(kubernetes["caFile"], "kubernetes.caFile"),
        token_file=_absolute_file(kubernetes["tokenFile"], "kubernetes.tokenFile", secret=True),
    )
    profile = _object(root["clusterProfile"], "clusterProfile", _PROFILE_KEYS)
    if not all(isinstance(profile[key], str) and profile[key] for key in _PROFILE_KEYS - {"qualifiedImages"}):
        raise InvalidRequestError("runtime clusterProfile fields must be non-empty strings")
    images = profile["qualifiedImages"]
    if (not isinstance(images, Mapping) or len(images) > 100
            or any(not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,64}", key)
                   or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for key, value in images.items())):
        raise InvalidRequestError("qualifiedImages must bind at most 100 template IDs to SHA-256 digests")
    cluster_profile = ClusterProfile(
        namespace_prefix=profile["namespacePrefix"],
        cloudstack_secret_name=profile["credentialSecretName"],
        cloudstack_secret_namespace=profile["credentialSecretNamespace"],
        qualified_images=dict(images),
    )
    flux = _object(root["flux"], "flux", _FLUX_KEYS)
    if not all(isinstance(flux[key], str) and flux[key] for key in _FLUX_KEYS):
        raise InvalidRequestError("runtime Flux fields must be non-empty strings")
    return RuntimeConfig(
        release_manifest, state_database, cloudstack, session, kubernetes_config,
        cluster_profile, flux["path"], flux["sourceNamespace"],
    )


def build_runtime(config_path: Path | str) -> ControllerRuntime:
    config = load_runtime_config(config_path)
    contract = load_release_contract(config.release_manifest)
    contract.readiness.require_deployable()
    kubernetes = KubernetesClient(config.kubernetes)
    resolver = CloudStackResolver(CloudStackClient(config.cloudstack), config.profile)
    flux = FluxBaseline(
        repository_url=contract.readiness.flux_repository or "",
        commit=contract.readiness.flux_commit or "",
        path=config.flux_path,
        source_namespace=config.flux_namespace,
    )
    executor = E1Executor(kubernetes, resolver, contract.gates, flux)
    store = SagaStore(config.state_database)
    service = ControllerService(store, CloudStackCapabilityAuthorizer(), executor, contract.gates,
                                qualified_images=config.profile.qualified_images)
    authenticator = CloudStackSessionAuthenticator(config.session)
    return ControllerRuntime(config, contract, store, service, BFFApplication(service, authenticator))


def create_application():
    path = os.environ.get("LAYERSENTRY_K8S_CONFIG")
    if not path:
        raise InvalidRequestError("LAYERSENTRY_K8S_CONFIG is required")
    return build_runtime(path).application
