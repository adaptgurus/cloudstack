# LayerSentry control-plane database and R0 evidence gate

Date: 2026-09-05 (Asia/Kolkata)

Status: `PARTIAL` — exact source/documentation and Hyper-V reachability were revalidated; authenticated CloudStack inventory, database-topology selection, multi-node HA, and DR remain `NOT_TESTED` or `BLOCKED` as stated below.

## Scope and current approach

LayerSentry retains Apache CloudStack 4.22.1.1 as the control-plane authority and does not select a three-node database implementation until the exact database version, JDBC behavior, failover routing, backup/restore, and upgrade path are demonstrated. The existing runner first performs R0 discovery and must not use an inventory workflow that changes guest authorization state merely to obtain read access.

## Evidence inspected

- CloudStack repository branch `layersentry/4.22.1.1-ui`, fetched head `26a5e4b092b37ff0693c6b3154a2090171440bd6`.
- Cozystack runner branch `ops/layersentry-hyperv-inventory`, fetched head `605866aa1b3736e52357cc9aff52272c73cb2ded`.
- GitHub Actions run `33913985331`, job `101156784267`, conclusion `success`.
- Artifact `9952447606`, name `layersentry-dr-r0-live-inventory-33913985331`, retained until 2026-10-04 according to GitHub metadata.
- Artifact assertions: `R0_READ_ONLY`; `MUTATION_PERFORMED=false`; Hyper-V VMMS running; one VM named `sen` running with nested virtualization exposed; one internal `Cozystack-NAT` switch; CloudStack UI endpoint reachable with HTTP 200; unauthenticated `listCapabilities` rejected with HTTP 401.
- Exact Apache CloudStack documentation tag `4.22.1.1` from `apache/cloudstack-documentation`.
- Apache CloudStack 4.22.1.1 source package requirements and `db.properties`/database connection implementation.

## Database compatibility finding

The exact official documentation tag is internally inconsistent: `source/releasenotes/compat.rst` lists `MySQL 8.4 (or equivalent compatible DBMS)`, while `source/installguide/management-server/_database.rst` says CloudStack has been tested with MySQL 8.0. Documentation history attributes the 8.4 compatibility-matrix change to the 2026-03-10 commit `c3f0a0fcae1ef4c4b558f0f364235dcf66883ea7`, while the installation-guide 8.0 statement remains. The exact CloudStack source packaging also accepts `mysql`, `mariadb`, or `mysql8.4`; package acceptance is not proof that MySQL 8.4 Group Replication/InnoDB Cluster has passed LayerSentry workload, failover, or upgrade tests.

Consequently neither MySQL 8.0 nor 8.4 is promoted as the LayerSentry HA database baseline by documentation inference alone. The version/topology decision remains `PENDING` until a candidate matrix is executed against the exact 4.22.1.1 release artifact on Rocky Linux 9.

## Advantages and disadvantages of the current hold point

Advantages: it prevents an untested database version/topology from becoming a production default; preserves CloudStack JDBC and schema semantics; and keeps rollback possible before any database mutation. Disadvantages: it blocks installer finalization and control-plane HA certification until sufficient lab capacity and repeatable tests exist.

## Alternatives considered

1. CloudStack's documented connector-level source/replica HA and two-way replication: closest to historical documentation, but the HA guide still describes old MySQL generations and limitations and is insufficient certification evidence for the current target.
2. MySQL 8.0 single-primary Group Replication/InnoDB Cluster: aligns with the installation guide's tested-version statement but still needs exact CloudStack failover and upgrade proof.
3. MySQL 8.4 single-primary Group Replication/InnoDB Cluster: aligns with the exact release compatibility matrix and package alternative but conflicts with the unchanged installation-guide tested-version statement and lacks LayerSentry runtime proof.
4. External HAProxy, ProxySQL, MySQL Router, or VIP routing: can provide a stable endpoint but adds its own quorum, routing, health-check, and split-brain behavior that must be tested; it does not make an unsupported database topology safe.
5. A single database node: operationally simpler but does not satisfy the production HA target.

## Recommendation and reason

Keep the candidate architecture as a three-member, single-writer, quorum-based database service behind a separately tested stable routing endpoint, but do not select MySQL 8.0 versus 8.4 or the routing product yet. First run an explicit compatibility matrix using exact immutable CloudStack 4.22.1.1 artifacts. This is superior to choosing from one contradictory sentence because it measures the actual JDBC, transaction, schema, failover, recovery, and upgrade behavior that LayerSentry must support.

## Implementation impact

Workstream D adds a dispatch-only authenticated CloudStack R0 API inventory workflow in the runner repository. It accepts the API endpoint as a dispatch input, consumes API credentials only from GitHub secrets, signs requests in memory, performs only list operations, stores a fixed allowlisted projection of responses, and never writes credentials or request URLs to the artifact. No CloudStack backend, schema, KVM agent, database, network, storage, VM, or live configuration is changed.

## Risks and mitigations

- Credential exposure: fixed secret names, no credential output, generic API failure messages, and sanitized allowlisted evidence fields.
- Accidental mutation: the workflow contains only explicit `list*` API calls and declares `MUTATION_PERFORMED=false` only after all calls succeed.
- Endpoint misuse: only HTTP/HTTPS endpoints ending in `/client/api` are accepted; production certification must require HTTPS even though the present lab endpoint is HTTP.
- Excess privilege: provision a scoped inventory identity where CloudStack permissions permit; if platform-admin visibility is required, keep the credential in the runner secret boundary and rotate it according to policy.
- False HA inference: one reachable VM is not a second Site, database quorum, LB pair, independent failure domain, or fencing proof.

## Tests performed

- Existing runner evidence run and downloaded artifact were inspected without live mutation.
- The new workflow passed YAML parsing, structural assertions, `git diff --check`, fixed-secret reference inspection, and source review against the exact 4.22.1.1 API command names.
- No authenticated workflow was dispatched because the repository currently lists no configured LayerSentry CloudStack API secret names.
- No database, HA, DR, VM, network, storage, package, firewall, SELinux, reboot, upgrade, failover, or fencing action was executed.

## Rollback and recovery

The source-only workflow can be removed by reverting its commit. It is dispatch-only and cannot run on push. A failed credential preflight occurs before an API call and before evidence claims completion. The evidence document changes no runtime state.

## Production-readiness status and next gate

- Hyper-V host/one-VM reachability discovery: `LIVE_VERIFIED` only for the exact assertions in run `33913985331`.
- Authenticated CloudStack inventory: `BLOCKED` pending provisioning of `LAYERSENTRY_CLOUDSTACK_API_KEY` and `LAYERSENTRY_CLOUDSTACK_SECRET_KEY`, then a successful dispatch and artifact review.
- Second independent Rocky Linux 9/KVM failure domain: `BLOCKED`; current inventory contains one VM on one Hyper-V host.
- Native two-Zone NAS B&R recovery: `BLOCKED` by authenticated inventory and missing second target capacity; no recovery point was created or restored.
- Database version/topology selection: `PENDING` and `NOT_TESTED`.
- 3-Management/3-DB/2-LB control-plane HA: `NOT_TESTED`.
- Production certification: `PENDING`.

After scoped credentials are provisioned, dispatch the authenticated R0 workflow, verify Zone/Pod/Cluster/KVM host/storage/B&R/provider/VM/async-job inventory, and only then prepare an R3/R4 checkpoint for any native backup/recovery or HA mutation.
