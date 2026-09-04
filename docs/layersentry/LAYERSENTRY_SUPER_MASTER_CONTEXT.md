# LayerSentry V1 — Super Master Context

## 0. Purpose

This is the authoritative continuity and execution context for converting Apache CloudStack 4.22.1.1 into **LayerSentry V1**, a production-oriented, KVM-first, on-prem private-cloud appliance with a simplified self-service portal, Kubernetes, object storage buckets, backup and a validated DR foundation, while deliberately keeping CloudStack core functionality and data models intact.

This file is designed so that any new ChatGPT/Codex session can continue from the exact current point without re-discovering the project from scratch.

---

## 1. Non-negotiable product rule

**Do not rewrite CloudStack core.**

Preserve upstream CloudStack 4.22.1.1 behavior and interfaces unless a verified upstream defect forces an isolated fix.

Do not change unnecessarily:

- CloudStack backend APIs or API names
- database schemas
- asynchronous job behavior
- VM lifecycle semantics
- KVM agent protocol
- RBAC enforcement
- Zone/Pod/Cluster/Host internal model
- storage orchestration semantics
- network orchestration semantics
- plugin API contracts
- upgrade model
- supported upstream hypervisor code

LayerSentry should be a **product layer** over CloudStack, not a forked virtualization engine.

Allowed customization should be concentrated in:

- Vue/Ant Design UI
- route/menu visibility
- customer terminology
- dashboards
- simplified workflow components
- feature visibility/profile logic
- branding/config.json
- installation/bootstrap automation
- external health/orchestration services
- CI/CD and runtime validation
- LayerSentry-specific documentation

If the same customer outcome can be achieved by GUI translation, feature visibility or supported CloudStack API orchestration, prefer that over a backend change.

---

## 2. Source repositories and branches

### CloudStack / LayerSentry source

Repository:

`adaptgurus/cloudstack`

Active branch:

`layersentry/4.22.1.1-ui`

Upstream immutable validation base:

`71af23d73741cfeae854d2f1a6d36324307c32c4`

Historical branch HEAD at this handoff:

`6452853f903d88e9ce4951d69bd9d3512334dcf9`

The branch is currently 38 commits ahead of the immutable upstream base and 0 behind.

**Every new session must fetch the real branch HEAD before changing anything. Repository state overrides this historical SHA. Never force a branch backward.**

### Runner / live-test automation

Repository:

`adaptgurus/cozystack`

Branch:

`ops/layersentry-hyperv-inventory`

Historical current HEAD at this handoff:

`caa1f69b6b3e245abb3b5f1c578134f8d27fd283`

Again, always fetch the actual current branch HEAD first.

---

## 3. Last verified live UI deployment

Latest proven customer UI deployment run at this handoff:

- Workflow: `LayerSentry CloudStack Customer UI Deploy`
- Workflow file: `.github/workflows/layersentry-cloudstack-customer-ui-deploy.yml`
- Run ID: `33856746145`
- Job ID: `100971705863`
- Conclusion: `success`
- Request commit: `caa1f69b6b3e245abb3b5f1c578134f8d27fd283`
- Artifact ID: `9930784385`
- Artifact: `layersentry-customer-ui-deploy-33856746145`
- Artifact digest: `sha256:6a6751c9c07723f73df36e02b9f66ee3a41cb3098ac2f2834945af4759e9a50b`

Historical live verification markers from this run:

- HTTP 200
- served config `/etc/cloudstack/management/config.json`
- LayerSentry logo assets present
- onboarding present
- customer-friendly terminology present
- runtime config/branding checks passed

This run proved the existing branding/served-webapp mechanism, but it predates the new KVM-only private-cloud/self-service redesign requested in this context.

---

## 4. Current live target

Historical live management VM:

- VM: `sen`
- UI: `http://10.10.10.14:8080/client/`
- OS: Rocky Linux 9.x
- served UI root: `/usr/share/cloudstack-management/webapp`
- runtime config: `/etc/cloudstack/management/config.json`

Do not assume current agent, Zone, cluster, storage, System VM or network state from old handoffs. Inspect the live environment before making infrastructure claims or mutations.

Never repeat or commit passwords. Continue using ephemeral SSH keys/runner secrets.

---

## 5. Current branding state that must be preserved

Customer identity:

- Product: `LayerSentry`
- Customer version: `LayerSentry V1.0`
- subtitle: `Secure cloud infrastructure management`

