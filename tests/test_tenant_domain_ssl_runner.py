import importlib.util
import ipaddress
from pathlib import Path
import socket
import stat
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tenant_domain_ssl_runner', ROOT / 'scripts/tenant-domain-ssl.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


@pytest.fixture
def config():
    return {'public_ips': ['8.8.8.8'], 'service_user': 'telz', 'install_dir': '/opt/telz',
            'api_port': 8000, 'web_port': 3000}


@pytest.fixture
def job():
    return {'job_id': 'job-123', 'lease_token': 'secret_lease-123', 'domain_id': 'domain-123',
            'tenant_id': 'tenant-123', 'hostname': 'pizza.example.com', 'email': 'ops@example.com'}


@pytest.mark.parametrize('host', ['example.com;id', '-d.example.com', '*.example.com',
                                 'example.com\nserver {}', 'https://example.com',
                                 'EXAMPLE.com', 'example.com.', 'example..com',
                                 'localhost', '127.0.0.1', 'tést.example.com'])
def test_hostname_rejects_nginx_and_argv_injection(host):
    with pytest.raises(worker.WorkerError):
        worker.hostname(host)


@pytest.mark.parametrize('email', ['--config=/tmp/x', 'ops@example.com\n-d attacker.com',
                                  'a@b@example.com', 'user name@example.com'])
def test_email_rejects_control_characters_and_options(email):
    with pytest.raises(worker.WorkerError):
        worker.email_address(email)


@pytest.mark.parametrize('patch', [{'unknown': 'value'}, {'service_user': 'root'},
                                 {'install_dir': '/opt/telz/../../etc'}, {'api_port': True},
                                 {'public_ips': ['127.0.0.1']}, {'public_ips': ['224.0.0.1']}])
def test_configuration_is_strict_and_public_only(config, patch):
    with pytest.raises((worker.WorkerError, ValueError)):
        worker.validate_config({**config, **patch})


@pytest.mark.parametrize('raw', ['{"api_port":8000,"api_port":9000}', '{"x": NaN}', ' ' * 8193])
def test_protocol_rejects_duplicates_constants_and_oversize(raw):
    with pytest.raises(worker.WorkerError):
        worker.strict_json(raw)


def resolver(addresses):
    return lambda *args: [(socket.AF_INET6 if ':' in ip else socket.AF_INET,
                          socket.SOCK_STREAM, 6, '', (ip, 443)) for ip in addresses]


def test_dns_requires_every_a_and_aaaa_to_be_authorized():
    with pytest.raises(worker.WorkerError, match='DNS_INVALID'):
        worker.validate_dns('pizza.example.com', ['8.8.8.8'], resolver(['8.8.8.8', '2606:4700:4700::1111']))
    with pytest.raises(worker.WorkerError, match='DNS_INVALID'):
        worker.validate_dns('pizza.example.com', ['8.8.8.8'], resolver(['8.8.8.8', '127.0.0.1']))
    assert worker.validate_dns('pizza.example.com', ['8.8.8.8'], resolver(['8.8.8.8'])) == {ipaddress.ip_address('8.8.8.8')}


def test_trusted_path_rejects_symlink_hardlink_and_writable_parents():
    class FakePath:
        def __init__(self, info, parents=()):
            self.info, self.parents = info, parents
        def is_absolute(self):
            return True
        def lstat(self):
            return self.info
        stat = lstat
    def info(mode=stat.S_IFREG | 0o644, uid=0, links=1):
        return SimpleNamespace(st_mode=mode, st_uid=uid, st_nlink=links)
    original = worker.Path
    try:
        worker.Path = lambda value: value
        for path in [FakePath(info(stat.S_IFLNK | 0o777)), FakePath(info(links=2)),
                     FakePath(info(uid=1000)),
                     FakePath(info(), [FakePath(info(stat.S_IFDIR | 0o777))])]:
            with pytest.raises(worker.WorkerError):
                worker.trusted(path)
    finally:
        worker.Path = original


