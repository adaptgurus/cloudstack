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

import re
import hashlib
import urllib.parse
from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from .model import InvalidRequestError


_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def bounded_name(cluster_name: str, suffix: str) -> str:
    value = cluster_name + '-' + suffix
    return value if len(value) <= 63 else value[:50].rstrip('-') + '-' + hashlib.sha256(value.encode()).hexdigest()[:12]


def desired_matches(desired, actual):
    if isinstance(desired, Mapping):
        return isinstance(actual, Mapping) and all(key in actual and desired_matches(value, actual[key]) for key, value in desired.items())
    return desired == actual


def flux_ready(resource):
    metadata, status = resource.get('metadata', {}), resource.get('status', {})
    generation = metadata.get('generation')
    if type(generation) is not int or generation < 1 or status.get('observedGeneration') != generation or metadata.get('deletionTimestamp') or resource.get('spec', {}).get('suspend'):
        return False
    conditions = status.get('conditions', [])
    return (any(c.get('type') == 'Ready' and c.get('status') == 'True' and c.get('observedGeneration') == generation for c in conditions)
            and not any(c.get('type') in ('Reconciling', 'Stalled') and c.get('status') == 'True' for c in conditions))


def baseline_ready(desired, actual, commit):
    revision = actual.get('status', {}).get('lastAppliedRevision', '')
    return (desired_matches(desired['spec'], actual.get('spec', {})) and flux_ready(actual)
            and isinstance(revision, str) and (revision == 'sha1:' + commit or revision.endswith('@sha1:' + commit)))


def git_source_ready(desired, actual, commit):
    revision = actual.get('status', {}).get('artifact', {}).get('revision', '')
    return (desired_matches(desired['spec'], actual.get('spec', {})) and flux_ready(actual)
            and isinstance(revision, str) and (revision == 'sha1:' + commit or revision.endswith('@sha1:' + commit)))


@dataclass(frozen=True)
class FluxBaseline:
    repository_url: str
    commit: str
    path: str
    source_namespace: str = "flux-system"


def build_flux_baseline(
    cluster_name: str, tenant_namespace: str, project_id: str, config: FluxBaseline,
) -> Tuple[Mapping[str, Any], ...]:
    if not all(isinstance(value, str) and _NAME.fullmatch(value) for value in (cluster_name, tenant_namespace, config.source_namespace)):
        raise InvalidRequestError("Flux cluster/namespace identity is invalid")
    if not isinstance(project_id, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,62}', project_id):
        raise InvalidRequestError("Flux project identity is invalid")
    parsed = urllib.parse.urlsplit(config.repository_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise InvalidRequestError("Flux source must be an HTTPS URL without userinfo")
    if not _COMMIT.fullmatch(config.commit):
        raise InvalidRequestError("Flux baseline must be pinned to an exact Git commit")
    if not config.path.startswith("./") or ".." in config.path.split("/"):
        raise InvalidRequestError("Flux baseline path must be repository-relative")
    source_name = "layersentry-e1-catalog"
    source_labels = {"layersentry.io/managed": "true", "layersentry.io/project": project_id}
    workload_labels = {
        **source_labels,
        "layersentry.io/cluster": cluster_name,
        "layersentry.io/project": project_id,
    }
    return (
        {
            "apiVersion": "source.toolkit.fluxcd.io/v1",
            "kind": "GitRepository",
            # Keep sources beside the CAPI kubeconfig Secret. source_namespace
            # remains accepted for old configuration files, not remote targeting.
            "metadata": {"name": source_name, "namespace": tenant_namespace, "labels": source_labels},
            "spec": {
                "interval": "10m",
                "url": config.repository_url,
                "ref": {"commit": config.commit},
            },
        },
        {
            "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
            "kind": "Kustomization",
            "metadata": {"name": bounded_name(cluster_name, 'baseline'), "namespace": tenant_namespace, "labels": workload_labels},
            "spec": {
                "interval": "10m",
                "retryInterval": "1m",
                "timeout": "15m",
                "prune": True,
                "wait": True,
                "path": config.path,
                "sourceRef": {"kind": "GitRepository", "name": source_name},
                "kubeConfig": {"secretRef": {"name": cluster_name + "-kubeconfig", "key": "value"}},
                "postBuild": {"substitute": {
                    "CLUSTER_NAME": cluster_name,
                    "CLUSTER_NAMESPACE": tenant_namespace,
                }},
            },
        },
    )
