# LayerSentry V1 — Secure Engineering Policy

## Purpose

Stable secure-development policy for LayerSentry source, automation, UI, release tooling and LayerSentry-specific services.

This file does **not** contain current vulnerability status, live configuration, CVE results or release certification. Current execution/evidence belongs in `LAYERSENTRY_PROGRESS_LEDGER.md` and release artifacts.

The canonical architecture/evidence rules in `LAYERSENTRY_SUPER_MASTER_CONTEXT.md` remain authoritative. This policy adds implementation-level security requirements without duplicating product status.

---

## 1. Threat-model rule

Before adding or materially changing a privileged trust boundary, document a focused threat model.

Triggers include:

- authentication/session behavior;
- authorization/RBAC wrappers;
- installer/updater/root-level automation;
- artifact signing/trust verification;
- support/remote-access mechanisms;
- file upload/import/archive extraction;
- proxy/URL-fetch/integration endpoints;
- DR/fencing/backup/delete/restore operations;
- licensing/entitlement services;
- new LayerSentry server-side services/controllers;
- storage/network/security policy mutation.

At minimum identify:

- assets/secrets at risk;
- actors/trust boundaries;
- entry points/data flows;
- abuse/failure cases;
- authorization requirements;
- confidentiality/integrity/availability impact;
- mitigations and residual risk;
- security tests/evidence required.

Do not produce a large theoretical threat model for trivial presentation-only changes; focus effort on privileged boundaries.

---

## 2. Untrusted-input rule

Treat all data outside the immediate trusted process/config boundary as untrusted until validated, including:

- browser/API fields;
- query/path/header values;
- CloudStack API responses when reused in commands/paths/HTML;
- VM/user-data/template metadata;
- uploaded files/archives;
- repository issue/PR/comment text;
- support bundle content/log lines;
- DNS/URLs/provider endpoints;
- environment variables and inventory supplied by operators;
- filenames/paths returned by external tools;
- webhook/external integration payloads.

Validate type, format, length, allowed values and state transition at the narrowest useful boundary. Prefer explicit schemas/allowlists over ambiguous coercion.

Do not use validation only in the browser as a security boundary.

---

## 3. Authorization and confused-deputy prevention

CloudStack server-side RBAC remains authoritative for CloudStack operations. LayerSentry services/controllers must also authorize any additional privileged action they introduce.

Required principles:

- authenticate caller/session before privileged operation;
- authorize the exact action on the exact tenant/resource, not merely the menu/route;
- never trust a resource ID/domain/account supplied by the client without authorization lookup;
- prevent cross-tenant object reference abuse;
- preserve account/domain/project boundaries;
- do not let a low-privilege LayerSentry caller cause a high-privilege service to perform an operation outside the caller's allowed scope;
- test direct API invocation and object-ID tampering, not only normal UI navigation;
- deny by default when authorization context is missing/ambiguous.

A LayerSentry service account should have the minimum CloudStack/system privileges required for its purpose.

---

## 4. Browser/UI security

For LayerSentry browser code:

- avoid raw HTML rendering (`v-html` or equivalent) for untrusted data; if unavoidable, use a reviewed sanitizer and tests;
- use framework escaping by default;
- validate/sanitize dynamic URLs and navigation targets; prevent `javascript:`/unsafe schemes and open-redirect behavior;
- do not place secrets/private keys/reusable infrastructure credentials in browser bundles/local storage;
- do not rely on minification/obfuscation for security;
- preserve server-side authorization for every privileged action;
- do not log sensitive API responses to browser console in production;
- review file upload/download names/content disposition where relevant;
- avoid introducing DOM XSS through unsafe string-to-HTML/template patterns.

Production portal security should validate, for the deployed architecture:

- HTTPS/TLS endpoint behavior and certificate lifecycle;
- secure cookie/session flags where applicable;
- CSRF protections for state-changing browser requests according to CloudStack/session semantics;
- CORS behavior when cross-origin access exists;
- appropriate security headers such as CSP/frame-ancestors/X-Content-Type-Options/referrer policy where compatible with the product architecture;
- clickjacking/frame embedding requirements;
- cache behavior for authenticated/sensitive responses.

Do not claim a header/control is enabled until measured on the served target.

---

## 5. Command/process execution

Never build shell commands by interpolating untrusted values into a shell string when a direct argv/subprocess API is available.

Required controls:

- prefer argument arrays and `shell=false` behavior;
- validate executable/path and arguments;
- set explicit timeouts;
- bound stdout/stderr capture where necessary;
- check exit status and expected side effects;
- do not silently continue after a privileged command fails;
- redact secrets from command logging;
- use explicit environment variables rather than inheriting an uncontrolled environment for privileged processes;
- avoid executing scripts/binaries from world-writable/unverified locations.

