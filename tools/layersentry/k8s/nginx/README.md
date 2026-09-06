# Kubernetes browser route

The customer client calls `/client/layersentry-k8s/v1/kubernetes/`. Include
`layersentry-k8s-location.conf` inside the same TLS virtual server that serves
`/client/`. Nginx strips the module prefix and forwards `/v1/kubernetes/` to the
existing restricted Gunicorn Unix socket. CloudStack GUI/API locations remain
with their existing upstream. This file does not create or replace a listener.

The BFF authenticates the native CloudStack session cookie and session-key header,
checks the configured browser origin, and enforces project/API permissions.
Nginx must pass Cookie, Origin, X-LayerSentry-Session-Key, Idempotency-Key and
Content-Type unchanged. No CORS grant or trusted browser identity header is added.
Automatic upstream retry and response caching are disabled. A transport failure
after submission remains ambiguous and must be observed by operation/idempotency
identity before retry. Unknown module paths return JSON rather than SPA HTML.

Before deployment, install the reviewed runtime and qualified manifest, grant the
nginx worker only the required socket-group access, preserve the existing TLS
configuration, validate with `nginx -t`, and qualify SELinux Unix-socket access on
Rocky Linux 9. Keep the BFF/reconciler stopped when its component tuple is blocked.
Do not replace false release evidence with true values to start it. This routing
artifact alone does not provision the first management cluster or certify DBaaS.

Research: native URI replacement and Unix-socket proxy syntax are documented at
https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_pass. The selected
directives also exist in the local preliminary Nginx 1.18 qualification build;
actual Rocky package/version and browser deployment evidence remain required.