@pytest.mark.parametrize('target', ['runner', 'renew-hook'])
def test_only_exact_sticky_run_lock_is_permitted_with_private_child(monkeypatch, target):
    module = worker
    if target == 'renew-hook':
        import sys
        monkeypatch.setitem(sys.modules, 'fcntl', SimpleNamespace())
        spec = importlib.util.spec_from_file_location('ssl_hook_paths', ROOT / 'scripts/tenant-domain-ssl-renew-hook.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    class FakePath:
        def __init__(self, name, mode, parents=()):
            self.name, self.parents = name, parents
            self.info = SimpleNamespace(st_mode=mode, st_uid=0, st_nlink=1)
        def is_absolute(self):
            return True
        def lstat(self):
            return self.info
        stat = lstat
        def __eq__(self, other):
            return self.name == (other.name if isinstance(other, FakePath) else other)
    monkeypatch.setattr(module, 'Path', lambda value: value)
    root = FakePath('/run/lock', stat.S_IFDIR | 0o1777)
    child = FakePath('/run/lock/telz', stat.S_IFDIR | 0o700, [root])
    module.trusted(child, directory=True)
    for mode in (stat.S_IFDIR | 0o777, stat.S_IFLNK | 0o777):
        with pytest.raises((worker.WorkerError, ValueError)):
            module.trusted(FakePath('/run/lock/telz', mode, [root]), directory=True)
    with pytest.raises((worker.WorkerError, ValueError)):
        module.trusted(FakePath('/tmp/worker', stat.S_IFDIR | 0o700,
                               [FakePath('/tmp', stat.S_IFDIR | 0o1777)]), directory=True)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    vhosts, acme = tmp_path / 'nginx', tmp_path / 'acme'
    vhosts.mkdir()
    acme.mkdir()
    monkeypatch.setattr(worker, 'VHOSTS', vhosts)
    monkeypatch.setattr(worker, 'ACME', acme)
    monkeypatch.setattr(worker, 'trusted', lambda *args, **kwargs: SimpleNamespace(st_mode=0o640))
    # Ownership and permissions are tested separately; transaction tests use local files.
    monkeypatch.setattr(worker.os, 'fchmod', lambda *args: None, raising=False)
    monkeypatch.setattr(worker, 'cert_paths', lambda name: (Path('/safe/fullchain.pem'), Path('/safe/privkey.pem')))
    return vhosts


def callbacks(job):
    operations = []
    def queue(config, operation, data):
        operations.append((operation, data))
        return dict(job) if operation == 'validate' else {
            'domain_id': job['domain_id'], 'hostname': job['hostname'], 'ssl_status': 'active'}
    return operations, queue


def test_success_uses_bound_job_and_shell_free_certbot(sandbox, config, job):
    operations, queue = callbacks(job)
    commands, reloads, probes = [], [], []
    result = worker.process_job(config, job, q=queue,
        dns=lambda *args: {'8.8.8.8'}, reload=lambda: reloads.append(True),
        probe=lambda *args: probes.append(args), execute=lambda argv, **kwargs: commands.append((argv, kwargs)))
    assert result == {'status': 'completed'}
    assert [item[0] for item in operations] == ['validate', 'validate', 'validate', 'complete']
    assert len(reloads) == 2 and len(probes) == 1
    argv, kwargs = commands[0]
    assert argv[:3] == ['/usr/bin/certbot', 'certonly', '--webroot']
    assert '--no-directory-hooks' in argv and '--nginx' not in argv
    assert argv[-2:] == ['-d', job['hostname']]
    content = next(sandbox.iterdir()).read_text()
    assert 'listen 443 ssl;' in content and 'proxy_set_header Host $host;' in content
    http = content.split('listen 443 ssl;', 1)[0]
    assert 'return 308 https://$host$request_uri;' in http
    assert 'location ^~ /.well-known/acme-challenge/' in http
    assert 'proxy_pass' not in http


@pytest.mark.parametrize('failure_stage', ['issue', 'dns_after_issue', 'reload', 'tls', 'complete'])
def test_failure_restores_previous_vhost_exactly(sandbox, config, job, failure_stage):
    import hashlib
    path = sandbox / ('telz-domain-' + hashlib.sha256(job['hostname'].encode()).hexdigest() + '.conf')
    original = b'# Previous active TLS configuration\nserver { listen 443 ssl; }\n'
    path.write_bytes(original)
    operations, base_queue = callbacks(job)
    def queue(config, operation, data):
        if operation == 'complete' and failure_stage == 'complete':
            raise worker.WorkerError('DOMAIN_INELIGIBLE')
        return base_queue(config, operation, data)
    calls = {'dns': 0, 'reload': 0}
    def dns(*args):
        calls['dns'] += 1
        if failure_stage == 'dns_after_issue' and calls['dns'] == 2:
            raise worker.WorkerError('DNS_INVALID')
        return {'8.8.8.8'}
    def reload():
        calls['reload'] += 1
        if failure_stage == 'reload' and calls['reload'] == 1:
            raise worker.WorkerError('NGINX_FAILED')
    def issue(*args, **kwargs):
        if failure_stage == 'issue':
            raise worker.WorkerError('CERTBOT_FAILED')
    def probe(*args):
        if failure_stage == 'tls':
            raise worker.WorkerError('TLS_INVALID')
    result = worker.process_job(config, job, q=queue, dns=dns, reload=reload, probe=probe, execute=issue)
    assert result['status'] == 'failed'
    assert path.read_bytes() == original
    assert operations[-1][0] == 'fail'
    assert operations[-1][1]['error_code'] in worker.ERRORS


def test_lease_reassignment_after_issuance_removes_new_vhost(sandbox, config, job):
    operations, base_queue = callbacks(job)
    validations = 0
    def queue(config, operation, data):
        nonlocal validations
        result = base_queue(config, operation, data)
        if operation == 'validate':
            validations += 1
            if validations == 2:
                result['tenant_id'] = 'other-tenant'
        return result
    result = worker.process_job(config, job, q=queue, dns=lambda *args: {'8.8.8.8'},
        reload=lambda: None, probe=lambda *args: None, execute=lambda *args, **kwargs: None)
    assert result == {'status': 'failed', 'error_code': 'DOMAIN_INELIGIBLE'}
    assert not list(sandbox.iterdir())
    assert not any(operation == 'complete' for operation, _ in operations)


def test_backend_adapter_runs_only_as_service_user_without_inherited_env(monkeypatch, config, job):
    monkeypatch.setattr(worker, 'active_release', lambda: (Path('/release/app'), Path('/release/app/.venv/bin/python')))
    recorded = []
    def command(argv, **kwargs):
        recorded.append((argv, kwargs))
        import json
        return json.dumps(job)
    monkeypatch.setattr(worker, 'command', command)
    assert worker.queue(config, 'claim') == job
    argv, kwargs = recorded[0]
    assert argv[:6] == ['/usr/sbin/runuser', '-u', 'telz', '--', '/usr/bin/env', '-i']
    assert kwargs['cwd'] == Path('/release/app')
    assert argv[-3:] == ['-m', 'backend.scripts.tenant_domain_ssl_queue', 'claim']
    assert 'shell' not in kwargs


def test_backend_adapter_rejects_error_protocol_without_leaking_message(monkeypatch, config):
    monkeypatch.setattr(worker, 'active_release', lambda: (Path('/release/app'), Path('/release/app/.venv/bin/python')))
    monkeypatch.setattr(worker, 'command', lambda *args, **kwargs: '{"error_code":"secret-private-error"}')
    with pytest.raises(worker.WorkerError, match='^WORKER_ERROR$'):
        worker.queue(config, 'claim')


def test_failed_nginx_test_in_renewal_hook_never_reloads(monkeypatch):
    import sys
    import subprocess
    fake_fcntl = SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *args: None)
    monkeypatch.setitem(sys.modules, 'fcntl', fake_fcntl)
    spec = importlib.util.spec_from_file_location('ssl_renew_hook', ROOT / 'scripts/tenant-domain-ssl-renew-hook.py')
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    monkeypatch.setattr(hook, 'trusted', lambda *args, **kwargs: None)
    monkeypatch.setattr(hook.Path, 'resolve', lambda self, **kwargs: self)
    monkeypatch.setattr(hook.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(hook.os, 'O_NOFOLLOW', 0, raising=False)
    monkeypatch.setattr(hook.os, 'open', lambda *args, **kwargs: 12345)
    monkeypatch.setattr(hook.os, 'fstat', lambda *args: SimpleNamespace(st_uid=0, st_mode=0o600, st_nlink=1))
    monkeypatch.setattr(hook.os, 'close', lambda *args: None)
    calls = []
    def run(argv, **kwargs):
        calls.append(argv)
        raise subprocess.CalledProcessError(1, argv)
    monkeypatch.setattr(hook.subprocess, 'run', run)
    assert hook.main() == 1
    assert calls == [['/usr/sbin/nginx', '-t']]


@pytest.mark.parametrize('state', ['valid', 'building', 'wrong_commit', 'missing', 'missing_adapter'])
def test_queue_accepts_only_matching_validated_release(monkeypatch, tmp_path, state):
    import json
    releases = tmp_path / 'releases'
    release = releases / ('a' * 40) / 'app'
    (release / '.venv/bin').mkdir(parents=True)
    (release / '.venv/bin/python').write_text('system interpreter fixture')
    (release / 'backend/scripts').mkdir(parents=True)
    adapter = release / 'backend/scripts/tenant_domain_ssl_queue.py'
    if state != 'missing_adapter':
        adapter.write_text('unprivileged queue adapter')
    manifest = release / '.telz-release.json'
    if state != 'missing':
        manifest.write_text(json.dumps({'schema_version': 2,
            'status': 'building' if state == 'building' else 'validated',
            'git_commit': 'b' * 40 if state == 'wrong_commit' else 'a' * 40,
            'alembic_revision': 'future_safe_revision'}))
        manifest.chmod(0o444)
    class Current:
        parent = tmp_path
        def lstat(self):
            return SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0, st_nlink=1)
        def resolve(self, **kwargs):
            return release
    def trust(path, **kwargs):
        if not path.exists():
            raise worker.WorkerError()
    monkeypatch.setattr(worker, 'CURRENT', Current())
    monkeypatch.setattr(worker, 'RELEASES', releases)
    monkeypatch.setattr(worker, 'trusted', trust)
    monkeypatch.setattr(worker.os, 'O_NOFOLLOW', 0, raising=False)
    try:
        if state == 'valid':
            assert worker.active_release()[0] == release
        else:
            with pytest.raises(worker.WorkerError):
                worker.active_release()
    finally:
        if manifest.exists():
            manifest.chmod(0o644)


