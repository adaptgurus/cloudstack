# Codex Workstream B — Release / Installer / Build

## Mission

Make LayerSentry installation, release, rollback, and future upgrades deterministic, supportable, and low-risk. The customer should install signed/versioned LayerSentry artifacts; production management nodes must not compile the Vue UI.

## Startup

Read `/AGENTS.md`, `docs/layersentry/CODEX_MASTER_CONTEXT.md`, and all mandatory documents. Fetch the actual integration HEAD and create/use an isolated branch/worktree such as `codex/layersentry-release-installer`.

## File ownership

Primary ownership:

- `install-layersentry*.sh`
- build/release scripts added under a LayerSentry-specific path
- `ui/vue.config.js` and build-only production settings
- release manifest/SBOM/checksum/signature tooling
- installer/resume/rollback logic
- CI configuration in this repository if introduced for product artifacts

Avoid dashboard/wizard implementation and avoid CloudStack Java/backend changes.

## Required outcomes

1. Move production UI compilation off the CloudStack management VM.
2. Define a reproducible builder with exact/pinned Node/npm/toolchain versions suitable for the CloudStack 4.22 UI.
3. Build one immutable LayerSentry UI artifact (archive or package) from an exact source commit.
4. Disable production source maps by default; support builds may enable them explicitly.
5. Produce digest metadata and a versioned release manifest.
6. Add a signing/verification design; never commit private signing keys.
7. Installer verifies exact artifact provenance/digest/signature before deployment.
8. Maintain fresh/resume parity and idempotent/retry-safe stages.
9. Add explicit backup/atomic deployment/rollback behavior for the served UI.
10. Preserve `/WEB-INF`, `/META-INF`, runtime config, and CloudStack backend files.
11. Reduce/eliminate production-side Node/npm/compiler dependencies.
12. Prepare an SBOM/support-bundle path for production releases.
13. Preserve future CloudStack upgradeability and keep the upstream delta minimal.

## Current source facts

- DBaaS/APaaS placeholders are already removed and live-verified. Do not reintroduce their old checks.
- Current main/resume/served-repair pins are aligned for the cleaned V1 UI, but the existing process still contains legacy production-side npm build behavior.
- Current target CloudStack is 4.22.1.1; Rocky Linux 9; Java 17; product DB compatibility baseline MySQL 8.4/equivalent.

## Upgrade requirements

Respect `LAYERSENTRY_UPGRADE_AND_IP_PROTECTION.md`:

- no unsupported automatic downgrade promises after DB schema migration;
- versioned release manifest for every release;
- pre-upgrade backups/checkpoints;
- CloudStack schema-aware management-server sequencing;
- supported N-1 -> N tests before certification;
- rolling KVM host upgrades only after capacity/maintenance validation;
- post-upgrade functional regression.

## Security/IP requirements

- No production source maps by default.
- No secrets, signing keys, proprietary decision logic, or licensing secrets in browser JS.
- Keep proprietary LayerSentry orchestration server-side when practical.
- Do not claim reverse engineering can be made impossible.
- Signed artifacts are integrity controls, not obscurity.

## Testing

At minimum validate:

- deterministic build from clean checkout;
- repeated build/provenance behavior;
- artifact digest verification;
- installer syntax/static checks;
- fresh/resume idempotency at the level available in the test environment;
- atomic UI deployment/rollback behavior;
- source maps absent from production artifact;
- DBaaS/APaaS still absent;
- LayerSentry branding/config/terminology still present.

Do not run destructive CloudStack upgrade or package mutation on the live `sen` VM unless the task explicitly authorizes it and a durable checkpoint exists.

## Handoff

Report exact branch/base/final commit, artifact/build design, changed files, tests run/not run, runtime mutation, rollback behavior, security assumptions, and dependencies on Workstream A/C/D. Do not edit the shared progress ledger unless explicitly assigned.
