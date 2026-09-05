# Rocky 9 first-node installer and database backups

Status: `SOURCE_COMPLETE` for the source and local tests described here. Rocky runtime, installation, API, browser, restart, backup and restore acceptance: `NOT_TESTED` by this change. The tool reports `PARTIAL` after installation stages because service/UI reachability does not prove product acceptance.

## Decision and research

The existing `bootstrap-rocky9-management.sh` accepts an already initialized encrypted database configuration. Its advantage is a small node-local scope; it does not install or initialize a database. The new `install-rocky9.py` adds first-node orchestration while preserving that configuration contract and using the packaged native `cloudstack-setup-databases` and `cloudstack-setup-management` programs. CloudStack core/schema/agent source is unchanged. Scoped firewall rules improve the existing bootstrap's unrestricted port examples.

Compared alternatives were extending the join-only shell script, running an unpinned general-purpose CloudStack installer, and implementing CloudStack schema creation ourselves. A separate Python standard-library orchestrator keeps the existing entrypoint stable, avoids executing a moving remote script, and retains native schema/encryption behavior. Costs are an additional reviewed entrypoint, an explicit runtime configuration contract, and conservative stops after ambiguous database interruptions.

The version-pinned [CloudStack 4.22.1.1 compatibility page](https://docs.cloudstack.apache.org/en/4.22.1.1/releasenotes/compat.html), inspected during this work, lists Rocky Linux 9, Java 17 and MySQL **8.4**. This differs from earlier project evidence for MySQL 8.0. Exact fetched documentation and source must be reconciled before selecting a release DB profile. The installer requires an explicit `mysql_series` of `8.0` or `8.4` and exact matching RPM identities; accepting an input is not compatibility certification. No automatic MySQL version/Percona migration occurs. The local upstream references are `setup/bindir/cloud-setup-databases.in` and `python/lib/cloudutils/serviceConfigServer.py`.

Backup uses native [mysqldump](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html) with one transaction covering `cloud` and `cloud_usage`, routines, events and triggers. Non-InnoDB tables are rejected because transactional consistency would not cover them. Database DDL/upgrades must be serialized against backups. [OpenSSL CMS](https://docs.openssl.org/3.2/man1/openssl-cms/) supplies standard recipient-certificate encryption. SHA-256 detects accidental corruption/tampering against a trusted manifest; the manifest is not signed, so replacing both files is outside this integrity claim.

## Modes and inputs

`combined` provisions MySQL and management on the current VM, binds MySQL to loopback, and initializes an empty CloudStack database. `external` joins an already provisioned DB using encrypted `db.properties` and the shared management encryption key. External initialization and DB-only provisioning are not implemented in this entrypoint: the remote DB owner must supply the initialized schema, database grants, TLS identity/truststore configuration, and an existing `layersentry_backup` account. This boundary avoids presenting an unvalidated remote DB/HA controller as an installer feature.

All commands run as root. Runtime config, secrets, repository input files, certificates, and imported encrypted configuration must be root-owned regular files with no group/other access; scripts never source shell environment files. Configuration is JSON schema version 1. An operator/runner resolves actual package NEVRAs and repository keys before filling this example; angle-bracket values deliberately fail validation:

```json
{
  "schema_version": 1,
  "mode": "combined",
  "initialize_database": true,
  "hostname": "layersentry-dr-mgmt1",
  "management_ip": "192.0.2.10",
  "db_host": "localhost",
  "mysql_series": "8.0",
  "management_package": "<exact cloudstack-management 4.22.1.1 NEVRA>",
  "java_package": "<exact java-17-openjdk-headless NEVRA>",
  "mysql_client_package": "<exact matching MySQL client NEVRA>",
  "mysql_server_package": "<exact matching MySQL server NEVRA>",
  "repo_files": ["/run/layersentry/cloudstack.repo", "/run/layersentry/database.repo"],
  "ui_cidr": "192.0.2.0/24",
  "agent_cidr": "192.0.2.0/24",
  "firewall_zone": "public",
  "management_nodes": 1,
  "backup_db_user": "layersentry_backup",
  "backup_recipient_certificate": "/run/layersentry/backup-recipient.pem",
  "backup_retention": 14
}
```

External mode additionally requires `db_properties_file`, `encryption_key_file`, and `db_tls_ca`. The installer parses effective [Java Properties](https://docs.oracle.com/en/java/javase/17/docs/api/java.base/java/util/Properties.html) values, including comments, separators, escapes, continuations and last-value precedence. Original ISO-8859-1 input bytes are preserved during deployment. `cluster.node.IP` must equal this node's configured management address; copying an existing manager's node identity fails preflight.

Both DB hosts must match `db_host`, use `jdbc:mysql`, port 3306 and their expected schema names, and have actual encrypted password properties. URI keys are rejected even when empty: `TransactionLegacy.getConnectionUriAndDriver` gives a nonempty URI precedence over the separate host/TLS settings. HA/replica composition is outside this single-endpoint profile. Each of `db.cloud.url.params` and `db.usage.url.params` independently requires `useSSL=true`, `requireSSL=true`, `verifyServerCertificate=true` and `sslMode=VERIFY_IDENTITY`; comments or another schema's parameters do not satisfy the gate. Duplicate URL parameters and unreviewed driver options are rejected. The allowed extra options cover the upstream prepared-statement/session/timezone defaults and selected encoding/batching options; extending them requires review. Validate actual Java truststore and hostname verification in live testing. Backup MySQL connections use `ssl-mode=VERIFY_IDENTITY` and the supplied CA. Static properties validation alone is not TLS certification.

The separate secrets JSON contains `db_password`, `db_admin_password`, `management_key`, `database_key`, and `backup_db_password` for combined mode; external joins need only `backup_db_password`. The installer never generates a universal password or embeds supplied credentials in source. It constrains native setup inputs to 8–128 characters in `[A-Za-z0-9_+=.-]` because the upstream setup program interpolates values into SQL/shell commands. Passwords are supplied to the wrapper through stdin/in-memory arguments and diagnostics are suppressed. **Residual risk:** upstream setup invokes MySQL/Java children with sensitive arguments; local privileged process inspection and native audit tooling can observe them. Run initialization on a controlled single-operator node and do not enable shell tracing/process-argument capture. Resolving this upstream boundary without a core patch remains a release-hardening gate.

Only the backup public certificate is installed. Generate/retain its private key in an approved recovery secret store outside the management VM. Losing that key loses recovery access to the encrypted backups. Preflight checks certificate expiry but does not validate organizational key custody or revocation.

```bash
python3 tools/layersentry-management/install-rocky9.py \
  --config /run/layersentry/install.json --secrets /run/layersentry/secrets.json --action preflight
python3 tools/layersentry-management/install-rocky9.py \
  --config /run/layersentry/install.json --secrets /run/layersentry/secrets.json --action apply
```

Preflight verifies host identity/IP, Rocky 9, SELinux enforcing, active firewalld, certificate expiry, disk floor and configuration. Target packages and DB credentials/schema existence are checked during apply. It does not install prerequisite commands to make preflight pass: Python 3, dnf/rpm, OpenSSL, SELinux tools, curl, firewalld, tar and systemd must be present. It does not disable SELinux, open DB ports or change root SSH access. The requested Java, management and MySQL RPMs are exact; transitive distro dependency snapshot pinning remains a release-manifest gate. Repo trust roots must be independently reviewed; `gpgcheck=1` does not establish the identity of an arbitrary supplied key.

For combined mode, the installer initializes without a temporary password only when the datadir is a real, completely empty directory. It rejects symlinks, `lost+found`, and partial initialization. The first service startup disables TCP and MySQL X, applies the supplied root password from a temporary MySQL-owned file, verifies authenticated access, deletes that file, removes the bootstrap restrictions, and restarts normally on loopback. Failure stops and disables the fresh database service. An existing system schema is reused without initialization; an ambiguous datadir stops for inspection. Existing protected root credentials are not reset. The combined backup account is created with SELECT, SHOW VIEW, TRIGGER and EVENT on the two CloudStack databases and SHOW_ROUTINE globally; it cannot mutate CloudStack rows. External accounts need equivalent reviewed grants on the DB host.

## Checkpoint, resume, repair and recovery

The private state directory is `/var/lib/layersentry/installation`. An exclusive lock prevents two local installer runs. Before package/configuration mutation, a restricted tar checkpoint preserves configuration, packages and unit inventory. The JSON journal records configuration hash and stage transitions, without passwords. It is root-only and must not be uploaded as a support bundle with its adjacent secret-bearing checkpoint.

`resume` uses the same input configuration and skips applied stages. `repair` reapplies packages, management settings and backup services but does not initialize the database again. Changed config is rejected until a reviewed migration is planned. If database initialization started but did not journal a successful result, both actions stop: inspect native schema/config state before deciding whether to retain the initialized DB, repair a partial schema with supported recovery, or restore a disposable pre-action snapshot. There is no `--force-recreate` path.

The narrow `recover-database-bootstrap` action applies only when checkpoint and package stages are applied, the database stage is `in_progress`, MySQL is stopped, the native system schema and server identity exist, and the temporary bootstrap input is absent. It starts MySQL without TCP or MySQL X on a private recovery socket, distinguishes the supplied password from the fresh empty local account, and requires both CloudStack schemas to be absent. If the account is still empty it assigns and verifies the supplied password, then promotes normal loopback configuration and re-verifies authentication before clearing only the database-stage marker. Any mismatch leaves the marker intact and stops/disables MySQL. A fresh preflight and normal resume remain mandatory afterward; this action never recreates or deletes a schema.

Rollback is a **manual recovery procedure**, not an automatic package/database downgrade. After failure the script retains the journal and checkpoint and does not assume that a failed command had no side effects. Stop/drain the affected node, inspect the stage and exact host state, and restore only the reviewed configuration files from `checkpoint/configuration.tar` where compatible. Reconcile any new rich firewall rules against the saved firewall configuration, relabel with `restorecon`, reload systemd/firewalld and validate the node before rejoining. A database/schema rollback requires matching DB, configuration, encryption keys and software; package removal or config restoration alone is insufficient. Never restore the whole checkpoint blindly over live unrelated changes.

The installer does not build the LayerSentry UI. Production LayerSentry UI promotion remains the separate verified immutable-artifact flow.

## Automatic backup and restore checks

Apply starts and verifies the first backup service execution before enabling the persistent daily timer (02:00 host local time, up to 15 minutes jitter). Defaults retain the last 14 successful recovery points, with a minimum of two. `systemctl list-timers layersentry-db-backup.timer` and `systemctl status layersentry-db-backup.service` show scheduling/execution state; the backup manifest itself records restore validation as `NOT_TESTED`.

Backups are staged under root-only `/var/lib/layersentry/db-backups`, compressed, gzip-read checked, encrypted as CMS AES-256-CBC, and hashed before atomic publication. Payload and manifest files and their staging directory are fsynced; after rename, the parent directory is fsynced before retention can remove an older point. A failed dump does not publish a recovery point or prune successful backups. If publication-directory fsync fails, the newly visible point is not assumed durable and older points are retained. Retention removes only the two known files of this tool's verified expired directories. Plaintext exists in restricted temporary staging during backup/restore and is normally unlinked after use; this is not a forensic-erasure guarantee. Keep the storage volume encrypted where required. A local backup is not off-site protection.

```bash
python3 /usr/local/libexec/layersentry-db-backup verify --backup /var/lib/layersentry/db-backups/backup-IDENTIFIER
python3 /usr/local/libexec/layersentry-db-backup restore-check \
  --backup /secure-recovery/backup-IDENTIFIER \
  --target-defaults /run/recovery/disposable-mysql.cnf \
  --confirm-target-uuid TARGET-SERVER-UUID \
  --private-key /run/recovery/backup-private-key.pem
```

Restore-check is a destructive-to-target operation intended only for an empty disposable MySQL server. It refuses the source server UUID, requires explicit target UUID confirmation and refuses any preexisting application schemas. It imports the full native dump, checks both schemas and `cloud.version`, and runs mysqlcheck. The restored target remains for investigation/product startup checks and is not automatically deleted. These SQL/table checks are narrower than complete CloudStack recovery.

Database dumps do not include the management encryption key, db.properties, custom server configuration, UI artifact or OS. Escrow these separately through a protected configuration backup path, and test their recovery together. Binlogs are enabled with seven-day expiry in combined mode, but this tool does not ship/archive binlogs or implement PITR. Off-host replication, alert delivery, credential/key rotation, backup authenticity signatures, management-key escrow and repeated actual CloudStack restore remain production gates.

## Verification and next evidence gates

Local verification: 39 unit tests pass, including actual CMS encrypt/decrypt, successful-backup retention, corruption/path tampering, dump failure without publication, publication-directory fsync failure without retention, nontransactional rejection, restore source/nonempty-target rejection, stage idempotency, interrupted schema refusal, repository signature enforcement and secret/shell injection rejection. External-DB negative tests cover commented TLS/password fields, one-schema-only TLS, last-value overrides, URI redirects including escaped key names, TLS downgrades/duplicates, alternate endpoint composition and mismatched node IPs. Java-properties continuation/escape parsing and byte-preserving copying also pass. Existing management bootstrap tests remain passing. These are developer-environment tests, not Rocky live evidence; differential execution against Java and actual JDBC TLS remain live/CI gates.

Runner acceptance must bind exact source/RPMs/target and verify fresh installation; repeated apply; interrupted setup inspection; repair; service and host restart; firewall sources and denial cases; SELinux AVC review; authenticated API and Chrome/Firefox workflows; scheduled backups; latest and older recovery points into a disposable DB; matching management key/config restore; negative DB/cert/storage cases; off-host retention and measured backup/restore time. DB HA, KVM onboarding, Zone/storage/network setup, DR and production certification are outside this node installer evidence.
