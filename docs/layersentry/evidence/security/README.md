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
object fixtures and executes this exact matrix on Rocky Linux 9.

The executable evidence boundary is
`tools/layersentry/security/evaluate_rbac_observations.py`. A browser/API adapter
streams bounded observations over stdin; the evaluator rejects any
secret-named field, requires exact matrix coverage, independently classifies
the outcomes, hashes the target and response bodies, and creates (without
overwriting) a mode-`0600` evidence file. Authentication stays entirely in the
runner adapter/process environment. Example integration shape:

```bash
browser_and_api_adapter \
  | python3 tools/layersentry/security/evaluate_rbac_observations.py \
      tools/layersentry/security/rbac_matrix.json evidence.json \
      --status LIVE_VERIFIED
```

The evaluator returns `1` and records `PARTIAL` if any assertion fails; malformed,
incomplete, duplicate, oversized, or secret-bearing input returns `2` without
creating trusted evidence. The remaining gate is implementing the controlled
browser/API observation adapter, validating the output against the JSON Schema,
and retaining it as a runner artifact.

## Decision record

- Current approach: no dedicated LayerSentry RBAC/direct-route evidence harness existed.
- Advantages of the selected approach: stdlib-only linting/evaluation, explicit role and tamper coverage, read-only failure safety, stdin-only observation transport, no credential persistence, bounded inputs, and a stable body-free evidence contract.
- Disadvantages: a browser/API adapter must still acquire runtime identities and perform the calls; source tests cannot prove deployed RBAC.
- Alternatives: extend legacy Marvin suites immediately, embed credentials in a local integration configuration, or wait for A/B implementation. Marvin is useful for later live integration but is heavier and does not itself define sanitized evidence; credential files violate the secret boundary; waiting leaves no reusable contract.
- Recommendation: integrate this source-only contract first, then add runner execution after ephemeral identities/fixtures are available.
- Impact: validation tooling/docs only; no CloudStack API, RBAC, database, UI, KVM agent, or installer behavior changes.
- Risks and mitigations: role definitions may vary by deployment, so live role-to-account mapping remains explicit runner configuration; API negatives are read-only; raw bodies and target URLs are represented by hashes.
- Tests performed: matrix lint and focused Python unit tests.
- Rollback: revert the single tooling/documentation commit; no runtime cleanup is required.
- Production readiness: RBAC runtime behavior remains `NOT_TESTED` until Rocky Linux 9 direct-route/API/object-tampering execution evidence exists.
