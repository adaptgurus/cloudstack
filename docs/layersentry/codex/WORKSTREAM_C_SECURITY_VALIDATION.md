# Codex Workstream C — Security / Validation

## Mission

Build evidence-driven security, RBAC, appliance-hardening, and negative-test coverage for LayerSentry without hiding uncertainty or weakening upstream CloudStack behavior.

## Startup

Read `/AGENTS.md`, `docs/layersentry/CODEX_MASTER_CONTEXT.md`, and all mandatory documents. Fetch the actual integration HEAD and create/use an isolated branch/worktree such as `codex/layersentry-security-validation`.

## File ownership

Primary ownership:

- new LayerSentry validation/test tooling
- RBAC/direct-URL negative tests
- SELinux/firewalld validation assets
- package/repository-lock validation
- support/evidence collection scripts
- KVM snapshot-conflict safety tests/specification
- CKS metadata-isolation and CSI validation assets
- security documentation directly required by the tests

Avoid broad customer-UI redesign, installer/release refactors owned by Workstream B, and DR/Hyper-V infrastructure mutation owned by Workstream D.

## Required outcomes

1. Create a role/RBAC test matrix covering Platform Admin, Department Admin, Department Operator/User, and Read-only as applicable.
2. Verify menu visibility is not treated as authorization; direct URLs/API mutations must be denied server-side when unauthorized.
3. Define/test feature-gating prerequisites for K8s, Buckets, Backup/DR, public-IP/firewall/LB features.
4. Build SELinux enforcing validation workflow: collect AVC denials, classify them, and produce minimum reviewed policy requirements; never blindly ship broad `audit2allow` output.
5. Build firewalld-enabled validation matrix for management/agent/libvirt migration/storage/System VM/CKS/B&R traffic before product certification.
6. Define/validate package/repository lockdown behavior: normal customer admins cannot add repos or arbitrary packages; approved update mechanism remains possible.
7. Add KVM Instance-snapshot vs Volume-snapshot conflict guard/test requirements based on the documented 4.22 limitation.
8. Validate CKS metadata/user-data isolation using NetworkPolicy compatible with the selected CNI.
9. Validate CKS CSI enablement and Disk Offering -> StorageClass behavior without inventing unsupported APIs.
10. Produce support/evidence bundles that expose enough diagnostic information without secrets.

## Evidence discipline

A successful test must record:

- exact source commit
- exact target/environment
- exact role/account used
- command/API/UI action
- expected result
- actual result
- logs/evidence location

Use `UNKNOWN`/`NOT_TESTED` when the lab cannot prove a requirement, especially physical OOBM/fencing and independent-site failures.

## Security constraints

- Do not disable SELinux/firewall merely to make tests pass.
- Do not expose root/password credentials in reports.
- Do not put signing/private keys in the repository.
- Do not add client-side security assumptions that server-side RBAC does not enforce.
- Do not call the appliance immutable until the actual mechanism is implemented and tested; current target wording is appliance-locked.
- Do not claim non-reverse-engineerability.

## Current limitations to preserve

- Physical IPMI/Redfish fencing cannot be certified in the nested Hyper-V lab.
- Full air-gap CKS remains pending.
- NAS B&R is not the primary protection path for CKS nodes.
- Application-consistent DB backup requires application-native methods/hooks beyond filesystem freeze alone.

## Handoff

Report exact branch/base/final commit, tests/specs added, tests actually executed, evidence, untestable items, production blockers, and dependencies on A/B/D. Do not edit the shared progress ledger unless explicitly assigned.
