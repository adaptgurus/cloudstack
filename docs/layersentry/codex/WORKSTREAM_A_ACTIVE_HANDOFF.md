# Workstream A — Active GUI / Self-Service Handoff

**Purpose:** durable continuation checkpoint for the LayerSentry GUI-only coding workstream.  
**Repository:** `adaptgurus/cloudstack`  
**Branch:** `layersentry/4.22.1.1-ui`  
**GUI code checkpoint before this handoff document:** `38e3ce550f0413d13745647768658e5e3cbc4dec`  
**Earlier GUI baseline for this continuation:** `8b8937757c89a062a9ea524994f38e83c7dbfc32`  
**Core/backend impact from this continuation:** **NO**

## Mandatory continuation rule

This is a **shared, concurrently moving branch**. A future chat/agent must:

1. fetch the current `layersentry/4.22.1.1-ui` HEAD first;
2. verify that the GUI commits listed below remain ancestors of current HEAD;
3. continue from current HEAD and **never reset the branch back to a handoff SHA**;
4. preserve all unrelated concurrent DR, Kubernetes, DBaaS, APaaS, release, security and installer commits;
5. read `/AGENTS.md`, `docs/layersentry/codex/WORKSTREAM_A_UI_SELF_SERVICE.md`, and this file before changing GUI-owned source.

## Scope lock for this handoff

This continuation is **LayerSentry GUI / self-service only**.

It owns presentation-layer work such as:

- branding and terminology;
- role/persona dashboards and navigation;
- KVM-first customer presentation;
- Quick Provision VM UX;
- GUI capability/provider gating;
- loading, empty, unavailable, error and partial-result presentation;
- accessibility/responsive presentation;
- UI-only API composition using existing CloudStack APIs.

It does **not** own or implement Kubernetes/RKE2 lifecycle, DBaaS, APaaS, Streaming/Kafka, DR controller logic, installer/release logic, CloudStack Java/backend schema, scheduler, agent or server-side authorization. Concurrent files for those workstreams may exist on this branch and must be preserved.

## GUI commits produced by this coding pass

### `e6e4a362179f7e89e3fdb3f46f353469716a901c`

`layersentry: complete quick provision planning helpers`

`ui/src/views/layersentry/quickProvision.js`

Added/finished:

- current / Department-Account / Project deployment-scope modeling;
- Admin/DomainAdmin ownership targeting helpers;
- scope validation;
- custom Compute Profile validation;
- root Storage Profile validation;
- new data-volume validation;
- detached existing-volume validation;
- native deploy payload construction for account/domain/project scope;
- custom CPU / CPU speed / memory details;
- SSH key-pair payload support;
- multiple data disks with deterministic device IDs;
- multi-network `iptonetworklist` payload construction;
- native Backup Offering assignment payload helper;
- preflight blocking issues for provider/API readiness.

### `9922324cb569ffbce74c2c2a5a78c91edd180ea4`

`layersentry: complete one-page KVM quick provision flow`

`ui/src/views/layersentry/QuickProvision.vue`

Finished the one-page VM flow with:

- ownership and Site section;
- privileged current / Department-Account / Project targeting without changing server-side RBAC;
- KVM-only Site and OS Image preflight;
- OS Image and Compute Profile selection;
- custom vCPU, CPU-speed and memory inputs when the selected Compute Profile is customized;
- optional SSH key-pair selection;
- root Storage Profile and root-size controls;
- zero or more new data volumes;
- detached existing data-volume selection and post-deploy attachment;
- VPC, primary Network Blueprint, additional networks and permitted private-IP override;
- resolved VLAN, CIDR, gateway, DNS and network-domain presentation;
- truthful HA request display based on Compute Profile data;
- real Backup Protection Plan selection only when capability policy and APIs permit it;
- no invented DR browser orchestration; DR remains gated until a real server-side contract/mapping exists;
- resolved-plan review and blocking preflight state;
- explicit async operation stages: Validate → Deploy VM → Finalize storage → Configure protection → Complete;
- native `queryAsyncJobResult` polling with job correlation;
- generated VM password presentation when CloudStack returns one;
- truthful unknown/pending state that warns against duplicate submission;
- post-deploy partial-completion semantics: a successfully created VM is never reported as a generic deployment failure merely because a later volume attachment or Backup Offering assignment failed;
- direct VM-detail action after a confirmed result;
- responsive/reduced-motion-aware presentation.

### `b63b09958947f0c83945ba14588e165522c90136`

`layersentry: require assign API for backup self service`

`ui/src/config/layersentryCapabilities.js`

Backup self-service now requires both:

