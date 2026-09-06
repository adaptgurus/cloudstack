#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT="$ROOT/agent"
PKG="$ROOT/packaging"
OUT="${1:-$ROOT/dist}"
command -v go >/dev/null || { echo "Go toolchain required on build host" >&2; exit 1; }
command -v rpmbuild >/dev/null || { echo "rpmbuild required on build host" >&2; exit 1; }
mkdir -p "$OUT"
work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
mkdir -p "$work/rpmbuild"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
pushd "$AGENT" >/dev/null
GOTOOLCHAIN=auto go build -trimpath -buildvcs=true -ldflags='-s -w' -o "$work/rpmbuild/SOURCES/layersentryd" ./cmd/layersentryd
GOTOOLCHAIN=auto go build -trimpath -buildvcs=true -ldflags='-s -w' -o "$work/rpmbuild/SOURCES/layersentryctl" ./cmd/layersentryctl
popd >/dev/null
install -m 0644 "$PKG/layersentry-privileged.service" "$work/rpmbuild/SOURCES/"
install -m 0644 "$PKG/layersentryd.service" "$work/rpmbuild/SOURCES/"
install -m 0644 "$PKG/layersentry-firstboot.service" "$work/rpmbuild/SOURCES/"
install -m 0644 "$PKG/layersentry-maintenance.service" "$work/rpmbuild/SOURCES/"
install -m 0644 "$PKG/layersentry-maintenance.timer" "$work/rpmbuild/SOURCES/"
install -m 0644 "$PKG/tmpfiles.conf" "$work/rpmbuild/SOURCES/"
install -m 0644 "$PKG/sysusers.conf" "$work/rpmbuild/SOURCES/"
install -m 0644 "$PKG/layersentry-single-os.spec" "$work/rpmbuild/SPECS/"
rpmbuild --define "_topdir $work/rpmbuild" -bb "$work/rpmbuild/SPECS/layersentry-single-os.spec"
find "$work/rpmbuild/RPMS" -type f -name '*.rpm' -exec cp -p {} "$OUT/" \;
sha256sum "$OUT"/*.rpm > "$OUT/SHA256SUMS"
printf 'RPM_BUILD_OK output=%s\n' "$OUT"
