# LayerSentry Rocky Linux 9 locked-host profile

Status: `SOURCE_COMPLETE`; runtime behavior is `NOT_TESTED`.

## Decision

LayerSentry uses a constrained Rocky Linux 9 appliance profile, not a claim that a root or physical administrator cannot change the host. Normal changes flow through a verified, signed LayerSentry release transaction. SELinux enforcing, firewalld, auditd, fapolicyd and AIDE provide layered policy, detection and integrity evidence. eBPF may enrich detection but is neither the authorization boundary nor prevention mechanism.

The implementation starts fail-closed and deliberately separates `preflight`, `stage`, `apply`, `verify`, and `rollback`. `apply` requires root, `--execute`, a reviewed stage, and JSON evidence proving a non-root key-based administrator, sudo access, and an out-of-band break-glass test. It writes configuration drop-ins only; it does not install packages, restart SSH, alter firewall rules, reboot, or lock the local root account. Those actions require a release-specific R3 procedure and Rocky acceptance evidence.

## Package and storage model

The policy JSON is an explicit allowlist for product-managed package additions and repositories. A release-generated package lock contains the complete exact installed NEVRA set; `verify-package-lock` fails on any missing or additional package. Every enabled release repository must use package signatures, repository metadata signatures, and TLS verification. A production updater must additionally validate the LayerSentry release manifest/signature, exact target compatibility, package NEVRAs and transaction set before invoking DNF. The current source does not yet implement that signed updater or ship a release-specific complete lock, so package immutability is `PENDING`.

CloudStack KVM operation requires narrow writable state. The policy records exceptions for CloudStack agent state, libvirt, logs, iSCSI initiator state and multipath configuration/state. It does not grant arbitrary user write access. Multipath and iSCSI changes remain controlled storage transactions with preflight, device/WWID validation and rollback.

## Safe use

1. Run `layersentry-locked-host preflight` on the exact Rocky 9 candidate.
2. Run `stage`, inspect the generated files, and capture the current config/package/firewall/SELinux/SSH state outside the VM.
3. Establish and independently test a non-root key-based administrative account and OOB console recovery.
4. Create root-owned, non-group/world-writable evidence JSON with `admin_user`, `ssh_key_login_tested`, `sudo_tested`, `oob_break_glass_tested`, and `tested_at`.
5. Run `apply --execute --evidence ...`, validate SSH from a second session, then explicitly reload SSH only through the approved change procedure.
6. Run `verify`. Use `rollback --execute` from the retained session or OOB console if validation fails.

## Threats and limitations

Assets are administrative access, package/release integrity and KVM/storage availability. Entry points include repositories, release metadata, local privileged users and mutable KVM/storage configuration. Fail-closed staging and access evidence reduce accidental lockout; signature/repository requirements reduce supply-chain exposure; SELinux/fapolicyd/audit/AIDE provide enforcement or detection according to their actual scope.

This source does not prevent a privileged or physical operator from disabling controls. It does not yet configure AIDE baselines, fapolicyd rules, audit/eBPF sensors, firewall services, DNF versionlocks or a signed updater. Those require exact release packages, ports and live negative/recovery tests. Do not label the appliance immutable or production secure from this source alone.

## Percona/MySQL compatibility gate

Percona Server or Percona XtraDB Cluster is not adopted merely because it is MySQL-compatible. CloudStack 4.22.1.1 documentation/source, JDBC behavior and schema tooling must be checked against the exact Percona product/version/topology. The current CloudStack documentation has conflicting MySQL baseline language, so the release matrix remains undecided.

Required evidence before adoption includes clean schema creation, management startup, representative API/async jobs, one-member loss, writer loss and connection recovery, quorum loss/partition behavior, rejoin, repeated failover, backup/restore/PITR where claimed, N-1 to N upgrade, interruption/recovery, latency and transaction correctness, and absence of CloudStack data corruption. Until those gates pass on Rocky Linux 9, Percona status is `PENDING` and installers must not select or install it automatically.