The existing brand lock prevents stale CloudStack GUI theme data from overriding the LayerSentry logo, footer, colors and customer config.

Keep Apache LICENSE/NOTICE/source headers and legally required upstream attribution in source/distribution. Do not remove legal attribution merely to hide upstream branding from the normal customer portal.

Customer-facing normal UI must not show:

- Apache CloudStack logo
- upstream version notification
- API Docs menu
- upstream issue/report links
- irrelevant CloudStack customer-facing footer text

---

## 6. Validated CloudStack 4.22.1 facts that drive the design

The following design assumptions have been revalidated against the official CloudStack 4.22.1 documentation.

### UI and RBAC

CloudStack has a single web UI for administrators and end users. It uses API auto-discovery (`listApis`) to construct navigation/views based on the APIs permitted to the logged-in account/role.

Therefore LayerSentry does **not** need a second provisioning backend or a separate customer portal application. Reuse the CloudStack UI/API/RBAC model and improve the presentation.

Domain Administrators can administer users/resources in their domain hierarchy and do not have visibility into physical servers or other domains.

Accounts can represent a department/customer. Resources belong to the account, not the individual user. Dynamic roles provide API allow/deny rules.

### Management HA

CloudStack Management Server is stateless and should be deployed multi-node behind a load balancer.

Documented load-balanced ports:

- 80/443 -> 8080 (or AJP 20400): persistence required
- 8250 -> 8250: persistence required
- 8096 -> 8096: persistence not required

Global `host` must point to the VIP for System VM connectivity in a load-balanced setup.

Agents support multiple management servers through the `hosts` list and `indirect.agent.lb.algorithm`; `roundrobin` is appropriate for production distribution.

### KVM HA

HA-enabled guest instances restart within the same Availability Zone and do **not** perform HA across zones.

KVM Host HA exists, uses a state-machine approach, and requires out-of-band management/fencing for participating hosts.

### Database HA

CloudStack documents MySQL replication and supports `db.ha.enabled`, `db.cloud.replicas` and `db.usage.replicas`. However the DB HA section contains historical MySQL 5.x validation references and CloudStack itself does not monitor replica hosts or integrate DB-side events.

Therefore the final LayerSentry 3-node MySQL 8 design must be explicitly tested; do not treat the old documentation alone as certification. External health monitoring is required if the LayerSentry dashboard shows DB replica status.

### KVM / Rocky Linux

CloudStack 4.22.1 KVM guidance requires homogeneous hosts within a cluster, HVM support, consistent networking and current libvirt/QEMU. Rocky Linux 9 is listed as a supported KVM distribution in current 4.22.1 documentation for relevant KVM workflows.

CloudStack warns against running unrelated services on production KVM hosts. Any co-location in the nested POC must be labeled test-only.

### Kubernetes

CloudStack Kubernetes Service (CKS) already provides UI/API lifecycle management: create, list, start, stop, scale, upgrade and delete.

It is disabled by default and uses a version-specific binaries ISO. The ISO bundles Kubernetes binaries and container images and can be custom-built using CloudStack tooling.

Important limitation: the 4.22.1 documentation explicitly says **complete offline Kubernetes provisioning is not supported natively** because `kubeadm init` still requires active Internet access.

Therefore do not promise full air-gap CKS until a LayerSentry-specific internal registry/bootstrap method has been implemented and tested.

### Object storage / buckets

CloudStack already provides user/admin bucket creation, object browsing/upload/delete, mandatory bucket quota and account/domain/project object-storage limits.

LayerSentry only needs to simplify the customer form and hide provider internals when there is a single preconfigured provider.

### Backup and DR

CloudStack 4.22 allows users to create a new instance from a backup in another Zone, currently only through the NAS Backup & Recovery plugin.

The NAS plugin supports KVM and backup repositories over NFS, CIFS/Samba and CephFS. It has been tested on EL8/EL9 and current Ubuntu versions.

When cross-zone instance creation is enabled, matching destination resources can be auto-selected, but zone-specific resources such as networks still require selection if they differ.

CloudStack documentation explicitly describes two DRaaS extension patterns:

1. zone-local backup repositories replicated in the background with DNS resolving the same repository name to the local NAS in each zone;
2. a global repository with WAN-tuned NFS.

LayerSentry V1 should prefer **zone-local replicated repositories** for realistic recovery time.

