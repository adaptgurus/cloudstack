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
import urllib.parse
from dataclasses import dataclass
from typing import Any, Mapping, Tuple

from .model import InvalidRequestError


_COMMIT = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class FluxBaseline:
    repository_url: str
    commit: str
    path: str
    source_namespace: str = "flux-system"


def build_flux_baseline(
    cluster_name: str, tenant_namespace: str, project_id: str, config: FluxBaseline,
) -> Tuple[Mapping[str, Any], ...]:
    parsed = urllib.parse.urlsplit(config.repository_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise InvalidRequestError("Flux source must be an HTTPS URL without userinfo")
    if not _COMMIT.fullmatch(config.commit):
        raise InvalidRequestError("Flux baseline must be pinned to an exact Git commit")
    if not config.path.startswith("./") or ".." in config.path.split("/"):
        raise InvalidRequestError("Flux baseline path must be repository-relative")
    source_name = "layersentry-e1-catalog"
    source_labels = {"layersentry.io/managed": "true"}
    workload_labels = {
        **source_labels,
        "layersentry.io/cluster": cluster_name,
        "layersentry.io/project": project_id,
    }
    return (
        {
            "apiVersion": "source.toolkit.fluxcd.io/v1",
            "kind": "GitRepository",
            "metadata": {"name": source_name, "namespace": config.source_namespace, "labels": source_labels},
            "spec": {
                "interval": "10m",
                "url": config.repository_url,
                "ref": {"commit": config.commit},
            },
        },
        {
            "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
            "kind": "Kustomization",
            "metadata": {"name": f"{cluster_name}-baseline", "namespace": config.source_namespace, "labels": workload_labels},
            "spec": {
                "interval": "10m",
                "retryInterval": "1m",
                "timeout": "15m",
                "prune": True,
                "wait": True,
                "path": config.path,
                "sourceRef": {"kind": "GitRepository", "name": source_name},
                "postBuild": {"substitute": {
                    "CLUSTER_NAME": cluster_name,
                    "CLUSTER_NAMESPACE": tenant_namespace,
                }},
            },
        },
    )
