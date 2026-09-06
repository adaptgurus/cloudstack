#!/usr/bin/env bash
set -euo pipefail
source_dir=$(realpath "${1:?source directory required}")
evidence_dir=$(realpath "${2:?evidence directory required}")
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_commit=$(git -C "$source_dir" rev-parse HEAD)
test "$source_commit" = a84477e922d62b82387ab55134fafc9c0b5aaf64
layer_commit=$(git -C "$script_dir" rev-parse HEAD)
scanner=docker.io/docker/buildkit-syft-scanner@sha256:ae4f3b554449e7e25548e7d8ccc029d17357348e30c6e3df01b92bc93654d6a9
for component in cloudstack-csi-driver cloudstack-csi-sc-syncer; do
  tag="layersentry-${component}:qualification"
  ldflags="-s -w -X main.version=3.0.2-layersentry.${layer_commit} -X github.com/cloudstack/cloudstack-csi-driver/pkg/driver.driverVersion=3.0.2-layersentry.${layer_commit} -X github.com/cloudstack/cloudstack-csi-driver/pkg/driver.gitCommit=${source_commit}"
  docker buildx build --platform linux/amd64 --file "$source_dir/cmd/$component/Dockerfile" \
    --build-arg "LDFLAGS=$ldflags" --tag "$tag" \
    --attest "type=sbom,generator=$scanner" --provenance=mode=max \
    --metadata-file "$evidence_dir/$component-build.json" \
    --output "type=oci,dest=$evidence_dir/$component.oci.tar" "$source_dir" \
    2>&1 | tee "$evidence_dir/$component-build.log"
  # Docker's local image store does not preserve attestations. Export the cached
  # same build for smoke testing; compare its config identity to the retained OCI.
  docker buildx build --platform linux/amd64 --file "$source_dir/cmd/$component/Dockerfile" \
    --build-arg "LDFLAGS=$ldflags" --tag "$tag" --provenance=false --load "$source_dir" \
    2>&1 | tee "$evidence_dir/$component-load.log"
  docker image inspect "$tag" > "$evidence_dir/$component-inspect.json"
  timeout 30 docker run --rm --network none --read-only --cap-drop ALL \
    --security-opt no-new-privileges --memory 512m --pids-limit 64 \
    "$tag" --version > "$evidence_dir/$component-version.json"
  timeout 30 docker run --rm --network none --read-only --cap-drop ALL \
    --security-opt no-new-privileges --memory 512m --pids-limit 64 \
    --entrypoint /bin/sh "$tag" -ec 'test -s /etc/ssl/certs/ca-certificates.crt; apk info -v' \
    > "$evidence_dir/$component-runtime-packages.txt"
  if [ "$component" = cloudstack-csi-driver ]; then
    timeout 60 docker run --rm --network none --read-only --cap-drop ALL \
      --security-opt no-new-privileges --memory 512m --pids-limit 64 \
      --tmpfs /tmp:rw,noexec,nosuid,size=1g --entrypoint /bin/sh "$tag" -ec '
        for tool in mkfs.ext2 mkfs.ext3 mkfs.ext4 resize2fs mkfs.xfs xfs_growfs blkid mount umount udevadm; do command -v "$tool"; done
        xfs_growfs -V
        mount --version
        umount --version
        udevadm --version
        truncate -s 32M /tmp/ext4.img
        mkfs.ext4 -F /tmp/ext4.img
        test "$(blkid -s TYPE -o value /tmp/ext4.img)" = ext4
        truncate -s 64M /tmp/ext4.img
        resize2fs /tmp/ext4.img
        e2fsck -fn /tmp/ext4.img
        truncate -s 512M /tmp/xfs.img
        mkfs.xfs -f /tmp/xfs.img
        test "$(blkid -s TYPE -o value /tmp/xfs.img)" = xfs
      ' > "$evidence_dir/$component-filesystem-smoke.log" 2>&1
  fi
  python3 "$script_dir/verify_oci.py" --archive "$evidence_dir/$component.oci.tar" \
    --inspect "$evidence_dir/$component-inspect.json" --component "$component" \
    --source-commit "$layer_commit" --output "$evidence_dir/$component-verification.json"
done
sha256sum "$evidence_dir"/*.oci.tar > "$evidence_dir/OCI-SHA256SUMS"
