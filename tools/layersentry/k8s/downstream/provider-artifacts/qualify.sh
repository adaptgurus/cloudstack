#!/usr/bin/env bash
set -euo pipefail
component=${1:?component required}
source_dir=$(realpath "${2:?source directory required}")
evidence_dir=$(realpath "${3:?evidence directory required}")
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
case "$component" in
  capc) expected=7521b14a31e6c46f81f16aae3738a27c08ad063f ;;
  cloudstack-ccm) expected=4740dbcacc7fc5892354b03b2f0be7ebf5c92584 ;;
  *) exit 2 ;;
esac
source_commit=$(git -C "$source_dir" rev-parse HEAD)
test "$source_commit" = "$expected"
source_date=$(git -C "$source_dir" show -s --format=%cI HEAD)
source_epoch=$(git -C "$source_dir" show -s --format=%ct HEAD)
layer_commit=$(git -C "$script_dir" rev-parse HEAD)
scanner=docker.io/docker/buildkit-syft-scanner@sha256:ae4f3b554449e7e25548e7d8ccc029d17357348e30c6e3df01b92bc93654d6a9
tag="layersentry.local/$component:qualification"
args=(--platform linux/amd64 --file "$script_dir/$component.Containerfile" --target runtime
  --build-arg "SOURCE_COMMIT=$source_commit" --build-arg "SOURCE_DATE=$source_date" --build-arg "SOURCE_DATE_EPOCH=$source_epoch"
  --label "org.opencontainers.image.revision=$layer_commit" --label "io.layersentry.upstream.revision=$source_commit" --tag "$tag")
docker buildx build "${args[@]}" --attest "type=sbom,generator=$scanner" --provenance=mode=max \
  --metadata-file "$evidence_dir/$component-build.json" --output "type=oci,dest=$evidence_dir/$component.oci.tar" "$source_dir" \
  2>&1 | tee "$evidence_dir/$component-build.log"
docker buildx build "${args[@]}" --provenance=false --load "$source_dir" 2>&1 | tee "$evidence_dir/$component-load.log"
docker image inspect "$tag" > "$evidence_dir/$component-inspect.json"
if [ "$component" = capc ]; then smoke=--help; else smoke=--version; fi
smoke_status=0
timeout 30 docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --memory 512m --pids-limit 64 "$tag" "$smoke" > "$evidence_dir/$component-smoke.txt" 2>&1 || smoke_status=$?
test -s "$evidence_dir/$component-smoke.txt"
if [ "$component" = capc ]; then
  # Exact upstream pflag ExitOnError returns 2 for --help; require its expected
  # usage and provider flags so a crash/timeout cannot masquerade as smoke pass.
  test "$smoke_status" = 2
  grep -Fx 'Usage of /manager:' "$evidence_dir/$component-smoke.txt"
  grep -Fx 'pflag: help requested' "$evidence_dir/$component-smoke.txt"
  grep -F -- '--cloudstackmachine-concurrency' "$evidence_dir/$component-smoke.txt"
else
  test "$smoke_status" = 0
fi
if [ "$component" = cloudstack-ccm ]; then
  grep -F 'v1.2.0-layersentry.k8s1.36' "$evidence_dir/$component-smoke.txt"
fi
python3 "$script_dir/verify_oci.py" --archive "$evidence_dir/$component.oci.tar" --inspect "$evidence_dir/$component-inspect.json" \
  --component "$component" --source-commit "$layer_commit" --output "$evidence_dir/$component-verification.json"
manifest_args=()
if [ "$component" = capc ]; then
  docker buildx build --platform linux/amd64 --file "$script_dir/capc.Containerfile" --target tools \
    --output "type=local,dest=$evidence_dir/build-tools" "$source_dir" 2>&1 | tee "$evidence_dir/kustomize-export.log"
  "$evidence_dir/build-tools/kustomize" version > "$evidence_dir/kustomize-version.txt"
  manifest_args=(--kustomize "$evidence_dir/build-tools/kustomize")
fi
python3 "$script_dir/bind_components.py" --component "$component" --source "$source_dir" --evidence "$evidence_dir" "${manifest_args[@]}"
sha256sum "$evidence_dir"/*.oci.tar > "$evidence_dir/OCI-SHA256SUMS"
