#!/usr/bin/python3 -I
"""Restricted HTTP-01 worker. Installed root-owned; never import application code."""
from __future__ import annotations

import contextlib
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import selectors
import signal
import socket
import ssl
import stat
import subprocess
import sys
import tempfile
import time


CONFIG = Path('/etc/telz/domain-ssl.json')
RUNTIME = Path('/var/lib/telz/domain-ssl/runtime.json')
CURRENT = Path('/var/lib/telz/current')
RELEASES = Path('/var/lib/telz/releases')
VHOSTS = Path('/etc/nginx/conf.d')
ACME = Path('/var/lib/telz/acme')
CERTIFICATES = Path('/etc/letsencrypt/live')
LOCK = Path('/run/lock/telz/maintenance.lock')
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': '/root', 'LANG': 'C.UTF-8'}
ERRORS = {'DNS_INVALID', 'DOMAIN_INELIGIBLE', 'CERTBOT_FAILED', 'NGINX_FAILED',
          'TLS_INVALID', 'WORKER_ERROR', 'LEASE_EXPIRED'}


class WorkerError(Exception):
    def __init__(self, code='WORKER_ERROR'):
        self.code = code if code in ERRORS else 'WORKER_ERROR'
        super().__init__(self.code)


def trusted(path: Path, *, directory=False, private=False):
    """No links or group/other writers; check each parent as well."""
    path = Path(path)
    if not path.is_absolute():
        raise WorkerError()
    for item in [*reversed(path.parents), path]:
        info = item.lstat()
        # Ubuntu intentionally exposes a sticky /run/lock. Its private child
        # remains root:root 0700; never permit this exception for another path.
        sticky_lock_root = (item == Path('/run/lock') and stat.S_ISDIR(info.st_mode)
                            and stat.S_IMODE(info.st_mode) == 0o1777)
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or (info.st_mode & 0o022 and not sticky_lock_root):
            raise WorkerError()
        if item != path and not stat.S_ISDIR(info.st_mode):
            raise WorkerError()
    info = path.stat()
    if directory and not stat.S_ISDIR(info.st_mode):
        raise WorkerError()
    if not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise WorkerError()
    if private and stat.S_IMODE(info.st_mode) != 0o600:
        raise WorkerError()
    return info


def hostname(value):
    if not isinstance(value, str) or len(value) > 253 or value != value.lower():
        raise WorkerError('DOMAIN_INELIGIBLE')
    labels = value.split('.')
    if len(labels) < 2 or any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', x)
                              for x in labels) or not re.fullmatch('[a-z]{2,63}|xn--[a-z0-9-]{2,59}', labels[-1]):
        raise WorkerError('DOMAIN_INELIGIBLE')
    return value


def email_address(value):
    if not isinstance(value, str) or len(value) > 254 or value.count('@') != 1:
        raise WorkerError('DOMAIN_INELIGIBLE')
    local, host = value.split('@')
    if len(local) > 64 or '..' in local or not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9._+%-]*[A-Za-z0-9])?', local):
        raise WorkerError('DOMAIN_INELIGIBLE')
    hostname(host)
    return value


def strict_json(raw, limit=8192):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise WorkerError()
            result[key] = value
        return result
    if len(raw.encode('utf-8')) > limit:
        raise WorkerError()
    return json.loads(raw, object_pairs_hook=object_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(WorkerError()))


def validate_config(config):
    """Shared by setup and the worker; reject all unknown configuration keys."""
    required = {'public_ips', 'service_user', 'install_dir', 'api_port', 'web_port'}
    if not isinstance(config, dict) or not required <= set(config) or set(config) - required - {'platform_hostnames'}:
        raise WorkerError()
    if not isinstance(config['public_ips'], list) or not 1 <= len(config['public_ips']) <= 32:
        raise WorkerError('DNS_INVALID')
    ips = []
    for value in config['public_ips']:
        if not isinstance(value, str):
            raise WorkerError('DNS_INVALID')
        ip = ipaddress.ip_address(value)
        if not ip.is_global or ip.is_multicast or ip.is_reserved:
            raise WorkerError('DNS_INVALID')
        ips.append(str(ip))
    config['public_ips'] = ips
    if not isinstance(config['service_user'], str) or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', config['service_user']) or config['service_user'] == 'root':
        raise WorkerError()
    if not isinstance(config['install_dir'], str) or not re.fullmatch(r'/opt/[a-zA-Z0-9_-]+', config['install_dir']):
        raise WorkerError()
    for key in ('api_port', 'web_port'):
        if type(config[key]) is not int or not 1024 <= config[key] <= 65535:
            raise WorkerError()
    if config['api_port'] == config['web_port']:
        raise WorkerError()
    if 'platform_hostnames' in config:
        if not isinstance(config['platform_hostnames'], list) or len(config['platform_hostnames']) > 100:
            raise WorkerError()
        config['platform_hostnames'] = sorted({hostname(value) for value in config['platform_hostnames']})
    return config


