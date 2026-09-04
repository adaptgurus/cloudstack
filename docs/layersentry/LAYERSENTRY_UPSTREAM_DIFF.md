# LayerSentry V1 — Upstream Delta Register

## Baseline

Upstream validation base:

`Apache CloudStack 4.22.1.1`

Base commit:

`71af23d73741cfeae854d2f1a6d36324307c32c4`

LayerSentry branch:

`layersentry/4.22.1.1-ui`

This register exists to keep future upstream upgrades/rebases predictable. Always regenerate the actual comparison against the current branch HEAD; counts in this file are historical snapshots, not permanent truth.

## Current architectural observation

At the snapshot used to create this register, the LayerSentry branch delta is confined to:

- LayerSentry documentation;
- LayerSentry installation/recovery scripts;
- UI branding/configuration/assets;
- UI header/footer/theme/terminology/navigation/onboarding presentation.

No CloudStack Java backend/API/database-schema/KVM-agent source file appears in the current branch delta against the immutable 4.22.1.1 base.

This is intentional and must be preserved whenever possible.

## Modified upstream UI files

### `ui/public/config.json`

Purpose: LayerSentry customer branding, theme lock, API-doc/version-notification visibility and UI configuration.

Risk: low to medium. Re-audit new upstream config keys on every upgrade; never replace a newer upstream config wholesale with an old LayerSentry copy.

Tests: branding/runtime config, login, route/menu visibility, browser refresh/cache behavior.

### `ui/src/components/header/Logo.vue`

Purpose: LayerSentry customer logo/title presentation.

Risk: low. Rebase onto any upstream header/layout changes.

### `ui/src/components/page/GlobalFooter.vue`

Purpose: customer-facing LayerSentry footer while preserving legal notices in source/distribution.

Risk: low to medium. Check new upstream footer functionality before reapplying.

### `ui/src/locales/index.js`

Purpose: centralized customer-facing terminology translation while preserving backend API/resource names.

Risk: medium. Global terminology overrides can be context-sensitive; every upgrade requires wrong-label regression review.

### `ui/src/main.js`

Purpose: LayerSentry runtime/config integration.

Risk: medium because application bootstrap can change upstream. Keep delta minimal.

### `ui/src/utils/guiTheme.js`

Purpose: prevent stale/upstream GUI-theme data from overwriting locked LayerSentry customer branding.

Risk: medium. Re-audit upstream theme behavior on every version.

### `ui/src/views/dashboard/OnboardingDashboard.vue`

Purpose: LayerSentry first-run/onboarding customer experience.

Risk: medium. Prefer wrapper/new LayerSentry component if future edits become large.

## LayerSentry-only UI additions

- `ui/public/assets/layersentry-icon.svg`
- `ui/public/assets/layersentry-logo.svg`
- `ui/src/style/layersentry-navigation.less`
- `ui/src/style/layersentry.less`

These are preferred upgrade-friendly deltas because they are product-specific additions rather than invasive edits to upstream logic.

## LayerSentry-only installer/documentation additions

Current branch contains LayerSentry-specific Rocky installers/recovery scripts and project documentation. These do not alter CloudStack backend source, but they must be kept version-pinned and tested independently for each target CloudStack release.

Long-term target: replace production-side UI compilation and ad-hoc script patching with versioned signed CI-built release artifacts and a modular bootstrap/update controller.

## Removed obsolete LayerSentry-only placeholders

The V1 DBaaS/APaaS placeholder route files and LayerSentry ServiceCatalog placeholder were removed in UI commit:

`9ad724eb76843d40d6a883c0a0ab47a75ceed449`

The exact delta from the audited pre-removal point `44b93e1bf6bc742c1c1a0c66e6319d25a6c47dda` is limited to:

- four route/import deletions from `ui/src/config/router.js`;
- deletion of `ui/src/config/section/dbaas.js`;
- deletion of `ui/src/config/section/apaas.js`;
- deletion of `ui/src/views/layersentry/ServiceCatalog.vue`.

No CloudStack backend capability was removed.

## Upgrade/rebase procedure

For each new CloudStack target:

1. create an immutable upstream target base ref;
2. generate base-vs-LayerSentry changed-file report;
3. reclassify every delta in this register;
4. review upstream changes to every modified upstream file;
5. port the smallest LayerSentry behavior, not the old whole file;
6. drop LayerSentry changes that upstream has made unnecessary;
7. run UI build/static/role/terminology tests;
8. run fresh install and supported N-1 -> N upgrade tests;
9. run live smoke/HA/backup/DR tests appropriate to certified features;
10. update this register with the exact new release commit and evidence.

## Fork-debt guard

Any future change to CloudStack Java/backend/database/KVM-agent source requires an explicit architecture-review record explaining why a supported UI/config/API/external-service solution cannot achieve the requirement.

The default decision remains: **do not modify CloudStack core**.