Important limitation: NAS B&R backup/restore is not fully supported for CKS cluster instances and should be avoided. Kubernetes/DBaaS DR must therefore use Kubernetes/database-native protection rather than treating CKS nodes as ordinary CloudStack backup VMs.

---

## 7. Product scope for LayerSentry V1

### Include

- KVM-only customer experience
- VM self service
- Department Admin self service
- normal User self service
- compute profiles
- storage profiles
- VLAN/isolated/shared VM networking where configured
- public IP/firewall/NAT/load balancing where permitted
- images/templates/ISOs
- volumes
- snapshots
- HA
- live migration
- KVM Host HA/fencing where configured
- maintenance operations
- Kubernetes (native CKS, with honest offline limitations)
- object storage buckets
- Backup & Recovery
- cross-zone recovery / DR foundation
- activity/events/alerts
- RBAC
- role-based navigation
- automated Rocky 9 installation/bootstrap
- appliance lockdown
- controlled signed updates

### Exclude from V1

Do **not** present DBaaS or APaaS as CloudStack-native LayerSentry services in V1.

The user’s current plan is to deliver future DBaaS from Kubernetes using prepackaged/offline assets and a separate service workflow. Do not expose the current placeholder `DBaaS` / `APaaS` pages.

Future DBaaS should be an orchestration layer over Kubernetes, not a CloudStack-core rewrite.

---

## 8. GUI architecture

Keep one LayerSentry URL. The interface changes by role/API permissions and feature availability.

### Platform Administrator

Show infrastructure administration and all supported operational functions.

Recommended top-level navigation:

- Dashboard
- Compute
- Storage
- Network
- Images
- Infrastructure
- Backup & DR
- Activity
- Administration

Optional feature entries inside those sections appear only when enabled and functional.

### Department Administrator

Use a domain-admin/custom role suitable for delegated departmental administration.

Recommended customer navigation:

- Dashboard
- Compute
  - Virtual Machines
  - Kubernetes (only if enabled/allowed)
- Storage
  - Disks
  - Snapshots
  - Buckets (only if provider configured/allowed)
- Network
  - VM Networks
  - Public IPs (where relevant)
  - Firewall
- Images
- Backup & DR
- Department
  - Users
  - Teams/Accounts as appropriate
  - Resource Limits
- Activity

Do not show physical infrastructure internals.

### Normal User

Recommended minimal navigation:

- Dashboard
- Virtual Machines
- Kubernetes (conditional)
- Storage
- Buckets (conditional)
- Networks
- Images
- Backup & DR (conditional)
- Activity

### Security rule

UI hiding is UX, not authorization. CloudStack RBAC remains the server-side enforcement boundary.

---

## 9. Customer terminology

Keep backend names unchanged; translate only presentation.

- Zone -> Site
- Pod -> Infrastructure Group
- Cluster -> Compute Cluster
- Host -> KVM Host / Compute Host
- Service Offering -> Compute Profile / Resource Profile
- Disk Offering -> Storage Profile
- Template -> OS Image
- Guest Network -> VM Network / Workload Network
- Physical Network -> Datacenter Network
- Public Traffic -> Public / Internet Network
- Guest Traffic -> VM / Workload Network
- Storage Traffic -> Storage Network
- Reserved System Gateway -> Management Network Gateway
- Reserved System Netmask -> Management Network Subnet Mask
- Reserved System IP range -> Management IP Pool
- Security Groups -> VM Firewall Groups

For most customers, automatically create and hide the default Pod/Infrastructure Group unless advanced topology requires it.

---

## 10. KVM-only customer profile

Normal LayerSentry V1 UI must not show selectors or menu choices for:

- VMware
- XenServer
- Hyper-V
- Proxmox
- MaaS

Do **not** delete those implementations from CloudStack. Hide them from the `layersentry-kvm` product profile and automatically supply `KVM` where the API requires a hypervisor value.

Platform/support mode may expose upstream internals only when explicitly needed.

---

## 11. Dashboard targets

### Platform Administrator dashboard

Show real, actionable status only:

- Virtual Machines: total/running/stopped/error
- KVM Hosts: healthy/total/maintenance/disconnected
- CPU: used/allocated/available
- Memory: used/allocated/available
- VM Storage: used/free/health
- Active alerts: critical/warning
- Kubernetes: cluster/node health if enabled
- Object Storage: provider/bucket usage if enabled
- Backup & DR: protected workloads, stale backups, RPO violations, DR readiness
- Management plane health when reliable probes exist

