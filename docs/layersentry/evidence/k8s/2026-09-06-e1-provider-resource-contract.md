# Workstream E1 — pinned CAPI/CAPC/CAPRKE2 resource and Kubernetes API contract

**Date:** 2026-09-06  
**Status:** resource builders and restricted Kubernetes client `SOURCE_COMPLETE`; provider reconciliation `NOT_TESTED`  
**CloudStack core impact:** none

## Exact source validation and decision

The builders were checked against:

- CAPC `v0.6.1`, commit `7521b14a31e6c46f81f16aae3738a27c08ad063f`, including `api/v1beta3` types and `templates/cluster-template.yaml`;
- CAPRKE2 `v0.25.2`, commit `38602b72a23faf719b94b250eba66ef804bf9706`, including v1beta2 bootstrap/control-plane Go types, CRDs and example templates;
- the candidate CAPI v1beta2 contract recorded for Lane B.

The exact tuple is mixed by design: CAPI `Cluster`/`MachineDeployment` and CAPRKE2 objects use `v1beta2`; CAPC infrastructure objects use its served/storage `v1beta3`. Contract references use `apiGroup`, kind and name as required by CAPI v1beta2. This is the pinned compatibility candidate, not proof that the provider controllers reconcile together.

The generated control plane uses `registrationMethod: control-plane-endpoint`, the exact `v1.36.4+rke2r1` release, and one CAPC-owned endpoint annotated for both TCP 6443 and 9345. CloudStack Machine templates carry the downstream CAPC volume-ownership annotation. CloudStack project/Site/network/offering/template inputs must be pre-resolved to exact IDs; mismatches fail before generating resources. Credential contents are never generated—only an existing Kubernetes Secret reference is included.

CAPRKE2 v1beta2 accepts `none`, `calico`, `canal` or `cilium` for `serverConfig.cni`; it does not accept `flannel`. LayerSentry therefore removed Flannel from this pinned release policy and GUI instead of sending a CRD-invalid field.

## Kubernetes API behavior

The restricted client:

- accepts only an HTTPS origin with a pinned CA file and runtime token file;
- disables redirects and never places the token in URLs;
- permits only the exact E1 CAPI/CAPC/CAPRKE2 and Flux kinds;
- uses server-side apply with field manager `layersentry-controller` and `force=false`;
- maps 404 and 409 distinctly;
- treats any mutating transport timeout/failure as ambiguous rather than retrying;
- bounds response bodies and suppresses upstream response content from errors.

## Tests, risks and rollback

All 40 Workstream E Python tests passed. New tests cover exact API versions/references, automatic RKE2 join selection, 6443/9345 and Machine-volume annotations, resolved scope mismatches, unsupported CNI rejection, safe Kubernetes REST paths/server-side apply and ambiguous mutation transport behavior.

No CRD was installed and no API server/provider reconciliation ran. The combined version bridge, CAPC endpoint rules, actual Machine bootstrap, CloudStack CCM and CNI readiness remain `NOT_TESTED`. Roll back by removing the generated desired resources through CAPI in dependency-safe order; never delete CloudStack VMs behind CAPC. Any apply timeout must be reconciled by GET before another apply/delete.

Next gate: implement the E1 step executor, exact status/condition evaluation, scale/delete operations, CloudStack preflight adapter, one certified CCM/CSI profile and central Flux baseline package reconciliation.
