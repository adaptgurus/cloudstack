# LayerSentry V1 — Master Context Re-audit (2026-09-04)

## Purpose and authority

This file records a deep re-audit of `LAYERSENTRY_SUPER_MASTER_CONTEXT.md` against the current LayerSentry source and version-pinned Apache CloudStack 4.22.1 documentation.

The existing master context is **largely correct**, but this audit found important clarifications and guardrails that must be applied before implementation. Until these points are folded directly into the main master context, this file is an authoritative companion and **overrides conflicting or less-specific wording** in the older sections.

Future ChatGPT/Codex sessions must read, in this order:

1. `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`
2. this re-audit file
3. `LAYERSENTRY_PROGRESS_LEDGER.md`
4. actual current repository/workflow/live evidence

Repository/runtime evidence still overrides all historical text.

---

## 1. Documentation-version discipline

Capability and requirement claims for LayerSentry V1 must use **version-pinned CloudStack 4.22.1.0 documentation** plus **4.22.1.1 release notes/fixes**.

Do not use the unversioned `/en/latest/` documentation as the sole authority because `latest` can move to a later CloudStack release and silently change requirements or capabilities.

Preferred evidence order for support/capability questions:

1. current source at the exact CloudStack/LayerSentry commit;
2. 4.22.1.1 release notes for patch-specific fixes;
3. 4.22.1.0 Administrator/Installation/Plugin documentation;
4. older 4.22/4.21 documentation only when an exact 4.22.1 page is unavailable and the behavior is cross-checked against current source/release notes.

---

## 2. Rocky Linux / Java / database compatibility correction

Version-pinned CloudStack 4.22.1.0 compatibility documentation lists:

- Rocky Linux 8, 9 and 10 as supported Management Server operating systems;
- Rocky Linux 8, 9 and 10 with KVM as supported hypervisor hosts;
- Java JRE 17;
- MySQL **8.4**, or an equivalent compatible DBMS.

Therefore LayerSentry V1 should standardize the supported database baseline as **MySQL 8.4/equivalent**, not merely a generic “MySQL 8” statement.

The planned three-database-node topology remains **DESIGN_DEFINED / NOT CERTIFIED** until it is deployed and failure-tested on the exact LayerSentry release.

The compatibility matrix also notes a known `ipmitool` issue on EL/SUSE distributions that may affect out-of-band management. Because LayerSentry intends to use KVM Host HA/fencing on Rocky Linux 9, OOBM must be tested on the target physical hardware. A nested Hyper-V POC cannot certify real BMC/IPMI/Redfish fencing behavior.

---

## 3. KVM live-migration security rule

The production KVM configuration must follow the full CloudStack 4.22.1 KVM installation guidance rather than older quick-install examples that enabled unsecured libvirt TCP on port 16509.

For the LayerSentry production profile:

- do not deliberately expose insecure unauthenticated libvirt TCP;
- follow the current full KVM guide that disables insecure TCP and allows CloudStack to establish its required host security/certificate configuration;
- validate the current documented KVM/libvirt migration ports and certificate behavior on Rocky Linux 9;
- keep host configuration homogeneous across every Compute Cluster;
- never weaken libvirt security merely to make the nested lab easier.

The nested POC may require environment-specific workarounds, but those must be marked **LAB ONLY** and must never become production defaults.

---

## 4. SELinux clarification

The current master context is correct to target SELinux **enforcing** in production, but this is not achieved by simply changing the mode from permissive to enforcing.

CloudStack installation documentation notes permissive mode during installation and explicitly says that production should use enforcing mode with the necessary policies.

Therefore LayerSentry must:

1. collect AVC denials during installer/runtime/KVM/backup/Kubernetes testing;
2. create the minimum required LayerSentry SELinux policy modules/labels;
3. test management, agent, libvirt, storage mounts, backup operations, System VMs, console access, live migration and upgrades while enforcing;
4. reject broad `audit2allow` generated policy without review;
5. make `SELinux=enforcing` a production validation gate.

Until those tests exist, use `DESIGN_DEFINED` or `PARTIAL`, never “SELinux hardened/verified”.

---

## 5. Department/tenant model clarification

The earlier context correctly states that CloudStack Accounts can represent departments/customers and that Domain Administrators provide delegated administration. LayerSentry must make the intended mapping explicit to avoid building the wrong self-service model.

Recommended enterprise model when a Department Admin must manage subordinate teams/accounts and resource limits:

- **Department = CloudStack Domain**
- **Department Admin = Domain Administrator account/custom role in that Domain**
- **Team / application / workload boundary = Accounts under that Domain**
- **Individual login identities = Users inside an Account**

Important CloudStack behavior: resources belong to the **Account**, and Users inside the same Account are not isolated from each other. Therefore, if per-person or per-team resource isolation is required, create separate Accounts (or intentionally use Projects where enabled); do not assume multiple Users in one Account provide isolation.

For very small deployments where no delegated sub-account administration is required, an Account can still directly represent a department. The installer/GUI must not silently force one mapping for every customer.

