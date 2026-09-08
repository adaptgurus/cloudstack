# LayerSentry K8s / DBaaS / APaaS / Streaming — Master Context Audit

**Date:** 2026-09-06  
**Repository:** `adaptgurus/cloudstack`  
**Branch:** `layersentry/4.22.1.1-ui`  
**Starting branch commit inspected:** `d62cd0cfeab977aebe0c8a3971efcb863b5251dd`  
**Change type:** documentation / stable architecture / Codex governance only  
**Runtime mutation:** none  
**CloudStack core impact:** none  
**Documentation/governance status:** `SOURCE_COMPLETE`  
**K8s/DBaaS/APaaS/Streaming runtime status:** remains only at the evidence status independently proven by implementation/CI/live tests; the new specialist architecture itself is `DESIGN_DEFINED`

## Purpose

Create one production-oriented, anti-hallucination specialist master context for LayerSentry-managed RKE2/Kubernetes, DBaaS, APaaS and Streaming while preserving unrelated LayerSentry VM, DR, appliance, security, release and CloudStack-core rules.

The user explicitly superseded the earlier product-scope statement that DBaaS/APaaS were excluded. The update therefore removes that exclusion from current authoritative/active governance and replaces it with a narrower architectural rule:

> DBaaS/APaaS/Streaming are valid LayerSentry modules, but they are implemented above LayerSentry-managed Kubernetes and must not be forced into Apache CloudStack core APIs/schema/orchestration.

Historical commits/checkpoints that accurately record the former scope are not rewritten. Git history and historical Progress Ledger entries remain evidence of what the project previously intended. The canonical Super Master Context now explicitly states that old historical exclusion statements are superseded.

## Existing governance inspected

The review inspected the active LayerSentry governance structure before writing the new module contract, including:

- root `AGENTS.md`;
- canonical `LAYERSENTRY_SUPER_MASTER_CONTEXT.md`;
- current `LAYERSENTRY_PROGRESS_LEDGER.md`;
- `LAYERSENTRY_KNOWLEDGE_GRAPH.md`;
- `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`;
- `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`;
- `LAYERSENTRY_DRAAS_ARCHITECTURE.md` relationship/authority;
- `LAYERSENTRY_CONTROL_PLANE_XAAS_AND_FUTURE_UPGRADE_POLICY.md`;
- `LAYERSENTRY_UNIFIED_PROVISIONING_UI_DR_POLICY.md`;
- `LAYERSENTRY_UI_EXPERIENCE_SPEC.md`;
- active Codex workstream/index/runbook documents;
- release/UI configuration surfaces relevant to the stale-exclusion check.

The existing global rules for exact CloudStack 4.22.1.1 research, core preservation, RBAC, secrets, supply chain, R0-R4 risk, Rocky Linux 9 acceptance, `adaptgurus/cozystack` live evidence and anti-hallucination status labels were retained.

## New specialist context

Added:

`docs/layersentry/LAYERSENTRY_K8S_DBAAS_APAAS_SUPER_MASTER_CONTEXT.md`

The specialist document is intentionally subordinate to the canonical shared context for global rules and intentionally superior to historical scope text for this module.

It defines, among other items:

1. CAPI-first LayerSentry-managed RKE2 architecture;
2. CAPC as CAPI CloudStack Machine owner after exact CloudStack 4.22.1.1 qualification;
3. CAPRKE2 automatic RKE2 bootstrap/join/control-plane lifecycle;
4. native CloudStack APIs for infrastructure discovery/IP/network/storage/platform functions outside CAPC Machine ownership;
5. central Flux package reconciliation from the LayerSentry management cluster;
6. separation of native CloudStack CKS from LayerSentry-managed RKE2;
7. QCOW2 as immutable node runtime and ISO as signed offline release/catalog carrier;
8. universal CPU node storage/troubleshooting tooling including `lsscsi`, iSCSI, multipath, NVMe and NFS clients;
9. GPU-specific QCOW2/NVIDIA lifecycle rather than loading an NVIDIA driver into every CPU worker;
10. multiple simultaneous Kubernetes StorageProfiles;
11. exact distinction between CloudStack node disks, CloudStack CSI block, CloudStack Shared FileSystem/NFS, NFS CSI and OEM CSI;
12. prohibition on treating CloudStack `shared` disk-offering storage type as safe raw guest multi-attach;
13. one-owner resize semantics for node CloudStack disks versus CSI-managed PVCs;
14. NVMe-only production DBaaS storage policy and no silent slower-tier fallback;
15. CloudStack L4/IPAM versus Gateway API L7 versus OEM hardware ADC/WAF ownership;
16. one LayerSentry Frontend lifecycle object per externally managed VIP, with multiple VIPs allowed per backend/application;
17. hardware ADC/WAF provider abstraction without CloudStack-core patches;
18. package states `AVAILABLE` / `ENABLED` / `READY` and late package installation without ISO reinstall;
19. two signed offline release families: LayerSentry K8s and LayerSentry Data Services/APaaS;
20. OpenEverest branding persistence and fail-closed branding overlay strategy;
21. explicit upstream-air-gap qualification rule for OpenEverest;
22. Redis/Valkey provider separation where stable OpenEverest does not provide the engine;
23. OpenBao and Harbor APaaS profiles;
24. Strimzi/Kafka and protocol-correct multi-endpoint exposure;
25. GUI-only normal customer workflows;
26. durable provisioning/reconciliation states rather than long untracked shell scripts;
27. capability discovery/preflight and compatibility matrix;
28. three-month-and-later upgrade model separating packages, QCOW2/RKE2, CNI/CSI, operators and database engines;
29. production destructive storage/data-safety gates;
30. production cluster, DBaaS, Kafka, OpenBao and Harbor certification gates;
31. explicit rule that a short coding sprint can produce a release candidate/POC but not production certification without real evidence;
32. licensing/redistribution controls;
33. non-interference boundary protecting unrelated existing modules.

