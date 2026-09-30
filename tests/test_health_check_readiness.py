from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HEALTH_CHECK = ROOT / "scripts" / "health-check.sh"


def extract_shell_function(source: str, name: str) -> str:
    match = re.search(
        rf"^{re.escape(name)}\(\) \{{.*?^\}}\r?$",
        source,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"funcao {name} ausente do health check"
    return match.group(0)


def bash_executable() -> str:
    candidate = shutil.which("bash")
    if candidate and not (os.name == "nt" and "system32" in candidate.lower()):
        return candidate
    if os.name == "nt":
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "bin" / "bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    pytest.skip("bash compativel indisponivel")


def run_readiness_scenario(scenario: str) -> subprocess.CompletedProcess[str]:
    source = HEALTH_CHECK.read_text(encoding="utf-8")
    functions = "\n\n".join(
        extract_shell_function(source, name)
        for name in ("die", "health_monotonic_seconds", "wait_for_local_api")
    )
    script = f"""
set -Eeuo pipefail
{functions}

API_URL=http://127.0.0.1:8000/health
API_READY_TIMEOUT_SECONDS=5
API_REQUEST_TIMEOUT_SECONDS=3
API_RETRY_INTERVAL_SECONDS=2
calls=0
READY_AFTER=3
virtual_seconds=0

curl() {{
  calls=$((calls + 1))
  local output=""
  while (( $# )); do
    case "$1" in
      --output) output="$2"; shift 2 ;;
      *) shift ;;
    esac
  done
  if [[ "{scenario}" == "delayed" && "$calls" -ge "$READY_AFTER" ]]; then
    printf '%s' '{{"status":"healthy"}}' > "$output"
  else
    printf '%s' '{{"status":"starting"}}' > "$output"
  fi
}}

validate_health_response() {{
  grep -q '"status":"healthy"' "$1"
}}

sleep() {{
  virtual_seconds=$((virtual_seconds + $1))
}}

health_monotonic_seconds() {{
  printf '%s\n' "$virtual_seconds"
}}

response_file="$(mktemp)"
trap 'rm -f -- "$response_file"' EXIT
wait_for_local_api "$response_file"
printf 'calls=%s\n' "$calls"
"""
    return subprocess.run(
        [bash_executable(), "-c", script],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_local_api_readiness_retries_until_valid_health_json() -> None:
    result = run_readiness_scenario("delayed")

    assert result.returncode == 0, result.stderr
    assert "API local pronta apos 3 tentativa(s)" in result.stdout
    assert "calls=3" in result.stdout
    assert result.stderr.count("API local ainda indisponivel") == 2


def test_local_api_readiness_fails_after_finite_deadline() -> None:
    result = run_readiness_scenario("never")

    assert result.returncode != 0
    assert "API local nao ficou pronta em 5s apos 3 tentativa(s)" in result.stderr
    assert result.stderr.count("API local ainda indisponivel") == 3


def test_health_check_keeps_bounded_defaults_and_json_validation() -> None:
    source = HEALTH_CHECK.read_text(encoding="utf-8")
    readiness = extract_shell_function(source, "wait_for_local_api")

    assert 'TELZ_HEALTH_API_READY_TIMEOUT_SECONDS:-60' in source
    assert 'TELZ_HEALTH_API_REQUEST_TIMEOUT_SECONDS:-5' in source
    assert 'TELZ_HEALTH_API_RETRY_INTERVAL_SECONDS:-2' in source
    assert 'curl --fail --silent --show-error --max-time "$request_timeout"' in readiness
    assert 'validate_health_response "$response_file"' in readiness
    assert 'now="$(health_monotonic_seconds)"' in readiness
    assert 'die "API local nao ficou pronta em ${API_READY_TIMEOUT_SECONDS}s' in readiness
