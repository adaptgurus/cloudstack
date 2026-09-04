# UI Dependency Lock Repair Evidence — 2026-09-05

Status: `SOURCE_COMPLETE` with local pinned-toolchain build evidence. The hosted
release workflow and Rocky Linux 9 artifact deployment remain `NOT_TESTED`.

## Observed failure and root cause

With Node 16.20.2/npm 8.19.4, plain `npm ci --no-audit --no-fund` rejected the
checked-in npm-v6 lock. The manifest had moved beyond it, including direct
`axios`, `nan`, `node-gyp` and `semver` requirements. During old-lock metadata
repair npm also interpreted nested `vue-loader-v16` alias data as a request for
a package named `vue-loader-v16@16.8.3`, which does not exist.

This was dependency metadata drift, not a missing application source module.

## Alternatives and decision

1. Return the workflow to `npm install`: rejected because it permits resolution
   drift and violates the immutable release-build contract.
2. Generate a new lock from current open manifest ranges: rejected after it
   selected dependencies requiring Node 18/20/24 and therefore silently changed
   the tested 4.22 dependency graph.
3. Upgrade the existing resolved graph to npm lockfile v2 using the exact pinned
   npm and its required legacy peer mode: selected because it preserves known
   dependency intent while making alias and direct-dependency metadata complete.

`ui/.npmrc` records `legacy-peer-deps=true`; this is required by the legacy Vue
CLI 4 peer topology and ensures lock generation and `npm ci` use the same mode.
Tests are not weakened: lint, the full unit suite and production build still run.

The exact 4.22.1.1 UI README recommends Node 24 for general development, while
the existing upstream UI workflow still selects Node 16. Direct validation below
proves the retained graph works with Node 16.20.2/npm 8.19.4. LayerSentry keeps
that exact release-builder pin for this baseline rather than combining a lock
repair with a major runtime/dependency migration. Node 24 builder migration must
be handled separately with its own lock generation and full regression evidence.
Node 16 is end-of-life, so this compatibility result does not by itself satisfy
the production builder-security gate.

## Validation performed

- original failure reproduced with pinned Node 16.20.2/npm 8.19.4;
- repaired lock accepted by clean `npm ci` in recorded legacy peer mode;
- second clean install produced the same package-lock SHA-256 before and after:
  `1a0bf395144b036bb81ff651091d7926adefd2d3a3cfc159af8cdca6deaabac1`;
- UI lint: passed with no errors;
- UI unit tests: 5 suites, 180 tests passed;
- production UI build: passed; only existing asset-size/caniuse warnings emitted;
- dependency deprecation warnings remain and require separate vulnerability and
  modernization review before production certification.

The test environment was local engineering Linux, not Rocky Linux 9 acceptance.
No runtime, package repository, CloudStack service, database, network or VM was
mutated.

## Rollback and next gate

This is an R1 source-only change. Rollback is a Git revert of the lock repair and
`.npmrc` addition. The next gate is the hosted candidate workflow using the exact
source commit, followed by artifact/signature installer and Rocky Linux 9 gates.
