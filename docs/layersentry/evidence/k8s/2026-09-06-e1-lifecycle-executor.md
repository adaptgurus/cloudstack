# Workstream E1 — cluster lifecycle executor and preflight

**Date:** 2026-09-06  
**Status:** create/status/scale/delete source paths `SOURCE_COMPLETE`; runtime `NOT_TESTED`  
**CloudStack core impact:** none

## Current approach

The E1 executor consumes the durable saga one step at a time and delegates desired state to CAPI/CAPC/CAPRKE2 and Flux through the restricted Kubernetes API client. It never creates or deletes CloudStack VMs directly.

Before any CAPI apply, the read-only CloudStack 4.22.1.1 adapter resolves the exact authorized project, Site, network, service offerings, KVM image and reserved endpoint public IP. It uses only the documented `listProjects`, `listZones`, `listNetworks`, `listServiceOfferings`, `listTemplates`, `listPublicIpAddresses` and `listLoadBalancerRules` commands found in the exact integration source. API requests use CloudStack signature version 3, a five-minute expiry and POST form data so the API key is not placed in a URL. API/secret keys are read at request time from files with mode 0600 or stricter.

Cluster creation applies provider resources with server-side apply and `force=false`, then waits for current-generation conditions. The endpoint step requires exact non-ambiguous Active CloudStack LB rules on both 6443 and 9345 before advancing. The immutable central Flux source is pinned to a full Git commit; per-cluster Kustomization uses prune/wait and repository-relative paths.

Status checks exact LayerSentry/project labels. Scale uses a narrow merge patch to `spec.replicas`, waits for available replicas and blocks scale-down until CAPC volume ownership has live evidence. Delete requires exact typed confirmation, `retain_workload_volumes=true`, the CAPC live gate and LayerSentry/project ownership; it deletes only the CAPI Cluster and waits for absence, leaving VM lifecycle to CAPI/CAPC.

## Advantages, disadvantages and alternatives

- Exact ID preflight prevents name ambiguity and catches disabled/unready infrastructure before CAPI mutation.
- CAPI remains the lifecycle owner and central Flux remains the package owner.
- Endpoint verification uses CloudStack rule inventory rather than treating a CAPC Ready condition as proof of TCP 9345.
- Signed CloudStack requests are dependency-free, but the custom client is intentionally read-only and must be integration-tested against TLS/signature enforcement.
- Direct CloudStack VM lifecycle was rejected because it would race CAPC.
- Force-applying CRDs was rejected because it could steal fields from provider controllers.
- Automatic scale-down/delete while data-safety gates are false was rejected.

## Risks and mitigations

The combined provider tuple and generated resources have not reached a real admission webhook. DNS endpoint-to-public-IP binding is a server-owned profile contract; IP literals are additionally compared to the exact CloudStack public IP. Flux source trust/signature enforcement is a separate Workstream B gate even though the Git revision is immutable here. A Ready condition is accepted only at the observed generation, while the external E0 harness still owns destructive/data/port evidence.

## Tests performed

All 52 Workstream E Python tests passed. Coverage includes:

- a complete fake-provider create saga through READY;
- pending current-generation conditions;
- exact dual endpoint rule IDs;
- commit-pinned Flux catalog and per-cluster scope;
- convergent scale-up and fail-closed scale-down;
- deletion gate/confirmation and CAPI-only deletion;
- status/project-label tampering;
- CloudStack Signature V3 POST behavior and private credential-file modes;
- disabled/unready/ambiguous CloudStack preflight failures;
- Kubernetes merge patch and ambiguous transport handling.

No actual CloudStack, Kubernetes, CAPI, RKE2, CCM, CSI, Flux, network or VM mutation ran.

## Rollback/recovery and remaining gates

For an ambiguous apply/patch/delete, do not replay until exact Kubernetes/CloudStack state has been read. Roll back cluster creation through CAPI deletion only after the volume-safety gate and retention preflight pass. A Flux baseline rollback pins the prior qualified commit and waits for reconciliation; do not use an unpinned branch.

Remaining before E1 can pass: package/service wiring, authenticated CloudStack-backed authorization, real CRD admission/reconciliation, automatic RKE2 join, one CNI, CloudStack CCM, one CSI storage path, central Flux delivery, restart/rollback/failure tests and Rocky Linux evidence. PostgreSQL remains blocked until E0/E1 live gates pass.

## 2026-09-08 live qualification checkpoint

