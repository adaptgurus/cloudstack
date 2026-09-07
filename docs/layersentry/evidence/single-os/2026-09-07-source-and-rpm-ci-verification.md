# LayerSentry Single-OS — Source and RPM CI Verification

Date: 2026-09-07  
Scope: VM-native Single-OS DBaaS/APaaS  
Status: `CI_VERIFIED` for source validation and exact RPM construction only

This record does **not** claim `LIVE_VERIFIED`, production certification, or provider lifecycle acceptance on a real Rocky Linux 9 VM.

## Source validation

Exact verified source SHA:

`1387794a4e1123746f734815c946cb58e5aea0be`

GitHub Actions workflow: `LayerSentry Single-OS Source Validation`  
Run: `34122976977`  
Job: `101745048201`  
Conclusion: `success`

The gate completed:

- `go mod tidy -diff`;
- clean `gofmt` check;
- `go test -count=1 ./...`;
- `go vet ./...`;
- `layersentryd` and `layersentryctl` builds;
- Python module compilation;
- Ansible syntax checks for all Single-OS playbooks using checkout-local CI temp/search paths while preserving production Ansible configuration;
- shell syntax checks.

Terminal success marker:

`SINGLE_OS_SOURCE_VALIDATION_OK`

Durable evidence artifact:

- artifact ID: `10018963979`;
- artifact name: `layersentry-single-os-source-34122976977-1`;
- artifact ZIP SHA-256: `9c259ba409c22904261c5fd70b04d116b17d6e025212ef5bd9e2c2d6f4ca5c37`;
- retention: 30 days from creation.

## Exact Rocky 9 RPM build

Exact packaged source SHA:

`5e22bed39998a93b1a9c3dca65cda2566a380ba6`

The packaging SHA contains only CI workflow changes after the source gate; the RPM workflow first reran and passed the same Single-OS source validator before packaging.

GitHub Actions workflow: `LayerSentry Single-OS RPM Build`  
Run: `34124256595`  
Source-validation job: `101749090990` — `success`  
Rocky RPM job: `101749349783` — `success`

Builder facts:

- container image: `rockylinux:9`;
- pulled image digest: `sha256:d7be1c094cc5845ee815d4632fe377514ee6ebcf8efaed6892889657e5ddaaa6`;
- observed builder release: `Rocky Linux release 9.3 (Blue Onyx)`;
- architecture: `x86_64`;
- Go: `go1.23.12 linux/amd64`;
- RPM/rpmbuild: `4.16.1.3`.

Canonical builder:

`tools/layersentry/single-os/packaging/build-rpm.sh`

Exact RPM:

`layersentry-single-os-0.2.0-1.el9.x86_64.rpm`

RPM SHA-256:

`a47d6fce81f19a87ce7c02374551775541f0a93aadaddf44c6bb96a25bd24d45`

Package inspection completed successfully:

- `rpm -K` reported `digests OK`;
- package metadata inspection passed;
- packaged file-list inspection passed;
- dependency inspection passed;
- exactly one RPM was accepted by the gate.

`rpmbuild` emitted non-fatal missing-build-id warnings for `layersentryd` and `layersentryctl`. These warnings did not fail the RPM build, but release hardening/signing remains a later certification gate.

Durable RPM artifact:

- artifact ID: `10019489680`;
- artifact name: `layersentry-single-os-rpm-34124256595-1`;
- artifact ZIP SHA-256: `7288cbdb8e45afdab8223ee78575a1a77139d9f7058ae18383cd20b9b9c8ad1e`;
- size: `3,181,838` bytes;
- retention expiry: `2026-10-07T12:54:42Z`.

## Certification boundary

The following remain `NOT_TESTED` / not live-certified:

- installation of the exact RPM on a fresh Rocky Linux 9 VM;
- separate non-OS data-disk inventory and destructive-operation safety proof against the live root/OS disk;
- PostgreSQL standalone exact-artifact plan/install/health/read-write/idempotent rerun/reboot/start/stop/restart;
- backup/restore verification on the exact installed artifact;
- repair/upgrade acceptance;
- uninstall and residue audit;
- MySQL/MariaDB, Redis/Valkey and APaaS/runtime live provider qualification;
- PostgreSQL multi-node HA and Keepalived VRRP failover;
- signed production release and performance/security certification.

## Next exact gate

1. obtain or provision a clean disposable Rocky Linux 9 VM;
2. attach a separate non-OS data disk;
3. install the exact RPM identified above and verify its SHA-256 before installation;
4. execute `acceptance/storage-inventory.py` and `acceptance/root-disk-negative.py`;
5. execute the PostgreSQL standalone exact-artifact acceptance flow with `acceptance/postgresql-e2e.py` and supporting preparation/install scripts;
6. persist exact host, artifact, commands, outputs and failure/reset state;
7. do not promote beyond `CI_VERIFIED` until those live gates pass.
