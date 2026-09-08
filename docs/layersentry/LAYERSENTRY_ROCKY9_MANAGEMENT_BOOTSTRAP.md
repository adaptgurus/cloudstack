# LayerSentry Rocky Linux 9 Management-Node Bootstrap

Status: `SOURCE_COMPLETE`; Rocky Linux 9 execution is `NOT_TESTED`.

## Decision and boundary

CloudStack remains authoritative. The bootstrap installs an exact signed RPM and deploys an already-generated encrypted `db.properties`; it does not create, recreate, migrate, elect, or fail over the database. This separation lets an operator provide a tested DB HA endpoint without making a node-local installer a database orchestrator.

All three Management VMs use the same CloudStack release, DB endpoint/configuration and encryption material. Generate the database schema and encrypted configuration once with the supported `cloudstack-setup-databases` flow, then transfer the resulting inputs through a protected secret-delivery path. Never commit them. Do not run `--force-recreate` on an existing environment.

## Inputs and invocation

Required environment variables are `LAYERSENTRY_PACKAGE_NEVRA`, `LAYERSENTRY_DB_PROPERTIES_FILE`, and explicit `LAYERSENTRY_FIREWALL_PORTS`. The package value must be a full NEVRA. The input file must be a regular non-symlink file with mode `0600` or stricter. Set `LAYERSENTRY_ENCRYPTION_KEY_FILE` when the selected CloudStack encryption mode uses a key file. Optionally provide `LAYERSENTRY_REPO_FILE` and `LAYERSENTRY_MANAGEMENT_DEFAULT_FILE` under the same protected-file rules; a repository must enable `gpgcheck=1`.

Run on each fresh Rocky Linux 9 node:

```bash
sudo --preserve-env=LAYERSENTRY_PACKAGE_NEVRA,LAYERSENTRY_DB_PROPERTIES_FILE,LAYERSENTRY_ENCRYPTION_KEY_FILE,LAYERSENTRY_REPO_FILE,LAYERSENTRY_MANAGEMENT_DEFAULT_FILE,LAYERSENTRY_FIREWALL_PORTS \
  tools/layersentry-management/bootstrap-rocky9-management.sh preflight
sudo --preserve-env=LAYERSENTRY_PACKAGE_NEVRA,LAYERSENTRY_DB_PROPERTIES_FILE,LAYERSENTRY_ENCRYPTION_KEY_FILE,LAYERSENTRY_REPO_FILE,LAYERSENTRY_MANAGEMENT_DEFAULT_FILE,LAYERSENTRY_FIREWALL_PORTS \
  tools/layersentry-management/bootstrap-rocky9-management.sh apply
```

The tool refuses non-Rocky-9 hosts, disabled SELinux enforcement, inactive firewalld, unpinned packages and insecure inputs. It opens only the explicitly supplied ports, restores SELinux labels, enables/restarts the service, and waits for the local UI endpoint. It never disables security controls or prints secret contents.

## Resume, repair and recovery

`apply` is state-checked and safe to rerun with identical inputs. Before changing node-local configuration it saves a restricted rollback copy below `/var/lib/layersentry/management-bootstrap/rollback`. On a failed apply it restores those files and attempts to restart the previous service configuration. The rollback copy contains secrets and must remain root-only and be securely destroyed under the operator's retention policy after acceptance.

For manual recovery, remove the node from the LB, stop `cloudstack-management`, restore the restricted files from the rollback directory, run `restorecon -RF /etc/cloudstack/management`, start the service, verify local UI/API and agent connectivity, then return the node to the LB. Package/schema downgrade is not implied by config restoration.

## Three-node rollout and acceptance

Provision one node at a time. Verify exact RPM identity, SELinux enforcing, firewalld state, service health, signed API access, DB connectivity and logs before adding that node to the LB. Then verify LB health removal, UI/API continuity, port 8250 agent behavior, async jobs, rolling restart, and each Management VM failure independently.

This source does not configure the LB, DB HA, schema, TLS certificates, VIP, DNS, placement, fencing or independent rescue path. Those remain separate evidence gates. A successful local HTTP response is not HA or product certification; exact Rocky Linux 9 workflow evidence is required before `LIVE_VERIFIED`.
