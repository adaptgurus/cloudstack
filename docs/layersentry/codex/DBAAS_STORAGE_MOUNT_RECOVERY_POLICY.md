# LayerSentry DBaaS — Storage Mount and Recovery Policy

Status: `DESIGN_DEFINED`

This document refines and supersedes any earlier future-DBaaS statement that a critical database mount must categorically avoid `nofail`.

## Decision

A managed DB guest must remain bootable enough for the DBaaS runner/monitoring path to report and repair an unavailable data volume, while the database service itself must fail closed.

Therefore the certified pattern is:

```text
CloudStack data volume
  -> exact guest-device identity verification
  -> LVM/XFS
  -> bounded systemd-managed mount
  -> OS/runner may boot if the mount is unavailable
  -> DB service has RequiresMountsFor=<managed mount>
  -> DB service ExecStartPre verifies volume/LVM/filesystem/mount identity
  -> DB starts only when all checks pass
```

## fstab policy

The managed XFS data mount may use a bounded recoverable-boot form such as:

```text
UUID=<uuid> /var/lib/dbaas/data xfs defaults,nofail,nodev,nosuid,x-systemd.device-timeout=30s,x-systemd.mount-timeout=30s 0 0
```

`nofail` is allowed only together with the fail-closed database-service guard. It must never be interpreted as permission for a database to use the plain directory on the root filesystem when the intended data volume is absent.

## Mandatory database-service guard

Every database systemd unit using the managed volume must have an equivalent to:

```ini
[Unit]
RequiresMountsFor=/var/lib/dbaas/data
After=local-fs.target

[Service]
ExecStartPre=/usr/local/libexec/layersentry/verify-managed-mount <cloudstack-volume-uuid> /var/lib/dbaas/data
```

The verifier must validate at least:

- expected CloudStack volume UUID;
- release-certified KVM guest disk serial mapping;
- exactly one matching guest block device;
- expected VG and LV;
- recorded filesystem UUID;
- expected filesystem type;
- expected active mountpoint;
- actual mount source is the managed LV.

Any mismatch blocks DB startup and reports a storage-unsafe/degraded state.

## Rationale

Failing the entire OS into emergency mode solely because a tenant database data disk is temporarily unavailable can remove the very management/agent path needed to diagnose or repair the instance. Allowing the OS and DBaaS runner to start while separately refusing database service startup provides a better recovery posture without creating a root-disk fallback hazard.

## Certification tests

Before production certification prove all of the following:

1. normal reboot with the data volume present;
2. reboot with data volume absent: OS/runner becomes reachable, DB stays stopped;
3. reattach correct volume: identity verifies, mount recovers, DB can start;
4. attach wrong/foreign volume: DB remains blocked;
5. filesystem UUID mismatch: DB remains blocked;
6. expected LV absent: DB remains blocked;
7. an empty mountpoint directory on root cannot satisfy the guard;
8. CloudStack volume resize -> guest rescan -> `pvresize` -> `lvextend` -> `xfs_growfs` preserves identity and service availability where the certified backend supports online resize.