def read_config(path=CONFIG):
    trusted(path, private=True)
    # O_NOFOLLOW and fstat bind validation to the opened file.
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'r', encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
            raise WorkerError()
        config = strict_json(stream.read(8193))
    return validate_config(config)


def validate_dns(host, public_ips, resolver=socket.getaddrinfo):
    allowed = {ipaddress.ip_address(value) for value in public_ips}
    try:
        answers = resolver(host, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        addresses = {ipaddress.ip_address(item[4][0]) for item in answers}
    except (OSError, ValueError):
        raise WorkerError('DNS_INVALID') from None
    if not addresses or any(not ip.is_global or ip.is_multicast or ip.is_reserved or ip not in allowed for ip in addresses):
        raise WorkerError('DNS_INVALID')
    return addresses


def payload(value):
    if not isinstance(value, dict) or set(value) != {'job_id', 'lease_token', 'domain_id', 'tenant_id', 'hostname', 'email'}:
        raise WorkerError('DOMAIN_INELIGIBLE')
    for key in ('job_id', 'lease_token', 'domain_id', 'tenant_id'):
        if not isinstance(value[key], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value[key]):
            raise WorkerError('DOMAIN_INELIGIBLE')
    hostname(value['hostname'])
    email_address(value['email'])
    return value


def command(argv, *, input=None, cwd=None, timeout=60, code='WORKER_ERROR', allow_failure=False):
    """No inherited environment, shell or unbounded child output."""
    process = None
    try:
        trusted(Path(argv[0]).resolve(strict=True))
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, env=ENV, cwd=cwd,
                                   start_new_session=True)
        raw_input = (input or '').encode('utf-8')
        if len(raw_input) > 8192:
            raise WorkerError(code)
        process.stdin.write(raw_input)
        process.stdin.close()
        deadline = time.monotonic() + timeout
        output = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WorkerError(code)
                for key, _ in selector.select(min(remaining, 1)):
                    chunk = os.read(key.fileobj.fileno(), 4096)
                    if not chunk:
                        selector.unregister(key.fileobj)
                    else:
                        output.extend(chunk)
                        if len(output) > 65536:
                            raise WorkerError(code)
        if process.wait(timeout=max(0.01, deadline - time.monotonic())) and not allow_failure:
            raise WorkerError(code)
        return output.decode('utf-8')
    except (OSError, ValueError, subprocess.TimeoutExpired, WorkerError):
        raise WorkerError(code)
    finally:
        if process is not None:
            if process.poll() is None:
                # Kill the whole tree (runuser/backend or Certbot), not just its parent.
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            if process.stdout is not None:
                process.stdout.close()


def active_release():
    trusted(CURRENT.parent, directory=True)
    info = CURRENT.lstat()
    if not stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1:
        raise WorkerError()
    release = CURRENT.resolve(strict=True)
    if release.parent.parent != RELEASES or release.name != 'app' or not re.fullmatch('[0-9a-f]{40}', release.parent.name):
        raise WorkerError()
    trusted(release, directory=True)
    manifest_path = release / '.telz-release.json'
    trusted(manifest_path)
    try:
        with os.fdopen(os.open(manifest_path, os.O_RDONLY | os.O_NOFOLLOW), 'r', encoding='utf-8') as stream:
            manifest_info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(manifest_info.st_mode) or manifest_info.st_uid != 0
                    or manifest_info.st_nlink != 1 or manifest_info.st_mode & 0o022
                    or manifest_info.st_size > 8192):
                raise WorkerError()
            manifest = strict_json(stream.read(8193))
    except (OSError, ValueError):
        raise WorkerError() from None
    if (not isinstance(manifest, dict) or type(manifest.get('schema_version')) is not int or manifest.get('schema_version') != 2
            or manifest.get('status') != 'validated' or manifest.get('git_commit') != release.parent.name
            or not isinstance(manifest.get('alembic_revision'), str)
            or not re.fullmatch(r'[A-Za-z0-9_]{1,128}', manifest['alembic_revision'])):
        raise WorkerError()
    # Do not pin the migration name: future validated releases may advance it.
    # The worker adapter itself must belong to the same immutable release.
    trusted(release / 'backend/scripts/tenant_domain_ssl_queue.py')
    interpreter = release / '.venv/bin/python'
    trusted(interpreter.parent, directory=True)
    # Virtualenv interpreters normally link to the root-owned system Python.
    trusted(interpreter.resolve(strict=True))
    return release, interpreter


