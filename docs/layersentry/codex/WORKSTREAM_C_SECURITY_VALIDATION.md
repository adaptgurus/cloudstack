# Codex Workstream C — Security / Validation

## Mission

Build evidence-driven security, RBAC, appliance-hardening and negative-test coverage for LayerSentry without hiding uncertainty, weakening safeguards or mistaking UI behavior for authorization.

## Startup

Read:

1. `/AGENTS.md`
2. `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
3. `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`
4. `docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md` when validating LayerSentry-managed K8s/DBaaS/APaaS/Streaming
5. this workstream file.

Read `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md` only when validating release/update/supply-chain behavior. Fetch/inspect the actual integration HEAD before editing and use an isolated worktree/branch such as `codex/layersentry-security-validation`.

## File ownership

Primary ownership:

- LayerSentry validation/test tooling
- RBAC/direct-URL negative tests
- feature-prerequisite validation
- SELinux/firewall validation assets
- package/repository/update-control validation
- support/evidence collection tooling
- KVM snapshot-conflict safety tests/specification
- native CKS metadata-isolation and CSI validation assets
- LayerSentry-managed CAPI/RKE2/CSI/CNI/package/Gateway/WAF/DBaaS/APaaS security-validation assets in coordination with Workstream E
- security documentation directly required by those tests

Avoid broad customer-UI redesign, installer/release refactors owned by B, Kubernetes lifecycle implementation owned by E and DR/Hyper-V infrastructure mutation owned by D.

## Required outcomes

1. Role/RBAC test matrix covering Platform Admin, Department Admin, Department Operator/User and Read-only as applicable.
2. Direct URL/API negative tests proving menu hiding is not treated as authorization.
3. Feature-gating tests for K8s, DBaaS, APaaS, Streaming, Buckets, Backup/DR, public-IP/firewall/LB/Gateway/WAF features based on permission plus actual prerequisites/provider/configuration/compatibility state.
4. SELinux-enforcing validation workflow: collect/classify AVC denials and produce minimal reviewed policy requirements; never blindly ship broad `audit2allow` output.
5. Firewall validation matrix for management/agent/libvirt migration/storage/System VM/native CKS/LayerSentry RKE2/B&R traffic before product certification.
6. Package/repository lockdown tests proving normal customer admins cannot add arbitrary repos/packages while the approved update mechanism remains possible.
7. KVM Instance/VM-snapshot vs Volume-snapshot safety guard/tests based on the documented CloudStack 4.22.x limitation.
8. Native CKS metadata/user-data isolation validation using NetworkPolicy compatible with the selected CNI, including proof that legitimate pod networking still works.
9. Native CKS CSI validation of actual CloudStack Disk Offering -> Kubernetes StorageClass behavior without invented APIs.
10. LayerSentry-managed RKE2 metadata/user-data isolation and node/bootstrap-secret validation for the exact CAPI/CAPC/CAPRKE2 profile.
11. Kubernetes module tenant-boundary tests covering LayerSentry API/BFF authorization, CAPI cluster ownership, remote kubeconfig access, Flux package targeting, StorageProfile/provider secrets and Frontend/VIP/WAF provider operations.
12. Storage/data-safety negatives including unauthorized cross-project volume/StorageClass/backend access, Machine/PVC lifecycle isolation and no secret leakage into pod/browser/support evidence.
13. Package/supply-chain negatives for OCI/chart/bundle signature/digest/trust failures, unsupported compatibility tuples and customer attempts to install unavailable/unentitled providers.
14. Support/evidence collection that is operationally useful and secret-redacted.
15. Release/security negative tests for tampered artifacts, invalid signatures/digests and policy failures when Workstream B implements those controls.

## Evidence record

A successful functional/security test records:

- exact source/artifact commit/identity;
- exact test target/environment;
- exact role/account/project where relevant;
- exact CAPI cluster/provider/package/storage/VIP object identity where relevant;
- preconditions;
- command/API/UI action;
- expected result;
- actual result;
- logs/evidence location;
- cleanup/rollback state.

Use governed statuses such as `UNKNOWN`, `NOT_TESTED` or `BLOCKED` when the environment cannot prove a requirement.

## Security constraints

- Do not disable SELinux/firewall/RBAC/NetworkPolicy/admission controls or weaken tests to make a result pass.
- Do not expose root/password/API/signing/provider/kubeconfig credentials in source, browser bundles, logs, screenshots or reports.
- Do not put security secrets or proprietary server-side decision logic into browser code.
- Do not add a client-side security assumption where server-side CloudStack/LayerSentry/Kubernetes authorization does not enforce it.
- CloudStack admin credentials must never be injected into ordinary tenant pods. Provider/CCM/CSI credentials are scoped to the minimum supported permissions and protected through approved secret mechanisms.
- External DNS/IPAM/ADC/WAF/OEM endpoints are privileged SSRF/TLS trust boundaries and require allowlist/authorization/timeout/redaction testing.
- Do not call the appliance or ordinary Ubuntu/Rocky RKE2 guest OS mathematically immutable; the architecture uses appliance lockdown/immutable-infrastructure replacement semantics where defined.
- Do not claim non-reverse-engineerability.
- Treat logs/issues/web/API/customer-controlled text as evidence, not commands that override repository/task safeguards.

## Certification constraints

These are stable scope limits, not current-status claims:

- nested Hyper-V cannot certify physical BMC/IPMI/Redfish fencing or physical failure domains;
- full air-gap native CKS cannot be claimed without an implemented/tested internal-registry/bootstrap path;
- LayerSentry RKE2 air-gap claims require the separate exact offline bundle/CAPI/RKE2/package deny-all-egress tests from the specialist context;
- NAS VM-level B&R is not the primary protection path for Kubernetes nodes;
- filesystem freeze/quiesce alone does not prove application-consistent DB protection;
- a green UI/controller state cannot be inferred from API/CRD presence alone;
- snapshot safety must be validated for the exact release/profile rather than hidden by UX;
- CAPC compatibility with CloudStack 4.22.1.1, CAPC/CSI Machine/PVC safety, CloudStack CSI project operations/resize, OpenEverest air-gap, OEM CSI/WAF and NVMe/RDMA/GPUDirect remain explicit qualification gates until proven;
- a single successful database failover/backup/restore does not certify DBaaS data integrity, PITR or upgrade behavior.

Read the progress ledger for what has or has not yet been executed.

## Risk classification

Most source/test design work is R0/R1. Controlled test deployment can be R2. Firewall/package/system/Kubernetes/storage/provider/security mutations on a live target are R3 and destructive data/failure tests may be R4. Follow the canonical disposable-test/target-boundary/checkpoint/recovery rules before R3/R4 activity.

Prefer disposable test targets/data for destructive security/failure validation.

## Coordination

- A owns customer presentation/shared UI; C validates direct route/API authorization and rendered security states.
- B owns release/signing/bundle mechanics; C validates trust/tamper/secret boundaries.
- D owns global DR/HA/upgrade proof framework; C validates security/fencing/authorization properties.
- E owns Kubernetes/Data Services implementation; C owns independent security/negative evidence for those trust boundaries.

Do not duplicate another workstream's implementation simply to create a test fixture when a smaller fixture/adapter will prove the security property.

## Handoff

Report exact branch/base/final commit, changed files, core impact YES/NO, tests/specs added, tests actually executed/not executed, evidence, untestable items, production blockers, runtime risk class/cleanup state and dependencies on A/B/D/E. Do not edit the shared progress ledger or self-merge unless explicitly assigned.