Do not prominently show Pod count, System VM count, Virtual Router count or other CloudStack internals.

### Department Admin dashboard

Show:

- VMs and state summary
- Kubernetes clusters if allowed
- storage use vs department limit
- bucket use vs limit
- backup/protection summary
- CPU/RAM/VM/storage resource usage vs limits
- recent activity
- quick actions

### Normal user dashboard

Show only owned/usable resources and direct actions.

Reuse the existing `UsageDashboard.vue` data/API model rather than creating a duplicate backend.

---

## 12. Simplified VM wizard

Reuse existing CloudStack VM deployment APIs/components but simplify presentation.

Normal customer fields:

- Name
- Operating System
- Compute Profile
- Storage Profile / size
- VM Network
- HA toggle where allowed
- optional Backup Policy

Hide placement/hypervisor internals for non-root users.

If only one valid Site/network/storage profile exists for the account, auto-select it rather than asking the user.

---

## 13. Kubernetes UX

Use native CKS.

Customer wizard should expose only:

- Name
- Site if more than one is available
- Kubernetes Version
- HA control plane yes/no
- worker count
- worker resource profile
- network
- storage class/profile

KVM is implicit.

Do not build a separate Kubernetes provisioning engine unless a native CKS limitation specifically requires a wrapper.

For full air-gap mode, add a separate LayerSentry internal-registry/bootstrap project and validate it independently.

---

## 14. Bucket UX

Use native CloudStack bucket APIs.

Customer form should normally show:

- Name
- Capacity/quota
- Access/policy if the provider exposes a supported policy
- Encryption only if the selected provider actually supports it

Hide object-store endpoint/access key/provider internals from ordinary users.

---

## 15. Backup and DR UX

LayerSentry V1 should first expose the native, supportable foundation:

- Protect workload
- Backup policy
- Recovery points
- Recover
- Recover to DR Site

Preconfigure source-to-DR mappings for:

- Site
- VM Network
- Compute Profile
- Storage Profile

Do not fake automatic failover/failback until each step is implemented and tested.

### V1 DR implementation strategy

Prefer:

Source Zone local backup repository -> background replication -> DR Zone local replica

Use a common logical repository DNS name resolved to the site-local NAS when practical.

### Advanced DR controller — later milestone

Only after native cross-zone restore is proven, add:

- Test Recovery into isolated network
- Recovery Groups
- startup dependency order
- source fencing
- planned failover
- emergency failover
- DNS/BGP/traffic switching
- failback
- RPO/RTO reporting
- DR drill evidence

Keep this orchestration outside CloudStack core and drive supported CloudStack APIs.

---

## 16. DC/DR two-VM POC topology

The user currently has one nested-KVM test VM and can provide one additional VM.

One additional VM is enough to validate the **functional cross-zone DR path**, but it is not enough to certify the final 3-management/3-DB/2-LB production HA architecture.

Recommended minimal test-only layout:

### VM1 — existing `sen`

- current LayerSentry/CloudStack management
- source KVM host if current nested KVM arrangement permits it
- source Site/Zone
- source primary storage for POC
- source backup repository export if no separate storage service is available

### VM2 — new DR VM

- Rocky Linux 9.x Minimal
- nested KVM enabled
- DR KVM host
- DR Site/Zone
- DR primary storage for POC
- DR replica backup repository export if no separate storage service is available

For a lab only, NFS/repository services may be co-located on the test VMs to save time. Mark this as non-production because upstream advises against unrelated services on production KVM hosts.

Test the zone-local repository model by replicating source backup files to the DR repository and making the common repository hostname resolve to the local copy at each Site.

---

## 17. What is needed from the user for the second DR VM

Minimum requested VM for the current functional DC/DR POC:

- Rocky Linux 9.x Minimal
- x86_64
- 10-12 vCPU
- 32 GB RAM
- 100 GB OS disk
- preferably an additional 300-500 GB data disk
- nested virtualization extensions exposed
- static IP on the same reachable lab network as `sen`
- Hyper-V MAC spoofing/promiscuous forwarding enabled as required for nested KVM/CloudStack guest traffic
- outbound Internet access for the initial build **or** access to the same internal package/artifact sources used by the current test environment
- DNS and NTP reachability

Need from the user before destructive network/storage testing:

