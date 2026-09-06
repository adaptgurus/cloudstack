# E1 controller runtime and project-isolation wiring

**Date:** 2026-09-06  
**Implementation:** `58e9e2e18e13d91422fe264530828fc6ba538b3d`  
**Status:** source `SOURCE_COMPLETE`; deployment `BLOCKED`  
**Runtime mutation:** none

## Current approach

The LayerSentry controller now has one strict runtime composition root. It
loads an absolute, non-writable JSON configuration containing only credential
file references; validates the immutable release contract; constructs the
CloudStack-session authenticator/capability authorizer, signed read-only
CloudStack resolver, restricted Kubernetes client, E1 executor, durable saga
store and BFF; and refuses startup while the release component/evidence gate
is unresolved.

The BFF uses two Gunicorn workers only for HTTP/API concurrency. A separate
systemd timer invokes one bounded single-active reconciler batch every ten
seconds. Operations in `REQUESTED`, `RUNNING` or `FAILED_RETRYABLE` survive
process restart through SQLite WAL; `UNKNOWN` operations are deliberately not
replayed. Unexpected adapter exceptions persist only a redacted retry marker.
The database is forced to mode `0600`; the service uses `UMask=0077` and a
non-writable state parent. Hardened systemd service examples restrict devices,
home, kernel/control-group mutation, writable paths and address families.

## Project/frontend ownership corrections

Every cluster request now requires an exact CloudStack project ID and a
distinct preallocated frontend public-IP ID. The privileged read-only resolver
verifies that IP is `Allocated` in the same project and Site and derives the
actual endpoint address from CloudStack rather than a global configuration.
This prevents multiple clusters from silently sharing a fixed 6443/9345
frontend.

The management namespace is deterministic per CloudStack project:
`<configured-prefix>-<first-12-of-sha256(project-id)>`. A Namespace with exact
LayerSentry/project labels is created before namespaced CAPI resources. Before
server-side apply, the executor performs an authoritative GET and refuses to
adopt any existing Namespace/provider/Flux object without matching ownership.
The same ownership rule applies when resolving an ambiguous mutation. The one
shared Flux `GitRepository` is accepted only when both its managed label and
exact HTTPS URL/commit match; each cluster Kustomization carries project and
cluster labels.

## Advantages, disadvantages and alternatives

This design gives a deterministic install surface, keeps credentials out of
Git/JSON/saga events, survives controller restarts, prevents cross-project
name collisions/adoption and keeps CAPI/CAPC as lifecycle owners. It also
makes current artifact blockers visible before any provider mutation.

SQLite still permits only one active reconciler; the timer must not be enabled
on multiple nodes against copied databases. A later active/active design needs
a tested shared transactional store and leases. A long-running custom
CloudStack service was not added, avoiding Java/API/schema changes. Direct
CloudStack VM creation remains rejected; CAPC owns Machines. A global shared
frontend was removed because it cannot safely represent independent cluster
endpoint ownership.

## Failure handling and rollback

- config typos, duplicate keys, weak secret permissions, writable state
  parents, insecure unapproved origins and unresolved components fail startup;
- provider mutation transport ambiguity remains `UNKNOWN` and requires
  authoritative observation rather than replay;
- a restart reselects only safe actionable statuses;
- permanent/terminal and `UNKNOWN` operations are excluded;
- foreign preexisting objects fail before apply;
- scale-down/delete remain additionally blocked by CAPC volume live evidence.

Rollback stops/disables the two service units and timer, restores the prior
package/config, and retains the SQLite journal for diagnosis. No direct
provider cleanup is inferred; CAPI/Flux authoritative state must be observed
before any retry or rollback mutation.

## Tests performed and remaining gates

All 74 Workstream E Python tests and Python bytecode compilation passed
locally. Added cases cover restart selection, database mode, redacted worker
failure, strict runtime config, weak secret/state permissions, per-project
namespace determinism, required project/frontend, foreign frontend and
Namespace rejection, shared Flux pinning and project labels. Systemd unit
syntax was inspected locally; the development host does not have the future
packaged Gunicorn executable/module and is not a Rocky acceptance target.

No RPM/package install, Gunicorn request, reverse proxy, SELinux policy,
systemd start/restart, provider admission, CAPI reconciliation, endpoint rule,
CCM/CSI/Flux workload or Rocky Linux 9 test ran. Current release artifacts and
evidence remain false, so service startup is intentionally `BLOCKED`. This is
not `CI_VERIFIED`, `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED`.