## New workstream

Added:

`docs/layersentry/codex/WORKSTREAM_E_K8S_DBAAS_APAAS.md`

Workstream E owns only the new module and coordinates with:

- A for shared/customer UI;
- B for release/offline bundle mechanics;
- C for independent security/negative evidence;
- D for global DR/HA/upgrade evidence.

It is explicitly prohibited from using the module as permission to refactor unrelated CloudStack/LayerSentry areas.

## Active governance updates

Current active documents were aligned only where needed to remove contradiction or route work to the new specialist context:

- `AGENTS.md`;
- `LAYERSENTRY_SUPER_MASTER_CONTEXT.md` (schema 3.2);
- `LAYERSENTRY_KNOWLEDGE_GRAPH.md`;
- `LAYERSENTRY_UNIFIED_PROVISIONING_UI_DR_POLICY.md`;
- `LAYERSENTRY_UI_EXPERIENCE_SPEC.md`;
- `CODEX_MASTER_CONTEXT.md`;
- `CODEX_MULTI_AGENT_MASTER_CONTEXT.md`;
- `CODEX_4_AGENT_RUNBOOK.md`;
- `docs/layersentry/codex/README.md`;
- Workstreams A, B and C;
- `LAYERSENTRY_25_DAY_ACCELERATED_ACCEPTANCE_PLAN.md` only to clarify that the new valid modules are outside that historical base-plan estimate unless re-baselined, not excluded from the product.

Workstream D did not contain the obsolete DBaaS/APaaS exclusion and its global DR/HA authority remains unchanged. The specialist module already requires E to integrate with D rather than create a second DR framework.

## Preserved unrelated policies

The following specialist authorities were not rewritten by this task:

- `LAYERSENTRY_SECURE_ENGINEERING_POLICY.md`;
- `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`;
- `LAYERSENTRY_DRAAS_ARCHITECTURE.md`;
- `LAYERSENTRY_CONTROL_PLANE_XAAS_AND_FUTURE_UPGRADE_POLICY.md`;
- CloudStack Java/backend/API/database/KVM-agent/runtime source;
- LayerSentry Vue runtime implementation;
- installer/workflow/runtime configuration.

Shared active docs were changed only where they needed to recognize the new product module or remove an obsolete exclusion.

## Production qualification / anti-hallucination gates retained

The master context deliberately does not assert that the architecture has already passed production testing.

High-risk gates explicitly retained include:

- exact CAPC + CloudStack 4.22.1.1 + target CAPI/RKE2 compatibility;
- CAPC Machine deletion versus attached CSI/PVC data safety;
- CloudStack CSI project-scoped volume/resize behavior;
- CloudStack SharedFS/NFS RWX behavior and resize/failure semantics;
- OEM CSI/multipath/NVMe/TCP/NVMe-RDMA exact hardware/driver matrices;
- NVIDIA/vGPU/GPUDirect exact hardware/licensing support;
- CloudStack CCM VIP reconciliation and future replacement for deprecated Kubernetes `loadBalancerIP` semantics;
- Gateway/WAF/ADC exact provider behavior;
- OpenEverest complete deny-all-egress offline operation;
- DB backup/PITR/failover/data-integrity/upgrade;
- Kafka broker/storage/VIP upgrade/failure behavior;
- package late-install, rollback/remediation and Flux reconciliation;
- fully offline create/scale/repair/node-replacement/upgrade;
- supported N-1 -> N lifecycle and interruption recovery.

No one may promote these capabilities based on this design document alone.

## Source change-boundary verification

A repository compare from starting commit `d62cd0cfeab977aebe0c8a3971efcb863b5251dd` through the documentation batch before this audit record showed only documentation/context/workstream files changed. No CloudStack Java/API/schema/KVM source, Vue runtime source, installer, workflow or production configuration was changed by the master-context task.

This audit record itself is also documentation-only.

## Next evidence gate

Implementation must start from Workstream E phase E0:

1. fetch exact current CAPI/CAPC/CAPRKE2/RKE2 releases/source;
2. pin a candidate compatibility tuple for CloudStack 4.22.1.1;
3. record issues/PRs/source constraints;
4. build the smallest offline CAPI/RKE2 vertical slice;
5. run CI and then real disposable-lab E2E/data-safety tests;
6. keep runtime status below `LIVE_VERIFIED` until those exact tests pass.
