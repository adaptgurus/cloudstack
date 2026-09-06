# CloudStack CSI immutable runtime package closure

Status: `PARTIAL`. Scope: CloudStack CSI 3.0.2 downstream build only; no CloudStack core or runtime mutation.

## Research and design decision

The exact upstream source `a84477e922d62b82387ab55134fafc9c0b5aaf64` installs CA certificates, ext filesystem tools, XFS tools, blkid, mount, umount and udev through an unversioned `apk add`. The existing LayerSentry overlay pins both OCI bases but leaves this repository resolution moving. Alpine's [official package handbook](https://docs.alpinelinux.org/user-handbook/0.1a/Working/apk.html) confirms that repository indexes resolve available package versions and virtual providers. This is a build supply-chain concern, so CloudStack API/plugin/XaaS changes are not applicable. The upstream Dockerfiles were rechecked at the exact source; the product's CSI project-scope and expansion qualifications remain separate gates.

Retain Alpine and all upstream runtime utilities. A distroless or scratch replacement would require separately proving filesystem executables, dynamic libraries and trust roots; a snapshot mirror alone would still require content verification. Select a checked-in per-architecture, per-binary complete package closure with SHA-256 and size, downloaded before build and installed with networking disabled. Keep Alpine package signature verification using keys in the digest-pinned base. Pin the checksum list inside the downstream patch as well as the lock so changing supplied files and their checksum list cannot silently change the build.

The pinned OCI index resolves Alpine 3.21.7: amd64 manifest `sha256:f27cad9117495d32d067133afff942cb2dc745dfe9163e949f6bfe8a6a245339`, layer `sha256:897d797d2723cf0e318402f4d6f37d51b011517e5cf09246b22155f0fa90dc81`; arm64 manifest `sha256:1832327faf048390adc33852575d37c7ba155e064a339e78b9bd81983a8c7a00`, layer `sha256:2dd7199cff98a7400e801cbfad6de906972a4e3dd0a749d4c1b80f5a1e3e4108`. Registry response bodies and layers were checked against these digests before use. The official base's own apk-tools 2.14.6 resolved the closure using signature-checked repositories. Cross-architecture resolution uses each architecture's keys from that exact base, without allowing untrusted signatures.

Updates require a reviewed lock and overlay digest change. Missing historical Alpine files fail closed; release mirroring must retain the exact bytes for long-term rebuilds. No package version fallback or automatic lock refresh occurs during build. An imported local closure supports disconnected build preparation. Go dependencies retain upstream go.sum verification; this change does not claim byte-identical complete OCI rebuilds, an SBOM, vulnerability clearance, signing or production certification.

Rollback is a source/manifest revert and rebuilding the prior qualified artifact; there is no live rollback action in this task. Required next gates are exact OCI builds, registry publication/digests, SBOM/scanning/signing, then Rocky Linux 9 CSI project/resize and destructive PVC-survival qualification. Keep all corresponding release booleans false until evidenced.

## Implemented and verified

Both target architectures have 43 driver packages and five syncer packages with exact size/SHA-256/source URLs. The checked-in overlay binds the corresponding checksum-list hashes, rejects unknown architectures and extra APKs, and installs through a read-only BuildKit mount with `--network=none` and `apk --no-network`. The downloader supports a strictly offline imported closure, rejects redirects/invalid URLs/path traversal/duplicate lock keys, bounds download size/time, checks digests and publishes only a complete staging directory. It does not execute downloaded content.

The first offline runtime proof exposed an existing upstream gap: `xfsprogs` alone omits `xfs_growfs`, although CSI `pkg/mount/mount.go` invokes Kubernetes mount-utils filesystem expansion. Added `xfsprogs-extra` and its complete dependencies. Alpine's exact package index lists `cmd:xfs_growfs` under that package. The additional Python dependency expands installed driver packages to 52 MiB; the five-package CA syncer closure stays at 7 MiB. This preserves package ownership/signature checks and supports the required XFS operation rather than silently dropping expansion support.

Preliminary local verification passed:

- seven package-lock/downloader tests, covering changed URL/path/size/digest, duplicate keys, manifest/patch/lock digest bindings, truncated/oversize/corrupt payloads, missing offline cache without network fallback, symlink input, redirects, atomic staging and patch-to-lock binding;
- four existing component-release tests; all image/live readiness gates remain false;
- verified import of both architecture closures and fresh HTTPS download of every amd64 package using the new downloader;
- amd64 driver and syncer installation from clean exact-base root filesystems under `unshare -Urn` (new user and network namespaces), with no repository network access and Alpine signatures enforced;
- real commands found: mkfs.ext2/ext3/ext4, resize2fs, mkfs.xfs, xfs_growfs, blkid, mount, umount, udevadm; CA bundle nonempty; xfs_growfs 6.10.1, resize2fs 1.47.1, util-linux mount 2.40.4 and udevadm 251 executed;
- all 48 arm64 driver/syncer package signatures checked using arm64 keys extracted from the digest-verified base; arm64 binaries were not executed;
- overlay materialization applied cleanly to a fresh exact-upstream checkout and then recognized the result as `ALREADY_APPLIED`; existing expansion source changes and their upstream tests are byte-for-byte preserved in the patch.

Local logs are under `/tmp/layersentry-csi-package-proof/`: `driver-offline-v2.log`, `syncer-offline-v2.log`, `arm64-signatures.log`. No Docker/Podman/Buildah daemon or executable is available (`docker buildx version` exited 127), so a complete OCI build remains `NOT_TESTED`. No image digest/signature was invented, and `apkPackageLayerDeterministic` remains false pending exact OCI build verification. No DC/DR/lab mutation occurred.
