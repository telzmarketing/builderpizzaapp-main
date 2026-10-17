import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile
import textwrap

import pytest


ROOT = Path(__file__).parents[1]
WORKFLOWS = ("deploy.yml", "prepare-manual-deploy.yml")
TARGET, PREVIOUS = "a" * 40, "b" * 40


def read(name):
    return (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")


def block(name, marker):
    for match in re.finditer(r"<<'PY'\n(.*?)\n          PY", read(name), re.S):
        source = textwrap.dedent(match.group(1))
        if marker in source:
            return source
    raise AssertionError(f"Python block missing: {marker}")


@pytest.mark.parametrize("name", WORKFLOWS)
def test_workflows_download_graphs_separately_and_package_per_commit_freezes(name):
    source = read(name)
    commands = [line.strip() for line in source.splitlines() if "python -m pip download" in line]
    assert len(commands) == 3
    assert "pytest==8.3.5 httpx==0.28.1" in commands[0] and " -r " not in commands[0]
    assert '-r "$work/target-freeze.txt"' in commands[1]
    assert '-r "$work/previous-freeze.txt"' in commands[2]
    assert "-- wheelhouse pnpm-store python-freezes .telz-dependencies.json" in source


@pytest.mark.parametrize("name", WORKFLOWS)
@pytest.mark.parametrize("same_sha,different_pins", [(False, True), (True, False), (True, True)])
def test_packaging_preserves_exact_bytes_and_rejects_differing_pins_for_same_sha(tmp_path, monkeypatch, name, same_sha, different_pins):
    dependencies = tmp_path / "dependencies"
    dependencies.mkdir()
    source_paths, freezes = [], []
    for suffix, version in (("target", "1.0"), ("previous", "2.0" if different_pins else "1.0")):
        source = tmp_path / suffix
        (source / "backend").mkdir(parents=True)
        (source / "backend/requirements.txt").write_text("Example>=1.0\n")
        (source / "pnpm-lock.yaml").write_text("lock\n")
        frozen = tmp_path / f"{suffix}-freeze.txt"
        frozen.write_bytes(f"Example=={version}\n".encode("ascii"))
        source_paths.append(source)
        freezes.append(frozen)
    previous = TARGET if same_sha else PREVIOUS
    monkeypatch.setattr(sys, "argv", ["package", str(dependencies), TARGET, previous,
        *(str(path) for path in source_paths), *(str(path) for path in freezes)])
    script = block(name, "freeze_directory.mkdir()")
    if same_sha and different_pins:
        with pytest.raises(SystemExit, match="mesmo commit"):
            exec(compile(script, name, "exec"), {})
        return
    exec(compile(script, name, "exec"), {})
    metadata = json.loads((dependencies / ".telz-dependencies.json").read_text())
    assert metadata["schema_version"] == 1
    assert set(metadata["commits"]) == {TARGET, previous}
    for commit, original in ((TARGET, freezes[0]), (previous, freezes[1])):
        actual = (dependencies / "python-freezes" / f"{commit}.txt").read_bytes()
        assert actual == original.read_bytes()
        assert metadata["commits"][commit]["python_freeze_sha256"] == hashlib.sha256(actual).hexdigest()


def tar_bytes(path, entries):
    with tarfile.open(path, "w:gz") as archive:
        for name, raw in entries.items():
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            archive.addfile(info, io.BytesIO(raw))


@pytest.mark.parametrize("failure", [None, "missing", "wrong_sha", "digest", "invalid_pin", "nested_path", "oversize"])
def test_ci_archive_guard_requires_exact_target_and_previous_freezes(tmp_path, monkeypatch, failure):
    archives = []
    for commit in (TARGET, PREVIOUS):
        archive = tmp_path / f"{commit}.tar.gz"
        tar_bytes(archive, {".telz-source-commit": commit.encode("ascii")})
        archives.append(archive)
    freezes = {f"python-freezes/{TARGET}.txt": b"Example==1.0\n", f"python-freezes/{PREVIOUS}.txt": b"Example==2.0\n"}
    metadata = {"schema_version": 1, "target_commit": TARGET, "previous_commit": PREVIOUS,
        "commits": {commit: {"python_freeze_sha256": hashlib.sha256(freezes[f"python-freezes/{commit}.txt"]).hexdigest(),
            "requirements_sha256": "c" * 64, "pnpm_lock_sha256": "d" * 64} for commit in (TARGET, PREVIOUS)}}
    key = f"python-freezes/{TARGET}.txt"
    if failure == "missing":
        freezes.pop(key)
    elif failure == "wrong_sha":
        freezes[f"python-freezes/{'e' * 40}.txt"] = freezes.pop(key)
    elif failure == "digest":
        freezes[key] = b"Example==3.0\n"
    elif failure == "invalid_pin":
        freezes[key] = b"--index-url https://example.com\n"
    elif failure == "nested_path":
        freezes["python-freezes/nested/extra.txt"] = b"Example==1.0\n"
    elif failure == "oversize":
        freezes[key] = b"x" * 262145
    dependencies = tmp_path / "dependencies.tar.gz"
    tar_bytes(dependencies, {".telz-dependencies.json": json.dumps(metadata).encode(), ".telz-public-build.json": b"{}\n", **freezes})
    monkeypatch.setattr(sys, "argv", ["guard", str(archives[0]), TARGET, str(archives[1]), PREVIOUS, str(dependencies)])
    script = block("deploy.yml", "def validate_source(path, commit):")
    if failure is None:
        exec(compile(script, "workflow-archive-guard", "exec"), {})
    else:
        with pytest.raises((SystemExit, ValueError)):
            exec(compile(script, "workflow-archive-guard", "exec"), {})


def test_offline_ci_checks_pin_hash_before_venv_and_keeps_test_dependencies_constrained():
    source = read("deploy.yml")
    verify = source[source.index("verify_python() {"):source.index('verify_python "$work/target"')]
    assert verify.index("freeze promovido nao corresponde") < verify.index('python -m venv "$venv_dir"')
    assert '-r "$source_dir/backend/requirements.txt" -c "$constraints"' in verify
    assert '-c "$work/dependencies/python-freezes/$GITHUB_SHA.txt" pytest==8.3.5 httpx==0.28.1' in source
