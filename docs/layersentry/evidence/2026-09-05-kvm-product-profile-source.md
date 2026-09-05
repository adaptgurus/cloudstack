# LayerSentry KVM product-profile source evidence

**Date:** 2026-09-05

**Workstream:** A — UI / Self-Service

**Risk:** R1 source-only

**Status:** SOURCE_COMPLETE after the recorded checks pass; runtime remains NOT_TESTED

## Current approach and decision

CloudStack's UI previously consumed every value returned by `listHypervisors` independently in each provisioning workflow. That preserves upstream flexibility, but it exposes non-KVM choices in the LayerSentry V1 customer experience.

The selected approach adds the explicit `layersentry-kvm` public UI product profile and one shared presentation-layer filter. The VM, native CKS, Compute Cluster, Site wizard and primary-storage creation surfaces use the filter. CloudStack's APIs, RBAC, database, scheduler, KVM agent, other hypervisor implementations and persisted resource model are unchanged.

Advantages:

- one explicit, testable product-profile switch;
- KVM-only choices in the main provisioning paths;
- upstream behavior remains the fail-safe default when the profile is absent or different;
- an empty API result remains empty rather than inventing KVM availability.

Disadvantages and risks:

- this first batch does not yet restructure the complete role-based navigation;
- support/detail pages may still display the actual hypervisor of existing records;
- a configured LayerSentry environment with no KVM capability presents no choice and requires an appropriate UI empty/error state in a later batch.

Alternatives reviewed:

1. Delete or globally alter upstream hypervisor support. Rejected because it changes CloudStack core/product capability and raises upgrade risk.
2. Hard-code KVM separately in every form. Rejected because behavior would drift and the absence of KVM could be hidden.
3. Filter only server responses. Rejected because it requires backend/API changes for a presentation requirement.

## Implementation impact

The profile is configured in `ui/public/config.json`. `ui/src/config/productProfile.js` supplies pure detection/filter functions used only by UI provisioning selectors. The filter accepts object and string option formats because existing CloudStack UI forms use both.

## Validation and edge cases

Planned/source checks:

- unit coverage for explicit-profile detection, object choices, string choices, upstream-default behavior and missing responses;
- JSON parse validation for `config.json`;
- `git diff --check`;
- UI lint/unit execution when the Node/npm toolchain is available.

No runtime was mutated. Rocky Linux 9 served-UI and Chrome/Firefox workflow validation remain required before `LIVE_VERIFIED`.

## Rollback and continuity

Reverting the coherent source commit removes the profile and restores the prior unfiltered UI choices. No data or backend rollback is required. This implements an already documented product relationship, so no stable knowledge-graph or Super Master Context change is required. The integration lead owns progress-ledger updates.
