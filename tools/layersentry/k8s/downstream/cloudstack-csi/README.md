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