- `listBackupOfferings`;
- `assignVirtualMachineToBackupOffering`;

in addition to LayerSentry feature-policy readiness. Read-only ability to list offerings can no longer make Backup self-service appear usable.

### `5b727993424047af4cbd4d76b04bb185f0ece7bf`

`layersentry: harden strict root storage planning`

`ui/src/views/layersentry/quickProvision.js`

A Compute Profile with disk-offering strictness can no longer emit a stale browser-side root Storage Profile override after the user switches profiles. The planning helper blocks contradictory state and omits the override from the native deploy payload.

### `38e3ce550f0413d13745647768658e5e3cbc4dec`

`layersentry: gate backup offering navigation by readiness`

`ui/src/config/layersentryNavigation.js`

The Backup Offering route is now hidden by the same provider/API readiness gate as Backup and Backup Schedule rather than appearing merely because an upstream route exists.

## Existing GUI foundation inherited by this continuation

Earlier Workstream A commits on the same branch already provide the broader LayerSentry GUI foundation, including:

- LayerSentry product profile and branding;
- KVM-focused customer presentation without deleting upstream non-KVM implementations;
- role-aware Platform Administrator, Department Administrator, User/Operator and Read-only dashboard behavior;
- task-focused navigation;
- Platform and self-service dashboards backed by existing CloudStack APIs;
- LayerSentry exception states;
- consistent action presentation/icons;
- KVM image/site provisioning guards;
- precise customer terminology such as Site, Infrastructure Group, Compute Profile, Storage Profile and OS Image;
- provider-gated Bucket/Backup presentation.

Key earlier checkpoints for this GUI line include:

- `c31fca81a786cd0429ec0a094589eea7edef7c7c` — precise customer terminology;
- `5739e23296e97f7dd2f45d7c6c655876710cf2fb` — GUI/provider scope separation;
- `8b8937757c89a062a9ea524994f38e83c7dbfc32` — provider gating correction.

## API boundary used by Quick Provision

The browser does not invent new CloudStack VM deployment fields.

Native CloudStack APIs used by this flow include, when authorized/available:

- `listZones`;
- `listDomains`;
- `listAccounts`;
- `listProjects`;
- `listTemplates`;
- `listServiceOfferings`;
- `listDiskOfferings`;
- `listSSHKeyPairs`;
- `listVolumes`;
- `listVPCs`;
- `listNetworks`;
- `listBackupOfferings`;
- `deployVirtualMachine`;
- `attachVolume`;
- `assignVirtualMachineToBackupOffering`;
- `queryAsyncJobResult`.

Account deployment uses `account + domainid`; project deployment uses `projectid`. Backup selection is a post-deploy assignment, not an invented `deployVirtualMachine` field.

## Truthfulness and safety invariants retained

- KVM is implicit in the LayerSentry customer VM path; no alternate hypervisor selector is introduced here.
- UI visibility never replaces CloudStack authorization.
- Provider/API/policy readiness is checked before optional self-service capability is presented.
- A click or submitted async job never becomes a false `Protected`, `HA`, `DR Ready` or `Complete` state.
- Post-deploy failure does not erase the fact that the VM may already exist.
- DR is not fabricated from browser intent.
- SAN/provider credentials and raw LUN handling never enter tenant UI code.
- Concurrent specialist-module files on the branch are outside this handoff and must not be deleted or rewritten by a future GUI-only continuation.

## Validation status for this coding pass

**Tests/build/browser validation were intentionally NOT RUN in this pass because the user explicitly requested code completion first without testing.**

Therefore this checkpoint is a **GUI code-completion handoff**, not a claim of formal `SOURCE_COMPLETE` or `LIVE_VERIFIED` status under the Workstream A acceptance contract.

Do not transfer older CI/browser results to these newer commits. The exact current artifact must be validated later when the user asks for testing.

A historical GUI-validation attempt before these commits had exposed an existing Node/OpenSSL build-toolchain incompatibility involving `--openssl-legacy-provider`; that historical result was not rechecked during this coding-only pass and must not be represented as the status of the current commit.

## Next-chat instruction

When asked to continue LayerSentry GUI work:

1. fetch current branch HEAD;
2. confirm the GUI commits in this file remain reachable from HEAD;
3. preserve any newer concurrent specialist-workstream commits;
4. continue only GUI/self-service presentation work unless the user explicitly changes scope;
5. do not run tests unless the user requests validation/testing;
6. do not edit `docs/layersentry/LAYERSENTRY_PROGRESS_LEDGER.md` from this workstream;
7. never claim formal source/live completion from this handoff alone.
