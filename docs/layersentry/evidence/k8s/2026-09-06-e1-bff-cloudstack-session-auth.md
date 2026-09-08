# E1 BFF CloudStack session authentication design

**Date:** 2026-09-06  
**Status:** `SOURCE_COMPLETE`; runtime and security validation `NOT_TESTED`  
**CloudStack target:** `4.22.1.1`  
**CloudStack core impact:** none

## Decision

The LayerSentry BFF authenticates browser requests by validating the existing
CloudStack login session against the exact configured `/client/api` endpoint.
It forwards only the HttpOnly `JSESSIONID` cookie and a session key which must
match both the HttpOnly `sessionkey` cookie and the
`X-LayerSentry-Session-Key` request header. The header value is read by the UI
from the session key returned by CloudStack login; it is not an independent
credential.

CloudStack `listApis` supplies the effective API capability set for the real
calling user. CloudStack `listProjects` supplies the active project IDs visible
to that same authenticated session. The composite-action authorizer requires
both exact project membership and the CloudStack capabilities corresponding
to create, status, scale or delete. Readable cookies and headers claiming a
role, user, account, domain or project are ignored.

Mutating BFF calls require an exact configured browser Origin. Redirects are
disabled, TLS is the default, payloads are bounded, and incomplete/ambiguous
permission or project inventories fail closed.

## Exact source validation

The decision was checked against the fetched CloudStack `4.22.1.1` source:

- `ApiServer.loginUser` stores `userid`, the account object and a random
  session key in the server-side HTTP session;
- `ApiServlet.invalidateHttpSessionIfNeeded` invokes
  `HttpUtils.validateSessionKey`; the default configuration is
  `CookieAndParameter`;
- the UI persists the login response session key and supplies it on each
  CloudStack API request;
- API Discovery `listApis` runs the configured `APIChecker` implementations
  for the current calling user and role;
- `listProjects` remains the CloudStack-authoritative project/RBAC query.

No new CloudStack API, Java class, database schema or RBAC semantic is needed.

## Advantages

- CloudStack remains the identity, role and project authority.
- Custom CloudStack roles are honored through effective API grants rather than
  fragile role-name comparisons.
- A forged UI `role`, `userid`, `account`, `domainid` or project header cannot
  grant a BFF action.
- The BFF's privileged controller credentials do not replace caller
  authorization.

## Disadvantages and alternatives

This design adds two bounded read-only CloudStack calls to initial request
authentication. A short-lived server-side capability cache may be added only
after logout/revocation behavior is tested; there is no cache in the initial
implementation.

Trusting the UI's readable cookies was rejected because they are caller
controlled. Adding a CloudStack Java session-introspection API was rejected
because supported session, discovery and project APIs already satisfy the
need. Issuing separate long-lived API keys to every browser was rejected due
to secret exposure and revocation complexity.

## Risks and mitigations

- **CSRF/session riding:** mutating requests require a configured exact Origin
  plus matching CloudStack session-key cookie/header.
- **stale permission:** every request revalidates current CloudStack grants.
- **partial inventory:** reported project count must equal the bounded returned
  page or authentication fails.
- **credential leakage:** only the two session cookies are reconstructed for
  upstream validation; neither is stored in saga state or error payloads.
- **central-controller privilege:** the authorizer checks caller project and
  effective capability before any operation is persisted.

## Tests performed

Local unit tests cover valid authentication, spoofed readable cookie
exclusion, exact Origin checks, missing/mismatched/duplicate session tokens,
upstream rejection, duplicate permissions, incomplete project inventory,
project tampering, capability denial, read-only access and safe BFF error
mapping. The full Workstream E Python suite passed locally with 62 tests.

## Rollback and production status

The new authenticator is opt-in; without explicit service wiring the BFF still
uses `DenyAllAuthenticator`. Removing the new module restores the prior
default-deny behavior without CloudStack runtime changes.

Real login/logout, timeout, custom-role, project-tampering, reverse-proxy,
Chrome/Firefox, TLS and Rocky Linux 9 tests remain `NOT_TESTED`. This is not
`CI_VERIFIED`, `LIVE_VERIFIED` or `PRODUCTION_CERTIFIED`.
