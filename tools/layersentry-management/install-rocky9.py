#!/usr/bin/env python3
"""Guarded first-node orchestration; CloudStack owns database initialization."""
import argparse
import configparser
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from urllib.parse import parse_qsl

STATE = Path('/var/lib/layersentry/installation')
SCRIPT_DIR = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def private_file(name):
    path = Path(name)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
            and info.st_mode & 0o077 == 0, 'input must be an owner-only regular file')
    return path


def write_private(path, value, mode=0o600):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(not path.is_symlink(), 'refusing symlink destination')
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'wb' if isinstance(value, bytes) else 'w') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def run(argv, *, data=None, timeout=1800, env=None):
    # Native tools can include secrets and SQL in their errors. Do not emit them.
    result = subprocess.run(argv, input=data, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=timeout, env=env)
    if result.returncode:
        raise RuntimeError(Path(argv[0]).name + ' failed; output withheld to protect credentials')
    return result.stdout.strip()


def java_properties(content):
    """Read the effective Properties.load(InputStream) values without executing them.

    Handles Java separators, comments, continuations and escapes; duplicate keys
    use the last value. Callers decode bytes as ISO-8859-1, like Properties.load.
    """
    def unescape(value):
        result = []
        index = 0
        while index < len(value):
            character = value[index]
            index += 1
            if character == '\\':
                require(index < len(value), 'incomplete Java properties escape')
                character = value[index]
                index += 1
                if character == 'u':
                    digits = value[index:index + 4]
                    require(len(digits) == 4 and re.fullmatch('[0-9a-fA-F]{4}', digits),
                            'invalid Java properties Unicode escape')
                    character = chr(int(digits, 16))
                    index += 4
                else:
                    character = {'t': '\t', 'n': '\n', 'r': '\r', 'f': '\f'}.get(character, character)
            result.append(character)
        return ''.join(result)

    properties = {}
    pending = None
    for natural in re.split(r'\r\n|\r|\n', content):
        line = natural.lstrip(' \t\f')
        if pending is None and (not line or line.startswith(('#', '!'))):
            continue
        line = (pending or '') + line
        trailing = len(line) - len(line.rstrip('\\'))
        if trailing % 2:
            pending = line[:-1]
            continue
        pending = None
        index = 0
        while index < len(line):
            if line[index] == '\\':
                index += 2
            elif line[index] in '=:\t\f ':
                break
            else:
                index += 1
        key = unescape(line[:index])
        offset = index
        while offset < len(line) and line[offset] in ' \t\f':
            offset += 1
        if offset < len(line) and line[offset] in '=:':
            offset += 1
        while offset < len(line) and line[offset] in ' \t\f':
            offset += 1
        properties[key] = unescape(line[offset:])
    require(pending is None, 'incomplete Java properties continuation')
    return properties


def validate_external_properties(content, config):
    properties = java_properties(content)
    require(properties.get('cluster.node.IP') == config['management_ip'],
            'external configuration cluster.node.IP must match this management node')
    require(properties.get('db.ha.enabled', 'false').lower() == 'false',
            'external profile requires one endpoint; DB HA URI composition is not supported')
    tls = {'useSSL': 'true', 'requireSSL': 'true', 'verifyServerCertificate': 'true',
           'sslMode': 'VERIFY_IDENTITY'}
    allowed = set(tls) | {'serverTimezone', 'prepStmtCacheSize', 'cachePrepStmts', 'prepStmtCacheSqlLimit',
                          'sessionVariables', 'useUnicode', 'characterEncoding', 'zeroDateTimeBehavior',
                          'rewriteBatchedStatements'}
    for schema, database in (('cloud', 'cloud'), ('usage', 'cloud_usage')):
        prefix = 'db.' + schema + '.'
        require(prefix + 'uri' not in properties, 'external database URI overrides are not supported')
        require(properties.get(prefix + 'host') == config['db_host'], 'external database properties host mismatch')
        require(properties.get(prefix + 'driver') == 'jdbc:mysql'
                and properties.get(prefix + 'port') == '3306'
                and properties.get(prefix + 'name') == database,
                'external database driver/port/schema differs from supported endpoint')
        require(not properties.get(prefix + 'replicas', '').strip(), 'external database replica overrides are not supported')
        require(re.fullmatch(r'ENC\([^\r\n()]+\)', properties.get(prefix + 'password', '')),
                'both external database passwords must be encrypted')
        require(bool(properties.get(prefix + 'url.params')),
                'both external JDBC connections require explicit verified TLS settings')
        try:
            pairs = parse_qsl(properties.get(prefix + 'url.params', ''), keep_blank_values=True, strict_parsing=True)
        except ValueError:
            raise ValueError('invalid JDBC URL parameter syntax') from None
        keys = [key.casefold() for key, _ in pairs]
        require(len(keys) == len(set(keys)), 'duplicate JDBC URL parameters are not supported')
        parameters = dict(pairs)
        require(set(parameters) <= allowed, 'unreviewed JDBC URL parameter in external profile')
        require(all(parameters.get(key) == value for key, value in tls.items()),
                'both external JDBC connections require explicit verified TLS settings')


