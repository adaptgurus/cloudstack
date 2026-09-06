#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "usage: $0 --version VERSION --output-dir DIR [--source-commit SHA] [--dist-dir DIR]" >&2
  exit 2
}

release_version=''
output_dir=''
source_commit=''
dist_dir='ui/dist'

while (($#)); do
  case "$1" in
    --version) [[ $# -ge 2 ]] || usage; release_version="$2"; shift 2 ;;
    --output-dir) [[ $# -ge 2 ]] || usage; output_dir="$2"; shift 2 ;;
    --source-commit) [[ $# -ge 2 ]] || usage; source_commit="$2"; shift 2 ;;
    --dist-dir) [[ $# -ge 2 ]] || usage; dist_dir="$2"; shift 2 ;;
    *) usage ;;
  esac
done

[[ "$release_version" =~ ^[0-9A-Za-z][0-9A-Za-z._+-]{0,63}$ ]] || { echo 'invalid release version' >&2; exit 2; }
[[ -n "$output_dir" ]] || usage
[[ -f "$dist_dir/index.html" && -f "$dist_dir/config.json" ]] || { echo "UI dist is incomplete: $dist_dir" >&2; exit 1; }
if [[ -z "$source_commit" ]]; then source_commit="$(git rev-parse HEAD)"; fi
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || { echo 'source commit must be a full lowercase Git SHA-1' >&2; exit 2; }

if find "$dist_dir" -type f \( -name '*.map' -o -name '*.map.gz' \) -print -quit | grep -q .; then
  echo 'production UI dist contains source-map files' >&2
  exit 1
fi
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd -P)"
artifact_name="layersentry-ui-${release_version}.tar.gz"
artifact_path="$output_dir/$artifact_name"
for release_output in "$artifact_path" "$output_dir/release-manifest.json" \
  "$output_dir/layersentry-ui.sbom.cdx.json" "$output_dir/layersentry-ui.provenance.json" \
  "$output_dir/SHA256SUMS"; do
  [[ ! -e "$release_output" ]] || { echo "refusing to overwrite release output: $release_output" >&2; exit 1; }
done
source_epoch="${SOURCE_DATE_EPOCH:-$(git show -s --format=%ct "$source_commit")}"
[[ "$source_epoch" =~ ^[0-9]+$ ]] || { echo 'SOURCE_DATE_EPOCH must be an integer' >&2; exit 2; }

tar --sort=name --format=posix --mtime="@$source_epoch" --owner=0 --group=0 --numeric-owner \
  --pax-option=delete=atime,delete=ctime -C "$dist_dir" -cf - . | gzip -n >"$artifact_path"

python3 tools/layersentry-release/release_contract.py build \
  --version "$release_version" --source-commit "$source_commit" --source-epoch "$source_epoch" \
  --artifact "$artifact_path" --package-lock ui/package-lock.json --output-dir "$output_dir"

printf 'Built unsigned candidate bundle in %s\n' "$output_dir"
printf 'Production consumers must reject it until detached-signature support is completed.\n'
