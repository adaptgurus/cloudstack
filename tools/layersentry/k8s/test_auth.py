#!/usr/bin/env python3
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

import io
import json
import unittest
import urllib.error
import urllib.parse

from controller.auth import (
    CloudStackCapabilityAuthorizer,
    CloudStackSessionAuthenticator,
    CloudStackSessionConfig,
)
from controller.model import Actor, AuthenticationError, AuthorizationError, InvalidRequestError


SESSION_ID = "0123456789ABCDEF0123456789ABCDEF"
SESSION_KEY = "abcdefghijklmnopqrstuvwx_123456"


class Response:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, limit):
        return json.dumps(self.value).encode()[:limit]


class RecordingOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return Response(value)


def config(**overrides):
    values = {
        "endpoint": "https://cloud.example.test/client/api",
        "trusted_origins": ("https://cloud.example.test",),
    }
    values.update(overrides)
    return CloudStackSessionConfig(**values)


def environ(method="GET", origin="", cookie=True, header_key=SESSION_KEY):
    result = {"REQUEST_METHOD": method}
    if origin:
        result["HTTP_ORIGIN"] = origin
    if cookie:
        result["HTTP_COOKIE"] = f"role=Admin; JSESSIONID={SESSION_ID}; sessionkey={SESSION_KEY}; userid=spoofed"
    if header_key is not None:
        result["HTTP_X_LAYERSENTRY_SESSION_KEY"] = header_key
    return result


class CloudStackSessionAuthenticatorTest(unittest.TestCase):
    def test_authenticates_from_upstream_permissions_and_projects_only(self):
        opener = RecordingOpener([
            {"listapisresponse": {"api": [
                {"name": "listProjects"}, {"name": "deployVirtualMachine"},
                {"name": "createLoadBalancerRule"}, {"name": "createVolume"},
            ]}},
            {"listprojectsresponse": {"count": 1, "project": [
                {"id": "project-1", "state": "Active"},
            ]}},
        ])
        auth = CloudStackSessionAuthenticator(config(), opener=opener)
        actor = auth.authenticate(environ("POST", "https://cloud.example.test"))
        self.assertEqual(actor.project_ids, ("project-1",))
        self.assertEqual(actor.account_id, "")
        self.assertEqual(actor.roles, ())
        self.assertIn("deployVirtualMachine", actor.capabilities)
        self.assertNotIn("Admin", actor.roles)
        self.assertTrue(actor.subject.startswith("cloudstack-session:"))

        for request, timeout in opener.requests:
            self.assertEqual(timeout, 15)
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(
                request.headers["Cookie"],
                f"JSESSIONID={SESSION_ID}; sessionkey={SESSION_KEY}",
            )
            body = urllib.parse.parse_qs(request.data.decode(), strict_parsing=True)
            self.assertEqual(body["sessionkey"], [SESSION_KEY])
            self.assertNotIn("role", body)
            self.assertNotIn("userid", body)

    def test_mutations_require_exact_trusted_origin(self):
        auth = CloudStackSessionAuthenticator(config(), opener=RecordingOpener([]))
        for origin in ("", "null", "https://evil.example", "https://cloud.example.test.evil"):
            with self.subTest(origin=origin), self.assertRaises(AuthenticationError):
                auth.authenticate(environ("DELETE", origin))

    def test_default_ports_normalize_but_paths_are_rejected(self):
        auth = CloudStackSessionAuthenticator(
            config(trusted_origins=("https://cloud.example.test:443/",)),
            opener=RecordingOpener([]),
        )
        with self.assertRaises(AuthenticationError):
            auth.authenticate(environ("POST", "https://cloud.example.test/path"))
        with self.assertRaises(InvalidRequestError):
            CloudStackSessionAuthenticator(
                config(trusted_origins=("https://cloud.example.test/app",)),
                opener=RecordingOpener([]),
            )

    def test_cookie_and_header_session_keys_must_match(self):
        auth = CloudStackSessionAuthenticator(config(), opener=RecordingOpener([]))
        for candidate in (None, "different-session-key-12345", "bad value"):
            with self.subTest(candidate=candidate), self.assertRaises(AuthenticationError):
                auth.authenticate(environ(header_key=candidate))

        duplicate = environ()
        duplicate["HTTP_COOKIE"] += f"; JSESSIONID={SESSION_ID}"
        with self.assertRaisesRegex(AuthenticationError, "ambiguous"):
            auth.authenticate(duplicate)

    def test_http_origins_require_explicit_development_override(self):
        with self.assertRaises(InvalidRequestError):
            CloudStackSessionAuthenticator(
                config(trusted_origins=("http://cloud.example.test",)),
                opener=RecordingOpener([]),
            )

    def test_rejects_session_error_invalid_json_duplicate_capability_and_truncation(self):
        cases = [
            urllib.error.URLError("down"),
            {"errorresponse": {"errorcode": 401}},
            {"listapisresponse": {"api": [{"name": "listProjects"}, {"name": "listProjects"}]}},
        ]
        for response in cases:
            with self.subTest(response=response):
                auth = CloudStackSessionAuthenticator(config(), opener=RecordingOpener([response]))
                with self.assertRaises(AuthenticationError):
                    auth.authenticate(environ())

    def test_incomplete_project_inventory_fails_closed(self):
        opener = RecordingOpener([
            {"listapisresponse": {"api": [{"name": "listProjects"}]}},
            {"listprojectsresponse": {"count": 2, "project": [
                {"id": "project-1", "state": "Active"},
            ]}},
        ])
        auth = CloudStackSessionAuthenticator(config(), opener=opener)
        with self.assertRaisesRegex(AuthenticationError, "incomplete"):
            auth.authenticate(environ())


class CloudStackCapabilityAuthorizerTest(unittest.TestCase):
    def test_create_requires_project_and_exact_effective_capabilities(self):
        authorizer = CloudStackCapabilityAuthorizer()
        actor = Actor(
            "session", "", "", ("project-1",), (),
            ("listProjects", "deployVirtualMachine", "createLoadBalancerRule", "createVolume"),
        )
        authorizer.require(actor, "kubernetes.cluster.create", "project-1")
        with self.assertRaises(AuthorizationError):
            authorizer.require(actor, "kubernetes.cluster.create", "project-2")
        with self.assertRaises(AuthorizationError):
            authorizer.require(
                Actor("session", "", "", ("project-1",), (), ("listProjects",)),
                "kubernetes.cluster.create",
                "project-1",
            )

    def test_unknown_action_and_read_only_mutation_are_denied(self):
        authorizer = CloudStackCapabilityAuthorizer()
        read_only = Actor(
            "session", "", "", ("project-1",), (), ("listProjects", "listVirtualMachines"),
        )
        authorizer.require(read_only, "kubernetes.cluster.status", "project-1")
        with self.assertRaises(AuthorizationError):
            authorizer.require(read_only, "kubernetes.cluster.delete", "project-1")
        with self.assertRaises(AuthorizationError):
            authorizer.require(read_only, "kubernetes.cluster.unknown", "project-1")


if __name__ == "__main__":
    unittest.main()