def validate(config, secrets):
    require(config.get('schema_version') == 1, 'unsupported configuration schema')
    require(config.get('mode') in ('combined', 'external'), 'mode must be combined or external')
    require(config.get('mode') != 'external' or config.get('initialize_database') is False,
            'external mode joins a provisioned database; initialize it on its own authorized DB host')
    for key, pattern in (
        ('management_package', r'cloudstack-management-4\.22\.1\.1-[A-Za-z0-9._+~]+\.(x86_64|noarch)'),
        ('java_package', r'java-17-openjdk-headless-[A-Za-z0-9._+~]+-[A-Za-z0-9._+~]+\.x86_64'),
        ('mysql_client_package', r'(mysql|mysql-community-client|percona-server-client)-8\.(0|4)\.[A-Za-z0-9._+~]+-[A-Za-z0-9._+~]+\.x86_64'),
    ):
        require(re.fullmatch(pattern, config.get(key, '')), 'exact supported NEVRA required: ' + key)
    require(config.get('mysql_series') in ('8.0', '8.4'), 'select researched mysql_series explicitly')
    require('-' + config['mysql_series'] + '.' in config['mysql_client_package'], 'MySQL series mismatch')
    if config['mode'] == 'combined':
        require(re.fullmatch(r'(mysql-server|mysql-community-server|percona-server-server)-'
                             + re.escape(config['mysql_series']) + r'\.[A-Za-z0-9._+~]+-[A-Za-z0-9._+~]+\.x86_64',
                             config.get('mysql_server_package', '')), 'exact MySQL server NEVRA required')
        require(config.get('db_host') == 'localhost', 'combined mode database must be localhost')
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', config.get('db_host', '')), 'invalid DB host')
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]{0,252}', config.get('hostname', '')), 'invalid hostname')
    require(config['hostname'] not in ('localhost', 'localhost.localdomain'), 'unique hostname required')
    ipaddress.IPv4Address(config['management_ip'])
    require(isinstance(config.get('initialize_database'), bool), 'initialize_database must be explicit boolean')
    require(config['mode'] != 'combined' or config['initialize_database'], 'combined mode initializes a fresh DB')
    require(config.get('backup_retention', 14) in range(2, 366), 'retention must be 2..365 successful backups')
    require(config.get('management_nodes', 1) in range(1, 11), 'management_nodes must be 1..10')
    require(config.get('backup_db_user', 'layersentry_backup') == 'layersentry_backup', 'dedicated layersentry_backup user required')
    for key in ('ui_cidr', 'agent_cidr'):
        network = ipaddress.IPv4Network(config[key], strict=True)
        require(network.prefixlen > 0, 'firewall source must not be all addresses')
    require(re.fullmatch(r'[A-Za-z0-9_-]+', config.get('firewall_zone', '')), 'firewall zone required')
    require(config.get('repo_files'), 'reviewed repository files required')
    for filename in config['repo_files']:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(private_file(filename).read_text())
        require(bool(parser.sections()), 'empty repository input')
        for section in parser.values():
            if section.name == 'DEFAULT':
                continue
            require(section.get('gpgcheck') == '1', 'every repository must verify RPM signatures')
            require(section.get('sslverify', '1') == '1', 'repository TLS verification required')
            require(section.get('baseurl', '').startswith('https://'), 'repository HTTPS baseurl required')
            require(bool(section.get('gpgkey')), 'repository trust key required')
    private_file(config['backup_recipient_certificate'])
    if not config['initialize_database']:
        db = private_file(config['db_properties_file']).read_bytes().decode('iso-8859-1')
        validate_external_properties(db, config)
        private_file(config['encryption_key_file'])
        private_file(config['db_tls_ca'])
    required = ['backup_db_password']
    if config['initialize_database']:
        required += ['db_password', 'db_admin_password', 'management_key', 'database_key']
    for name in required:
        value = secrets.get(name, '')
        # Native CloudStack 4.22.1.1 setup uses shell/SQL interpolation.
        require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_+=.-]{8,128}', value),
                'secret must be 8..128 safe characters: ' + name)
    return config


