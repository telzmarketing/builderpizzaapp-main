"""Exercise the worker in a clean interpreter, without the HTTP app registry."""
from pathlib import Path
import subprocess
import sys
import textwrap


ROOT = Path(__file__).parents[1]


def test_standalone_cli_registers_foreign_key_targets_and_flushes_claim_and_audit():
    script = textwrap.dedent("""
        import ipaddress
        import sys
        from types import SimpleNamespace
        from uuid import uuid4
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from backend.scripts import tenant_domain_ssl_queue as queue
        from backend.database import Base
        from backend.models.tenant_domain_ssl import TenantDomainCertificateJob as Job
        from backend.services import tenant_domain_ssl_service as ssl
        execute = queue.execute

        assert 'backend.main' not in sys.modules
        assert set(Base.metadata.tables) == {
            'admin_users', 'tenants', 'tenant_domains', 'tenant_domain_certificate_jobs',
            'platform_audit_logs', 'platform_error_events', 'platform_worker_heartbeats',
        }
        # Resolving every FK catches missing registry imports before touching a DB.
        for table in Base.metadata.tables.values():
            for foreign_key in table.foreign_keys:
                assert foreign_key.column is not None

        settings = SimpleNamespace(TENANT_DOMAIN_SSL_MODE='manual', TENANT_DOMAIN_SSL_ENABLED=True,
            TENANT_DOMAIN_SSL_PUBLIC_IPS='8.8.8.8', TENANT_DOMAINS_PLATFORM_HOSTNAMES='app.example.com',
            TENANT_DOMAIN_SSL_HEARTBEAT_SECONDS=300, TENANT_DOMAIN_SSL_LEASE_SECONDS=900,
            TENANT_DOMAIN_SSL_COOLDOWN_SECONDS=3600)
        ssl.get_settings = lambda: settings
        ssl.resolve_public_addresses = lambda host, **kwargs: frozenset([ipaddress.ip_address('8.8.8.8')])

        # An isolated local DB proves real SQLAlchemy flush/commit ordering.
        # No production engine, HTTP app, external DNS or certificates are used.
        engine = create_engine('sqlite://')
        Base.metadata.create_all(engine)
        now = ssl.utcnow()
        job_id = str(uuid4())
        with Session(engine, expire_on_commit=False) as db:
            db.add(ssl.Tenant(id='tenant-a', slug='tenant-a', name='A', status='active'))
            db.add(queue.AdminUser(id='admin-a', name='A', email='a@example.com', password_hash='unused'))
            db.commit()
            db.add(ssl.TenantDomain(id='domain-a', tenant_id='tenant-a', hostname='store.example.com',
                kind='custom', status='verified', verified_at=now, verification_token_hash='a' * 64,
                ssl_status='pending'))
            db.commit()
            db.add(Job(id=job_id, domain_id='domain-a', tenant_id='tenant-a', hostname='store.example.com',
                email='a@example.com', requested_by='admin-a', status='queued', attempts=0,
                terms_accepted_at=now, idempotency_key_hash='a' * 64, request_hash='b' * 64))
            db.commit()
            assert execute('heartbeat', {}, db) == {'status': 'ready'}
            assert db.query(Job).one().status == 'queued'
            assert execute('reconcile', {}, db) == {'reconciled': 0, 'refreshed': 0}
            claim = execute('claim', {}, db)
            assert claim['job_id'] == job_id
            assert db.query(Job).one().status == 'running'
            assert db.query(Job).one().attempts == 1
            identity = {'job_id': claim['job_id'], 'lease_token': claim['lease_token']}
            assert execute('validate', identity, db)['tenant_id'] == 'tenant-a'
            result = execute('fail', {**identity, 'error_code': 'CERTBOT_FAILED'}, db)
            assert result['job']['status'] == 'failed'
            assert result['job']['error_code'] == 'CERTBOT_FAILED'
            audit = Base.metadata.tables['platform_audit_logs']
            assert db.execute(audit.select()).mappings().one()['action'] == 'domain_certificate_failed'
            assert 'backend.main' not in sys.modules
        print('standalone SSL queue FK and flush checks passed')
    """)
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, text=True,
                            capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "standalone SSL queue FK and flush checks passed"
