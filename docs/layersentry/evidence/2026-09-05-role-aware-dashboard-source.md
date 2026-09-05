# Role-aware self-service dashboard source evidence

**Date:** 2026-09-05

**Workstream:** A — UI / Self-Service

**Risk:** R1 source-only

**Status:** SOURCE_COMPLETE after recorded source checks; runtime remains NOT_TESTED

## Decision

The existing dashboard already reused CloudStack account/project usage and resource-list APIs, but presented the same undifferentiated surface to Domain Administrators, normal users and read-only custom roles. The selected foundation keeps those APIs and adds a presentation model derived from the authenticated CloudStack `roletype`, active project scope and APIs granted by `listApis`.

The dashboard now identifies Department Administrator, Project, User and Read-only contexts. A Create Instance shortcut appears only when the corresponding CloudStack mutation API is present. This is usability behavior, not authorization; CloudStack server-side RBAC remains authoritative.

## Alternatives and tradeoffs

- Separate dashboard implementations per role were rejected for this batch because they duplicate the existing usage/account API behavior and increase drift.
- Role-name string matching was rejected because custom role names are operator-controlled and do not prove capability.
- Provider-aware Kubernetes/Bucket/Backup route gating was deferred because current route generation completes before asynchronous provider discovery. Adding superficial API-only gating would violate the prerequisite contract; changing login orchestration requires a separately reviewed batch.

The capability-derived approach is small and deterministic. Its limitation is that read-only classification covers the principal LayerSentry self-service mutations, not every possible CloudStack mutation. Platform Administrators continue to use the existing capacity dashboard outside project scope.

## Validation and rollback

Unit coverage exercises project precedence, Domain Admin mapping, user/read-only capability distinction, permitted quick actions and empty API sets. JSON parsing, whitespace/static checks and the narrow unit command are recorded during handoff.

No runtime is mutated. Revert the coherent source commit to restore the prior dashboard. Rocky Linux 9 served-UI validation in Chrome and Firefox, accessibility review and direct-URL/API RBAC negatives remain required before `LIVE_VERIFIED`. Existing architecture relationships did not change, so the knowledge graph and Super Master Context require no update; the integration lead owns the shared progress ledger.
