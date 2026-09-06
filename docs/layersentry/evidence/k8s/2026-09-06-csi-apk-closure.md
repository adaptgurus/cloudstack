# CloudStack CSI immutable runtime package closure

Status: `CI_VERIFIED` for the amd64 artifact build and isolated image smoke tests; production/runtime qualification remains `PARTIAL`. Scope: CloudStack CSI 3.0.2 downstream build only; no CloudStack core or runtime mutation.

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

Local logs are under `/tmp/layersentry-csi-package-proof/`: `driver-offline-v2.log`, `syncer-offline-v2.log`, `arm64-signatures.log`. No Docker/Podman/Buildah daemon or executable is available (`docker buildx version` exited 127), so a complete OCI build was `NOT_TESTED` at this preliminary local checkpoint. The subsequent hosted result below supersedes that build limitation. No image digest/signature was invented, and `apkPackageLayerDeterministic` remains false pending exact OCI build verification. No DC/DR/lab mutation occurred.

## Hosted OCI qualification — CI_VERIFIED

The authorized build-only isolated-branch workflow `.github/workflows/layersentry-csi-artifact-qualification.yml` succeeded in [run 34047140051](https://github.com/adaptgurus/cloudstack/actions/runs/34047140051), job `101524118290`, at exact LayerSentry source `d40c54acb8a18b71475b154f14dd631460c94f89`. It used Ubuntu 24.04 hosted execution, Buildx 0.37.0, digest-pinned BuildKit 0.33.0 and a digest-pinned Syft scanner. No signing secrets, registry publication permissions or lab access were used. The workflow builds only the isolated branch; unrelated broad Java/UI workflows triggered by that branch were cancelled to conserve runner work.

Artifact `9993465630`, SHA-256 `102c9642a5a0cd81fcafe4d6e5771f18688a228bcf601706578f45f12f24c534`, size 48,030,165 bytes, retains both unsigned OCI archives, SPDX SBOM and SLSA-format provenance statements, source/lock/base identities, build logs, image inspection, binary versions and smoke results. Retention is 14 days; durable release promotion must copy and verify the exact approved bytes before expiry. These are format/provenance records, not a claim of SLSA certification or signature verification.

| Component | Runtime image manifest digest | OCI archive SHA-256 |
| --- | --- | --- |
| CSI driver | `sha256:9c1fac533078231833c41111f6b351904f81011801ac5c61ce54e43f2566dfa5` | `0a52fdf6194ac4efa5ac3f155f3a14a07f12d0fc98e9565db55e137fe53e5919` |
| Storage-class syncer | `sha256:c33d4988fefc444356a6559490cf46a2b45154e3cdf426f330685cd92188beeb` | `f0839c00895f754be994760d82ee4a0d498fbbc4bc2a88b407b7406634ecdd59` |

Both built binaries report `3.0.2-layersentry.d40c54acb8a18b71475b154f14dd631460c94f89`; the driver reports upstream commit `a84477e922d62b82387ab55134fafc9c0b5aaf64`, Go 1.23.12 and linux/amd64. Both images passed no-network, read-only-rootfs, dropped-capability, no-new-privileges version/CA checks. The driver additionally formatted ext4, expanded a regular-file filesystem from 32 MiB to 64 MiB, passed e2fsck, formatted a 512 MiB XFS file, and identified both filesystem types with blkid. Runtime mount/umount/udevadm and xfs_growfs binaries executed version checks. No mounted-volume growth or actual CloudStack CSI operation is claimed.

Nine package/OCI verification tests passed. The OCI verifier checks all blob SHA-256 values, descriptor reachability/sizes, one linux/amd64 runtime manifest, expected entrypoint, equality of the smoke-tested Docker config digest to the archived OCI config, and matching SBOM/provenance subjects. Negative cases cover corrupt blobs, missing SBOM, wrong attestation subject and another smoke image. An initial local fixture exposed incorrect traversal of an image config as a manifest; commit `d40c54acb8` fixed it before the successful build. The downloaded OCI archives were independently reverified locally and matched both recorded image identities; their SBOMs contain 98 driver and 67 syncer packages.

Machine-readable evidence is `2026-09-06-csi-oci-build.json`. These results establish the amd64 locked package build path and isolated artifact smoke behavior only. Arm64 image build, registry promotion, vulnerability/license qualification, signing, Rocky Linux 9 attach/mount/resize/project lifecycle and destructive PVC survival remain separate gates. No release live booleans were changed by this checkpoint.