def queue(config, operation, data=None):
    if operation not in {'claim', 'validate', 'complete', 'fail', 'reconcile', 'heartbeat'}:
        raise WorkerError()
    release, interpreter = active_release()
    argv = ['/usr/sbin/runuser', '-u', config['service_user'], '--', '/usr/bin/env', '-i',
            'PATH=/usr/sbin:/usr/bin:/sbin:/bin', 'HOME=/nonexistent',
            f'TELZ_PROJECT_ROOT={config["install_dir"]}', 'PYTHONNOUSERSITE=1',
            'PYTHONDONTWRITEBYTECODE=1', 'TENANT_DOMAIN_SSL_ENABLED=true',
            'TENANT_DOMAIN_SSL_MODE=manual',
            'TENANT_DOMAIN_SSL_PUBLIC_IPS=' + ','.join(config['public_ips'])]
    if 'platform_hostnames' in config:
        argv.append('TENANT_DOMAINS_PLATFORM_HOSTNAMES=' + ','.join(config['platform_hostnames']))
    argv.extend([str(interpreter), '-m', 'backend.scripts.tenant_domain_ssl_queue', operation])
    raw = command(argv, input=json.dumps(data or {}), cwd=release, timeout=120, allow_failure=True)
    try:
        value = strict_json(raw)
        if isinstance(value, dict) and ('error' in value or 'error_code' in value):
            raise WorkerError(value.get('error_code', 'WORKER_ERROR'))
        if operation == 'heartbeat' and value != {'status': 'ready'}:
            raise WorkerError()
        if operation in {'claim', 'validate'} and not (operation == 'claim' and value is None):
            payload(value)
        elif operation == 'reconcile':
            if not isinstance(value, dict) or set(value) != {'reconciled', 'refreshed'} or any(
                    type(number) is not int or not 0 <= number <= 100 for number in value.values()):
                raise WorkerError()
        elif operation in {'complete', 'fail'}:
            if not isinstance(value, dict) or not {'domain_id', 'hostname', 'ssl_status'} <= value.keys():
                raise WorkerError()
        return value
    except (ValueError, TypeError):
        raise WorkerError() from None


@contextlib.contextmanager
def maintenance_lock():
    import fcntl
    trusted(LOCK.parent, directory=True)
    if stat.S_IMODE(LOCK.parent.stat().st_mode) != 0o700:
        raise WorkerError()
    fd = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1:
            raise WorkerError()
        if os.environ.get('TELZ_MAINTENANCE_LOCK_HELD') == 'true':
            inherited = os.fstat(9)
            if (inherited.st_dev, inherited.st_ino) != (info.st_dev, info.st_ino) or inherited.st_uid != 0 or stat.S_IMODE(inherited.st_mode) != 0o600 or inherited.st_nlink != 1:
                raise WorkerError()
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                # Also prove descriptor 9 owns it, rather than a third process.
                fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)
                yield True
                return
            raise WorkerError()  # Environment alone can never bypass the lock.
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        os.close(fd)


