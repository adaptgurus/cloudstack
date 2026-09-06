#!/usr/bin/env python3
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements. See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership. The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License. You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Real local reverse-proxy transport test; no lab or credentials required."""
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import socketserver
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

NGINX = os.environ.get("LAYERSENTRY_TEST_NGINX") or shutil.which("nginx")


@unittest.skipUnless(NGINX, "exact Nginx executable required for proxy transport qualification")
class NginxRouteTest(unittest.TestCase):
    def test_real_unix_proxy_preserves_scope_auth_and_does_not_replay_mutations(self):
        calls = []
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                calls.append((self.path, dict(self.headers), self.rfile.read(int(self.headers.get("Content-Length", 0)))))
                self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"error":"provider unavailable"}')
            def log_message(self, *args):
                pass
        with tempfile.TemporaryDirectory(prefix="lsk8s-proxy-") as directory:
            root = Path(directory)
            unix = root / "bff.sock"
            server = socketserver.UnixStreamServer(str(unix), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            with socket.socket() as reserved:
                reserved.bind(("127.0.0.1", 0))
                port = reserved.getsockname()[1]
            route = (Path(__file__).parent / "nginx/layersentry-k8s-location.conf").read_text()
            route = route.replace("/run/layersentry-k8s/bff.sock", str(unix))
            config = root / "nginx.conf"
            config.write_text(f'''pid {root}/nginx.pid;
error_log {root}/error.log crit;
events {{ worker_connections 32; }}
http {{ access_log off; client_body_temp_path {root}/body;
proxy_temp_path {root}/proxy; fastcgi_temp_path {root}/fastcgi;
uwsgi_temp_path {root}/uwsgi; scgi_temp_path {root}/scgi;
server {{ listen 127.0.0.1:{port}; {route}
location /client/api {{ return 204; }} }} }}''')
            process = subprocess.Popen([NGINX, "-p", str(root), "-c", str(config), "-g", "daemon off; master_process off;"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                for _ in range(100):
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                            break
                    except OSError:
                        if process.poll() is not None:
                            self.fail("Nginx could not start with the candidate route")
                        time.sleep(0.02)
                origin = f"http://127.0.0.1:{port}"
                request = urllib.request.Request(origin + "/client/layersentry-k8s/v1/kubernetes/clusters?projectId=project-1",
                    method="POST", data=b'{}', headers={"Content-Type": "application/json", "Cookie": "JSESSIONID=fixture-only",
                    "Origin": origin, "X-LayerSentry-Session-Key": "fixture-only", "Idempotency-Key": "fixture-operation-001", "X-Remote-User": "forged"})
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    urllib.request.urlopen(request, timeout=3)
                self.assertEqual(failure.exception.code, 503)
                self.assertEqual(json.load(failure.exception), {"error": "provider unavailable"})
                self.assertEqual(len(calls), 1)
                path, headers, body = calls[0]
                headers = {key.lower(): value for key, value in headers.items()}
                self.assertEqual(path, "/v1/kubernetes/clusters?projectId=project-1")
                self.assertEqual(headers["cookie"], "JSESSIONID=fixture-only")
                self.assertEqual(headers["origin"], origin)
                self.assertEqual(headers["x-layersentry-session-key"], "fixture-only")
                self.assertEqual(headers["idempotency-key"], "fixture-operation-001")
                self.assertNotIn("x-remote-user", headers)
                self.assertEqual(body, b'{}')
                with self.assertRaises(urllib.error.HTTPError) as failure:
                    urllib.request.urlopen(origin + "/client/layersentry-k8s/unknown", timeout=3)
                self.assertEqual(failure.exception.code, 404)
                self.assertEqual(json.load(failure.exception), {"error": "Unknown Kubernetes API route"})
                with urllib.request.urlopen(origin + "/client/api", timeout=3) as response:
                    self.assertEqual(response.status, 204)
            finally:
                process.terminate()
                process.wait(timeout=5)
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