def mysql(defaults, sql):
    return run(['mysql', '--defaults-extra-file=' + str(defaults), '--batch', '--skip-column-names'], data=sql)


def defaults_file(path, host, user, password, ca=None):
    # Values are validated before this writer; no CLI password arguments.
    write_private(path, '[client]\nuser=' + user + '\npassword=' + password
                  + '\nhost=' + host + '\nconnect-timeout=15\n'
                  + ('ssl-mode=VERIFY_IDENTITY\nssl-ca=' + ca + '\n' if ca else ''))


def initialize_insecure_mysql_datadir(datadir=Path('/var/lib/mysql')):
    """Initialize only a demonstrably blank local datadir for immediate password rotation."""
    require(not datadir.is_symlink(), 'MySQL datadir must not be a symlink')
    if (datadir / 'mysql').is_dir():
        return False
    entries = {entry.name for entry in datadir.iterdir()} if datadir.exists() else set()
    require(not entries,
            'MySQL datadir is neither initialized nor empty; inspect it before recovery')
    run(['install', '-d', '-o', 'mysql', '-g', 'mysql', '-m', '0750', str(datadir)])
    run(['mysqld', '--no-defaults', '--initialize-insecure', '--user=mysql',
         '--datadir=' + str(datadir)])
    require((datadir / 'mysql').is_dir(), 'MySQL insecure initialization did not create system schema')
    return True


