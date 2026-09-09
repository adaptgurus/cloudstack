# CloudStack/native RKE2 source audit — 2026-09-08

Starting shared Git: `0a68c004a7a49d17d39a502e048642d0e3df2ba6`.
One implementation writer, isolated `codex/k8s-native-api-completion` worktree.
No old source reset or foreign module edits.

| Surface | Result |
|---|---|
| Signing/transport | Reused V3/expiry/POST/TLS/custom CA/redirect/timeout/response bounds. Fixed reserved parameter command override, credential rotation/symlink/mode checks, non-object/duplicate JSON and untrusted error-code/exception disclosure. |
| Resolver | Reused exact IDs, project state, Site, offerings, KVM images. Added returned network project, template Site/project query and frontend associated-network checks. |
| Endpoint observation | Revalidates frontend; complete bounded pagination; rejects foreign/ambiguous rules; both Active TCP public/private 6443 and 9345 required. No endpoint mutations. |
| Capacity | Added native type-specific reads, exact single-host/shared-pool POC discovery, offering/image sizing, physical capacity intersection, freshness and management/storage reserves. Missing allocation is UNKNOWN. |
| VM observation | Exact CAPC-supplied VM ID, project/Site isolation; only sanitized ID/state returned; absence and ambiguity tested. No scheduler or VM lifecycle calls. |
| UNKNOWN/restart | Reused durable saga and Kubernetes authoritative GET. Fixed premature convergence when owned resources exist but desired spec was not applied; restart regression proves no duplicate successful apply. |
| Async native jobs | NOT_REQUIRED: zero native mutations. CAPC owns native jobs. No unused async framework or mutation replay introduced. |
| ExternalManaged | NOT_REQUIRED: adds no necessary V1 lifecycle proof; no registration/lifecycle bridge introduced. |
| Runtime config | Existing configuration reused; no new secrets or production policy overrides. Read-only POC entry point loads the existing configuration. |
| Live | BLOCKED. See `lab-capacity-preflight.json`; unknown capacity is not proof of insufficient hardware or production readiness. |

Validation before this change: five CloudStack tests; full validator 74 tests +
five downstream tests, green. Expanded source validation: 93 tests + five
downstream tests, green. The restart test initially simulated response loss before
all infrastructure objects were applied; the executor correctly reported missing
objects. The no-duplicate-completed-apply test now loses the response after the
last object, while a separate test covers an owned object with the wrong spec.

Exact native contracts were inspected in current CloudStack source:
`Capacity.java`, `CapacityResponse.java`, `CapacityDaoImpl.java`,
`ManagementServerImpl.java`, `ListCapacityCmd.java`, `ListClustersCmd.java`,
`HostResponse.java`, `StoragePoolResponse.java`, `TemplateResponse.java`,
`TemplateJoinDaoImpl.java`, `ServiceOfferingResponse.java`,
`IPAddressResponse.java`, `LoadBalancerResponse.java`.

Limits: this POC helper deliberately blocks multi-host/ambiguous pool placement,
local/custom disk profiles and additional node disks. It is read-only and must be
rerun immediately before a separately gated CAPI request. It is not a new
production admission service. Endpoint API metadata is not a TCP or Ready proof.
No release tuple, production HA semantics, application gates or runtime ownership
changed. No GUI/DBaaS/APaaS/CSI/CCM/DR work belongs to this result.

## Live continuation: management cluster recovered

User authorized 3 control planes + 1 worker. The disposable local kind management
cluster now runs digest-pinned Kubernetes 1.36.4. CAPI 1.13.5, upstream CAPC 0.6.1
and CAPRKE2 bootstrap/control-plane 0.25.2 deployments are Available; provider
CRDs are Established. Existing CAPC overlay was applied to exact upstream source
and compiled successfully with upstream-pinned Go 1.23.2. The image uses the
recorded distroless digest, was loaded into kind, and its Deployment rollout
succeeded. Both changed CRD schemas were applied. See
`live-management-checkpoint.json` for artifact and running image digests. This
proves management/provider startup only, not workload lifecycle readiness.

DC API and verified SSH work. Project is Active; both supplied offerings resolve.
Native capacity reports 12 total/2 allocated/10 available cores; the 3+1 workload
requests 8 cores and 26,000 MiB RAM, with at least 180 GiB roots. Management runs
locally to preserve the DC reserve. These numbers do not approve provisioning.