def atomic_write(path, data, mode=0o644):
    trusted(path.parent, directory=True)
    if path.exists() or path.is_symlink():
        trusted(path)
    fd, temporary = tempfile.mkstemp(prefix='.telz-domain-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def ensure_directory(path, mode=0o755):
    """Bootstrap only. Never follow links or relax an existing private directory."""
    missing = []
    cursor = path
    while not cursor.exists() and not cursor.is_symlink():
        missing.append(cursor)
        cursor = cursor.parent
    trusted(cursor, directory=True)
    for directory in reversed(missing):
        directory.mkdir(mode=mode if directory == path else 0o755)
        os.chown(directory, 0, 0)
        os.chmod(directory, mode if directory == path else 0o755)
        trusted(directory, directory=True)
    trusted(path, directory=True)
    if mode == 0o700 and stat.S_IMODE(path.stat().st_mode) != mode:
        raise WorkerError()


def cert_paths(cert_name):
    directory = CERTIFICATES / cert_name
    paths = (directory / 'fullchain.pem', directory / 'privkey.pem')
    for path in paths:
        trusted(path.parent, directory=True)
        info = path.lstat()
        if not stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1:
            raise WorkerError('TLS_INVALID')
        target = path.resolve(strict=True)
        if target.parent != Path('/etc/letsencrypt/archive') / cert_name:
            raise WorkerError('TLS_INVALID')
        trusted(target)
    return paths


def vhost(config, host, cert_name, tls=False):
    # All interpolated values are canonical hosts, validated ports or hash paths.
    common = f'''
    client_max_body_size 30m;
    location ^~ /.well-known/acme-challenge/ {{ root {ACME}; try_files $uri =404; }}
    location /api/ {{
        proxy_pass http://127.0.0.1:{config['api_port']};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    location /health {{
        proxy_pass http://127.0.0.1:{config['api_port']}/health;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
    }}
    location / {{
        proxy_pass http://127.0.0.1:{config['web_port']};
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
'''
    http = common if not tls else f'''
    location ^~ /.well-known/acme-challenge/ {{ root {ACME}; try_files $uri =404; }}
    location / {{ return 308 https://$host$request_uri; }}
'''
    text = f'# Managed by telz-domain-ssl; hostname {host}\nserver {{\n    listen 80;\n    listen [::]:80;\n    server_name {host};\n{http}}}\n'
    if tls:
        chain, key = cert_paths(cert_name)
        text += f'''server {{
    listen 443 ssl;
    listen [::]:443 ssl;
    server_name {host};
    ssl_certificate {chain};
    ssl_certificate_key {key};
    ssl_protocols TLSv1.2 TLSv1.3;
{common}}}
'''
    return text.encode('utf-8')


def nginx_reload():
    command(['/usr/sbin/nginx', '-t'], code='NGINX_FAILED')
    command(['/usr/bin/systemctl', 'reload', 'nginx'], code='NGINX_FAILED')


def probe_tls(host, addresses):
    # Reload sends a signal; new workers may not serve the certificate yet.
    # Every retry must approve all advertised destinations within one budget.
    addresses = tuple(addresses)
    if not addresses:
        raise WorkerError('TLS_INVALID')
    context = ssl.create_default_context()
    deadline = time.monotonic() + 45
    while True:
        try:
            for address in addresses:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise WorkerError('TLS_INVALID')
                with socket.create_connection((str(address), 443), timeout=min(10, remaining)) as connection:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise WorkerError('TLS_INVALID')
                    connection.settimeout(min(10, remaining))
                    with context.wrap_socket(connection, server_hostname=host):
                        pass
                if time.monotonic() >= deadline:
                    raise WorkerError('TLS_INVALID')
            return
        except (OSError, ssl.SSLError):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WorkerError('TLS_INVALID') from None
            time.sleep(min(1, remaining))


def process_job(config, job, *, q=queue, dns=validate_dns, reload=nginx_reload,
                probe=probe_tls, execute=command):
    job = payload(job)
    identity = {key: job[key] for key in ('job_id', 'lease_token')}
    name = 'telz-domain-' + hashlib.sha256(job['hostname'].encode('ascii')).hexdigest()
    path = VHOSTS / (name + '.conf')
    previous = None
    mode = 0o644
    mutated = False
    try:
        if job['hostname'] in config.get('platform_hostnames', []):
            raise WorkerError('DOMAIN_INELIGIBLE')
        if payload(q(config, 'validate', identity)) != job:
            raise WorkerError('DOMAIN_INELIGIBLE')
        dns(job['hostname'], config['public_ips'])
        trusted(VHOSTS, directory=True)
        trusted(ACME, directory=True)
        if path.exists() or path.is_symlink():
            info = trusted(path)
            previous, mode = path.read_bytes(), stat.S_IMODE(info.st_mode)
        # Keep an existing dedicated TLS block serving during issuance.
        if previous is None:
            atomic_write(path, vhost(config, job['hostname'], name))
            mutated = True
            reload()
        execute(['/usr/bin/certbot', 'certonly', '--webroot', '-w', str(ACME),
                 '--cert-name', name, '--non-interactive', '--agree-tos',
                 '--no-directory-hooks', '--email', job['email'], '-d', job['hostname']],
                timeout=240, code='CERTBOT_FAILED')
        if payload(q(config, 'validate', identity)) != job:
            raise WorkerError('DOMAIN_INELIGIBLE')
        addresses = dns(job['hostname'], config['public_ips'])
        atomic_write(path, vhost(config, job['hostname'], name, tls=True))
        mutated = True
        reload()
        probe(job['hostname'], addresses)
        if payload(q(config, 'validate', identity)) != job:
            raise WorkerError('DOMAIN_INELIGIBLE')
        dns(job['hostname'], config['public_ips'])
        result = q(config, 'complete', identity)
        if not isinstance(result, dict) or result.get('domain_id') != job['domain_id'] or result.get('hostname') != job['hostname'] or result.get('ssl_status') != 'active':
            raise WorkerError()
        return {'status': 'completed'}
    except Exception as exc:
        code = exc.code if isinstance(exc, WorkerError) else 'WORKER_ERROR'
        if mutated:
            try:
                if previous is None:
                    trusted(path)
                    path.unlink()
                else:
                    atomic_write(path, previous, mode)
                reload()
            except Exception:
                code = 'NGINX_FAILED'
        try:
            q(config, 'fail', {**identity, 'error_code': code})
        except Exception:
            pass
        return {'status': 'failed', 'error_code': code}


def discover_public_ips(execute=command):
    raw = execute(['/usr/sbin/ip', '-j', 'address', 'show', 'scope', 'global'])
    rows = strict_json(raw, limit=65536)
    if not isinstance(rows, list) or len(rows) > 1024:
        raise WorkerError('DNS_INVALID')
    addresses = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('ifname'), str):
            raise WorkerError('DNS_INVALID')
        name = row['ifname']
        if not isinstance(row.get('flags'), list) or 'UP' not in row['flags']:
            continue
        kind = row.get('linkinfo', {}).get('info_kind', '')
        if name.startswith(('lo', 'docker', 'veth', 'virbr', 'br-', 'tun', 'tap', 'wg')) or kind in {'bridge', 'veth', 'tun', 'wireguard', 'dummy'}:
            continue
        for item in row.get('addr_info', []):
            if not isinstance(item, dict) or item.get('scope') != 'global':
                continue
            rejected = {'temporary', 'deprecated', 'tentative', 'dadfailed'}
            flags = item.get('flags', [])
            if not isinstance(flags, list) or rejected.intersection(flags) or any(item.get(flag) for flag in rejected) or item.get('preferred_life_time') == 0:
                continue
            try:
                ip = ipaddress.ip_address(item['local'])
            except (KeyError, ValueError, TypeError):
                raise WorkerError('DNS_INVALID') from None
            if ip.is_global and not ip.is_multicast and not ip.is_reserved:
                addresses.add(str(ip))
    return sorted(addresses)