class Installer:
    def __init__(self, config, secrets):
        self.c, self.s = config, secrets
        self.fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        self.journal = {'schema_version': 1, 'config_sha256': self.fingerprint, 'stages': {}}
        self.path = STATE / 'journal.json'
        if self.path.exists():
            self.journal = json.loads(private_file(self.path).read_text())
            require(self.journal['config_sha256'] == self.fingerprint, 'configuration changed; review checkpoint before migration')

    def save(self):
        write_private(self.path, json.dumps(self.journal, indent=2) + '\n')

    def stage(self, name, function, repeat=False):
        previous = self.journal['stages'].get(name)
        if previous == 'applied' and not repeat:
            return
        require(not (name == 'database' and previous == 'in_progress'),
                'database initialization interrupted; inspect schema and checkpoint before manual recovery')
        self.journal['stages'][name] = 'in_progress'
        self.save()
        function()
        self.journal['stages'][name] = 'applied'
        self.save()

    def preflight(self):
        require(os.geteuid() == 0, 'run as root')
        for command in ('curl', 'dnf', 'firewall-cmd', 'getenforce', 'ip', 'openssl',
                        'restorecon', 'rpm', 'systemctl', 'tar'):
            require(shutil.which(command), 'required host command missing: ' + command)
        release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
        require(release.get('ID', '').strip('"') == 'rocky'
                and release.get('VERSION_ID', '').strip('"').split('.')[0] == '9', 'Rocky Linux 9 required')
        require(run(['getenforce']) == 'Enforcing', 'SELinux must remain enforcing')
        run(['systemctl', 'is-active', '--quiet', 'firewalld'])
        require(run(['hostname', '-s']) == self.c['hostname'].split('.')[0], 'hostname differs from planned target')
        addresses = json.loads(run(['ip', '-j', '-4', 'address', 'show']))
        require(any(a['local'] == self.c['management_ip'] for i in addresses for a in i.get('addr_info', [])),
                'management IP is not assigned to this host')
        require(shutil.disk_usage('/var').free >= 5 * 1024 ** 3, 'at least 5 GiB free required before installation')
        run(['openssl', 'x509', '-in', self.c['backup_recipient_certificate'], '-checkend', '2592000', '-noout'])
        run(['firewall-cmd', '--zone=' + self.c['firewall_zone'], '--list-all'])
        installed = subprocess.run(['rpm', '-q', '--qf', '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}', 'cloudstack-management'],
                                   capture_output=True, text=True, timeout=30)
        require(installed.returncode != 0 or installed.stdout == self.c['management_package'],
                'installed CloudStack release differs; use reviewed upgrade workflow')

    def checkpoint(self):
        checkpoint = STATE / 'checkpoint'
        checkpoint.mkdir(mode=0o700, exist_ok=True)
        paths = ['/etc/cloudstack/management', '/etc/my.cnf.d', '/etc/yum.repos.d', '/etc/firewalld']
        existing = [x for x in paths if Path(x).exists()]
        run(['tar', '--acls', '--xattrs', '--selinux', '-cpf', str(checkpoint / 'configuration.tar'), *existing])
        write_private(checkpoint / 'packages.txt', run(['rpm', '-qa']) + '\n')
        write_private(checkpoint / 'services.txt', run(['systemctl', 'list-unit-files', '--no-pager']) + '\n')

    def packages(self):
        for index, source in enumerate(self.c['repo_files']):
            write_private('/etc/yum.repos.d/layersentry-install-' + str(index) + '.repo', Path(source).read_text(), 0o644)
        packages = [self.c[x] for x in ('management_package', 'java_package', 'mysql_client_package')]
        if self.c['mode'] == 'combined':
            packages.append(self.c['mysql_server_package'])
        run(['dnf', '-y', '--setopt=install_weak_deps=False', '--setopt=*.gpgcheck=1', 'install', *packages])
        installed = run(['rpm', '-qa', '--qf', '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n']).splitlines()
        require(all(package in installed for package in packages), 'installed package identity mismatch')
        # Pin JAVA_HOME for the native setup subprocess; no global alternatives change.
        require(Path('/usr/lib/jvm/jre-17-openjdk/bin/java').exists(), 'Java 17 runtime path missing')

    def database(self):
        if not self.c['initialize_database']:
            return
        with tempfile.TemporaryDirectory(prefix='layersentry-db-', dir='/run') as temporary:
            auth = Path(temporary) / 'client.cnf'
            if self.c['mode'] == 'combined':
                mysql_config = ('[mysqld]\nbind-address=127.0.0.1\n'
                                'innodb_rollback_on_timeout=1\ninnodb_lock_wait_timeout=600\nmax_connections='
                                + str(350 * self.c.get('management_nodes', 1))
                                + '\nlog_bin=mysql-bin\nbinlog_format=ROW\nserver_id=1\n'
                                'binlog_expire_logs_seconds=604800\ndefault-time-zone=+00:00\n')
                fresh = initialize_insecure_mysql_datadir()
                bootstrap = Path('/run/layersentry-mysql-bootstrap.sql')
                if fresh:
                    write_private(bootstrap, "ALTER USER 'root'@'localhost' IDENTIFIED BY '"
                                  + self.s['db_admin_password'] + "';\n")
                    run(['chown', 'mysql:mysql', str(bootstrap)])
                    write_private('/etc/my.cnf.d/layersentry.cnf', mysql_config
                                  + 'skip_networking=ON\nmysqlx=OFF\ninit_file=' + str(bootstrap) + '\n', 0o644)
                else:
                    write_private('/etc/my.cnf.d/layersentry.cnf', mysql_config, 0o644)
                try:
                    run(['systemctl', 'enable', '--now', 'mysqld'])
                    run(['systemctl', 'restart', 'mysqld'])
                    if fresh:
                        defaults_file(auth, 'localhost', 'root', self.s['db_admin_password'])
                        require(mysql(auth, 'SELECT 1;') == '1', 'fresh database password verification failed')
                except Exception:
                    if fresh:
                        subprocess.run(['systemctl', 'disable', '--now', 'mysqld'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
                    raise
                finally:
                    if fresh:
                        bootstrap.unlink(missing_ok=True)
                if fresh:
                    write_private('/etc/my.cnf.d/layersentry.cnf', mysql_config, 0o644)
                    run(['systemctl', 'restart', 'mysqld'])
            defaults_file(auth, self.c['db_host'], 'root', self.s['db_admin_password'])
            try:
                version = mysql(auth, 'SELECT VERSION();')
            except RuntimeError:
                require(self.c['mode'] == 'combined', 'external DB administrator connection failed')
                defaults_file(auth, 'localhost', 'root', '')
                # Fresh distro MySQL socket bootstrap only; existing protected DB is never reset.
                require(mysql(auth, "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('cloud','cloud_usage');") == '0',
                        'existing CloudStack database detected; credentials will not be changed')
                mysql(auth, "ALTER USER 'root'@'localhost' IDENTIFIED BY '" + self.s['db_admin_password'] + "';")
                defaults_file(auth, 'localhost', 'root', self.s['db_admin_password'])
                version = mysql(auth, 'SELECT VERSION();')
            require(version.startswith(self.c['mysql_series'] + '.'), 'database server series mismatch')
            require(mysql(auth, "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('cloud','cloud_usage');") == '0',
                    'CloudStack schema already exists; use external join mode, never recreate')
            native = shutil.which('cloudstack-setup-databases')
            require(native, 'native CloudStack setup utility unavailable')
            env = os.environ.copy()
            env['PATH'] = '/usr/lib/jvm/jre-17-openjdk/bin:' + env.get('PATH', '')
            # runpy puts arguments in Python memory, keeping secrets off the wrapper OS argv.
            payload = {'path': native, 'args': ['cloud:' + self.s['db_password'] + '@' + self.c['db_host'],
                       '--deploy-as=root:' + self.s['db_admin_password'], '-e', 'file',
                       '-m', self.s['management_key'], '-k', self.s['database_key'],
                       '-i', self.c['management_ip']]}
            run([sys.executable, '-c', 'import json,runpy,sys; p=json.load(sys.stdin); sys.argv=[p["path"]]+p["args"]; runpy.run_path(p["path"],run_name="__main__")'],
                data=json.dumps(payload), env=env)

    def management(self):
        with tempfile.TemporaryDirectory(prefix='layersentry-config-', dir='/run') as temporary:
            db = Path(temporary) / 'db.properties'
            key = Path(temporary) / 'key'
            if self.c['initialize_database']:
                source_db, source_key = '/etc/cloudstack/management/db.properties', '/etc/cloudstack/management/key'
            else:
                source_db, source_key = self.c['db_properties_file'], self.c['encryption_key_file']
                auth = Path(temporary) / 'external-check.cnf'
                defaults_file(auth, self.c['db_host'], 'layersentry_backup', self.s['backup_db_password'], self.c['db_tls_ca'])
                require(mysql(auth, 'SELECT VERSION();').startswith(self.c['mysql_series'] + '.'),
                        'external database server series mismatch')
                require(mysql(auth, "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('cloud','cloud_usage');") == '2',
                        'external database schemas missing or inaccessible')
            write_private(db, Path(source_db).read_bytes())
            write_private(key, Path(source_key).read_text())
            # Preserve the existing node bootstrap's encrypted-config/permission contract;
            # firewall changes below are additionally scoped to operator-supplied CIDRs.
            for source, target in ((db, '/etc/cloudstack/management/db.properties'), (key, '/etc/cloudstack/management/key')):
                run(['install', '-o', 'root', '-g', 'cloud', '-m', '0640', str(source), target])
            rules = [(self.c['ui_cidr'], 8080), (self.c['agent_cidr'], 8250)]
            for cidr, port in rules:
                rule = 'rule family="ipv4" source address="' + cidr + '" port port="' + str(port) + '" protocol="tcp" accept'
                run(['firewall-cmd', '--permanent', '--zone=' + self.c['firewall_zone'], '--add-rich-rule=' + rule])
            run(['firewall-cmd', '--reload'])
            run(['cloudstack-setup-management', '--no-start'])
            write_private('/etc/systemd/system/cloudstack-management.service.d/layersentry-java17.conf',
                          '[Service]\nExecStart=\nExecStart=/usr/lib/jvm/jre-17-openjdk/bin/java $JAVA_DEBUG $JAVA_OPTS -cp $CLASSPATH $BOOTSTRAP_CLASS\n', 0o644)
            run(['systemctl', 'daemon-reload'])
            run(['restorecon', '-RF', '/etc/cloudstack/management'])
            run(['systemctl', 'enable', '--now', 'cloudstack-management'])
            run(['systemctl', 'restart', 'cloudstack-management'])
            deadline = time.monotonic() + 300
            while True:
                try:
                    run(['curl', '--fail', '--silent', '--max-time', '5', 'http://127.0.0.1:8080/client/'], timeout=10)
                    break
                except RuntimeError:
                    require(time.monotonic() < deadline, 'management startup timed out; inspect protected host logs')
                    time.sleep(5)
            run(['systemctl', 'is-active', '--quiet', 'cloudstack-management'])

    def backups(self):
        directory = Path('/etc/layersentry/db-backup')
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.c['mode'] == 'combined':
            with tempfile.TemporaryDirectory(prefix='layersentry-backup-user-', dir='/run') as temporary:
                admin = Path(temporary) / 'client.cnf'
                defaults_file(admin, 'localhost', 'root', self.s['db_admin_password'])
                mysql(admin, "CREATE USER IF NOT EXISTS 'layersentry_backup'@'localhost' IDENTIFIED BY '" + self.s['backup_db_password'] + "';\n"
                      "ALTER USER 'layersentry_backup'@'localhost' IDENTIFIED BY '" + self.s['backup_db_password'] + "';\n"
                      "GRANT SELECT, SHOW VIEW, TRIGGER, EVENT ON cloud.* TO 'layersentry_backup'@'localhost';\n"
                      "GRANT SELECT, SHOW VIEW, TRIGGER, EVENT ON cloud_usage.* TO 'layersentry_backup'@'localhost';\n"
                      "GRANT SHOW_ROUTINE ON *.* TO 'layersentry_backup'@'localhost';\n")
        ca = None
        if self.c['mode'] == 'external':
            ca = str(directory / 'ca.pem')
            write_private(ca, Path(self.c['db_tls_ca']).read_text())
        defaults_file(directory / 'client.cnf', self.c['db_host'], 'layersentry_backup', self.s['backup_db_password'], ca)
        write_private(directory / 'recipient.pem', Path(self.c['backup_recipient_certificate']).read_text())
        write_private(directory / 'config.json', json.dumps({'defaults_file': str(directory / 'client.cnf'),
                      'recipient_certificate': str(directory / 'recipient.pem'),
                      'directory': '/var/lib/layersentry/db-backups', 'retention': self.c.get('backup_retention', 14)}))
        run(['install', '-D', '-m', '0755', str(SCRIPT_DIR / 'db-backup.py'), '/usr/local/libexec/layersentry-db-backup'])
        write_private('/etc/systemd/system/layersentry-db-backup.service', '[Unit]\nDescription=LayerSentry encrypted CloudStack DB backup\nAfter=network-online.target\n\n'
                      '[Service]\nType=oneshot\nUMask=0077\nExecStart=/usr/bin/python3 /usr/local/libexec/layersentry-db-backup backup --config /etc/layersentry/db-backup/config.json\n'
                      'TimeoutStartSec=3600\nNice=10\nNoNewPrivileges=true\nPrivateTmp=true\nProtectHome=true\nProtectSystem=strict\n'
                      'ReadWritePaths=/var/lib/layersentry/db-backups\n', 0o644)
        write_private('/etc/systemd/system/layersentry-db-backup.timer', '[Unit]\nDescription=Daily LayerSentry database backup\n\n[Timer]\nOnCalendar=*-*-* 02:00:00\nPersistent=true\nRandomizedDelaySec=900\n\n[Install]\nWantedBy=timers.target\n', 0o644)
        Path('/var/lib/layersentry/db-backups').mkdir(mode=0o700, parents=True, exist_ok=True)
        run(['restorecon', '-RF', str(directory), '/usr/local/libexec/layersentry-db-backup', '/etc/systemd/system/layersentry-db-backup.service', '/etc/systemd/system/layersentry-db-backup.timer'])
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'start', 'layersentry-db-backup.service'], timeout=3700)
        run(['systemctl', 'enable', '--now', 'layersentry-db-backup.timer'])

    def apply(self, repair=False):
        self.stage('checkpoint', self.checkpoint)
        self.stage('packages', self.packages, repeat=repair)
        self.stage('database', self.database)
        self.stage('management', self.management, repeat=repair)
        self.stage('backups', self.backups, repeat=repair)
        require(run(['getenforce']) == 'Enforcing', 'SELinux enforcement changed during installation')
        run(['systemctl', 'is-active', '--quiet', 'firewalld'])
        print(json.dumps({'status': 'PARTIAL', 'installation_stages': self.journal['stages'],
                          'acceptance': 'Rocky API/browser/restart/restore acceptance required'}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--secrets', required=True)
    parser.add_argument('--action', choices=['preflight', 'apply', 'resume', 'repair', 'status'], default='preflight')
    args = parser.parse_args()
    os.umask(0o077)
    config = json.loads(private_file(args.config).read_text())
    secrets = json.loads(private_file(args.secrets).read_text())
    validate(config, secrets)
    if args.action == 'preflight':
        Installer(config, secrets).preflight()
        print('preflight passed; package availability and DB schema gate run during apply')
        return
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        installer = Installer(config, secrets)
        if args.action == 'status':
            print(json.dumps(installer.journal))
        else:
            installer.preflight()
            installer.apply(repair=args.action == 'repair')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print('installation stopped: ' + (str(error) if isinstance(error, (ValueError, RuntimeError)) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