- new VM name/IP/gateway/DNS
- confirmation whether the existing Hyper-V external vSwitch/network can be reused
- confirmation whether VLAN trunking is available; if not, use a flat lab network for the first proof
- permission to reboot the two test VMs during failure testing
- confirmation that data on the new VM is disposable test data

Do not request passwords in chat. Use runner secrets or ephemeral SSH keys.

### Optional resources that would improve realism later

- a third small storage/NFS VM, or external NFS/Ceph test storage
- more VMs for the 3-management/3-DB/2-LB HA certification stage
- two physically or logically separated failure domains if true site-failure behavior must be certified

---

## 18. Rocky Linux 9 appliance policy

The production design should be **appliance-locked**, not falsely described as a fully immutable OSTree/appliance OS unless that mechanism is actually implemented.

Desired behavior:

- SELinux enforcing
- firewalld enabled
- auditd enabled
- password SSH disabled
- routine root SSH disabled
- normal users receive no OS shell
- customer admins cannot add repositories
- customer admins cannot run arbitrary `dnf install`, `yum install`, or `rpm -i`
- all required diagnostics are preinstalled
- only LayerSentry-controlled, signed update transactions can modify the package set

Important nuance: updates may legitimately pull a new dependency. Therefore enforce **who/what can change packages**, not a naive rule that no previously unseen RPM name can ever appear.

A true root account cannot be cryptographically prevented from modifying a normal Rocky system. Production security depends on not giving routine customers root access and routing changes through the signed update mechanism.

---

## 19. Required preinstalled diagnostic toolkit

Keep the image reasonably small but include support-critical tools before package lockdown.

Networking/transport:

- iproute
- iputils
- ethtool
- tcpdump
- traceroute
- mtr
- nmap-ncat
- bind-utils

System/performance:

- lsof
- strace
- sos
- sysstat
- iotop
- perf where supported
- dmidecode
- pciutils
- smartmontools
- jq
- curl
- rsync

Virtualization:

- virsh
- qemu-img
- virt-host-validate
- CloudStack/KVM diagnostic utilities

Storage, enabled by profile only where possible:

- nfs-utils
- cifs-utils
- device-mapper-multipath for SAN profiles
- ceph-common for Ceph profiles

Security:

- audit tools
- SELinux troubleshooting utilities
- integrity tooling if adopted

Do not install unrelated server workloads on production KVM nodes.

---

## 20. Update architecture

Build a LayerSentry update mechanism around approved repositories/bundles.

Expected flow:

1. obtain signed LayerSentry update metadata/bundle
2. verify signature and compatibility
3. preflight disk/database/cluster health
4. create required backup/snapshot
5. drain a management/KVM node where appropriate
6. apply only approved update transaction
7. reboot if required
8. health check
9. rejoin node
10. continue rolling update
11. generate evidence/report

Do not let normal users invoke arbitrary package managers.

---

## 21. Target production management architecture

Production profile target:

- 2 load-balancer nodes or external enterprise ADC
- 3 CloudStack/LayerSentry Management nodes
- 3 database nodes
- KVM compute clusters

The management VIP must remain online when one management node reboots.

CloudStack’s own Management Server HA and agent multi-manager functions should be used rather than reinvented.

Because CloudStack does not monitor DB replicas, LayerSentry must use an external health component if the GUI exposes DB replication health.

Do not route ordinary workload outbound Internet traffic through the management load balancer. Use the normal egress firewall/proxy/NAT path.

---

## 22. Bootstrap architecture

Customer should run one LayerSentry installer command, but implementation must be modular and idempotent rather than a monolithic Bash script.

Preferred architecture:

- thin shell entrypoint
- Python bootstrap/controller
- Ansible or equivalent declarative automation
- versioned inventory/config
- signed/immutable build artifacts
- CloudStack API client
- health checks
- state/resume logic
- deployment evidence/report

Bootstrap tasks:

- preflight
- OS preparation/hardening
- repository/artifact setup
- load balancers
- DB HA
- management nodes
- CloudStack configuration
- KVM host registration
- networking
- storage
- System VM templates
- LayerSentry UI
- roles
- Kubernetes
- buckets/object store
- backup/DR configuration
- validation
- appliance lockdown
- final report

Bootstrap must not become a runtime SPOF. After successful deployment, its loss must not stop VMs, UI/API, KVM agents or database service.

---

