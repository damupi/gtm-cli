"""Tests for GitHub release discovery, caching, install detection and upgrade."""

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gtm_cli.core import update

LS_REMOTE = (
    "aaa\trefs/tags/v0.3.0\n"
    "bbb\trefs/tags/v1.10.0\n"
    "ccc\trefs/tags/v1.2.1\n"
    "ddd\trefs/tags/v2.0.0-rc1\n"
    "eee\trefs/tags/vnext\n"
)

CURL = "/usr/bin/curl"


def _completed(stdout="", returncode=0, stderr=""):
    return MagicMock(stdout=stdout, stderr=stderr, returncode=returncode)


def _release(tag="v1.3.0", draft=False, prerelease=False):
    return json.dumps({"tag_name": tag, "draft": draft, "prerelease": prerelease})


def _enable_curl(monkeypatch):
    """Pretend curl is installed on PATH."""
    monkeypatch.setattr(update.shutil, "which", lambda _name: CURL)
    return CURL


@pytest.fixture
def cache(tmp_path, monkeypatch):
    path = tmp_path / "update-check.json"
    monkeypatch.setattr(update, "CACHE_PATH", path)
    return path


# ── Release discovery: bounded curl against /releases/latest ──────────────────


def test_curl_argv_is_wall_clock_bounded_and_https(monkeypatch):
    _enable_curl(monkeypatch)
    argv = update._curl_argv(2.5)
    assert argv is not None
    assert argv[0] == CURL
    assert argv[1] == "--disable"
    assert "--max-time" in argv
    assert argv[argv.index("--max-time") + 1] == "2.500"
    assert "=https" in argv
    assert "Authorization" not in " ".join(argv)
    assert "gtm-cli-update-check" in " ".join(argv)
    assert argv[-1] == update.REPO_RELEASES_LATEST_API


def test_curl_argv_returns_none_without_curl(monkeypatch):
    monkeypatch.setattr(update.shutil, "which", lambda _name: None)
    assert update._curl_argv(5.0) is None


def test_releases_endpoint_is_latest_not_paginated_list():
    assert update.REPO_RELEASES_LATEST_API == (
        "https://api.github.com/repos/damupi/gtm-cli/releases/latest"
    )
    assert "?" not in update.REPO_RELEASES_LATEST_API


def test_latest_release_api_returns_stable_version(monkeypatch):
    _enable_curl(monkeypatch)
    run = MagicMock(return_value=_completed(_release("v1.10.0")))
    with patch.object(update.subprocess, "run", run):
        assert update.latest_release_api() == "1.10.0"
    argv, kwargs = run.call_args
    assert argv[0] == update._curl_argv(5.0)
    assert kwargs["timeout"] == 5.0
    assert kwargs["check"] is False
    assert kwargs["capture_output"] is True


def test_latest_release_api_strips_whitespace(monkeypatch):
    _enable_curl(monkeypatch)
    with patch.object(update.subprocess, "run", return_value=_completed(_release(" v1.4.0 "))):
        assert update.latest_release_api() == "1.4.0"


@pytest.mark.parametrize(
    "body",
    [
        _release("v2.0.0", draft=True),
        _release("v2.1.0", prerelease=True),
        json.dumps({"tag_name": "vnext"}),
        json.dumps({"tag_name": 123}),
        json.dumps({"message": "Not Found"}),
        json.dumps([{"tag_name": "v1.5.0"}]),
    ],
)
def test_latest_release_api_rejects_unusable_payloads(monkeypatch, body):
    _enable_curl(monkeypatch)
    with patch.object(update.subprocess, "run", return_value=_completed(body)):
        assert update.latest_release_api() is None


@pytest.mark.parametrize("body", ["", "not json", '{"tag_name": "v1.2', "   "])
def test_latest_release_api_rejects_truncated_or_invalid_json(monkeypatch, body):
    _enable_curl(monkeypatch)
    with patch.object(update.subprocess, "run", return_value=_completed(body)):
        assert update.latest_release_api() is None


