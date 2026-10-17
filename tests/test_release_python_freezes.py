import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

import pytest


ROOT = Path(__file__).parents[1]
BUILDER = (ROOT / "scripts/build-telz-release.sh").read_text(encoding="utf-8")
PREFLIGHT = re.search(r'PYTHON_FREEZE_FILE=.*?<<\'PY\'\n(.*?)\nPY\n\)', BUILDER, re.S).group(1)


def fixture_bundle(tmp_path):
    dependencies = tmp_path / "dependencies"
    (dependencies / "python-freezes").mkdir(parents=True)
    (dependencies / "wheelhouse").mkdir()
    sources, metadata = {}, {"schema_version": 1, "commits": {}}
    for commit, version in (("a" * 40, "1.0"), ("b" * 40, "2.0")):
        code = tmp_path / commit
        (code / "backend").mkdir(parents=True)
        (code / ".telz-source-commit").write_text(commit, encoding="ascii")
        (code / "backend/requirements.txt").write_text("Pinned-Demo>=1.0\n", encoding="ascii")
        (code / "pnpm-lock.yaml").write_text("lock\n", encoding="ascii")
        freeze = dependencies / "python-freezes" / f"{commit}.txt"
        freeze.write_bytes(f"Pinned-Demo=={version}\n".encode("ascii"))
        metadata["commits"][commit] = {
            "python_freeze_sha256": hashlib.sha256(freeze.read_bytes()).hexdigest(),
            "requirements_sha256": hashlib.sha256((code / "backend/requirements.txt").read_bytes()).hexdigest(),
            "pnpm_lock_sha256": hashlib.sha256((code / "pnpm-lock.yaml").read_bytes()).hexdigest(),
        }
        sources[commit] = code
    (dependencies / ".telz-dependencies.json").write_text(json.dumps(metadata), encoding="ascii")
    return dependencies, sources, metadata


def validate(code, dependencies, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["preflight", str(code), str(dependencies)])
    exec(compile(PREFLIGHT, "release-freeze-preflight", "exec"), {})


def test_each_commit_selects_its_own_promoted_freeze(tmp_path, monkeypatch, capsys):
    dependencies, sources, _ = fixture_bundle(tmp_path)
    for commit, source in sources.items():
        validate(source, dependencies, monkeypatch)
        assert capsys.readouterr().out.strip() == str(dependencies / "python-freezes" / f"{commit}.txt")


@pytest.mark.parametrize("invalid", [b"--index-url https://example.com\n", b"Pinned-Demo @ https://example.com/a.whl\n",
    b"Pinned-Demo>=1.0\n", b"Pinned-Demo==1.0\r\n", b"Pinned-Demo==1.0", b"z==1.0\na==1.0\n",
    b"Pinned-Demo==1.0\npinned_demo==1.0\n", b"Pinned-Demo==1.0\n\n"])
def test_invalid_freeze_is_rejected_even_when_digest_matches(tmp_path, monkeypatch, invalid):
    dependencies, sources, metadata = fixture_bundle(tmp_path)
    commit = "a" * 40
    (dependencies / "python-freezes" / f"{commit}.txt").write_bytes(invalid)
    metadata["commits"][commit]["python_freeze_sha256"] = hashlib.sha256(invalid).hexdigest()
    (dependencies / ".telz-dependencies.json").write_text(json.dumps(metadata))
    with pytest.raises((SystemExit, ValueError)):
        validate(sources[commit], dependencies, monkeypatch)


@pytest.mark.parametrize("failure", ["missing", "hash_mismatch", "requirements_drift", "wrong_commit", "oversize"])
def test_missing_or_mismatched_pins_never_fall_back_to_unconstrained_install(tmp_path, monkeypatch, failure):
    dependencies, sources, _ = fixture_bundle(tmp_path)
    source = sources["a" * 40]
    freeze = dependencies / "python-freezes" / f"{'a' * 40}.txt"
    if failure == "missing":
        freeze.unlink()
    elif failure == "hash_mismatch":
        freeze.write_bytes(b"Pinned-Demo==2.0\n")
    elif failure == "requirements_drift":
        (source / "backend/requirements.txt").write_text("Pinned-Demo>=3.0\n")
    elif failure == "wrong_commit":
        (source / ".telz-source-commit").write_text("c" * 40)
    else:
        freeze.write_bytes(b"x" * 262145)
    with pytest.raises((SystemExit, ValueError, FileNotFoundError)):
        validate(source, dependencies, monkeypatch)


def make_wheel(directory, version):
    dist = f"pinned_demo-{version}.dist-info"
    entries = {
        "pinned_demo/__init__.py": f"VERSION = '{version}'\n",
        f"{dist}/METADATA": f"Metadata-Version: 2.1\nName: Pinned-Demo\nVersion: {version}\n\n",
        f"{dist}/WHEEL": "Wheel-Version: 1.0\nGenerator: local-test\nRoot-Is-Purelib: true\nTag: py3-none-any\n\n",
    }
    entries[f"{dist}/RECORD"] = "".join(f"{path},,\n" for path in [*entries, f"{dist}/RECORD"])
    with zipfile.ZipFile(directory / f"pinned_demo-{version}-py3-none-any.whl", "w") as wheel:
        for name, content in entries.items():
            wheel.writestr(name, content)


def test_union_wheelhouse_installs_different_promoted_versions_per_commit_offline(tmp_path, monkeypatch, capsys):
    dependencies, sources, _ = fixture_bundle(tmp_path)
    for version in ("1.0", "2.0"):
        make_wheel(dependencies / "wheelhouse", version)
    for (commit, source), version in zip(sources.items(), ("1.0", "2.0")):
        validate(source, dependencies, monkeypatch)
        freeze = capsys.readouterr().out.strip()
        target = tmp_path / f"installed-{version}"
        result = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir",
            "--no-index", "--no-compile", "--find-links", str(dependencies / "wheelhouse"),
            "--target", str(target), "-r", str(source / "backend/requirements.txt"), "-c", freeze],
            capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr
        assert (target / "pinned_demo/__init__.py").read_text().strip() == f"VERSION = '{version}'"


def test_builder_validates_before_venv_and_installs_only_with_commit_constraints():
    assert BUILDER.index("PYTHON_FREEZE_FILE=") < BUILDER.index('"$PYTHON_BOOTSTRAP" -m venv')
    assert '-r backend/requirements.txt -c "$PYTHON_FREEZE_FILE"' in BUILDER
    assert 'if actual != expected:' in BUILDER
    assert 'release nao reproduziu as dependencias promovidas' in BUILDER