## 23. Current installer technical debt — high priority

These issues are confirmed in the current branch and must be fixed before calling the installer production-ready.

### A. Main fresh installer still forces Rocky Node.js 16 module

`install-layersentry-rocky9.sh` dynamically injects an unconditional `dnf module enable nodejs:16` into the immutable full installer.

This is fragile because the long-lived Rocky 9 metadata on the test system has already shown that the Node.js 16 module may not be available.

Do not require a production appliance to compile Vue using an obsolete build toolchain at install time.

Preferred fix:

- build the UI in CI/build environment
- publish/checksum the immutable UI artifact
- installer deploys the already-built artifact

If a source build fallback is retained, reuse a proven isolated build runtime rather than forcing Node.js 16 on the production host.

### B. Resume path is stale

Current `install-layersentry-rocky9-resume-v3.sh` still pins:

- old UI commit `72b76a30f3dadf0dbe9e333ade073034c1afc514`
- old served-branding commit `7a500324ffec725012bcd089fae5f54c0e56de5e`

The main installer currently calls that resume script.

Update the resume path to the same current product artifact and verification logic as the fresh path.

### C. DBaaS/APaaS validation is obsolete

Current served-UI repair validates that `DBaaS` and `APaaS` strings exist in the built UI and the current branch still contains `ui/src/config/section/dbaas.js`, `ui/src/config/section/apaas.js` and router entries.

The current V1 requirement explicitly excludes those placeholder services.

Remove/hide them from the V1 product UI and remove installer/runtime checks that require them.

### D. SELinux production state

The current installer exposes a `--set-selinux-permissive` setup path. Production V1 must end in SELinux enforcing with required policy/labels validated.

Permissive may be used only as an explicitly controlled troubleshooting phase, never the final appliance state.

### E. Production host should not run npm builds

Current served UI repair can install build dependencies and run `npm install`/`npm run build` on the target management server.

For the locked-appliance design, move compilation to CI/build infrastructure and deploy an immutable artifact to production.

### F. Served webapp deployment safety

Current runtime deployment uses `rsync -a --delete` with exclusions for config/WEB-INF/META-INF and has succeeded in live validation.

For production, prefer a package/atomic artifact deployment or otherwise prove rollback/atomicity. Continue preserving CloudStack backend directories and runtime config.

---

## 24. Current UI technical debt — high priority

Current branch already has strong branding and terminology work but still needs the actual private-cloud product profile.

Priority changes:

1. remove DBaaS/APaaS placeholder routes and catalog from V1
2. add KVM-only customer product profile
3. finalize role-aware Standard/Admin/Support visibility
4. redesign Platform Admin dashboard
5. redesign Department Admin dashboard using existing UsageDashboard data model
6. simplify normal User dashboard
7. simplify VM wizard
8. simplify Kubernetes wizard
9. simplify bucket form
10. simplify Site/Infrastructure onboarding
11. hide non-KVM hypervisors in normal UI
12. keep Advanced/Platform access to required upstream internals for support
13. ensure responsive/mobile and accessibility/contrast states
14. feature-gate K8s/Buckets/Backup/DR on actual backend/API/provider availability

---

## 25. Time-saving principles

The project should save time by **reusing mature CloudStack functionality instead of recreating it**.

Do not build:

- a second VM scheduler
- a separate VM provisioning backend
- a separate quota engine
- another user/account database
- a new Kubernetes provisioning engine when CKS works
- a new bucket backend when native Object Storage works
- a custom RBAC engine
- a completely new DR engine before native cross-zone recovery is proven

Reuse:

- CloudStack API discovery
- dynamic roles
- Domain Admin/User semantics
- existing VM Deploy component
- existing UsageDashboard resource APIs
- native CKS
- native Object Storage
- NAS B&R cross-zone restore
- Management Server HA
- multi-manager agent distribution
- KVM Host HA

This is the main reason the current validated estimate is much lower than an initial greenfield estimate.

---

## 26. Revised engineering estimate

Current planning estimate for V1, assuming native CloudStack cross-zone DR rather than a full custom DR controller:

### GUI/self-service

Approximately **6-9 man-days**.

### Automated HA installer / Rocky appliance / K8s / buckets

Approximately **9-12 man-days**.

### Native cross-zone DR integration + simplified DR UX

Approximately **2-3 man-days**.

### Deep production validation

Approximately **3-5 man-days**.