def publish_runtime(config=None, *, ready=False, reason='setup_required'):
    reasons = {'setup_required', 'disabled', 'invalid_runtime', 'missing_public_ip',
               'missing_platform_hosts', 'preflight_failed', 'release_unavailable', 'worker_unavailable'}
    if type(ready) is not bool or (ready and reason is not None) or (not ready and reason not in reasons):
        raise WorkerError()
    ensure_directory(RUNTIME.parent)
    value = {'schema_version': 1, 'ready': ready, 'public_ips': (config or {}).get('public_ips', []),
             'platform_hostnames': (config or {}).get('platform_hostnames', []), 'reason': reason,
             'updated_at': datetime.now(timezone.utc).isoformat()}
    atomic_write(RUNTIME, (json.dumps(value, sort_keys=True) + '\n').encode(), 0o644)


def bootstrap_config(args, *, discover=discover_public_ips):
    hosts = sorted({hostname(value.strip()) for value in args.platform_hostnames.split(',') if value.strip()})
    identity = {'service_user': args.service_user, 'install_dir': args.install_dir,
                'api_port': args.api_port, 'web_port': args.web_port}
    if CONFIG.exists() or CONFIG.is_symlink():
        config = read_config()
        if any(config[key] != value for key, value in identity.items()):
            raise WorkerError()
        hosts = sorted(set(hosts) | set(config.get('platform_hostnames', [])))
    else:
        ips = [value.strip() for value in args.public_ips.split(',') if value.strip()] if args.public_ips else discover()
        if not ips:
            return {**identity, 'public_ips': [], 'platform_hostnames': hosts}, 'missing_public_ip'
        config = {**identity, 'public_ips': ips}
    config['platform_hostnames'] = hosts
    config = validate_config(config)
    return config, None if hosts else 'missing_platform_hosts'