The first IaaS blocker is the Basic-zone shared network: no returned project ID,
state Setup, no LB service and no project public IP. Existing LayerSentry requires
a project network and authoritative dual-port frontend. No CloudStack mutations
or workload cluster attempts were made. Do not reconstruct the existing DC Zone
or introduce a second endpoint lifecycle. Resume with an Advanced-zone target or
a separately authorized lab migration. Template and linked disk-offering/speed
validation remain subsequent prerequisites; CCM/CSI/Flux were not attempted.

## 2026-09-09: reboot recovery and persistent configuration

This continuation supersedes the earlier host-capacity observation: Linux and
CloudStack now report 48 CPUs. Linux reports 98,418,114,560 usable RAM bytes
(about 91.7 GiB). This is host inventory, not a completed workload qualification.

The missing native guest bridges blocked the existing one-use maintenance restore
unit after the user's reboot. Recovery restored the six recorded guests using
the existing CloudStack bridge helper. CloudStack host/system agents and storage
returned Up, the management UI returned HTTP 200, and the host has zero failed
systemd units. Consumed saved-memory checkpoints remain `.save.restored`; they
must never be replayed. The recovery script now records pending guest-clock
correction separately and requires synchronized host time before setting it.

The management connection failure was a missing transient reverse SSH tunnel.
The durable workstation supervisor uses pinned SSH trust, a singleton lock,
keepalives, loopback binding, kubeconfig port discovery and boot/minute cron
startup. Forced SSH-child termination, automatic reconnect and an authenticated
controller-side Cluster GET passed. This lab still depends on WSL and cron being
online. Local recovery receipts and the former crontab are preserved under
`/home/opc/.local/share/layersentry/rke2-poc/recovery-backups/20260909/`.

The persistence rule is committed in `AGENTS.md` at `b6629b6440`. The exact runtime
distribution is committed at `98992de53a438418090d63a1408c85f2d4162297`, with
[source CI 34348344365](https://github.com/adaptgurus/cloudstack/actions/runs/34348344365)
successful. Local validation passed 153 K8s and five downstream tests. The deployed
API service tolerates the absent optional `/run/credentials` directory, creates
its runtime directory, restarts on failure and is enabled for boot. A controlled
service restart passed with unchanged runtime, qualification and unit-file hashes.
Its unauthenticated socket request returns 401, not an authentication bypass.
The existing request and operation journal were retained; production gates remain
closed and the reconciler remains disabled.

All three existing workload nodes have the source-generated persistent 10-minute
container-runtime deadline and both RKE2 time-sync drop-ins. Although initial
daemon-reload clients timed out, subsequent effective unit reads confirmed the
new `ExecStartPre` on all three nodes. The first control plane also recorded a
successful execution of that gate on its automatic restart. Chrony reports Normal
leap status and less than one millisecond system-time offset on all three.
The shared time-drop-in SHA-256 is
`2641f43f3c14acd8a8d096e6862790adb05dab2313b087234ac4d7679654ccc9`;
the kubelet configuration SHA-256 is
`26e052c4cf694b45c142de917ad3c70b4e315956abc970e7179e53b173e343a7`.
Node backups reside in `/var/lib/layersentry/reboot-recovery/20260909/`.
Server release/unit/journal backups reside in
`/var/lib/layersentry/k8s/pre-reboot-persistence-release/`.

Workload recovery is still **BLOCKED**: `ls-rke2-cp8-net-poc` remains intentionally
paused, with two eight-vCPU control planes and one worker in RKE2 startup recovery.
Healthy local etcd health responses and corrected clocks did not establish
sustained Kubernetes API readiness. CPU saturation and CRI timeouts remain
observations; the underlying cause is not proven. A proposed CAPI-owned clean
replacement (three 12-vCPU control planes and one two-vCPU worker) awaits explicit
approval because it deletes the three existing 40-GiB root disks and cluster
state. That sizing is a diagnostic proposal, not a proven fix. No replacement or
direct disk deletion has been performed.

Full controlled reboot acceptance of these new fixes is **NOT_TESTED**. Do not
reboot the host or replay consumed memory images to manufacture that evidence.
First resolve the workload blocker, then follow the persistent-configuration
acceptance checks in `tools/layersentry/k8s/NATIVE_API_POC.md`.