### V1 production candidate total

Approximately **20-27 man-days**.

With aggressive ChatGPT/Codex automation and parallel CI work, elapsed calendar time can be materially shorter than summed engineering man-days.

Optional later additions:

- full LayerSentry DR controller with test failover/fencing/failback: roughly **+5-7 man-days** after native recovery is proven
- true fully air-gapped CKS support: roughly **+2-4 man-days** depending on image/registry behavior discovered in tests

Do not inflate estimates by counting existing CloudStack capabilities as new development.

---

## 27. Execution order to minimize wasted work

### Phase 0 — state audit

Every new session:

1. fetch current CloudStack LayerSentry branch HEAD
2. fetch current Cozystack runner branch HEAD
3. inspect current PR and latest relevant workflow state
4. inspect live server before infrastructure mutation
5. compare current source with this context

### Phase 1 — clean V1 scope

- remove DBaaS/APaaS placeholders/checks
- fix fresh/resume installer inconsistency
- stop production-side npm builds
- define KVM product-profile feature matrix

### Phase 2 — self-service GUI

- Platform Admin dashboard
- Department Admin dashboard
- User dashboard
- role-aware navigation
- simplified VM wizard
- K8s wizard
- bucket UX
- onboarding/site UX

Build, deploy and verify on the existing `sen` VM before starting DR infrastructure changes.

### Phase 3 — second VM and two-zone DR proof

- add DR nested-KVM VM
- create second Site/Zone
- configure DR KVM host/storage/network
- configure NAS B&R
- take backup
- replicate repository
- recover the test VM into the DR Site
- verify boot/network/application
- repeat after destroying the first recovery instance
- record actual RPO/RTO/throughput

Do not build sophisticated failover automation before this works reliably.

### Phase 4 — appliance/bootstrap

- modular controller
- Rocky 9 hardening
- diagnostic baseline
- package/repo lockdown
- signed update mechanism
- idempotency/resume
- full fresh-install test

### Phase 5 — management HA certification

When sufficient VMs/resources are available:

- 3 Management nodes
- 2 LB nodes/external ADC
- 3 DB nodes
- failure/reboot tests
- rolling update tests
- DB failover tests
- agent management-server redistribution

### Phase 6 — advanced DR only if required

- isolated test failover
- recovery groups
- fencing
- traffic switching
- planned failover
- emergency failover
- failback
- drill reporting

---

## 28. Required DC/DR functional test matrix

At minimum execute and collect evidence for:

### Baseline

- source Site healthy
- DR Site healthy
- one small test VM running at source
- backup repository healthy

### Backup

- adhoc backup
- scheduled backup if supported in test window
- running-instance backup
- verify backup object/files
- confirm repository sync to DR copy

### Cross-zone recovery

- recover to DR Site
- validate destination image/template mapping
- validate compute/storage profile mapping
- validate network mapping
- boot guest
- verify guest IP/network
- verify application/SSH/ICMP according to test policy

### Failure and retry

- temporarily break DR repository mount and prove safe failure
- restore mount and retry
- temporarily make DR storage unavailable and prove clear failure
- verify idempotent retry does not create duplicate uncontrolled resources

### Repeatability

- perform at least two complete recoveries from independent recovery points
- destroy only test recovery instances
- prove source VM remains untouched for test recovery

### Metrics

Capture:

- backup duration
- backup size
- repository replication duration
- recovery copy duration
- VM boot duration
- overall effective RPO
- overall effective RTO

---

## 29. Required GUI/RBAC test matrix

Test at least:

### Root/Platform Admin

Can operate infrastructure and all enabled services.

### Department Admin

Can manage permitted department users/resources but cannot see physical servers/other domains.

### Department Operator / custom role

Can operate permitted VMs/storage/network/K8s without user/domain/global infrastructure administration.

### User

Can create/use only allowed self-service resources.

### Read-only role

Can view but not mutate.

For every role:

- menu visibility
- direct URL behavior
- API denial for unauthorized actions
- dashboard accuracy
- Create VM
- storage/network access
- K8s/bucket visibility according to feature and role
- Backup/DR visibility according to role

Never consider menu hiding proof of security. Verify server-side API authorization.

---

## 30. Production validation gates

Do not call V1 production-ready until all applicable gates pass.

### UI

- correct LayerSentry branding
- no stale CloudStack shell branding
- KVM-only normal profile
- no DBaaS/APaaS placeholders
- responsive layout
- readable navigation
- clean empty/loading/error states
- no dead menu entries