def test_latest_release_api_nonzero_exit_is_none(monkeypatch):
    _enable_curl(monkeypatch)
    with patch.object(
        update.subprocess, "run", return_value=_completed("", returncode=22, stderr="404")
    ):
        assert update.latest_release_api() is None


def test_latest_release_api_subprocess_timeout_is_none(monkeypatch):
    _enable_curl(monkeypatch)
    expired = subprocess.TimeoutExpired(cmd=[CURL], timeout=5.0)
    with patch.object(update.subprocess, "run", side_effect=expired):
        assert update.latest_release_api() is None


def test_latest_release_api_oserror_is_none(monkeypatch):
    _enable_curl(monkeypatch)
    with patch.object(update.subprocess, "run", side_effect=OSError("no curl")):
        assert update.latest_release_api() is None


def test_latest_release_api_skips_nonpositive_timeout(monkeypatch):
    _enable_curl(monkeypatch)
    run = MagicMock()
    with patch.object(update.subprocess, "run", run):
        assert update.latest_release_api(timeout=0.0) is None
    run.assert_not_called()


def test_latest_release_api_returns_none_when_curl_missing(monkeypatch):
    monkeypatch.setattr(update.shutil, "which", lambda _name: None)
    run = MagicMock()
    with patch.object(update.subprocess, "run", run):
        assert update.latest_release_api() is None
    run.assert_not_called()


# ── Release discovery: public HTTPS git fallback ──────────────────────────────


def test_latest_release_git_picks_highest_stable_tag():
    with patch.object(update.subprocess, "run", return_value=_completed(LS_REMOTE)) as run:
        assert update.latest_release_git() == "1.10.0"
    args, kwargs = run.call_args
    assert args[0] == ["git", "ls-remote", "--tags", "--refs", update.REPO_GIT_HTTPS, "v*"]
    assert update.REPO_GIT_HTTPS.startswith("https://")
    assert kwargs["timeout"] == 5.0
    assert kwargs["check"] is False


def test_latest_release_git_env_is_non_interactive(monkeypatch):
    monkeypatch.setenv("GIT_ASKPASS", "/leak/askpass")
    monkeypatch.setenv("SSH_ASKPASS", "/leak/ssh-askpass")
    monkeypatch.setenv("GIT_CREDENTIAL_HELPER", "leak")
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'credential.helper=leak'")
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -i /leak/key")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/leak/gitconfig")
    with patch.object(update.subprocess, "run", return_value=_completed(LS_REMOTE)) as run:
        assert update.latest_release_git() == "1.10.0"
    env = run.call_args.kwargs["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GCM_INTERACTIVE"] == "never"
    assert "GIT_ASKPASS" not in env
    assert "SSH_ASKPASS" not in env
    assert "GIT_CREDENTIAL_HELPER" not in env
    assert "GIT_CONFIG_PARAMETERS" not in env
    assert "GIT_SSH_COMMAND" not in env
    assert env["GIT_CONFIG_GLOBAL"] == update.os.devnull
    assert env["GIT_CONFIG_SYSTEM"] == update.os.devnull
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == "credential.helper"
    assert env["GIT_CONFIG_VALUE_0"] == ""
    assert env["GIT_CONFIG_KEY_1"] == "credential.https://github.com.helper"
    assert env["GIT_CONFIG_VALUE_1"] == ""
    assert env["GIT_CONFIG_COUNT"] == "6"
    keys = {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(6)}
    assert keys["core.askPass"] == ""
    assert keys["credential.interactive"] == "false"
    assert keys["http.extraHeader"] == ""
    assert keys["http.https://github.com/.extraHeader"] == ""