Shell scripts must quote variable expansions appropriately and avoid `eval` on untrusted content.

---

## 6. Filesystem, archive and temporary-file safety

Protect against path traversal, symlink attacks and unsafe replacement.

- canonicalize/validate paths against an intended root;
- do not trust archive entry paths (`../`, absolute paths, device files, links) during extraction;
- use secure temporary creation with restrictive permissions;
- avoid predictable temp names for privileged data;
- validate ownership/mode before consuming sensitive files;
- use atomic write/rename patterns where appropriate;
- fsync/transactional behavior where data integrity requires it;
- do not follow attacker-controlled symlinks for privileged writes;
- verify sufficient disk space before large artifact/backup operations;
- clean temporary sensitive material reliably without claiming impossible forensic erasure.

---

## 7. Network/URL/SSRF controls

Any LayerSentry component that connects to a user/config-supplied URL or host must consider SSRF and trust-boundary risk.

- validate scheme/host/port according to the integration's allowlist/policy;
- do not allow arbitrary access to loopback/link-local/cloud metadata/management networks unless explicitly required;
- handle DNS resolution/rebinding concerns for privileged fetchers where material;
- set connect/read/overall timeouts;
- bound redirects and validate redirect destinations;
- verify TLS certificates by default;
- do not disable TLS verification as a production workaround;
- avoid leaking credentials through redirects, URLs or logs;
- use egress allowlists/proxy policy where the appliance architecture requires controlled Internet access.

---

## 8. Database/data parsing safety

LayerSentry-specific persistence must use parameterized queries/ORM binding; never concatenate untrusted SQL.

Avoid undocumented direct writes to CloudStack database tables as an integration mechanism.

For parsers/deserializers:

- prefer safe non-executable formats;
- reject unknown/unsupported schema versions as appropriate;
- bound input size/nesting to prevent resource exhaustion;
- do not deserialize arbitrary executable object graphs from untrusted sources;
- fuzz/test parsers that handle complex untrusted formats where practical.

---

## 9. Cryptography and TLS

Do not invent cryptographic algorithms or proprietary signing formats when standard well-reviewed primitives/formats meet the requirement.

- use established libraries;
- use CSPRNG for security-sensitive tokens/keys;
- keep private keys outside source/browser/customer-readable configuration;
- define key purpose, owner, storage, rotation, revocation and expiry behavior;
- validate signatures before consuming trusted metadata/artifacts;
- prevent algorithm/key confusion/downgrade where relevant;
- validate certificate chains/hostnames for TLS;
- define certificate renewal/failure behavior for product endpoints;
- do not log key material/session tokens.

Encryption-at-rest claims must name the actual layer/provider/mechanism and be tested; do not label data encrypted merely because TLS protects transit.

---

## 10. Secrets lifecycle

Secrets must be:

- generated/provisioned through approved mechanisms;
- least-privilege and scoped;
- excluded from Git/browser bundles/artifacts/logs/support bundles;
- rotated on exposure or according to policy;
- revocable where practical;
- removed from memory/files when no longer required using normal secure lifecycle practices.

No shared support backdoor credentials.

Bootstrap/default credentials, if any temporary bootstrap mechanism exists, must be unique/generated, short-lived or forced to rotate and never ship as a universal vendor default.

---

## 11. CI/CD trust boundaries

Build and signing infrastructure is a privileged security boundary.

- untrusted pull-request/fork code must not receive production signing/release secrets;
- release signing/publishing occurs only from an approved trusted ref/workflow after required review/checks;
- grant CI tokens minimum repository/cloud permissions;
- pin third-party CI actions/tools to controlled versions/digests where practical and review updates;
- separate build/test permissions from production promotion/signing where feasible;
- retain audit logs for release-signing/promotion events;
- protect artifact registries against overwrite of immutable versions;
- do not execute unreviewed downloaded scripts with release credentials;
- validate artifact identity again at promotion/deployment, not only at build time.

A successful PR build does not authorize that artifact for production release.

---

## 12. Dependency and build-script risk

Dependency lockfiles reduce drift but do not make dependencies trusted.

- review dependency additions/major updates;
- scan dependencies/licenses according to release policy;
- avoid unnecessary dependencies for trivial functionality;
- recognize that package-manager lifecycle scripts can execute code in CI/build environments;
- use isolated builders with least secrets/permissions;
- do not install dependencies dynamically on production appliances;
- record accepted vulnerability exceptions with owner/reason/expiry and re-evaluation trigger.

Never lower a dependency/security gate globally merely to get one release through CI.