---

## 6. Feature-gating correction

Do not show a feature merely because its API appears in `listApis` or a Vue route exists.

A normal user-facing action/menu requires all applicable gates:

1. RBAC/API permission is allowed;
2. product feature flag/global/zone configuration is enabled;
3. required provider/backend is configured;
4. required offerings/templates/networks/storage prerequisites exist;
5. provider/service health is sufficient for the action when a reliable health signal exists.

Examples:

- Kubernetes requires CKS enabled, valid Kubernetes ISO/template/offering/network prerequisites, and permission.
- Buckets require a configured usable Object Store plus permission/quota.
- Backup & DR requires backup framework/provider/repository/offering configuration, not just B&R API availability.
- Public IP/firewall/load-balancing controls appear only where the selected network offering actually supplies those services.

UI hiding remains UX only; server-side CloudStack RBAC remains the security boundary.

---

## 7. VM wizard backup-policy correction

The simplified LayerSentry VM wizard may present a `Backup Policy` choice to the user, but this is **not a native deployVirtualMachine field**.

If LayerSentry includes Backup Policy during Create VM, implement it as a supported post-deploy orchestration:

1. deploy the VM using normal CloudStack VM APIs;
2. wait for the deployment job/result;
3. assign the VM to the selected Backup Offering using the supported B&R API;
4. surface any assignment error clearly;
5. define whether VM creation is retained or rolled back if backup assignment fails;
6. make the result idempotent on retry.

Do not fake it as a native field or report the VM as protected until the backup offering assignment is actually confirmed.

---

## 8. CKS / CSI correction and security hardening

Native CKS already provides lifecycle operations and since 4.21 allows hypervisor selection plus separate templates/service offerings for worker/control/etcd nodes. LayerSentry may hide the hypervisor selector and supply KVM.

CloudStack 4.22 adds CSI integration for CKS. The native CKS creation UI exposes **Enable CSI Integration** in Advanced Settings. The CSI driver then supports dynamic CloudStack volumes and automatically synchronizes CloudStack Disk Offerings to Kubernetes Storage Classes.

Therefore the earlier simplified field `storage class/profile` must be treated carefully:

- native CKS creation directly exposes CSI enablement;
- Kubernetes Storage Classes are synced from CloudStack Disk Offerings;
- if LayerSentry presents a friendly Storage Profile selector during cluster creation, it is a LayerSentry wrapper/post-provision UX and must be implemented only after verifying the exact native API semantics.

Do not invent a native CKS parameter that does not exist.

### Mandatory CKS metadata isolation

CloudStack documentation warns that containers running on CKS nodes can access the underlying VM metadata/user-data service unless blocked by NetworkPolicy.

For LayerSentry production CKS:

- default to blocking pod access to the CloudStack metadata/user-data endpoint unless explicitly required;
- apply/test an egress NetworkPolicy compatible with the selected CNI;
- test that normal pod networking still functions;
- make this part of the CKS production security gate.

### Air-gap status

The Kubernetes binaries ISO speeds offline installation of binaries/images, but CloudStack 4.22.1 documentation explicitly says complete offline cluster provisioning is not natively supported because `kubeadm init` still requires Internet connectivity.

Therefore full air-gap CKS remains **PENDING / NOT TESTED** until the internal registry/bootstrap approach is implemented and proven.

---

## 9. Backup / DR corrections

CloudStack 4.22 cross-zone creation from backup is a valid DR foundation, but LayerSentry must preserve these exact limitations:

- currently cross-zone create-from-backup is supported only by the NAS B&R plugin;
- Cross-Zone Instance Creation must be enabled on the Backup Repository;
- backups are taken only from the original Zone;
- the repository must be reachable and mountable from destination-zone hosts;
- matching resources can be auto-selected, but Zone-unique resources such as networks still require mapping/selection;
- restore mounts the repository and copies backup data into destination Primary Storage, so RTO is directly sensitive to repository/storage/network throughput.

### Database retention dependency

CloudStack backup metadata still relies on the original/unmanaged/expunged instance database entry. The documentation warns that the entry must not be purged.

For DR-protected workloads LayerSentry must therefore add a retention/cleanup guard:

- do not purge the source instance DB record while backups/recovery points are still intended to be usable;
- document the interaction with expunge/resource-purge settings;
- add a negative test proving what happens if the record is purged;
- do not claim independent long-term DR retention until this dependency is accounted for.

### NAS backup application consistency

QEMU Guest Agent quiesce provides filesystem freeze/thaw but does not guarantee application-consistent databases. Fully application-consistent protection requires application-specific pre-freeze hooks or database-native backup mechanisms.

### CKS protection

NAS B&R backup/restore is not fully supported for CKS cluster instances and should be avoided. Kubernetes/DBaaS DR must use Kubernetes/database-native data protection rather than VM-level backup of CKS nodes.

---

## 10. KVM snapshot safety guard

