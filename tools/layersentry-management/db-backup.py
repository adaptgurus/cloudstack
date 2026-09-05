#!/usr/bin/env python3
"""Encrypted CloudStack logical backups and explicitly isolated restore checks."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid


def require(ok, message):
    if not ok:
        raise ValueError(message)


def private(name):
    path = Path(name)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid() and info.st_mode & 0o077 == 0,
            'backup input must be an owner-only regular file')
    return path


def command(argv, *, data=None, output=None):
    result = subprocess.run(argv, input=data, stdout=output if output else subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=3300)
    require(result.returncode == 0, Path(argv[0]).name + ' failed; credential-bearing diagnostics suppressed')
    return result.stdout.decode().strip() if result.stdout else ''


def query(defaults, sql):
    return command(['mysql', '--defaults-extra-file=' + str(private(defaults)), '--batch', '--skip-column-names'], data=sql.encode())


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def verify(directory):
    directory = Path(directory)
    require(not directory.is_symlink() and directory.is_dir(), 'invalid backup directory')
    manifest = json.loads(private(directory / 'manifest.json').read_text())
    require(manifest.get('schema_version') == 1, 'unsupported backup schema')
    require(manifest.get('file') == 'databases.sql.gz.cms', 'invalid payload filename')
    payload = private(directory / manifest['file'])
    require(payload.stat().st_size == manifest['bytes'] and digest(payload) == manifest['sha256'], 'backup integrity mismatch')
    return manifest


def backup(config):
    root = Path(config['directory'])
    require(root.is_absolute() and not root.is_symlink() and str(root) not in ('/', '/tmp', '/var', '/var/lib'), 'unsafe backup directory')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    require(root.stat().st_uid == os.geteuid() and root.stat().st_mode & 0o077 == 0, 'backup directory must be private')
    retention = config.get('retention', 14)
    require(type(retention) is int and 2 <= retention <= 365, 'retention must be 2..365')
    defaults = private(config['defaults_file'])
    certificate = private(config['recipient_certificate'])
    with (root / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        source_uuid = query(defaults, 'SELECT @@server_uuid;')
        uuid.UUID(source_uuid)
        require(query(defaults, "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('cloud','cloud_usage');") == '2', 'both CloudStack databases required')
        # Transactional consistency requires no DDL during dump; operator serializes upgrades.
        require(query(defaults, "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('cloud','cloud_usage') AND table_type='BASE TABLE' AND engine != 'InnoDB';") == '0', 'nontransactional table requires coordinated offline backup')
        estimate = int(query(defaults, "SELECT COALESCE(SUM(data_length+index_length),0) FROM information_schema.tables WHERE table_schema IN ('cloud','cloud_usage');"))
        require(shutil.disk_usage(root).free > max(1024 ** 3, estimate * 3), 'insufficient backup staging space')
        with tempfile.TemporaryDirectory(prefix='.pending-', dir=root) as temporary:
            staging = Path(temporary)
            raw = staging / 'databases.sql'
            with raw.open('wb') as output:
                command(['mysqldump', '--defaults-extra-file=' + str(defaults), '--single-transaction', '--quick',
                         '--routines', '--events', '--triggers', '--hex-blob', '--no-tablespaces',
                         '--set-gtid-purged=OFF', '--databases', 'cloud', 'cloud_usage'], output=output)
            require(raw.stat().st_size > 0, 'empty database dump')
            compressed = staging / 'databases.sql.gz'
            with raw.open('rb') as source, gzip.open(compressed, 'wb') as target:
                shutil.copyfileobj(source, target)
            raw.unlink()
            with gzip.open(compressed, 'rb') as stream:
                while stream.read(1024 * 1024):
                    pass
            payload = staging / 'databases.sql.gz.cms'
            command(['openssl', 'cms', '-encrypt', '-stream', '-binary', '-aes-256-cbc', '-in', str(compressed),
                     '-outform', 'DER', '-out', str(payload), str(certificate)])
            compressed.unlink()
            manifest = {'schema_version': 1, 'source_server_uuid': source_uuid, 'file': payload.name,
                        'sha256': digest(payload), 'bytes': payload.stat().st_size,
                        'consistency': 'single-transaction; no concurrent DDL permitted',
                        'restore_validation': 'NOT_TESTED', 'encryption': 'OpenSSL CMS AES-256-CBC',
                        'recipient_sha256': digest(certificate)}
            (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
            verify(staging)
            for path in (payload, staging / 'manifest.json'):
                with path.open('rb') as stream:
                    os.fsync(stream.fileno())
            final = root / ('backup-' + uuid.uuid4().hex)
            # Publish only after the encrypted payload and manifest have passed checks.
            os.rename(staging, final)
        retained = sorted((p for p in root.glob('backup-*') if p.is_dir() and not p.is_symlink()),
                          key=lambda p: p.stat().st_mtime, reverse=True)
        # Invalid backups never cause a valid older recovery point to be removed.
        valid = []
        for candidate in retained:
            try:
                verify(candidate)
                valid.append(candidate)
            except (ValueError, OSError, KeyError):
                continue
        for expired in valid[retention:]:
            require(expired.parent == root and expired.name.startswith('backup-'), 'retention target invalid')
            # Only remove this tool's two known files; unexpected contents fail closed.
            require({p.name for p in expired.iterdir()} == {'manifest.json', 'databases.sql.gz.cms'}, 'unexpected retention contents')
            (expired / 'databases.sql.gz.cms').unlink()
            (expired / 'manifest.json').unlink()
            expired.rmdir()
        print(json.dumps({'status': 'PARTIAL', 'backup': str(final), 'encrypted_digest_verified': True,
                          'restore_validation': 'NOT_TESTED'}))


def restore_check(args):
    manifest = verify(args.backup)
    target = private(args.target_defaults)
    target_uuid = query(target, 'SELECT @@server_uuid;')
    uuid.UUID(target_uuid)
    require(target_uuid != manifest['source_server_uuid'], 'cannot validate restore onto the source database')
    require(args.confirm_target_uuid == target_uuid, 'explicit disposable target UUID confirmation required')
    require(query(target, "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name NOT IN ('mysql','sys','performance_schema','information_schema');") == '0', 'restore target must have no application databases')
    # Contains CREATE DATABASE/USE and upstream routine definitions: only an empty,
    # operator-owned disposable server may consume the trusted recovery point.
    with tempfile.TemporaryDirectory(prefix='layersentry-restore-') as temporary:
        archive = Path(temporary) / 'restore.sql.gz'
        command(['openssl', 'cms', '-decrypt', '-binary', '-inform', 'DER', '-in', str(Path(args.backup) / manifest['file']),
                 '-inkey', str(private(args.private_key)), '-out', str(archive)])
        sql = Path(temporary) / 'restore.sql'
        with gzip.open(archive, 'rb') as source, sql.open('wb') as output:
            shutil.copyfileobj(source, output)
        with sql.open('rb') as source:
            result = subprocess.run(['mysql', '--defaults-extra-file=' + str(target)], stdin=source,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3300)
        require(result.returncode == 0, 'restore failed; disposable target retained for investigation')
    require(query(target, "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('cloud','cloud_usage');") == '2', 'restored schemas missing')
    require(int(query(target, 'SELECT COUNT(*) FROM cloud.version;')) > 0, 'restored CloudStack version rows missing')
    command(['mysqlcheck', '--defaults-extra-file=' + str(target), '--check', '--databases', 'cloud', 'cloud_usage'])
    print(json.dumps({'status': 'PARTIAL', 'restore_sql_and_table_checks': True,
                      'target_uuid': target_uuid, 'cleanup': 'restored disposable target retained',
                      'product_recovery': 'NOT_TESTED'}))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('backup').add_argument('--config', required=True)
    sub.add_parser('verify').add_argument('--backup', required=True)
    restore = sub.add_parser('restore-check')
    for field in ('backup', 'target-defaults', 'confirm-target-uuid', 'private-key'):
        restore.add_argument('--' + field, required=True)
    args = parser.parse_args()
    if args.action == 'backup':
        backup(json.loads(private(args.config).read_text()))
    elif args.action == 'verify':
        verify(args.backup)
        print('encrypted backup digest and size verified; authenticity and restore not implied')
    else:
        restore_check(args)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as error:
        print('backup stopped: ' + (str(error) if isinstance(error, ValueError) else type(error).__name__), file=sys.stderr)
        sys.exit(1)