def test_tls_global_deadline_fails_without_approving_unvisited_ips(monkeypatch):
    from contextlib import nullcontext
    clock = iter([0, 0, 1, 46])
    monkeypatch.setattr(worker.time, 'monotonic', lambda: next(clock))
    connections, timeouts = [], []
    connection = SimpleNamespace(settimeout=lambda value: timeouts.append(value))
    def connect(address, timeout):
        connections.append((address, timeout))
        return nullcontext(connection)
    context = SimpleNamespace(wrap_socket=lambda connection, server_hostname: nullcontext())
    monkeypatch.setattr(worker.socket, 'create_connection', connect)
    monkeypatch.setattr(worker.ssl, 'create_default_context', lambda: context)
    with pytest.raises(worker.WorkerError, match='TLS_INVALID'):
        worker.probe_tls('pizza.example.com', ['8.8.8.8', '1.1.1.1'])
    assert connections == [(('8.8.8.8', 443), 10)]


def test_tls_probes_all_ips_with_remaining_budget_and_hostname(monkeypatch):
    from contextlib import nullcontext
    clock = iter([0, 0, 1, 2, 44, 44.5, 44.9])
    monkeypatch.setattr(worker.time, 'monotonic', lambda: next(clock))
    connections, timeouts, names = [], [], []
    connection = SimpleNamespace(settimeout=lambda value: timeouts.append(value))
    def connect(address, timeout):
        connections.append((address, timeout))
        return nullcontext(connection)
    def wrap(connection, server_hostname):
        names.append(server_hostname)
        return nullcontext()
    monkeypatch.setattr(worker.socket, 'create_connection', connect)
    monkeypatch.setattr(worker.ssl, 'create_default_context', lambda: SimpleNamespace(wrap_socket=wrap))
    worker.probe_tls('pizza.example.com', ['8.8.8.8', '1.1.1.1'])
    assert connections == [(('8.8.8.8', 443), 10), (('1.1.1.1', 443), 1)]
    assert timeouts == [10, 0.5]
    assert names == ['pizza.example.com', 'pizza.example.com']