Source/distribution: `5d35ec923c4ce41014984fc6801d5071cb471125`; feature CI
[34261337474](https://github.com/adaptgurus/cloudstack/actions/runs/34261337474)
passed (137 K8s tests, five downstream tests, 13 governance tests).
Production live gates remain false. This is bounded first-cluster qualification,
not production certification. The co-located Rocky controller host was explicitly
approved by the operator; its pre-existing SELinux mode is Permissive.

Completed live actions:

- Installed the verified systemd/filesystem controller distribution and pinned
  Python/Gunicorn RPM dependencies on 10.10.10.14. BFF listens only on its Unix
  socket; the reconciler timer remains inactive. Steps were executed individually.
- Rolled CAPC to the approved immutable candidate
  `ghcr.io/adaptgurus/layersentry-capc@sha256:f955d6a90b9da6e8aa18ab57c0e1ed4b47ae92b3309c64af715460a21a3a462e`;
  all management provider Deployments became available. Seven other planned
  identity-preserving image pins were applied. Old CAPC rollback content was
  retained locally (archive SHA256
  `1b8272f3a925178f5bbbe2660d35c22eea3aeeb196e03d8b2474daed50acbe75`).
- Submitted the single approved 3-control-plane/1-worker request through the
  existing LayerSentry executor, operation `e4df4d27-0b96-4f25-a191-21f45d70892c`,
  namespace `lsk8s-83b979b50657`, cluster `ls-rke2-poc`.
- Fixed the live CRD rejection: CAPRKE2 air-gap fields belong under agentConfig.
  Fixed qualification template CPU details to request host-model through CAPC;
  the old qemu64 guest did not boot successfully. No host-wide CPU setting,
  service offering, template image, or provider version was changed.
- CAPI/CAPC deleted the first uninitialized, root-only Machine and created its
  replacement. No native CloudStack VM lifecycle API or finalizer removal was
  used. The replacement is UUID `13656367-58bf-4197-8ab7-9e4c8de8875a`,
  CloudStack name `ls-rke2-poc-control-plane-cpu-v2-q4nh7`, domain `i-4-9-VM`.
  Its CPU is Icelake-Server with host features; QEMU agent reports Rocky 9.8
  and kernel `5.14.0-687.10.1.el9_8.0.1.x86_64`.
- CAPC owns two Active LB rules on frontend 10.10.11.23: TCP 6443
  `fff91298-ec7b-42ea-95e1-793b224b581e` and TCP 9345
  `3436abc0-7496-45a4-88cc-54c082e29aec`. Active rules are not evidence of
  healthy/reachable RKE2 services.

First unmet live gate: guest DHCP/IPv4 initialization. The replacement has only
IPv6 link-local on eth0; native CloudStack's assigned address 172.17.30.202 is
not proof the guest configured it. The VR reservation and lease entry correctly
map MAC 02:02:00:d1:00:03 to 172.17.30.202. VR dnsmasq is active. Both guest
vnet16 and VR vnet12 are forwarding on breth1-153.

A 15-second guest-tap capture observed two DHCP requests and no reply. A separate
20-second VR capture observed no DHCP packets; a subsequent simultaneous
35-second capture observed no DHCP packets on either tap, so those windows do
not conclusively identify the dropping rule. Host bridge-nf-call-iptables=1;
firewalld puts unmatched bridged forwarding into its public chain, which ends
in reject. Host firewall forwarding is the leading infrastructure hypothesis,
not yet a packet-trace-proven root cause. No firewall, NAT, bridge, VLAN, or
Hyper-V changes were made. Guest-exec is disabled by the template's QEMU agent;
that restriction was preserved.

Current result: one CAPC-created Rocky guest Running; no workload Node registered,
no initialized control plane, no worker created, and no Cluster Ready, scale,
workload delete, CCM, CSI, or Flux live certification. Preserve the operation and
provider objects. Next action is a scoped host/VR packet trace and, if confirmed,
reviewed host bridge-forwarding remediation by the infrastructure owner; then
resume this same operation with fresh capacity evidence. Do not repeat cluster
creation or globally disable filtering to bypass the blocker.

Private diagnostic artifacts remain under
`/home/opc/.local/share/layersentry/lifecycle-qualification/` (not imported;
this directory also contains protected runtime material). No credentials,
kubeconfigs, tokens, or private keys are included in this checkpoint.

### 2026-09-09 DHCP remediation (operator approved)

The operator explicitly authorized resolving the host-network blocker. Runtime
firewalld inspection showed `breth1-153` absent from public-zone interfaces and
its forwarding allow chain; bridged IPv4 filtering was enabled. Added only this
project VLAN bridge to the existing public zone, first at runtime. Cycled only
the uninitialized guest's NIC link down/up to renew DHCP. VR eth0 capture then
proved two DHCP requests and two replies; QEMU agent confirmed 172.17.30.202/24
and guest SSH became reachable. Persisted the same interface membership using
`firewall-cmd --permanent --zone=public --add-interface=breth1-153`.
Host file affected: `/etc/firewalld/zones/public.xml`. No global forwarding
sysctl, NAT, route, VLAN, Hyper-V, or CloudStack network changes. Temporary nft
trace table was removed; its window produced no IP trace and is not claimed as
packet-level drop proof. The successful DHCP exchange after the scoped change
provides the live remediation evidence.

Read-only guest log inspection showed cloud-init previously completed with
`DataSourceNone` after the failed first-boot network attempt. Before replacing
that disposable Machine, native inventory proved exactly one 40-GiB ROOT volume,
no data volume, and CAPI no NodeRef. Requested deletion only of CAPI Machine
`ls-rke2-poc-control-plane-vsrmj`; provider finalizers own cleanup/recreation.
Retry guard allowed the materially changed firewall environment. No manual
RKE2 installation, cloud-init replay, native VM deletion, or finalizer removal.

Fresh replacement `e9c1ef73-99a2-4b13-9402-83a8f15f9105` / `i-4-10-VM`
obtained 172.17.30.32 on its first boot. VR HTTP access logs prove successful
cloud-init metadata and userdata retrieval. Its log reports DataSourceCloudStack.
A temporary diagnostic SSH public-key addition was rejected by the guest agent;
no SSH key was installed and the restriction was not disabled.

The next proven defect is CAPRKE2 0.25.2 cloud-init serialization: its air-gap
checksum command starts with unquoted `[[`, which YAML interprets as a flow
sequence. The actual guest log reports invalid YAML at line 258 and an empty
merged cloud-config. Independently decompressing the delivered userdata and
parsing it reproduces the error. Replacing only that command with a folded YAML
scalar and POSIX `test` makes the exact delivered document parse (eight runcmd
entries). The checksum remains mandatory and fail-closed.

Prepared a pinned downstream bootstrap-only patch at the same upstream commit
`38602b72a23faf719b94b250eba66ef804bf9706`; no provider version upgrade. Regression
tests render and parse initial CP, joining CP and worker cloud-config, then
execute checksum checks against valid, tampered and missing files. The patched
upstream cloudinit Go package passed locally; 137 K8s tests and five downstream
tests passed. Local image compilation was stopped after the tests so the scoped
K8s publishing workflow can perform the two authoritative clean builds and
publish with Actions package permission. The local GitHub credential lacks
package scope. No patched provider rollout or immutable-readiness assertion is
made before successful publication, digest retrieval and consumption binding.

Patched bootstrap image publication and pull-by-digest succeeded in artifact run
34309295922. Both clean runtime-content hashes are
`f1a4d901ef932ea3f2f5abeda51cbdf0bfaad05efb558ecf39d2f0b94814661a`.
Anonymous linux/amd64 pull succeeded for
`ghcr.io/adaptgurus/layersentry-caprke2-bootstrap@sha256:aa4f547351a2e0b374e7c4ab23cefec5c3820690195aae6a8ecbbc1c4de26217`.
The management lock binds that image; feature source CI 34309877516 passed for
`f3c3511967a0c76cad38211097863b40f5887159`. Controller distribution source bytes
were unchanged, so its existing source/tree binding remains valid. Only release
metadata was reinstalled, followed by the explicit audited qualification-release
revision (same request and idempotency key).

An image-only server dry run and Deployment backup preceded the bootstrap
controller rollout. The Deployment became available; the old upstream digest
remains the rollback image. Fresh native/host capacity again returned
PROVISION_ALLOWED. CAPI/CAPC replaced the root-only, uninitialized Machine;
current Machine `ls-rke2-poc-control-plane-v99w6`, VM UUID
`039e67f0-2738-4cf9-8893-78e61dff6e8b`, domain `i-4-11-VM`. Its newly generated
live bootstrap Secret decodes/parses correctly with eight commands including
checksum verification. Secret contents were not logged or committed. RKE2
service/Node/Cluster readiness is still a separate pending live gate.

### 2026-09-09 — SELinux air-gap prerequisite correction

The diagnostic replacement is Machine `ls-rke2-poc-control-plane-6bb2x`,
CloudStack VM `5b061506-22e1-4f1f-aeab-471c028dac1f`, `i-4-12-VM`,
172.17.30.83. Its SSH host key was verified against trusted libvirt console output;
an operator public key was temporarily delivered through CAPRKE2 Files. No
private key/password was embedded. This diagnostic access must be removed after
qualification. The Cluster is paused while bootstrap prerequisites are corrected.

The node verified/staged official RKE2 assets and imported all 16 release archive
images. Supervisor 9345 listens; API 6443 remains pending. The live container
runtime initially failed with `write fsmount:fscontext:proc/self/attr/keycreate:
invalid argument`. SELinux was Enforcing but both container-selinux and
rke2-selinux were absent. This is the documented air-gap prerequisite, not a
reason to disable SELinux or registry restrictions.

Installed exactly two checksum-pinned, signature-verified local RPMs with all
repositories disabled and local package GPG checking enabled:
`container-selinux-4:2.245.0-1.el9.noarch` and
`rke2-selinux-0:0.23-1.el9.noarch`. No package upgrades or additional dependencies.
The Rancher key fingerprint is
`C8CFF216455126E9B9C918BE925EA29AE257814A`; the Rocky key was supplied by the
unmodified rocky-gpg-keys RPM. Exact asset/key hashes are bound in the qualification
lock. SELinux remained Enforcing. Restored RKE2 file contexts and restarted the
service; stale failed sandboxes remained, so rebooted only this disposable guest.
API recovery is not yet claimed.

Source commit `cfd7816d50` now stages/verifies these exact prerequisites for CP
and worker before the RKE2 installer. Ordinary projects are unchanged. Source
validation passed 138 K8s and five downstream tests; checksum/URL/package/key
substitution fails closed. Controller distribution regenerated from exact source
commit bytes. All production live flags remain false.

The immutable bootstrap distribution is now `370e19082c2a961fc456122e9fb15e002084902d`
(source `cfd7816d50`, tree
`efc52d69ab7f42d18a4da324fcc3be3ce7a3c65dd808239c44b893d14a017ed9`).
Source CI `34313543946` passed. Installed the exact five changed payload/metadata
files on the authorized co-located controller host and explicitly revised the
same qualification journal/context; production deployability remains false.

Reboot confirmed the remaining pause-container AVC was an old unpacked image
file labeled `var_lib_t`, not a policy-package defect. Corrected only stale
`var_lib_t` objects beneath containerd overlay snapshots to `container_file_t`.
The initial label command followed image symlinks; immediately restored the two
existing host symlink targets with restorecon, then repeated using chcon -h.
No custom allow policy, SELinux disable, or registry fallback was introduced.
After correction, etcd and API pods run, local `/readyz` returns `ok`, RKE2 is
active, and SELinux remains Enforcing. Future nodes install policy before unpack.

The next observed infrastructure blocker was stale host BF-cloudbr0 filtering:
new public ingress fell through empty BF-cloudbr0-IN/OUT chains to FORWARD DROP.
The Virtual Router already had correct HAProxy backends and native 6443/9345
firewall rules. Windows/WSL probes failed before reaching VR eth2. Added only
bridged cloudbr0 -> cloudbr0 TCP 6443/9345 to 10.10.11.23/32 via firewalld direct.
The first runtime direct-rule activation reset legacy iptables state; immediately
restored the saved complete table set with the scoped rule prepended, and verified
zero missing original rules/chains. Persisted only the new direct rule in
`/etc/firewalld/direct.xml`. No Windows/Hyper-V/NAT/default-route or native LB
change. Verified MAC spoofing On for both sen adapters using enum string values.

Afterward Windows and management-client TCP probes succeed for both ports.
CAPRKE2 and CAPI recognize the first registered Node as Machine Ready/Available.
Updated only generated preRKE2Commands on the CP/worker bootstrap resources,
removed the temporary public-key Files entry from future CP templates, refreshed
native/host capacity (PROVISION_ALLOWED, 11 CPU and 41.19 GiB RAM headroom after
planned allocation), and resumed CAPI. CAPC created next CP VM
`5596283c-2989-47b5-a98e-4994fbb5515a` and worker VM
`a4270271-21da-4f7e-ae2d-1f5ebdce652d`. The old CP has diagnostic SSH access until
its provider-owned rolling replacement completes. Flux source is exact-commit
Ready; baseline/remote reconciliation and full 3+1 readiness are still pending.

### Current stop gate — measured control-plane CPU pressure

At 05:21–05:24 UTC the 2-vCPU first CP remained CPU-saturated: vmstat reported
27–37 runnable tasks, 0% idle, ~49% user/~50% system, negligible I/O wait, and load
average rising to 24.20. RAM was not exhausted (about 4.2 GiB available; no swap).
Local API readiness again timed out after 15 seconds and the external authenticated
API client timed out. Earlier Machine Ready/Available is historical/transient, not
proof of a stable Cluster. The host itself retains spare CPU/RAM; the constrained
per-VM offering is the immediate sizing gate. Four vCPU per CP is a proposed next
qualification measurement, not a proven sufficient production size.

Paused the CAPI Cluster and suspended both baseline and remote Flux Kustomizations
before further retries/provisioning. The controller reconciler timer remains
inactive. Three provider-created VMs remain preserved: first CP, next CP, worker;
no completed 3+1 Cluster or lifecycle/production certification is claimed. Next
operator decision: authorize a revised fixed CP offering/request (suggested 4
vCPU, retain measured-safe memory) and a fresh capacity check. Do not mutate the
existing locked request or use native VM resizing as a CAPC bypass. Preserve the
current protected journal, credentials and diagnostic evidence for continuation.

### 2026-09-09 — approved four-vCPU control-plane qualification

Operator approved a new 4-vCPU CP offering/request; worker stays 2 vCPU/8 GiB.
Created and read-back verified `LS-RKE2-CP-4CPU-V4`, UUID
`0ec438b2-642a-45fe-82cd-ff379c1c7d96`: 4 vCPU, 2000 MHz, 6144 MiB, fixed,
shared/thin, offerha=false, limitcpuuse=false, rootdisksize=0. Internal linked disk
offering `1ae1aac5-58d1-4ad1-a9ed-3aaf3b5a4112`. No existing offering was changed.
The private operator helper reused secure signed transport; the product preflight
client remains read-only and source was not modified.

Authoritative cleanup proof found exactly one ROOT volume per each of the three
old project VMs and no CAPC ownership tag on the pre-existing network/public IP.
Retired the old qualification journal. CAPI deleted the disposable Cluster and
CAPC removed all three VMs; no native VM resize/destroy API was issued manually.
Used documented CAPI drain/volume-wait exclusions only after this root-only proof.
Old suspended Flux Kustomizations were removed using supported Orphan deletion
policy because their disposable workload cluster was being deleted. Shared Flux
source and pre-existing CloudStack network/public IP remain.

Fresh preflight: PROVISION_ALLOWED; new plan 14 vCPU/28000 MHz, 26 GiB RAM,
160 GiB root storage. Remaining headroom: 7 CPU cores, 44.373844146728516 GiB RAM,
469.69885186851025 GiB primary storage. Safety reserves retained. Old journal
`controller.sqlite` remains retired; new protected journal is
`/var/lib/layersentry/k8s/controller-cp4.sqlite`, context
`/etc/layersentry/k8s/qualification-cp4.json`. No credentials copied to Git.

New request `ls-rke2-cp4-poc`, operation
`a9294dda-dbeb-46de-9a9c-b99a6a705c41`, idempotency
`layersentry-cp4-qualification-20260909`. Same project/template/Canal/provider
artifacts, topology 3+1. First CAPC VM `66004a18-35ff-4eef-bce0-52b204e2fbe7`,
`i-4-15-VM`, has 4 vCPU and 6 GiB in live libvirt XML. Fresh cloud-init verified
both pinned SELinux RPM signatures, installed them successfully, staged RKE2
assets and began container startup. No guest-specific repair/reboot was used.
Endpoint rules and worker desired state converged; operation waits before Flux
baseline while the first CP stabilizes. Full Cluster Ready is not yet claimed.

At 06:04–06:07 UTC the first CP and second CP had registered; etcd/API containers
were Running with zero restarts, but first CP controller-manager/scheduler had
restarted after API lease-renewal timeouts. First authenticated public readyz
passed all checks; later bounded queries were intermittently slow. Guest-agent
CPU deltas showed nearly zero idle on CP1 and about 2% idle on CP2, while the
worker was mostly idle. First kubelet statistics reported about 3.46 CPU cores
used: kubelet 0.93, API server 0.86, etcd 0.59, Canal 0.43. Available guest RAM
was about 3.45 GiB. This is not yet stable Cluster Ready or proof that 4 vCPU is
sufficient. Full 3+1 and Flux baseline remain pending. No manual node repair.

Diagnostic limits: guest-exec and guest-file operations are disabled by the
existing QEMU agent. Attempted temporary diagnostic public-key addition was
rejected with permission denied; no guest key was installed and no policy was
relaxed. Read-only virt-cat inspection failed on the live disk lock; no disk
write, forced unlock, filesystem edit or guest reboot was attempted.

### Current stop gate — four-vCPU CP pressure persists

At 06:06 UTC a second guest-agent measurement confirmed 0.00% CPU idle on both
CPs, negligible steal (0.23%/0.28%) and zero I/O wait. CP1 load1/load5 was
33.75/35.75; CP2 was 25.94/17.92. Worker CPU was 92.06% idle, load1 0.19, and
had not registered. The second CP Machine remained Not Ready after a bounded
wait. No additional addon baseline was applied. Paused `ls-rke2-cp4-poc` through
CAPI; reconciler timer remains inactive. Three provider-created VMs are preserved.
Do not interpret the first Node Ready or readyz pass as stable full-cluster proof.

Requested next operator sizing decision: increase outer `sen` from 24 to 32 vCPU
and qualify a new fixed 8-vCPU CP offering/request, retaining CP 6 GiB and worker
2 vCPU/8 GiB. This is a proposed measurement, not proven sufficient sizing.
Planned RKE2 CPU would be 3*8+2=26 vCPU. The earlier fresh admission showed
21 CPU available before RKE2 guest allocation; with 8 additional host CPU,
29-26=3 CPU remain, exceeding the 2-CPU floor if system usage is unchanged.
Arithmetic minimum increase for this proposed plan is 7 CPU; 32 total gives one
additional CPU beyond that floor. RAM/root storage plan remains 26 GiB/160 GiB;
no RAM or storage increase is requested on current evidence. Capacity must be
freshly remeasured after any host change. Do not resize individual VMs manually,
reuse a stale capacity approval, restart the old journal, or silently alter the
locked current request. No separate tenant cluster is admitted yet. Coordinate
host maintenance before any shutdown; do not power off `sen` unexpectedly.

No LayerSentry source defect was proven during this sizing pass. Existing source
validation (138 K8s tests plus 5 downstream tests; CI 34313543946 SUCCESS) remains
applicable to unchanged source. Only this scoped evidence file changed in Git;
no credentials or runtime kubeconfigs were copied. Live provisioning remains
BLOCKED at stable control-plane readiness, not LIVE_VERIFIED/PRODUCTION_CERTIFIED.

### 2026-09-09 — resized host and eight-vCPU qualification

Operator increased `sen` to 36 vCPU and the requested 84-GB RAM allocation,
then restarted it without a storage change. Hyper-V reported 36 processors and
88080384000 assigned memory bytes; Rocky `free -m` reported 81952 MiB total.
CloudStack reports 36 CPUs, 84859256832 memory bytes, host Up/Enabled. Restored
only the existing loopback SSH management tunnel after reboot. System VMs/router
restarted automatically; SSVM and Console Proxy both returned Running/Agent Up,
and router HAProxy is active. Router link-local IP changed to 169.254.208.179;
SSH validated against the same previously trusted VM host key using HostKeyAlias.
No Windows/Hyper-V networking, NAT, routes, NFS, template or firewall changes.

Created/read-back verified fixed `LS-RKE2-CP-8CPU-V5`, UUID
`4b1e8045-54cb-4ada-babb-ebfc730da62c`: 8 vCPU, 2000 MHz, 6144 MiB, shared/thin,
rootdisksize=0, offerha=false, limitcpuuse=false. Internal disk linkage
`3b82e86f-c907-42fe-864d-c3cd6323ab07`. Existing offerings retained unchanged.
Worker remains `a530859d-06fd-4bb6-8223-838afa0ee9b6` (2 vCPU/8 GiB).

Proved exactly one ROOT disk per each of the three stopped CP4 project VMs,
no additional project VMs, no Flux Kustomizations, and no CAPC ownership tags on
pre-existing network/frontend. CAPI/CAPC deleted the CP4 cluster and all three
VMs. Cleanup initially failed while the rebooting router was unavailable;
paused retries, verified router recovery, then resumed the same finalizers to
successful deletion. No forced finalizer removal or manual VM API deletion.
CP4 journal is retired and retained; source and all prior evidence preserved.

Fresh CP8 admission at 06:33 UTC: PROVISION_ALLOWED, nested KVM PASS, host Up,
36 total/3 allocated/33 available CPU before guests. New plan 3 CP + 1 worker:
26 vCPU, 52000 MHz, 26 GiB RAM, 160 GiB roots. Post-plan headroom: 7 CPU,
48.42567825317383 GiB RAM, 586.16796875 GiB primary storage. CPU/RAM safety floors,
20% primary/secondary reserves and healthy System VM requirements all retained.
Private sanitized result: lifecycle-qualification/preflight-cp8-admission.json.

New bounded context `/etc/layersentry/k8s/qualification-cp8.json`, protected
journal `/var/lib/layersentry/k8s/controller-cp8.sqlite`, request `ls-rke2-cp8-poc`,
operation `2443f8e6-65a7-4ea2-acfb-d55fd7025cd6`, idempotency
`layersentry-cp8-qualification-20260909`. Config check passed QUALIFICATION_ONLY,
productionDeployable=false with all seven live blockers unchanged. Started the
existing BFF; timer remains inactive and each lifecycle step is advanced manually.
Same provider/image/template/Canal artifacts. Cluster sizing remains under live
qualification; no production-readiness claim or additional tenant cluster.

CAPC created first CP8 VM `3af28c10-aceb-4095-9429-9ba39379ebc8`, `i-4-18-VM`,
with 8 vCPU/6 GiB and no CPU quota cap. Both native 6443 and 9345 rules are Active
on 10.10.11.23. First Node registered Ready, while bootstrap/system load still
needs stability measurement. Worker admission then exposed a new source defect:
native CPU already included the first 8-vCPU CP (11 allocated, 25 available), but
qualification subtracted the full 26-vCPU request again. Fresh host evidence
reproduced `Insufficient CPU after management/system reserve`. Paused the Cluster
before further provider creation; no extra compute requested to hide this defect.

Targeted correction in source commit `6bd61dcad45dfa74c816bdd9ab50b1fcf5510e7d`:
observe exact Cluster/RKE2ControlPlane/Machine/CloudStackMachine owner UIDs and
native project/zone/host/network/offering/template/CPU identity. Credit only
already Running CP CPU/MHz included in the native allocation, with stable reads
before/after capacity discovery. Workers, RAM and root storage remain reserved
in full; this is intentionally conservative. Missing/foreign/ambiguous/changing
ownership or allocation fails closed. No CloudStack mutation API was added.
Freshness, nested KVM, host/pool, CPU/RAM floors and 20% storage checks remain.

Focused capacity/qualification/executor tests: 44 PASS. Full source validation:
147 K8s tests + 5 downstream tests PASS; distribution verification and diff checks
PASS. Regenerated distribution from exact source commit above, tree
`b2756d8231c360df48680984f8c7b679b4902b574896c1667e9b0acd26f71e53`, receipt SHA
`942da569cdb93a777d0a8c7d9f2ccbb34cdd3f8bf77ea3ac539705b697f33e59`.
All production/live qualification booleans remain false.

Source CI 34320850503 passed at `a9cb7acb9c54fbdbc55980ebb772843112d24055`.
During stopped-BFF installation, the runtime correctly rejected the release:
the receipt SHA was updated, but duplicate controllerDistribution.sourceCommit
and treeSha256 fields were still old. Corrected these two release metadata fields
to the exact existing source/receipt identities; no controller source change or
gate bypass. Direct evaluate_component_readiness then returned exactly the seven
pending live blockers. The failed context revision did not alter journal binding.

Final corrected source CI 34321140776 passed at
`c4bfaf5dba998d62e29b34f2f74ca9c29355f415`. Exact release installed with BFF
stopped; explicit qualification-release revision succeeded without changing the
locked request or operation. Runtime then exposed missing Machine-list permission
for the new ownership observation. Added only namespaced Machine list and
CloudStackMachine get permissions for the existing qualifier ServiceAccount via
`tools/layersentry/k8s/qualification-capacity-read.yaml` (server dry-run PASS).
No Secret access, mutation verbs, ClusterRole broadening or foreign namespace.

Live corrected admission PASS: exact existing CP credit 8 CPU/16000 MHz;
remaining headroom 7 CPU, 42.160240173339844 GiB RAM, 549.6988518685102 GiB primary.
The same operation/journal resumed; no replayed Cluster create or VM duplication.
CAPI Cluster unpaused and BFF restarted; reconciler timer remains inactive.

CI 34321668345 failed only because hosted Python lacked PyYAML for the new RBAC
YAML. Converted identical Role/RoleBinding objects to
`tools/layersentry/k8s/qualification-capacity-read.json` (Kubernetes List).
Normalized objects compare equal; no extra dependency or permission change.
Installed controller source/release bytes remain those already CI-verified.

Final JSON RBAC validation passed 147 K8s + 5 downstream tests; server dry-run
reported identical existing permissions. Feature CI 34322029159 SUCCESS for
`ca56dade530b86b013d41b35f859e7e0016b74a1`. Shared branch remains unchanged.
First CP8 public 6443 and 9345 both passed TLS certificate verification against
the cluster CA (TLSv1.3), and authenticated public readyz returned ok.

CAPC next created CP2 `6324e025-aa22-4392-8003-eabc4ee8f24a` (`i-4-19-VM`, 8 CPU,
6 GiB, guest 172.17.30.124) and worker `50f07200-4589-47e6-bb6c-21ee11b57792`
(`i-4-20-VM`, 2 CPU, 8 GiB, guest 172.17.30.67). Both use the exact qualified
Rocky template. Same journal reached step 7 (before baseline packages). No Flux
baseline Kustomization applied yet; CP2/worker joining and final CP3 remain pending.

### 2026-09-09 — CP8 joined, then control-plane health failed

Both CP Machines acquired NodeRefs; CP2 reported EtcdMemberHealthy at 07:37:44
UTC. Last successful CAPI workload probe was 07:38:37 UTC. Subsequent public and
direct CP2 API reads timed out; both Machines became Ready UNKNOWN. CP3 has not
been created and the worker has no NodeRef. This is not stable Cluster Ready.

Authenticated, CA-verified kubelet observation recovered CP2 cloud-init and
service/container logs without installing guest keys. Cloud-init completed at
07:37:17 UTC after verified pinned SELinux RPM and RKE2 archive installation.
Etcd established peer streams to CP1, then logged loss of leader at 07:42:56 UTC
and repeated read/raft agreement timeouts. Read-only libguestfs inspection of
CP1 recovered its messages: RKE2 failed lease renewals, exited at 07:40:30 UTC,
and its automatic restart stopped progressing after opening the local etcd
connection at 07:40:53 UTC. No guest reboot, filesystem write, security-policy
relaxation or manual VM creation was used for these observations.

Host/guest clocks agree. A bounded guest CPU sample observed CP1 12.55% idle,
CP2 0.39% idle, and worker 74.56% idle; CP2 load1 was 38.27 on 8 vCPU. Earlier
fresh balloon measurements showed usable RAM on both CPs; sampled primary I/O
averages were approximately 3.5–3.7 ms/write and 1.3 ms/flush. These measurements
do not prove the root cause or exclude storage latency outliers. No additional
CPU/RAM/storage sizing is claimed sufficient from these observations alone.

Paused `ls-rke2-cp8-poc` via the CAPI pause annotation during forensics. The
reconciler timer remains inactive and the same operation remains at step 7,
before baseline packages. Private raw evidence is under the existing protected
`lifecycle-qualification` directory: `cp8-cp2-kubelet-messages.log`,
`cp8-cp2-etcd-file.log`, `cp8-cp2-kubelet.pprof`, and
`cp8-cp1-disk-messages.log`. Logs are not copied into Git. The next diagnostic is
CP1's etcd/container log; do not retry cluster creation or change offerings to
hide this failure. All production/live qualification flags remain false.

The next read-only disk inspection recovered CP1 etcd, API, kubelet and containerd
logs (`cp8-cp1-disk-detail.json`, private). Etcd logged slow apply/read operations;
kubelet housekeeping took 40–50 seconds. A concrete independent bootstrap defect
was also exposed: CNI portmap repeatedly failed pod sandbox creation because
`iptables` was absent from its PATH. This is a proven missing Rocky/RKE2
prerequisite, not proof that it alone caused every etcd timeout.

Extended the existing pinned air-gap prerequisite transaction with Rocky 9.8
BaseOS `iptables-nft`, `iptables-libs`, `libmnl`, `libnftnl`, `libnfnetlink`, and
`libnetfilter_conntrack`. Exact URLs, byte SHA256 and RPM NEVRA are in the existing
qualification lock. All six downloaded RPMs passed signature and checksum
verification; no host package was installed for this verification. This follows
the upstream [RKE2 air-gap prerequisites](https://docs.rke2.io/install/airgap),
which include iptables-nft/libnftnl. The same bootstrap transaction keeps all
repositories disabled, verifies every RPM signature, checks exact installed
versions, and now rejects missing/non-nft iptables and ip6tables before staging
RKE2. SELinux Enforcing, immutable RKE2 images, registry-fallback prohibition,
capacity reserves and ordinary-project behavior are preserved.

Seven focused consumption tests passed, including CP/worker staging, ordinary
project behavior, immutable prerequisite tampering, package closure inclusion,
missing/broken/legacy iptables rejection, and checksum failure stopping startup.
The failed CP8 cluster is still paused and preserved; this source correction is
not yet live-verified. All temporary diagnostic SSH forwards and read-only
inspection appliances were closed. The management tunnel is retained.

Source correction committed as `c8e7ab0cf8d369b5fbf10ca621bff32c10de9e82`.
Regenerated distribution from those exact committed bytes: tree
`2fda63c62246f87c4baf7bc8ed0da263a792d370b32a3c483a697973ca56aa17`, receipt SHA
`a92114ec2964b0f637b1368d209e13ba251ac6812aa53410d3dacbbeac500407`.
Qualification lock SHA is
`1f54c32e0f0e43fe1877322f9671ef42cc29ba5ef330ca97239f30db4d2b2212`.
Full source validation passed 150 K8s tests plus 5 downstream tests; distribution
verification and diff checks passed. Readiness still reports the same seven
pending live evidence gates. Existing live controller/request artifacts have not
yet been replaced by this correction; source CI and a fresh CAPI bootstrap are
the next gates.

Feature CI `34328507813` SUCCESS at
`16ef35980c672d1f3b928a7f6ecc3b7c7603d2b1`. Installed the exact five-file runtime/
artifact update, archive SHA
`3207ab06fe84348c74330f492d28451efd3785512b2390dd31bf723bd232a5e1`.
Runtime validates with the seven production blockers retained. Captured failure
logs and exact root-only volume proof before retiring CP8 through CAPI/CAPC.
Used the existing disposable root-only drain/volume-wait exclusions; no forced
finalizer removal or native/manual VM destruction. All three VMs and old Cluster
resources are deleted. Pre-existing project network/frontend were preserved.
Old CP8 journal was explicitly retired and retained.

Fresh admission for the corrected attempt: PROVISION_ALLOWED, nested KVM PASS,
36 CPU total, 3 allocated, 33 available; plan remains 3x8-CPU/6-GiB CP plus
1x2-CPU/8-GiB worker, 160 GiB roots. Post-plan headroom: 7 CPU,
37.34791564941406 GiB RAM, 509.69885186851025 GiB primary. Both storage reserves
and host freshness checks passed. Private `preflight-cp8-net-admission.json`
records cluster_create_executed=false at the preflight itself.

New Cluster `ls-rke2-cp8-net-poc`, operation
`c7329569-93f6-4e46-bebe-2c957d7ec600`, idempotency
`layersentry-cp8-net-qualification-20260909`. Protected journal/context are
`controller-cp8-net.sqlite` and `qualification-cp8-net.json`; prior contexts and
journals remain retired. CAPC created VM
`18ea4910-af62-4fd7-aff5-c68e7e1e3013` (`i-4-21-VM`, 172.17.30.104), 8 CPU/6 GiB,
approved offering/template. First Machine is
`ls-rke2-cp8-net-poc-control-plane-q47g4`. The saga reached step 7, before baseline
packages. BFF is active; reconciler timer remains inactive. First-node bootstrap
and stable Cluster Ready are still PENDING, not live success of the correction.


### CP8-NET join diagnosis — 2026-09-09T09:22:23.080829+00:00

First control-plane Machine q47g4 is Running/Ready with Node ls-rke2-cp8-net-poc-control-plane-cpu-v2-t7859. CAPC also created second control-plane VM ad617bcb-f1c4-45cd-b3ee-8530e6180020 (i-4-22-VM, 172.17.30.142) and worker aa754be3-452f-4c14-aa3a-89883c823375 (i-4-23-VM, 172.17.30.154); neither has a registered Node yet. Third CP creation remains pending provider sequencing. This is not Cluster Ready.

Compared the actual decoded bootstrap configurations without exposing tokens: the CP configuration differs only in server, with the second using https://10.10.11.23:9345 and the same nonempty registration token. CAPRKE2 registrationMethod is control-plane-endpoint; availableServerIPs contains 10.10.11.23. Both native 6443/9345 LB rules are Active and TCP reachable from the management host. No join-configuration source defect has been established by these checks.

Second CP console proves verified airgap installation reached systemctl start rke2-server, then reported startup failure and automatic retries. Its kubelet 10250 subsequently became reachable, but authenticated pods/log reads returned HTTP 500 Authorization error. The first API readyz passed including etcd at the sampled time, while recent events show intermittent component probe timeouts. These are not stable multi-node readiness proof. Host sample: approximately 41% idle CPU, no swap use; no evidence-based request for further compute is established.

Private console and diagnostic evidence is under lifecycle-qualification/ (cp8-net-cp2-console.log, cp8-net-cp2-kubelet-*.raw, cp8-net-cp2-filesystem-logs.*). Live read-only XFS inspection rejected a mount with Structure needs cleaning; this inconsistent live disk view does not prove guest filesystem corruption. No filesystem repair, native VM lifecycle action, networking change, source change, or readiness-gate relaxation was performed. Temporary diagnostic forward 16448 and console reader were closed; final root-only ro,norecovery inspection is pending. First unmet gate remains joining-node startup/registration and stable 3+1.

Root-only read-only XFS inspection with ro,norecovery succeeded (cp8-net-cp2-root-logs.json, private); no log replay or guest-disk mutation. Captured second-node messages at 09:20 UTC show Starting etcd for existing cluster member, Connection to etcd is ready, and ETCD server is now running. Earlier startup exited because the local API server never became ready (127.0.0.1:6443 connection refused, context deadline exceeded, systemd result protocol). Kubelet likewise cannot register against that local API. This establishes progress past registration-token discovery into etcd membership, not Kubernetes Node Ready. A focused API-server/containerd log read is the next diagnostic. Both CPs expose TCP 2379/2380 from the router, and router rules allow frontend TCP 6443/9345. First Node Ready heartbeat sampled at 09:26:23 UTC was 09:24:55 UTC. No live success or production qualification flag changed.

Focused API-server container-log inspection could not complete: read-only diagnostic appliance launch reached its 600-second bound. The stalled appliance and all temporary console/16448 diagnostic readers were terminated; management tunnel 16443 was preserved. No repeated provisioning or filesystem repair was attempted. First CP kubelet/supervisor ports were subsequently not listening while 6443 remained reachable; previous Ready status is not a claim of sustained health.

Verified the second CP SSH host key from its trusted libvirt console output and attempted the existing qualification diagnostic key through the trusted host/router path. SSH rejected it with publickey/gssapi methods only (password authentication is not offered). Management-host root access does not provide guest shell access. Current diagnostic blocker: a working SSH key or authenticated console on second CP 172.17.30.142 is needed to read its API-server/containerd/etcd logs and prove the cause before a permanent fix. Existing public key is cp4-diagnostic-key.pub in the protected local lifecycle-qualification directory; no private key or credential was copied into repository evidence. Product source and live readiness flags remain unchanged. Cluster/all-node readiness remains BLOCKED.

### CP8-NET authenticated diagnosis and etcd restart recovery — 2026-09-09

The guest-access blocker above is resolved under renewed operator authorization.
Trusted libvirt consoles installed the existing restricted diagnostic public key
on the two exact CP guests. Temporary console passwords were locked again and
removed from local storage; password SSH stays disabled and SELinux Enforcing.
Guest known_hosts keys were verified through the trusted consoles.

Authenticated evidence establishes an etcd logging restart deadlock: CP1 lost
its rke2-etcd leader lease at 09:07:27 UTC; RKE2/containerd exited while static etcd
continued with stdout/stderr pipes that were no longer drained. Both etcd
processes had threads blocked in pipe_write. RKE2's local-datastore-first startup
then failed with failed to reconcile with local datastore / context deadline
exceeded. The actual CP join configurations differ only in server and have the
same nonempty registration token; no join-token/address defect is established.
This matches upstream RKE2 issue 11056 and etcd issue 22326.

A bounded read-only drain of existing process log pipes (no datastore/member/VM
mutation) drained 895108 bytes from CP1 and 170278 from CP2. CP1 service became
active after 116.7 seconds; CP2 passed local etcd bootstrap and started containerd
but had not become active at the 150-second bound. Subsequent etcd member list
contained both exact CP members and a local linearizable health check passed.
CP2 has a separate proven unpack failure: kube-apiserver and kube-proxy container
creation cancels overlayfs layer extraction after about 120 seconds, leaving its
API unstarted. This is not yet stable 3+1 readiness.

The narrow source correction uses CAPRKE2 serverConfig.etcd.customConfig.extraArgs
to select a file-only log sink inside RKE2's existing protected etcd data mount,
with built-in rotation (20 MiB, three backups, seven days, compression). It does
not change peer/TLS, elections, fsync, membership or volume ownership. Verified
against the pinned RKE2 executor/k3s ToConfigFile path, CAPRKE2 config mapping and
live etcd 3.6.14 help. JSON-array log-outputs is required by that conversion path.
A protected CP2 RKE2 config drop-in is under live validation; no CAPI template
rollout or VM creation has been dispatched for this change. Existing latency
measurements remain a separate concern, not resolved by file logging.

Logging source commit: `7b6d3976948b1174c2db2c55544c24a01b7d62fd`.
Regenerated distribution from those exact bytes: tree
`fb85a7d67ef4a1eec7618858233dd4801e0b6d69a3e2b9018d1852b03dd43110`, receipt
`cc61b0d5aa98149ed94fa88bff9069f17e891c04f67b25e0cd4b711738bb0512`.
Validation: 18 focused tests PASS; complete validate-source.py PASS with 151 K8s
and 5 downstream tests. Distribution verification and diff checks PASS. The same
seven live-readiness blockers remain false; this source evidence is not cluster
or lifecycle qualification.

Logging feature CI `34339700527` SUCCESS at
`cf8873253bdced51a0101f52b6ea7628dd4a6610`. CP2 now runs etcd PID 20434 with
its protected 0600 file sink and a successful local linearizable health check;
no pipe_write block was present. CP1 requires completion of its static-pod
replacement before restart recovery can be called verified on both nodes.

### CP8-NET cold image extraction deadline — 2026-09-09

The pinned kubelet confirms runtimeRequestTimeout defaults to 2m. CP2 repeatedly
cancelled cold overlayfs extraction while CreateContainer was still working.
A qualification-only 0600 KubeletConfiguration drop-in sets a finite 10m deadline;
restarted only the kubelet child through RKE2's existing retry supervisor. No
etcd/containerd/service restart or image replacement was needed for this test.
After that change kube-proxy CreateContainer completed at 10:24:22 UTC and
kube-apiserver at 10:24:47 (started successfully at 10:24:51). Both previously
failed repeatedly at approximately 120 seconds. Their successful extraction
exceeded that default but stayed within the new bound. This proves the narrow
cold-image timeout hypothesis, not stable API/Node/Cluster readiness.

The source correction emits the same standard CAPRKE2 files entry for both
qualification CPs and workers. Pinned RKE2 writes its own 00-rke2-defaults.conf
without removing this supported later kubelet drop-in. Ordinary projects retain
their defaults. The only kubelet setting changed is runtimeRequestTimeout;
registry fallback, image identity, TLS, reservations and all live gates remain
unchanged. Nineteen focused tests PASS, including qualification/ordinary-path
separation and exact bounded configuration for CP and worker.

Worker diagnostic access was established through its exact trusted libvirt
console using the existing restricted public key; the temporary console password
was relocked and deleted locally. Its observed join requests reach the supervisor
and receive runtime-core-not-ready/503 while control planes recover. No worker
VM replacement or bootstrap-token change was performed.

Cold-unpack source commit: `4069864dd69a77d844d2da7900128a874f325e59`.
Exact regenerated tree:
`04e8a4ad54125c353481edd42ac5be0424f6167b3d86d2307f351e98b6d469ec`;
receipt SHA: `ad1acbe21235934394118ba66376f790cf065d76ca5c735b4030e99d1f8a61ec`.
Full validation PASS: 152 K8s tests + 5 downstream tests; distribution and diff
checks PASS. Seven live-readiness gates remain pending.

CP1 subsequently completed its logging-config static-pod replacement. Its RKE2
service is active, protected file sink exists, local etcd linearizable health
passed (sample latency 1.124793941s), and workload API responds again. This remains
high-latency recovery evidence, not sustained performance or all-node readiness.