def test_git_safe_env_ignores_global_auth_headers_and_https_rewrites(tmp_path):
    global_config = tmp_path / "gitconfig"
    global_config.write_text(
        "[http]\n\textraHeader = Authorization: Bearer secret\n"
        '[url "git@github.com:"]\n\tinsteadOf = https://github.com/\n'
    )
    base = {
        "PATH": update.os.environ.get("PATH", ""),
        "GIT_CONFIG_GLOBAL": str(global_config),
        "GIT_SSH_COMMAND": "ssh -i /leak/key",
    }
    env = update.git_safe_env(base)

    headers = subprocess.run(
        ["git", "config", "--get-all", "http.extraHeader"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )
    rewrite = subprocess.run(
        ["git", "config", "--get-all", "url.git@github.com:.insteadOf"],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=False,
    )
    resolved_url = subprocess.run(
        ["git", "ls-remote", "--get-url", update.REPO_GIT_HTTPS],
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
        check=True,
    )

    assert "Authorization" not in headers.stdout
    assert "secret" not in headers.stdout
    assert rewrite.stdout == ""
    assert resolved_url.stdout.strip() == update.REPO_GIT_HTTPS
    assert "GIT_SSH_COMMAND" not in env


def test_latest_release_git_nonzero_exit_is_none():
    with patch.object(update.subprocess, "run", return_value=_completed(LS_REMOTE, returncode=128)):
        assert update.latest_release_git() is None


def test_latest_release_git_timeout_is_none():
    expired = subprocess.TimeoutExpired(cmd=["git"], timeout=5.0)
    with patch.object(update.subprocess, "run", side_effect=expired):
        assert update.latest_release_git() is None


def test_latest_release_git_oserror_is_silent():
    with patch.object(update.subprocess, "run", side_effect=OSError("git not found")):
        assert update.latest_release_git() is None


# ── Aggregate deadline ────────────────────────────────────────────────────────


def test_latest_release_prefers_api_without_calling_git():
    with (
        patch.object(update, "latest_release_api", return_value="1.5.0") as api,
        patch.object(update, "latest_release_git") as git,
    ):
        assert update.latest_release() == "1.5.0"
    api.assert_called_once()
    assert 0 < api.call_args.kwargs["timeout"] <= 5.0
    git.assert_not_called()


def test_latest_release_falls_back_to_git_when_api_fails():
    with (
        patch.object(update, "latest_release_api", return_value=None),
        patch.object(update, "latest_release_git", return_value="1.5.0") as git,
    ):
        assert update.latest_release() == "1.5.0"
    assert 0 < git.call_args.kwargs["timeout"] <= 5.0


def test_latest_release_falls_back_to_git_when_curl_is_missing(monkeypatch):
    monkeypatch.setattr(update.shutil, "which", lambda _name: None)
    with patch.object(update.subprocess, "run", return_value=_completed(LS_REMOTE)):
        assert update.latest_release() == "1.10.0"


def test_latest_release_falls_back_when_api_has_no_releases():
    with (
        patch.object(update, "latest_release_api", return_value=None),
        patch.object(update, "latest_release_git", return_value="1.5.0"),
    ):
        assert update.latest_release() == "1.5.0"


def test_latest_release_reserves_time_for_git_when_api_stalls(monkeypatch):
    clock = iter([100.0, 100.0, 103.6])
    monkeypatch.setattr(update.time, "monotonic", lambda: next(clock))
    api_budgets: list[float] = []

    def stalled_api(timeout=5.0):
        api_budgets.append(timeout)
        return None

    monkeypatch.setattr(update, "latest_release_api", stalled_api)
    with patch.object(update, "latest_release_git", return_value="1.5.0") as git:
        assert update.latest_release(timeout=5.0) == "1.5.0"

    assert api_budgets == [3.0]
    assert git.call_args.kwargs["timeout"] == pytest.approx(1.4)


def test_latest_release_returns_none_when_deadline_exhausted(monkeypatch):
    clock = iter([100.0, 100.0, 105.0])
    monkeypatch.setattr(update.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(update, "latest_release_api", lambda *_args, **_kwargs: None)
    with patch.object(update, "latest_release_git") as git:
        assert update.latest_release(timeout=5.0) is None
    git.assert_not_called()


# ── Version comparison ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "latest, current, expected",
    [
        ("1.3.0", "1.2.0", True),
        ("1.10.0", "1.9.0", True),
        ("1.2.0", "1.2.0", False),
        ("1.2.0", "1.3.0", False),
        (None, "1.2.0", False),
        ("1.3.0", None, False),
        ("1.3.0-rc1", "1.2.0", False),
        ("not-a-version", "1.2.0", False),
    ],
)
def test_is_newer(latest, current, expected):
    assert update.is_newer(latest, current) is expected


# ── Install detection ─────────────────────────────────────────────────────────


class _FakeDist:
    def __init__(self, direct_url: str | None) -> None:
        self._direct_url = direct_url

    def read_text(self, _name: str) -> str | None:
        return self._direct_url


def test_install_info_detects_editable_checkout(monkeypatch):
    direct = json.dumps({"url": "file:///src/my%20cli", "dir_info": {"editable": True}})
    monkeypatch.setattr(
        update.metadata, "distributions", lambda *_args, **_kwargs: iter([_FakeDist(direct)])
    )
    info = update.install_info()
    assert info == {"kind": "editable", "path": "/src/my cli"}


def test_install_info_detects_uv_tool(monkeypatch, tmp_path):
    monkeypatch.setattr(update.metadata, "distributions", lambda *_args, **_kwargs: iter([]))
    monkeypatch.setattr(update.sys, "prefix", str(tmp_path))
    (tmp_path / "uv-receipt.toml").write_text("[tool]\n")
    assert update.install_info()["kind"] == "uv"


def test_install_info_defaults_to_pip(monkeypatch, tmp_path):
    monkeypatch.setattr(update.metadata, "distributions", lambda *_args, **_kwargs: iter([]))
    monkeypatch.setattr(update.sys, "prefix", str(tmp_path))
    assert update.install_info()["kind"] == "pip"


def test_install_info_ignores_non_editable_direct_url(monkeypatch, tmp_path):
    direct = json.dumps({"url": "file:///src/gtm", "dir_info": {}})
    monkeypatch.setattr(
        update.metadata, "distributions", lambda *_args, **_kwargs: iter([_FakeDist(direct)])
    )
    monkeypatch.setattr(update.sys, "prefix", str(tmp_path))
    assert update.install_info()["kind"] == "pip"


# ── Command generation ────────────────────────────────────────────────────────


def test_default_cache_path_is_project_config_home():
    from gtm_cli.core.config import DEFAULT_CONFIG_DIR

    expected = Path.home() / ".gtm-cli" / "update-check.json"
    assert expected == update.CACHE_PATH
    assert update.CACHE_PATH == DEFAULT_CONFIG_DIR / "update-check.json"


def test_install_url_is_tag_pinned_https():
    assert update.install_url("1.3.0") == "git+https://github.com/damupi/gtm-cli@v1.3.0"


def test_upgrade_command_uv_uses_tag_pinned_git_url():
    with patch.object(update, "install_info", return_value={"kind": "uv", "path": ""}):
        command = update.upgrade_command("1.3.0")
    assert command == ("uv tool install --force git+https://github.com/damupi/gtm-cli@v1.3.0")


def test_upgrade_command_pip_uses_running_python_and_tag_pinned_url():
    with patch.object(update, "install_info", return_value={"kind": "pip", "path": ""}):
        command = update.upgrade_command("1.3.0")
    assert "-m pip install --upgrade" in command
    assert sys.executable in command
    assert "git+https://github.com/damupi/gtm-cli@v1.3.0" in command


def test_upgrade_command_editable_quotes_path_and_is_valid_shell():
    with patch.object(
        update, "install_info", return_value={"kind": "editable", "path": "/src/my cli"}
    ):
        command = update.upgrade_command("1.3.0")
    assert command == "git -C '/src/my cli' pull  # editable install: update your checkout"
    subprocess.run(["sh", "-n"], input=command, text=True, check=True)


@pytest.mark.parametrize("kind", ["uv", "pip"])
def test_upgrade_command_never_targets_bare_pypi_package(kind):
    with patch.object(update, "install_info", return_value={"kind": kind, "path": ""}):
        command = update.upgrade_command("1.3.0")
    assert not re.search(r"(?:pip install --upgrade|tool install --force)\s+gtm-cli(\s|$)", command)
    assert "git+https://github.com/damupi/gtm-cli@v1.3.0" in command


@pytest.mark.parametrize(
    "info, expected",
    [
        (
            {"kind": "uv", "path": ""},
            ["uv", "tool", "install", "--force", update.install_url("1.3.0")],
        ),
        (
            {"kind": "pip", "path": ""},
            [sys.executable, "-m", "pip", "install", "--upgrade", update.install_url("1.3.0")],
        ),
        ({"kind": "editable", "path": "/src"}, None),
    ],
)
def test_upgrade_argv_matches_install_kind(info, expected):
    with patch.object(update, "install_info", return_value=info):
        assert update.upgrade_argv("1.3.0") == expected


# ── Upgrade execution ─────────────────────────────────────────────────────────


def test_perform_upgrade_success_passes_argv_and_env():
    runner = MagicMock(return_value=_completed("Installed", returncode=0))
    with patch.object(update, "install_info", return_value={"kind": "uv", "path": ""}):
        result = update.perform_upgrade("1.3.0", runner=runner)
    assert result.returncode == 0
    argv, kwargs = runner.call_args
    assert argv[0] == [
        "uv",
        "tool",
        "install",
        "--force",
        "git+https://github.com/damupi/gtm-cli@v1.3.0",
    ]
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
    assert kwargs["env"]["GCM_INTERACTIVE"] == "never"
    assert kwargs["check"] is False
    assert kwargs["timeout"] == 600.0


def test_upgrade_env_is_non_interactive_and_per_process(monkeypatch):
    monkeypatch.setenv("GIT_ASKPASS", "/leak/askpass")
    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'credential.helper=leak'")
    env = update.upgrade_env()
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GCM_INTERACTIVE"] == "never"
    assert "GIT_ASKPASS" not in env
    assert "GIT_CONFIG_PARAMETERS" not in env
    assert env["GIT_CONFIG_KEY_0"] == "credential.helper"
    assert env["GIT_CONFIG_VALUE_0"] == ""
    assert env["GIT_CONFIG_GLOBAL"] == update.os.devnull
    assert env["GIT_CONFIG_SYSTEM"] == update.os.devnull
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"


def test_perform_upgrade_nonzero_raises_with_detail():
    runner = MagicMock(return_value=_completed("", returncode=1, stderr="network error"))
    with (
        patch.object(update, "install_info", return_value={"kind": "pip", "path": ""}),
        pytest.raises(update.UpgradeError) as excinfo,
    ):
        update.perform_upgrade("1.3.0", runner=runner)
    assert "network error" in str(excinfo.value)
    assert "exit 1" in str(excinfo.value)


def test_perform_upgrade_oserror_raises():
    runner = MagicMock(side_effect=OSError("uv not found"))
    with (
        patch.object(update, "install_info", return_value={"kind": "uv", "path": ""}),
        pytest.raises(update.UpgradeError),
    ):
        update.perform_upgrade("1.3.0", runner=runner)


def test_perform_upgrade_editable_refuses_without_running():
    runner = MagicMock()
    with (
        patch.object(update, "install_info", return_value={"kind": "editable", "path": "/src"}),
        pytest.raises(update.UpgradeError, match="editable install"),
    ):
        update.perform_upgrade("1.3.0", runner=runner)
    runner.assert_not_called()


# ── Notice rendering ──────────────────────────────────────────────────────────


def test_upgrade_notice_is_network_free_and_actionable():
    with (
        patch.object(update, "latest_release_api") as api,
        patch.object(update, "latest_release_git") as git,
        patch.object(update, "latest_release") as latest,
    ):
        notice = update.upgrade_notice("1.3.0", "1.2.0")
    assert "1.2.0 → 1.3.0" in notice
    assert "To upgrade, run: gtm upgrade" in notice
    assert "releases/tag/v1.3.0" in notice
    api.assert_not_called()
    git.assert_not_called()
    latest.assert_not_called()


# ── Cache ─────────────────────────────────────────────────────────────────────


def test_cached_latest_release_uses_fresh_cache(cache):
    cache.write_text(json.dumps({"checked_at": int(time.time()), "latest": "1.3.0"}))
    with patch.object(update, "latest_release") as latest:
        assert update.cached_latest_release() == "1.3.0"
    latest.assert_not_called()


def test_cached_latest_release_refreshes_stale_cache(cache):
    stale = int(time.time()) - update.CHECK_INTERVAL - 1
    cache.write_text(json.dumps({"checked_at": stale, "latest": "1.2.0"}))
    with patch.object(update, "latest_release", return_value="1.3.0"):
        assert update.cached_latest_release() == "1.3.0"
    assert json.loads(cache.read_text())["latest"] == "1.3.0"


def test_cached_latest_release_records_failed_check_once(cache):
    with patch.object(update, "latest_release", return_value=None) as latest:
        assert update.cached_latest_release() is None
        assert update.cached_latest_release() is None
    latest.assert_called_once()
    assert cache.exists()


def test_corrupt_cache_triggers_refresh(cache):
    cache.write_text("not json")
    with patch.object(update, "latest_release", return_value="1.3.0"):
        assert update.cached_latest_release() == "1.3.0"


def test_write_cache_creates_parent(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "update-check.json"
    monkeypatch.setattr(update, "CACHE_PATH", path)
    update._write_cache("1.3.0")
    assert path.exists()


# ── When to check / notice gating ─────────────────────────────────────────────


def test_should_check_requires_tty(monkeypatch):
    monkeypatch.delenv(update.DISABLE_ENV, raising=False)
    monkeypatch.delenv("CI", raising=False)
    with patch.object(update.sys.stderr, "isatty", return_value=True):
        assert update.should_check() is True
    with patch.object(update.sys.stderr, "isatty", return_value=False):
        assert update.should_check() is False


@pytest.mark.parametrize("env", [update.DISABLE_ENV, "CI"])
def test_should_check_respects_opt_out_and_ci(monkeypatch, env):
    monkeypatch.setenv(env, "1")
    with patch.object(update.sys.stderr, "isatty", return_value=True):
        assert update.should_check() is False


def test_pending_notice_when_newer_release():
    with (
        patch.object(update, "should_check", return_value=True),
        patch.object(update, "installed_version", return_value="1.2.0"),
        patch.object(update, "cached_latest_release", return_value="1.3.0"),
    ):
        notice = update.pending_notice()
    assert notice is not None
    assert "1.2.0 → 1.3.0" in notice


def test_pending_notice_none_when_up_to_date():
    with (
        patch.object(update, "should_check", return_value=True),
        patch.object(update, "installed_version", return_value="1.3.0"),
        patch.object(update, "cached_latest_release", return_value="1.3.0"),
    ):
        assert update.pending_notice() is None


def test_pending_notice_skips_cache_when_disabled():
    with (
        patch.object(update, "should_check", return_value=False),
        patch.object(update, "cached_latest_release") as cached,
    ):
        assert update.pending_notice() is None
    cached.assert_not_called()


def test_pending_notice_never_raises():
    with (
        patch.object(update, "should_check", return_value=True),
        patch.object(update, "cached_latest_release", side_effect=RuntimeError("boom")),
    ):
        assert update.pending_notice() is None
