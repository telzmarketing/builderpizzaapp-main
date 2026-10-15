import json
import os
from pathlib import Path
import stat
from types import SimpleNamespace

import pytest

from backend.core import domain_ssl_runtime as runtime


def projection(**patch):
    return {"schema_version": 1, "ready": True, "public_ips": ["8.8.8.8"],
        "platform_hostnames": ["app.example.com"], "reason": None,
        "updated_at": "2026-10-15T12:00:00+00:00", **patch}


def trusted_file(tmp_path, monkeypatch, *, owner=0, writable=False, links=1, mutable_parent=False):
    path = tmp_path / "runtime.json"
    path.write_text(json.dumps(projection()), encoding="utf-8")
    original_stat, original_fstat = Path.lstat, os.fstat
    parents = set(path.parents)
    def parent_stat(item, *args, **kwargs):
        info = original_stat(item, *args, **kwargs)
        if item in parents:
            values = list(info)
            values[0], values[4] = stat.S_IFDIR | (0o777 if mutable_parent and item == tmp_path else 0o755), 0
            return os.stat_result(values)
        return info
    def descriptor_stat(fd):
        values = list(original_fstat(fd))
        values[0], values[3], values[4] = stat.S_IFREG | (0o666 if writable else 0o644), links, owner
        return os.stat_result(values)
    monkeypatch.setattr(Path, "lstat", parent_stat)
    monkeypatch.setattr(runtime.os, "fstat", descriptor_stat)
    return path


def test_root_owned_projection_enables_auto_despite_default_flag_false(tmp_path, monkeypatch):
    path = trusted_file(tmp_path, monkeypatch)
    monkeypatch.setattr(runtime, "RUNTIME_PATH", path)
    settings = SimpleNamespace(TENANT_DOMAIN_SSL_MODE="auto", TENANT_DOMAIN_SSL_ENABLED=False)
    result = runtime.ssl_runtime(settings)
    assert result.ready and result.public_ips == ("8.8.8.8",)
    assert result.platform_hostnames == ("app.example.com",)


@pytest.mark.parametrize("patch", [{"owner": 1000}, {"writable": True}, {"links": 2}, {"mutable_parent": True}])
def test_mutable_or_untrusted_projection_never_enables_issuance(tmp_path, monkeypatch, patch):
    path = trusted_file(tmp_path, monkeypatch, **patch)
    result = runtime.read_runtime(path)
    assert not result.ready and result.reason == "invalid_runtime"


@pytest.mark.parametrize("patch", [{"schema_version": True}, {"ready": 1},
    {"public_ips": ["127.0.0.1"]}, {"public_ips": ["224.0.0.1"]}, {"platform_hostnames": []},
    {"reason": "arbitrary private log"}, {"extra": "unknown"}, {"updated_at": "2026-10-15"}])
def test_runtime_projection_validates_every_field(tmp_path, monkeypatch, patch):
    path = trusted_file(tmp_path, monkeypatch)
    path.write_text(json.dumps(projection(**patch)), encoding="utf-8")
    assert runtime.read_runtime(path).reason == "invalid_runtime"


def test_runtime_false_is_preserved_and_duplicate_keys_rejected(tmp_path, monkeypatch):
    path = trusted_file(tmp_path, monkeypatch)
    path.write_text(json.dumps(projection(ready=False, public_ips=[], platform_hostnames=[], reason="preflight_failed")))
    assert runtime.read_runtime(path).reason == "preflight_failed"
    path.write_text('{"ready":true,"ready":false}')
    assert runtime.read_runtime(path).reason == "invalid_runtime"


def test_projection_rejects_oversize_and_visible_symlink(tmp_path, monkeypatch):
    path = trusted_file(tmp_path, monkeypatch)
    path.write_text(" " * 8193)
    assert runtime.read_runtime(path).reason == "invalid_runtime"
    path.write_text(json.dumps(projection()))
    original = Path.lstat
    def symlink_stat(item, *args, **kwargs):
        info = original(item, *args, **kwargs)
        if item == path:
            values = list(info)
            values[0] = stat.S_IFLNK | 0o777
            return os.stat_result(values)
        return info
    monkeypatch.setattr(Path, "lstat", symlink_stat)
    assert runtime.read_runtime(path).reason == "invalid_runtime"


def test_disabled_optout_and_manual_legacy_modes(monkeypatch):
    monkeypatch.setattr(runtime, "read_runtime", lambda: runtime.DomainSSLRuntime(True, ("8.8.8.8",), ("app.example.com",)))
    settings = SimpleNamespace(TENANT_DOMAIN_SSL_MODE="disabled", TENANT_DOMAIN_SSL_ENABLED=True,
        TENANT_DOMAIN_SSL_PUBLIC_IPS="1.1.1.1", TENANT_DOMAINS_PLATFORM_HOSTNAMES="master.example.com")
    assert runtime.ssl_runtime(settings).reason == "disabled"
    settings.TENANT_DOMAIN_SSL_MODE = "manual"
    assert runtime.ssl_runtime(settings).public_ips == ("1.1.1.1",)
    settings.TENANT_DOMAIN_SSL_MODE = "auto"
    assert runtime.ssl_runtime(settings).public_ips == ("8.8.8.8",)
    monkeypatch.setattr(runtime, "read_runtime", lambda: None)
    assert runtime.ssl_runtime(settings).public_ips == ("1.1.1.1",)
    monkeypatch.setattr(runtime, "read_runtime", lambda: runtime.DomainSSLRuntime(False, reason="invalid_runtime"))
    assert runtime.ssl_runtime(settings).reason == "invalid_runtime"
