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
