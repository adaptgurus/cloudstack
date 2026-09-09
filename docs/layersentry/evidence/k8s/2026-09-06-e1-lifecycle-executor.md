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
