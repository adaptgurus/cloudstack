# LayerSentry V1 — Historical Master-Context Re-audit (2026-09-04)

> **Status: SUPERSEDED / ARCHIVAL.** The validated findings from this re-audit have been folded into `docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md` context schema 2.0. This file is retained only as an audit pointer. It is **not mandatory startup context** and must not override the canonical Super Master Context, the current progress ledger, current repository state, workflow evidence or live-runtime evidence.

Git history preserves the full original re-audit and its detailed reasoning.

## Findings incorporated into the canonical context

The 2026-09-04 re-audit established or clarified the following rules, all of which are now represented in the canonical Super Master Context:

1. Use version-pinned Apache CloudStack 4.22.1.x documentation/source; do not rely on `/latest/` alone.
2. LayerSentry V1 product baseline is Rocky Linux 9, Java 17 and MySQL 8.4/equivalent for the target CloudStack generation.
3. Use the full secure KVM/libvirt guidance; do not make old insecure quick-install libvirt TCP settings production defaults.
4. SELinux enforcing requires reviewed policy engineering and live validation, not merely changing the mode.
5. For delegated enterprise administration, Department normally maps to CloudStack Domain, teams/workloads to Accounts, and Users in the same Account are not isolated from each other.
6. Feature visibility requires RBAC permission plus product/configuration/provider/prerequisite state; route/API presence alone is insufficient.
7. VM-create `Backup Policy` is product-level post-deploy B&R orchestration, not a native `deployVirtualMachine` parameter.
8. CKS CSI semantics must follow actual CloudStack APIs; Disk Offerings synchronize to Kubernetes Storage Classes rather than inventing unsupported fields.
9. Production CKS must address pod access to CloudStack metadata/user-data and validate NetworkPolicy behavior.
10. Complete air-gap CKS is not established by the Kubernetes binaries ISO alone; internal-registry/bootstrap work requires separate proof.
11. Cross-zone DR based on NAS B&R has repository reachability, destination mapping, original-instance-record retention and throughput/RTO dependencies.
12. NAS VM-level B&R is not the primary protection method for CKS nodes; application/database consistency requires workload-aware protection.
13. KVM Instance/VM snapshots and Volume snapshots have documented coexistence/restore safety risks that LayerSentry must guard and test.
14. A same-host nested two-VM DR lab can prove functional recovery assertions but cannot certify physical site independence, real WAN failure domains or hardware fencing.
15. Keeping firewalld enabled is a LayerSentry hardening divergence that requires a full traffic-path validation matrix before certification.
16. The 3-Management / 2-LB / 3-DB architecture is a certification target, not automatically proven by documentation.

## Historical-status warning

The original re-audit also contained source-state observations that were true when it was written, including statements about DBaaS/APaaS placeholders and pending installer work. Those observations are deliberately **not reproduced here** because later work superseded them.

For current completion state and evidence, read:

`docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md`

For current source, fetch the actual branch HEAD.