### Fresh install

- clean Rocky 9 installation path
- no reliance on unavailable Node.js 16 repo/module on production host
- installer rerun/resume safe
- exact package/artifact provenance

### Security/appliance

- SELinux enforcing
- firewalld enabled
- no normal password SSH/root shell
- package repo changes denied to normal administrators
- arbitrary package installation denied to normal administrators
- controlled update transaction works
- audit logs available

### HA

- management node reboot does not remove UI/API availability in HA profile
- LB member health behaves correctly
- KVM agents retain management connectivity
- DB failover behavior tested for the certified topology

### DR

- backup works
- repository copy works
- cross-zone recovery works repeatedly
- destination network/storage mapping works
- documented failure states are safe

### Upgrade

- custom UI survives the supported CloudStack upgrade process
- LayerSentry delta documented
- rollback/recovery path exists

---

## 31. Fork-debt control

Maintain a LayerSentry upstream-delta document.

For every modified upstream file record:

- path
- reason
- LayerSentry behavior
- upstream behavior
- upgrade risk
- test coverage

Prefer new LayerSentry wrapper/components and configuration over invasive edits to large upstream files.

The current branch already has 38 commits over the immutable upstream base; future work should reduce unnecessary divergence rather than expand it casually.

---

## 32. Continuity / anti-stall protocol

This section is mandatory.

If a chat approaches context limits, becomes stuck, hits repeated tool failure, or cannot safely continue in the same session:

1. **Do not guess or restart from memory.**
2. Fetch the actual current GitHub branch HEAD(s).
3. Fetch the latest relevant workflow/run result.
4. Record the exact last successful source commit, workflow run, artifact and live validation evidence.
5. Record every open issue and the exact next action.
6. Update this file (`docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md`) on the active LayerSentry branch if write access is available.
7. In the final message, output a copy-pastable `CONTINUE LAYERSENTRY` handoff containing:
   - repositories
   - branches
   - exact current HEADs
   - latest workflow/run IDs
   - last proven live state
   - completed tasks
   - failed/open tasks
   - next command/action
   - any required user input
8. The next chat must begin by reading this file and fetching live repository/runtime state before changing anything.

Never rely solely on an old SHA embedded in the context. Live repository/runtime evidence always wins.

Recommended new-chat opening instruction for the user:

`Continue LayerSentry from docs/layersentry/LAYERSENTRY_SUPER_MASTER_CONTEXT.md in adaptgurus/cloudstack. First fetch actual current HEADs and latest workflow/live state; repository/runtime evidence overrides the historical handoff.`

---

## 33. Status-report format for every milestone

Report:

### STATUS

What is complete and what is not.

### SOURCE

- repository
- branch
- exact current HEAD

### CHANGES

- files changed
- user-visible behavior

### CORE IMPACT

- backend core changed: YES/NO
- expected default: NO

### VALIDATION

- static checks
- build
- workflow
- live deployment
- role tests
- failure tests

### EVIDENCE

- workflow run ID
- artifact ID/digest
- important runtime markers

### OPEN

Explicit unresolved items.

### NEXT

Exact next task.

Do not report unexecuted tests as passing.

---

## 34. Immediate next actions from this handoff

1. Fetch actual branch HEAD and compare with this file.
2. Remove DBaaS/APaaS placeholder UI/routes and all runtime checks that require them.
3. Fix installer fresh/resume parity.
4. Replace production-side UI compilation with immutable CI-built UI artifact deployment.
5. Define and implement the `layersentry-kvm` product-profile visibility matrix.
6. Redesign Platform Admin / Department Admin / User dashboards using existing APIs.
7. Simplify VM/Kubernetes/Bucket workflows.
8. Deploy and role-test on `sen`.
9. Ask for/use the second Rocky 9 nested-KVM VM.
10. Execute the two-zone native NAS B&R cross-zone recovery proof before implementing advanced DR automation.

---

## 35. Final architecture principle

To the customer:

**LayerSentry = simple, production-grade on-prem KVM private cloud.**

Underneath:

**Apache CloudStack 4.22.1.1 remains the mature orchestration engine.**

Preserve the engine. Remove operational complexity from the customer experience. Reuse native functionality aggressively. Build only the missing product layer, automation, hardening and DR orchestration that is genuinely required.