---

## 13. Logging, privacy and data minimization

Logs/evidence should support incident diagnosis without becoming a second secret/customer-data store.

- never log passwords, private keys, authorization headers, session tokens or unredacted secret configuration;
- minimize customer payload/content in logs unless explicitly needed;
- prefer IDs, hashes, sizes and structured state over full sensitive content;
- sanitize support bundles by default;
- define retention/access controls for release/security/audit evidence;
- document when customer-identifying/personal data is collected by product telemetry/support tooling;
- do not enable external telemetry by surprise in an on-prem product;
- avoid sending infrastructure/customer data to third parties unless deliberately configured and documented.

Do not claim compliance with a privacy/security standard without an actual assessed control set and evidence.

---

## 14. Availability, retries and resource-exhaustion safety

Production code must consider failure as a normal state.

- set finite network/process timeouts;
- use bounded retries with backoff/jitter where appropriate;
- classify retryable vs permanent errors;
- make mutating retries idempotent/deduplicated;
- bound queues/concurrency/body/file sizes;
- avoid unbounded memory/log growth;
- handle partial disk/full filesystem conditions safely;
- rate-limit or otherwise protect expensive privileged APIs where the architecture needs it;
- use circuit-breaking/backpressure where an external dependency can cascade failure;
- preserve correlation/job IDs across asynchronous operations.

A timeout of a mutating operation is `UNKNOWN` until the authoritative job/resource state is checked.

---

## 15. Error handling

- fail closed for authentication/authorization/integrity/policy checks;
- return actionable errors without exposing sensitive internals;
- preserve the original/root cause in protected diagnostic logs;
- do not catch-and-ignore exceptions that leave unclear state;
- make partial success explicit;
- clean up or checkpoint partial resources according to the operation's transaction/retry design;
- avoid user-facing `success` before asynchronous jobs reach confirmed terminal success.

---

## 16. Secure-review and test gates

For security-relevant changes, use the applicable combination of:

- code review focused on trust boundaries;
- lint/static type checks;
- SAST rules where useful;
- dependency/SCA and secret scanning;
- unit tests;
- negative authorization tests;
- integration/API contract tests;
- tamper/signature tests;
- parser/file/archive fuzz/property tests when exposure warrants it;
- browser XSS/CSRF/security-header validation;
- failure/timeout/retry/idempotency tests;
- privilege-boundary tests;
- live/staging tests for appliance/network/security controls.

Do not substitute scanner output for design review or live behavior testing.

Release-blocking severity/exception criteria should be defined in the release process; unresolved accepted risks require an owner, rationale, compensating control where applicable and review/expiry point.

---

## 17. Source and release governance

Before stable production releases, source governance should include appropriate controls such as:

- protected integration/stable release branches;
- required CI/status checks;
- review requirements for release/security-sensitive changes;
- restricted force-push/deletion;
- least-privilege release/promotion permissions;
- immutable release tags/artifacts;
- auditable release approval/promotion.

Commit/tag signing may be used where it adds verified provenance, but do not equate an unsigned development commit with an insecure product artifact or a signed commit with sufficient review.

Production artifact signing/trust verification remains the primary release-integrity control defined by LayerSentry release policy.

---

## 18. Incident and security-response readiness

Before a stable commercial release, define:

- how customers report security issues;
- severity/triage ownership;
- security advisory/patch release process;
- signing-key compromise/revocation procedure;
- credential-leak response;
- vulnerable dependency response;
- support-bundle/evidence collection workflow;
- emergency release/rollback procedure;
- customer notification/update guidance appropriate to the issue.

Do not leave emergency signing/publishing access as an undocumented shared credential.

---

## 19. Production documentation gate

A production-certified release should have customer/support documentation appropriate to enabled features, including:

- release notes and known limitations;
- supported hardware/software matrix;
- installation/preflight guidance;
- network/port requirements;
- backup/recovery guidance;
- upgrade/rollback/recovery procedure;
- security-hardening/identity/certificate guidance;
- operational monitoring/support-bundle guidance;
- DR limitations and tested scope when DR is certified;
- third-party/open-source notices and licensing obligations.

Documentation must match the exact release rather than an unversioned moving design.

---

## 20. Security claim rule

Never claim:

- unhackable;
- impossible to penetrate;
- impossible to reverse engineer;
- zero-day proof;
- immutable;
- encrypted;
- compliant/certified to a standard;
- production secure;

without defining the exact technical/control scope and having corresponding evidence.

Use narrow factual language such as `TLS verified for management endpoint`, `artifact signature verification passed`, `RBAC negative tests passed for listed roles`, or `SELinux enforcing passed the release test matrix`.
