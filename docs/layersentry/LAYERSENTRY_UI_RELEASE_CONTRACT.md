# LayerSentry UI Release Contract v1

## Decision and status

Status: `SOURCE_COMPLETE` foundation; CI and Rocky Linux 9 deployment are `NOT_TESTED`.

The current Rocky installer paths build Vue on the Management Server. That is useful
for development recovery, but it adds a compiler, package-manager network activity
and mutable dependency resolution to a production trust boundary.

The selected first gate is a CI-built UI archive accompanied by a versioned manifest,
SHA-256 digests, CycloneDX 1.5 SBOM and source/builder provenance. Production source
maps are disabled by default. A support build can opt in with
`LAYERSENTRY_SUPPORT_BUILD=1`, but cannot be promoted under the production policy.

## Alternatives considered

- Continue building on Management Servers: simple today, but non-deterministic and
  contrary to the appliance/release contract.
- Package immediately as an RPM: strong eventual option, but prematurely couples
  the first artifact contract to package/repository/signing design.
- Start with a transport-neutral tar archive and signed-manifest-ready metadata:
  smallest upgrade-friendly foundation for later RPM or registry publication.

The transport-neutral archive is selected. Its deterministic archive controls fix
ordering, ownership, timestamps and gzip metadata. This is not yet a reproducible-build
claim because dependency resolution and CI image identity require stronger proof.

## Contract and trust behavior

`build-ui-release.sh` emits one UI tar archive, `release-manifest.json`, a CycloneDX
SBOM, provenance and `SHA256SUMS`. The verifier validates schema/compatibility,
expected source commit, artifact and metadata digests, archive path/type safety,
required UI files and the absence of source maps.

It rejects unsigned candidates by default. The explicit `--allow-unsigned` option
exists only for CI development of this foundation. No production installer consumes
this unsigned contract yet. Signature creation, trust roots, rotation/revocation,
installer preflight, atomic promotion and rollback remain separate mandatory gates.

## Risks, mitigation and recovery

- npm lock/manifest drift remains inherited from upstream and prevents a full
  deterministic dependency-source claim until the candidate workflow succeeds;
  the workflow now uses lockfile-strict `npm ci` and fails if the lockfile changes.
- `npm ci --ignore-scripts` was not selected because this UI has lifecycle hooks
  and its dependency install-time requirements have not been proven safe without
  scripts. Dependency lifecycle scripts therefore run only in the isolated build
  job, which has read-only repository permission and receives no release secrets.
- GitHub runner labels and action tags are not immutable builder digests; the exact
  Node version is pinned and builder strengthening remains pending.
- The SBOM reflects lockfile components and is a valid foundation, not evidence of
  vulnerability or license-policy acceptance.
- Rollback for this source-only R1 batch is `git revert` of its commit. No runtime,
  package, database, network or CloudStack state is mutated.

## Tests

The focused unit suite covers valid candidate verification, default unsigned
rejection, artifact tampering, SBOM tampering, source-commit mismatch and a source-map
archive with internally consistent updated digests. CI must additionally perform the
real UI lint/unit/build and contract verification before this becomes `CI_VERIFIED`.
