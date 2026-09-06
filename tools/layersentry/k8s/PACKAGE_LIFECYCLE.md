# Qualified package lifecycle

The authenticated BFF accepts package intent for an existing, ready, project-owned
CAPI cluster. Native central Flux remains the remote Helm lifecycle owner. This
adapter does not qualify OpenEverest, OpenBao, Harbor, Strimzi or any database
engine, and it never promotes release or stateful safety gates.

The protected runtime configuration may contain `packages` with `catalogFile`
and `catalogSha256`. Both identify the exact approved catalog bytes. The default
is `null`, which exposes an empty catalog and disables package mutations.
Optional `previousCatalogs` contains at most 16 objects with the same two fields;
retain these approved revisions until their existing releases have been removed.
Historical revisions permit existing lifecycle work, not new installation.

Routes beneath `/client/layersentry-k8s/v1/kubernetes`:

- `GET /packages?projectId=...`: approved current and historical profiles, their
  catalog digests and actual gate blockers. Catalog availability is not a live
  operator readiness claim.
- `POST /clusters/{name}/packages`: install a selected approved profile.
- `DELETE /clusters/{name}/packages`: uninstall a qualified stateless profile.
- `GET /clusters/{name}/packages`: observe one selected profile without mutation.
- `POST /operations/{id}/reconcile` with `{}`: explicitly observe an UNKNOWN
  accepted operation under its original mutation capability and project scope.

Package mutation JSON contains exactly `clusterName`, `namespace`, `projectId`,
`package`, `version` and `profile`, plus optional `catalogSha256`. Send the exact
catalog digest returned by discovery. The package GET uses the same fields as
query parameters except `clusterName`, which comes from the path. Mutations use
an `Idempotency-Key`; session authentication and CSRF protections are shared
with cluster operations. Request bodies never accept values overrides,
kubeconfigs, credentials or arbitrary charts. Browser retries recover the stored
receipt after fresh authorization, even if the target is no longer observable.

Before durable acceptance, the service verifies exact dependencies Ready and
rejects uninstall while any approved catalog's dependent release remains. One
transaction reserves the project/cluster for create, scale, delete or package
work; UNKNOWN keeps that reservation across restart. A single active worker is
required by the existing SQLite runtime contract. The accepted operation binds
the complete catalog revision and Cluster UID. Remote resources bind the full
approved profile, audited Flux tuple and Cluster incarnation, allowing unrelated
catalog additions without changing an existing release's ownership.

Only native create and UID/resourceVersion-fenced delete are used. Reconciliation
reads immutable ownership before each mutation. Added execution overrides or
values fail exact spec comparison. The only extra API-defaulted field accepted
for these resources is OCIRepository `provider=generic`, audited against the
pinned Flux 2.9.5 CRDs. Helm finalization must complete before its source is
removed; managed package resources block Cluster deletion so its workload
connectivity and CAPI credentials remain available. No finalizer, PVC or
application data is deleted by this path. Stateful uninstall remains closed
until the separate retention/backup workflow is qualified.

Source tests cover authorization, native ambiguity and restart, concurrent
acceptance, dependency admission, historical lifecycle, changed Cluster UID,
additive spec drift and cluster deletion interlocks. Native API/controller,
data-integrity and browser acceptance remain separate live gates.