def bootstrap(args):
    config = None
    reason = 'preflight_failed'
    ensure_directory(LOCK.parent, 0o700)
    with maintenance_lock() as acquired:
        if not acquired:
            raise WorkerError()
        publish_runtime(reason='setup_required')
        try:
            config, problem = bootstrap_config(args)
            if problem:
                reason = problem
                raise WorkerError()
            import pwd
            if pwd.getpwnam(config['service_user']).pw_uid == 0:
                raise WorkerError()
            reason = 'release_unavailable'
            active_release()
            reason = 'preflight_failed'
            for directory in (CONFIG.parent, VHOSTS, ACME, Path('/etc/letsencrypt'),
                              Path('/var/lib/letsencrypt'), Path('/var/log/letsencrypt'), Path('/var/log/nginx')):
                ensure_directory(directory)
            ensure_certbot()
            atomic_write(CONFIG, (json.dumps(config, sort_keys=True) + '\n').encode(), 0o600)
            command(['/usr/sbin/nginx', '-t'], code='NGINX_FAILED')
            command(['/usr/bin/systemctl', 'enable', '--now', 'certbot.timer', 'telz-domain-ssl.timer'])
            reason = 'worker_unavailable'
            if queue(config, 'heartbeat') != {'status': 'ready'}:
                raise WorkerError()
            publish_runtime(config, ready=True, reason=None)
            return {'status': 'ready'}
        except Exception:
            publish_runtime(config, reason=reason)
            raise


def ensure_certbot():
    if not Path('/usr/bin/certbot').exists():
        command(['/usr/bin/apt-get', 'install', '-y', '--no-install-recommends', 'certbot'], timeout=600)
    trusted(Path('/usr/bin/certbot').resolve(strict=True))


def bootstrap_arguments(argv):
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('--bootstrap', action='store_true', required=True)
    parser.add_argument('--service-user', required=True)
    parser.add_argument('--install-dir', required=True)
    parser.add_argument('--api-port', type=int, required=True)
    parser.add_argument('--web-port', type=int, required=True)
    parser.add_argument('--platform-hostnames', required=True)
    parser.add_argument('--public-ips', default='')
    return parser.parse_args(argv)


def main():
    try:
        if os.geteuid() != 0:
            raise WorkerError()
        trusted(Path(__file__).absolute())
        if '--bootstrap' in sys.argv[1:]:
            result = bootstrap(bootstrap_arguments(sys.argv[1:]))
            print(json.dumps(result))
            return 0
        configuring = sys.argv[1:] == ['--configure']
        config = validate_config(strict_json(sys.stdin.read(8193))) if configuring else read_config()
        import pwd
        if pwd.getpwnam(config['service_user']).pw_uid == 0:
            raise WorkerError()
        # Commands are chosen by this file alone; never by queue output.
        for executable in ('/usr/sbin/runuser', '/usr/bin/env', '/usr/sbin/nginx',
                           '/usr/bin/certbot', '/usr/bin/systemctl'):
            trusted(Path(executable).resolve(strict=True))
        active_release()
        if configuring:
            for directory in (CONFIG.parent, VHOSTS, ACME, Path('/etc/letsencrypt'),
                              Path('/var/lib/letsencrypt'), Path('/var/log/letsencrypt'),
                              Path('/var/log/nginx')):
                ensure_directory(directory)
            ensure_directory(LOCK.parent, 0o700)
            with maintenance_lock() as acquired:
                if not acquired:
                    raise WorkerError()
                atomic_write(CONFIG, (json.dumps(config, sort_keys=True) + '\n').encode('utf-8'), 0o600)
            print(json.dumps({'status': 'configured'}))
            return 0
        if sys.argv[1:] == ['--check-config']:
            print(json.dumps({'status': 'config_valid'}))
            return 0
        if sys.argv[1:]:
            raise WorkerError()
        with maintenance_lock() as acquired:
            if not acquired:
                print(json.dumps({'status': 'busy'}))
                return 0
            queue(config, 'reconcile')
            job = queue(config, 'claim')
            result = {'status': 'idle'} if job is None else process_job(config, job)
            print(json.dumps(result))
            return 0 if result['status'] != 'failed' else 1
    except Exception:
        print(json.dumps({'status': 'failed', 'error_code': 'WORKER_ERROR'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
