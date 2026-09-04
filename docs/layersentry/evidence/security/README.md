# LayerSentry Security Validation Contract

**Status:** `SOURCE_COMPLETE` for the matrix/evidence contract; live RBAC behavior is `NOT_TESTED`.

The first security-validation gate is a reusable, read-only RBAC matrix in
`tools/layersentry/security/rbac_matrix.json`. It separates three assertions:

1. a hidden menu cannot be bypassed with a direct route;
2. CloudStack rejects an unauthorized direct API call;
3. a foreign tenant object ID is rejected or returns an empty result.

Platform Administrator route/API positive controls distinguish a broadly
broken test target from a correctly denied lower-privilege request.

The matrix deliberately contains only read-only CloudStack API commands. An
unexpected authorization success therefore discloses visibility but does not
mutate the target. Runtime credentials and fixture IDs must be supplied by the
approved integration runner from its secret store; they never belong in this
matrix, CLI arguments, logs, or evidence.

`evidence.schema.json` is the v1 machine-readable output contract. It stores a
hash of the target URL and raw response, not the URL or response body. It also
requires exact source identity, governed status, per-role expected/actual
results, and cleanup state.

Run the source gate:

```bash
python3 tools/layersentry/security/validate_rbac_matrix.py \
  tools/layersentry/security/rbac_matrix.json
python3 -m unittest tools/layersentry/security/test_validate_rbac_matrix.py
```

An optional `--emit-not-tested PATH` creates a schema-shaped planning record.
It must not be treated as execution evidence. The next gate is a reviewed
runner adapter that resolves ephemeral role sessions and authorized foreign
object fixtures, executes this exact matrix on Rocky Linux 9, validates output
against the JSON Schema, and retains sanitized evidence.

## Decision record

- Current approach: no dedicated LayerSentry RBAC/direct-route evidence harness existed.
- Advantages of the selected approach: stdlib-only linting, explicit role and tamper coverage, read-only failure safety, no credential persistence, stable evidence contract.
- Disadvantages: it does not execute browser/API calls yet and cannot prove deployed RBAC.
- Alternatives: extend legacy Marvin suites immediately, embed credentials in a local integration configuration, or wait for A/B implementation. Marvin is useful for later live integration but is heavier and does not itself define sanitized evidence; credential files violate the secret boundary; waiting leaves no reusable contract.
- Recommendation: integrate this source-only contract first, then add runner execution after ephemeral identities/fixtures are available.
- Impact: validation tooling/docs only; no CloudStack API, RBAC, database, UI, KVM agent, or installer behavior changes.
- Risks and mitigations: role definitions may vary by deployment, so live role-to-account mapping remains explicit runner configuration; API negatives are read-only; raw bodies and target URLs are represented by hashes.
- Tests performed: matrix lint and focused Python unit tests.
- Rollback: revert the single tooling/documentation commit; no runtime cleanup is required.
- Production readiness: RBAC runtime behavior remains `NOT_TESTED` until Rocky Linux 9 direct-route/API/object-tampering execution evidence exists.
