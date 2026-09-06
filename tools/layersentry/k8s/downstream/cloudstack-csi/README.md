# CloudStack CSI downstream build

Apply the overlay to a checkout of the manifest's exact upstream commit using `../materialize.py`. Stage the runtime package closure before invoking BuildKit:

```bash
python3 tools/layersentry/k8s/downstream/materialize.py \
  --source /path/to/cloudstack-csi-driver \
  --manifest tools/layersentry/k8s/downstream/cloudstack-csi/manifest.json --apply
python3 tools/layersentry/k8s/downstream/cloudstack-csi/prepare_apk.py \
  --architecture amd64 --output /path/to/cloudstack-csi-driver/.layersentry-apk
```

The output must be a fresh directory. For disconnected builds, supply `--cache /path/to/imported-closure`, with the same `amd64/driver/*.apk` and `amd64/syncer/*.apk` layout. Cache mode never falls back to networking. All imported bytes are verified again. For arm64 use a separate source/build context and `--architecture arm64`. Unsupported architectures fail closed.

From the patched upstream checkout, build each exact target with a BuildKit-capable builder:

```bash
docker buildx build --platform linux/amd64 \
  --file cmd/cloudstack-csi-driver/Dockerfile \
  --tag layersentry-cloudstack-csi:qualification --load .
docker buildx build --platform linux/amd64 \
  --file cmd/cloudstack-csi-sc-syncer/Dockerfile \
  --tag layersentry-cloudstack-csi-sc-syncer:qualification --load .
```

These local tags are build conveniences, never release identities. Record registry digests, SBOM, scan/signature evidence and exact build provenance before release promotion. Docker build base arguments must retain the manifest's approved digests. Go modules remain checked by the upstream go.sum; fully offline Go build input preparation is a separate release-bundle responsibility.

Both Dockerfiles verify a patch-embedded hash of `SHA256SUMS`, verify every package, reject extra APKs, and execute signature-checked `apk add --no-network` in a BuildKit step with networking disabled. Packages are bound read-only into the step, not copied into the resulting image. Both architectures retain upstream Alpine trust keys; no `--allow-untrusted` escape exists.

The driver closure adds `xfsprogs-extra`: Alpine's base `xfsprogs` lacks `xfs_growfs`, required by CSI filesystem expansion. Its dependency closure includes Python used by other packaged XFS tools, increasing installed runtime packages from approximately 12 MiB to 52 MiB. This is an explicit functionality-versus-size choice; stripping individual files or lying to the package manager is not used. The syncer remains at the minimal CA closure, approximately 7 MiB installed.

Regenerate a lock only as an explicit reviewed release change: use each pinned base architecture's trusted apk keys, resolve/fetch the full dependency closure, record exact size/SHA-256/official source URL, regenerate checksum-list hashes in the overlay, update patch/lock manifest digests and rerun negative/offline installation tests. Upstream URLs can disappear; mirror these exact bytes into the release artifact store for long-term rebuilds. Do not substitute newer package versions automatically.

The dated evidence is `docs/layersentry/evidence/k8s/2026-09-06-csi-apk-closure.md`. Package closure tests are preliminary validation; no image digest or live CSI certification is implied.

## Reuse the retained build before rebuilding

`artifact-lock.json` records the existing linux/amd64 driver and syncer OCI archives, each complete OCI index, runtime manifest/config, unsigned SBOM/provenance and exact source identities. Both this manifest and the release candidate bind its bytes by SHA-256. It is build-artifact metadata, not an installable image reference or a live CSI qualification. The lock retains the original GitHub artifact identity and expiration; copy exact bytes into the approved long-term artifact store before expiration rather than rebuilding merely to recover a tag.

After downloading and validating the GitHub artifact against its recorded identity, check each retained archive and its original smoke-image inspection receipt, for example:

```bash
python3 tools/layersentry/k8s/downstream/cloudstack-csi/verify_oci.py \
  --archive /path/to/evidence/cloudstack-csi-driver.oci.tar \
  --inspect /path/to/evidence/cloudstack-csi-driver-inspect.json \
  --component cloudstack-csi-driver \
  --source-commit d40c54acb8a18b71475b154f14dd631460c94f89 \
  --artifact-lock tools/layersentry/k8s/downstream/cloudstack-csi/artifact-lock.json \
  --output /path/to/verified-driver.json
```

Repeat for `cloudstack-csi-sc-syncer` with its matching archive/inspection. The optional artifact-lock check requires the downstream manifest's approved lock hash and rejects substituted archive/index/runtime/config/platform/attestation identities. The provenance check examines the actual SLSA predicate's build arguments, source revision and base/scanner dependency digests; metadata labels alone are insufficient. Unsigned provenance consistency is not proof of a trusted signing identity.

Publication must preserve the OCI index and all referenced blobs, including the attestation manifest, rather than copying only the runnable platform manifest. Independently read the destination registry and verify the exact index and runtime digests before recording its immutable pull reference. No registry reference is inferred from the archive's local `qualification` annotation. `image` remains null until publication is evidenced; arm64 and every live/project/resize/data-safety gate remain unqualified.

The exact upstream chart at `a84477e922d62b82387ab55134fafc9c0b5aaf64` composes `repository:tag` for driver, syncer and five storage sidecars. It does not yet provide the required LayerSentry immutable image set by itself. Future installation needs a reviewed chart/image-reference overlay, pinned sidecar bytes and tested compatibility, approved private-registry content, exact project credentials and namespace/RBAC/StorageClass ownership. `controller/components.py` currently carries CSI image readiness metadata but no workload installer consumes it. These are separate installer/package integration tasks; the retained image build does not fulfill them. See `docs/layersentry/evidence/k8s/2026-09-07-csi-artifact-binding.md`.
