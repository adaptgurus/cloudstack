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
