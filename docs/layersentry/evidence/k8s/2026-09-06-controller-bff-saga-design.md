# Workstream E — LayerSentry Kubernetes BFF/controller saga foundation

**Date:** 2026-09-06  
**Status:** `SOURCE_COMPLETE` for the framework-neutral BFF/saga foundation; provider adapters and runtime are `NOT_TESTED`  
**CloudStack core impact:** none

## Decision and source validation

The specialist architecture requires LayerSentry to orchestrate supported CloudStack, CAPI/CAPC/CAPRKE2, Kubernetes and Flux APIs without becoming a second VM scheduler. It also requires composite requests to be durable sagas, preserve provider/resource/job IDs, and treat mutation timeouts as `UNKNOWN` until authoritative state is observed.

The implementation therefore separates:

- a WSGI BFF boundary for authenticated JSON requests;
- server-owned policy/evidence gates from `layersentry_k8s_policy.py`;
- an injected authorizer that checks each exact project/action;
- a durable SQLite WAL operation/event journal;
- one-step reconciliation through an adapter interface;
- a separate observation path for ambiguous outcomes.

No browser-supplied role/project header is trusted. Default authentication and authorization both deny all. Mutation requests require a 16–128 character idempotency key bound to the canonical request plus authenticated subject. Unknown JSON fields are rejected. Adapter resource metadata containing credential-like fields is rejected instead of persisted.

## Advantages and alternatives

- Returning `202` with an operation resource avoids holding one HTTP request across CAPI/RKE2 convergence.
- Immutable request fingerprints prevent reuse of one idempotency key for a different cluster or subject.
- Optimistic versions prevent two local workers from silently overwriting one operation.
- Blind retry after a timeout was rejected; only `observe_ambiguous` may move an `UNKNOWN` operation.
- Adding these APIs to Apache CloudStack core was rejected because the modules and saga state are LayerSentry-owned.
- A shell-command workflow was rejected because it cannot provide transactional intent, replay safety or exact audit state.

## Risks and mitigations

SQLite WAL is durable for one controller host but is not a distributed coordination system. The first packaged deployment must run one active reconciler, take tested backups and recover the journal on restart. Before active/active controller HA, replace or wrap this store with a tested transactional shared backend and lease/claim model.

Authentication, CloudStack RBAC lookup and provider clients are deployment integrations, not inferred by this source. The included BFF cannot serve requests with its default deny-all authenticator. Provider adapters must return sanitized resource IDs/conditions only; credentials remain runtime-injected.

## Tests performed

Local unit coverage proves:

- durable create/get and event journal behavior;
- exact-request idempotency and collision denial;
- authorization and release gates run before persistence;
- optimistic stale-writer rejection;
- mutation timeout enters `UNKNOWN`, normal advance cannot replay it, and observation can reconcile it;
- default BFF authentication denies all;
- missing idempotency keys fail;
- provider secret metadata is not persisted.

The complete Workstream E Python suite passed 32 tests at this checkpoint. No network, CloudStack, Kubernetes, CAPI, Flux, Rocky Linux or browser request was executed.

## Rollback/recovery and next gate

Stop the reconciler before restoring the SQLite database and its WAL/SHM files from a consistent backup. On restart, inspect `UNKNOWN` and in-progress operations through authoritative APIs before resuming. Never delete the journal merely to unblock a resource.

Next, add exact CAPI/CAPC/CAPRKE2 resource builders and Kubernetes/Flux API adapters for E1 cluster create/status/delete/scale. Keep all mutation entry points fail-closed while release gates or deployment authentication/RBAC are absent.