CloudStack 4.22 release notes document a serious known issue for KVM: VM/Instance snapshots and Volume snapshots cannot safely coexist; restoring a Volume snapshot can remove existing VM snapshots and may lead to data loss.

LayerSentry V1 must not hide this behind a friendly UI.

Required product guardrail:

- detect conflicting snapshot state/policy where possible;
- prevent or strongly warn on unsafe workflows;
- define one supported protection strategy per workload where necessary;
- regression-test VM snapshot + Volume snapshot + restore combinations;
- make the limitation visible in Advanced/Support diagnostics and relevant user confirmations.

Do not label both snapshot mechanisms as independently safe until this known issue is resolved or the LayerSentry guard is proven.

---

## 11. Two-VM DC/DR POC scope correction

Two nested Rocky/KVM VMs are enough to prove the **functional CloudStack two-Zone backup/recovery path**.

If both nested VMs run on the same physical Hyper-V host, vSwitch, storage array or upstream network, the test **cannot certify**:

- physical Site/DC failure independence;
- real WAN behavior;
- independent power/network/storage failure domains;
- physical KVM Host HA fencing/OOBM;
- final 3-Management / 2-LB / 3-DB production availability.

All such results must be labeled `FUNCTIONAL_POC` / `LIVE_VERIFIED` only for the exact tested assertions, not “DR site certified”.

---

## 12. Existing self-service approach remains valid

The existing master-context approach is confirmed:

- keep one CloudStack/LayerSentry web application;
- reuse API auto-discovery and CloudStack RBAC;
- reuse native VM deployment rather than building a second scheduler/provisioner;
- Platform Admin, Department Admin and normal User receive different task-focused navigation;
- non-root users should not be exposed to physical host placement choices that are not relevant to their role;
- hide non-KVM customer choices without deleting upstream hypervisor implementations.

The current source still contains DBaaS/APaaS imports/routes and generic extension/tool sections, so the KVM-only product-profile work is still **PENDING**, not completed.

---

## 13. Estimate revalidation

The existing V1 estimate of approximately **20–27 engineering man-days** remains reasonable for the presently defined production-candidate scope if the work aggressively reuses native CloudStack capabilities.

The corrections in this audit — SELinux policy work, CKS metadata NetworkPolicy, CSI semantics, snapshot guardrails, DR purge-retention handling and version-pinned documentation — should be absorbed into the existing installer/security/GUI/validation workstreams rather than counted as greenfield product development.

Do not reduce the estimate further merely because individual UI edits are small; production evidence, failure testing, idempotent installation, rollback and security gates still consume engineering effort.

Optional later scope remains separate:

- advanced automatic DR controller/failover/failback after native recovery proof;
- fully air-gapped CKS after internal-registry/bootstrap proof.

---

## 14. Audit conclusion

The previous Super Master Context was **directionally and architecturally correct, but not perfect**. No core architectural reversal is required.

The most important corrections are:

1. pin documentation to 4.22.1.x rather than relying on `latest`;
2. standardize DB compatibility on MySQL 8.4/equivalent for 4.22.1;
3. explicitly model delegated Department Admin as Domain-based when subordinate Accounts are required;
4. use the full secure KVM/libvirt guidance rather than old insecure quick-install examples;
5. treat SELinux enforcing as policy engineering/testing, not a mode toggle;
6. gate features on real prerequisites/provider state, not API presence alone;
7. treat VM-wizard Backup Policy as supported post-deploy B&R orchestration;
8. correct CKS CSI semantics and block pod metadata access by default;
9. preserve DR repository/original-instance-record limitations;
10. guard the KVM VM-snapshot/Volume-snapshot coexistence issue;
11. keep the two-VM same-host DR lab clearly scoped as functional proof only.

No runtime change or product capability is marked complete by this documentation audit alone.

---

## 15. Additional re-audit correction — firewalld is a LayerSentry divergence

The LayerSentry master context currently targets `firewalld enabled` for the Rocky Linux 9 appliance. The full CloudStack 4.22.1 KVM installation guide, however, recommends disabling firewalld on EL/SUSE in its reference KVM firewall procedure and provides iptables-style rules for required ports.

Therefore `firewalld enabled` must **not** be described as an upstream CloudStack default or automatically assumed safe merely because the relevant ports were opened.

LayerSentry may intentionally keep firewalld enabled as a hardening/product choice, but that becomes a tested LayerSentry deviation. Before certification it must prove at least:

- Management Server to KVM agent communication;
- KVM-to-KVM live migration traffic;
- libvirt/CloudStack certificate/security flows;
- VNC/console paths where applicable;
- guest/System VM bridge forwarding;
- VLAN/isolated/shared network forwarding;
- NFS/Ceph/CIFS/multipath storage paths used by the selected profile;
- NAS B&R repository mounts and recovery traffic;
- CKS and CSI traffic;
- reboot persistence of the rules;
- no unintended public exposure of management/agent/libvirt ports.

Until this matrix passes with `firewalld` enabled, mark the appliance firewall policy **DESIGN_DEFINED / NOT TESTED**, not `verified` or `production certified`.
