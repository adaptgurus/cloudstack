# LayerSentry Single-OS — Source and RPM CI Verification

Date: 2026-09-07  
Scope: VM-native Single-OS DBaaS/APaaS  
Status: `CI_VERIFIED` for source validation and exact RPM construction only

This record does **not** claim `LIVE_VERIFIED`, production certification, or provider lifecycle acceptance on a real Rocky Linux 9 VM.

## Current certified source validation

Exact verified source SHA:

`f2aee691867d974c2eb0b28184d92b4567100ce8`

GitHub Actions workflow: `LayerSentry Single-OS Source Validation`  
Run: `34126279393`  
Job: `101755596059`  
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

Durable source-validation evidence artifact:

- artifact ID: `10020246403`;
- artifact name: `layersentry-single-os-source-34126279393-1`;
- artifact ZIP SHA-256: `b0ce98514a78add677ba509f909ea5a4357f50b9c8fe949ccb8a47f43bb30735`;
- retention expiry: `2026-10-07T13:15:51Z`.

## Current exact Rocky 9 RPM build

Exact packaged source SHA:

`f2aee691867d974c2eb0b28184d92b4567100ce8`

GitHub Actions workflow: `LayerSentry Single-OS RPM Build`  
Run: `34126279307`  
Source-validation job: `101755594909` — `success`  
Rocky RPM job: `101755869061` — `success`

The RPM workflow reran and passed the same Single-OS source validator before packaging.

Canonical builder:

`tools/layersentry/single-os/packaging/build-rpm.sh`

Exact RPM for the next live qualification:

`layersentry-single-os-0.2.0-1.el9.x86_64.rpm`

RPM SHA-256:

`5ddfa332d222a616f9d9749282540ab3a4acaad64b4b4cba767236a0d4b58fe1`

Durable RPM artifact:

- artifact ID: `10020266864`;
- artifact name: `layersentry-single-os-rpm-34126279307-1`;
- artifact ZIP SHA-256: `6d06d4364a589ece107415b8c5734c6388e4030eeb47f897d7871f292aeea5fb`;
- size: `3,181,750` bytes;
- retention expiry: `2026-10-07T13:16:23Z`.

The artifact was independently downloaded after CI. Its ZIP SHA-256 matched the Actions artifact digest, and the contained RPM independently hashed to the exact RPM SHA-256 above. The embedded `BUILD-METADATA.txt` records source SHA `f2aee691867d974c2eb0b28184d92b4567100ce8`, run `34126279307`, Rocky Linux 9.3 builder, x86_64, Go 1.23.12 and RPM 4.16.1.3.

## Acceptance-harness closure included in this source

`tools/layersentry/single-os/acceptance/postgresql-e2e.py` now exercises the live gates that were previously documented but not directly asserted by the client:

- exact successful install replay using the same operation ID, idempotency key and confirmed plan digest, requiring the same successful operation rather than a second mutation;
- post-reboot `repair` followed by `upgrade`;
- SQL marker integrity after repair/upgrade before uninstall;
- existing backup/restore, reboot recovery, restart, uninstall residue and customer-data-preservation checks remain in the flow.

This is source/CI evidence only. Those assertions are not `LIVE_VERIFIED` until executed on the real Rocky 9 target.

## Superseded CI package

The earlier CI-verification record used source SHA `5e22bed39998a93b1a9c3dca65cda2566a380ba6` and RPM SHA-256 `a47d6fce81f19a87ce7c02374551775541f0a93aadaddf44c6bb96a25bd24d45` from run `34124256595`.

That package remains historical evidence but is **not** the artifact to use for the next live qualification because the acceptance source subsequently changed and a new exact package was built and certified from `f2aee691867d974c2eb0b28184d92b4567100ce8`.

## Certification boundary

The following remain `NOT_TESTED` / not live-certified:

- installation of the current exact RPM on a fresh Rocky Linux 9 VM;
- separate non-OS data-disk inventory and destructive-operation safety proof against the live root/OS disk;
- PostgreSQL standalone exact-artifact plan/install/health/read-write/idempotent replay/reboot/start/stop/restart;
- backup/restore verification on the exact installed artifact;
- repair/upgrade acceptance;
- uninstall and residue audit;
- MySQL/MariaDB, Redis/Valkey and APaaS/runtime live provider qualification;
- PostgreSQL multi-node HA and Keepalived VRRP failover;
- signed production release and performance/security certification.

## Next exact gate

1. obtain or provision a clean disposable Rocky Linux 9 VM;
2. attach a separate non-OS data disk;
3. transfer `layersentry-single-os-0.2.0-1.el9.x86_64.rpm` from artifact `10020266864` and verify SHA-256 `5ddfa332d222a616f9d9749282540ab3a4acaad64b4b4cba767236a0d4b58fe1` before installation;
4. execute `acceptance/storage-inventory.py` and `acceptance/root-disk-negative.py`;
5. execute the PostgreSQL standalone exact-artifact acceptance flow with `acceptance/postgresql-e2e.py` and supporting preparation/install scripts;
6. perform the required real VM reboot between phase 1 and phase 2;
7. persist exact host, artifact, commands, outputs and failure/reset state;
8. if a destructive or ambiguous failure dirties the VM, stop and report `LAB_RESET_REQUIRED` rather than continuing on an uncertain guest;
9. do not promote beyond `CI_VERIFIED` until those live gates pass.
