"""Check for newer gtm-cli GitHub releases and upgrade the installed copy.

gtm-cli is distributed only through GitHub tags; the ``gtm-cli`` distribution
on PyPI is unrelated and must never be used for installs. Release discovery
therefore uses a bounded ``curl`` request against the public GitHub Releases
API and falls back to a public ``git ls-remote`` over HTTPS. No credentials or
tokens are required, read, printed, or persisted.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from importlib import metadata
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from gtm_cli.core.config import DEFAULT_CONFIG_DIR

# Repository identity (public).
REPO = "damupi/gtm-cli"
REPO_GIT_HTTPS = f"https://github.com/{REPO}.git"
REPO_INSTALL_HTTPS = f"git+https://github.com/{REPO}"
REPO_RELEASES_LATEST_API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/tag"

# Cache lives under the project config home so it can be inspected/removed.
CACHE_PATH = DEFAULT_CONFIG_DIR / "update-check.json"
CHECK_INTERVAL = 24 * 3600
DISABLE_ENV = "GTM_NO_UPDATE_CHECK"

_CURL_USER_AGENT = "gtm-cli-update-check"

# Stable vX.Y.Z tags only: prereleases and non-semver tags are ignored.
_TAG = re.compile(r"refs/tags/v(\d+)\.(\d+)\.(\d+)$")
_RELEASE_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

# Environment hooks that could turn a background git/install call interactive.
_UNSAFE_GIT_ENV = (
    "GIT_ASKPASS",
    "SSH_ASKPASS",
    "GIT_ASKPASS_REQUIRE",
    "GIT_CREDENTIAL_HELPER",
    "GIT_CONFIG",
    "GIT_CONFIG_GLOBAL",
    "GIT_CONFIG_SYSTEM",
    "GIT_CONFIG_PARAMETERS",
    "GIT_SSH",
    "GIT_SSH_COMMAND",
    "GIT_SSH_VARIANT",
)

# Per-process config overrides (``GIT_CONFIG_*``); the user's global Git config
# is never modified or written. An empty ``credential.helper`` resets the
# inherited helper list, and the URL-scoped entry covers host-specific helpers.
_GIT_SUPPRESS_CONFIG: tuple[tuple[str, str], ...] = (
    ("credential.helper", ""),
    ("credential.https://github.com.helper", ""),
    ("credential.interactive", "false"),
    ("core.askPass", ""),
    ("http.extraHeader", ""),
    ("http.https://github.com/.extraHeader", ""),
)


class UpgradeError(RuntimeError):
    """Raised when an upgrade cannot be started or fails."""


# ── Release discovery ─────────────────────────────────────────────────────────


def _version_tuple(version: str) -> tuple[int, int, int] | None:
    match = _VERSION.match(version)
    if match is None:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _highest(versions: list[tuple[int, int, int]]) -> str | None:
    if not versions:
        return None
    return ".".join(str(part) for part in max(versions))


def _curl_argv(timeout: float) -> list[str] | None:
    """Bounded ``curl`` argv for ``/releases/latest``, or ``None`` without curl.

    The timeout is applied twice: curl's own ``--max-time`` caps the whole
    transfer, and the caller also sets a subprocess timeout so a stuck curl can
    never outlive its budget.
    """
    executable = shutil.which("curl")
    if not executable:
        return None
    return [
        executable,
        "--disable",
        "--fail",
        "--silent",
        "--show-error",
        "--location",
        "--proto",
        "=https",
        "--max-time",
        f"{max(timeout, 0.01):.3f}",
        "--header",
        "Accept: application/vnd.github+json",
        "--header",
        f"User-Agent: {_CURL_USER_AGENT}",
        REPO_RELEASES_LATEST_API,
    ]


def _parse_release_payload(body: str) -> str | None:
    """Stable ``X.Y.Z`` version from a Releases API JSON object, or ``None``.

    Drafts, prereleases, non-object payloads, and malformed/truncated JSON are
    all rejected so the caller can fall back to ``git ls-remote``.
    """
    try:
        payload: Any = json.loads(body)
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("draft") or payload.get("prerelease"):
        return None
    tag = payload.get("tag_name")
    if not isinstance(tag, str):
        return None
    match = _RELEASE_TAG.match(tag.strip())
    if match is None:
        return None
    return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"


def latest_release_api(timeout: float = 5.0) -> str | None:
    """Stable ``vX.Y.Z`` version of the latest GitHub release, or ``None``.

    Uses an optional, wall-clock-bounded ``curl`` subprocess against
    ``/releases/latest``. Returns ``None`` on missing curl, any network/HTTP
    failure, a timeout, or an unusable response so the caller can fall back to
    ``git ls-remote``. Drafts and prereleases are ignored and no credentials
    are sent.
    """
    if timeout <= 0:
        return None
    argv = _curl_argv(timeout)
    if argv is None:
        return None
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=dict(os.environ),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return _parse_release_payload(result.stdout)


def git_safe_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Non-interactive environment for git and install subprocesses.

    Removes inherited askpass/SSH hooks, ignores system and global Git config,
    and resets credential helpers and HTTP authorization headers for this
    process only. This prevents a public HTTPS lookup from inheriting secrets
    or an ``insteadOf`` rule that rewrites GitHub HTTPS to SSH. Nothing is
    written to the user's Git configuration.
    """
    env: dict[str, str] = dict(os.environ if base is None else base)
    for name in _UNSAFE_GIT_ENV:
        env.pop(name, None)
    for name in tuple(env):
        if name.startswith("GIT_CONFIG_KEY_") or name.startswith("GIT_CONFIG_VALUE_"):
            env.pop(name, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_CONFIG_COUNT"] = str(len(_GIT_SUPPRESS_CONFIG))
    for index, (key, value) in enumerate(_GIT_SUPPRESS_CONFIG):
        env[f"GIT_CONFIG_KEY_{index}"] = key
        env[f"GIT_CONFIG_VALUE_{index}"] = value
    return env


def latest_release_git(timeout: float = 5.0) -> str | None:
    """Highest stable ``vX.Y.Z`` tag via public HTTPS ``git ls-remote``.

    Compatibility fallback when the GitHub API is unreachable. Fails instead
    of prompting for credentials and requires no SSH setup.
    """
    try:
        with tempfile.TemporaryDirectory(prefix="gtm-cli-update-") as cwd:
            result = subprocess.run(
                ["git", "ls-remote", "--tags", "--refs", REPO_GIT_HTTPS, "v*"],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=git_safe_env(),
                cwd=cwd,
                check=False,
            )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    versions: list[tuple[int, int, int]] = []
    for line in result.stdout.splitlines():
        match = _TAG.search(line)
        if match is not None:
            versions.append((int(match.group(1)), int(match.group(2)), int(match.group(3))))
    return _highest(versions)


def latest_release(timeout: float = 5.0) -> str | None:
    """Latest stable release within one short aggregate ``timeout``.

    The Releases API is tried first; part of the deadline is reserved so the
    public ``git ls-remote`` fallback still runs when the API stalls or fails.
    """
    started = time.monotonic()
    deadline = started + timeout
    git_reserve = min(2.0, max(timeout / 2, 0.0))
    api_budget = max(deadline - time.monotonic() - git_reserve, 0.0)
    if api_budget > 0:
        latest = latest_release_api(timeout=api_budget)
        if latest is not None:
            return latest
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return None
    return latest_release_git(timeout=remaining)


def installed_version() -> str | None:
    """Installed ``gtm-cli`` distribution version, or ``None``."""
    try:
        return metadata.version("gtm-cli")
    except metadata.PackageNotFoundError:
        return None


def is_newer(latest: str | None, current: str | None) -> bool:
    """True when ``latest`` is a strictly newer stable version than ``current``."""
    latest_tuple = _version_tuple(latest or "")
    current_tuple = _version_tuple(current or "")
    return latest_tuple is not None and current_tuple is not None and latest_tuple > current_tuple


# ── Install detection and command generation ──────────────────────────────────


def install_info() -> dict[str, str]:
    """Describe how gtm-cli was installed: editable checkout, uv tool, or pip.

    Editable installs are detected through ``direct_url.json``. ``uv tool``
    installs leave a receipt in the tool environment; everything else is
    treated as a plain pip install.
    """
    direct_url: dict[str, Any] = {}
    for dist in metadata.distributions(name="gtm-cli"):
        raw = dist.read_text("direct_url.json")
        if not raw:
            continue
        try:
            parsed: Any = json.loads(raw)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            direct_url = parsed
        break
    dir_info = direct_url.get("dir_info")
    if isinstance(dir_info, dict) and dir_info.get("editable"):
        raw_url = direct_url.get("url")
        path = ""
        if isinstance(raw_url, str):
            path = _file_url_to_path(raw_url)
        return {"kind": "editable", "path": path}
    if (Path(sys.prefix) / "uv-receipt.toml").exists():
        return {"kind": "uv", "path": ""}
    return {"kind": "pip", "path": ""}


def _file_url_to_path(raw_url: str) -> str:
    """Decode a ``file://`` URL from ``direct_url.json`` into a local path."""
    return unquote(urlparse(raw_url).path)


def install_url(version: str) -> str:
    """Tag-pinned GitHub install target. Never the unrelated PyPI package."""
    return f"{REPO_INSTALL_HTTPS}@v{version}"


def upgrade_command(version: str) -> str:
    """Shell-safe command that installs ``version`` the way gtm-cli is installed.

    uv and pip installs use a tag-pinned ``git+https`` URL; the unrelated PyPI
    ``gtm-cli`` distribution is never referenced. Editable installs get valid
    ``git pull`` guidance instead of an install command.
    """
    info = install_info()
    if info["kind"] == "editable":
        path = info.get("path") or "<your gtm-cli checkout>"
        return f"git -C {shlex.quote(path)} pull  # editable install: update your checkout"
    if info["kind"] == "uv":
        argv = ["uv", "tool", "install", "--force", install_url(version)]
    else:
        argv = [sys.executable, "-m", "pip", "install", "--upgrade", install_url(version)]
    return shlex.join(argv)


def upgrade_argv(version: str) -> list[str] | None:
    """argv that installs ``version``, or ``None`` for an editable install."""
    info = install_info()
    if info["kind"] == "editable":
        return None
    target = install_url(version)
    if info["kind"] == "uv":
        return ["uv", "tool", "install", "--force", target]
    return [sys.executable, "-m", "pip", "install", "--upgrade", target]


def upgrade_env() -> dict[str, str]:
    """Environment for an install subprocess.

    Ignores inherited Git authentication and transport configuration for the
    subprocess only; it never changes the user's files or persists a secret.
    """
    return git_safe_env()


def perform_upgrade(
    version: str,
    timeout: float = 600.0,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the install command for ``version``.

    Raises :class:`UpgradeError` when the install cannot start, times out, or
    exits non-zero. Returns the completed process on success.
    """
    argv = upgrade_argv(version)
    if argv is None:
        raise UpgradeError(
            "gtm-cli is an editable install. Update your checkout instead, e.g. "
            "`git -C <checkout> pull`."
        )
    run = subprocess.run if runner is None else runner
    try:
        result = run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=upgrade_env(),
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise UpgradeError(f"Could not run {' '.join(argv)}: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        message = f"Upgrade failed (exit {result.returncode})."
        if detail:
            message = f"{message}\n{detail}"
        raise UpgradeError(message)
    return result


def upgrade_notice(latest: str, current: str) -> str:
    """Cached notice text. Must stay network-free: never probes GitHub."""
    return (
        f"A new release of gtm-cli is available: {current} → {latest}\n"
        f"To upgrade, run: gtm upgrade\n"
        f"Release notes: {RELEASES_URL}/v{latest}"
    )


# ── Once-a-day cache and notice ───────────────────────────────────────────────


def _read_cache() -> dict[str, Any]:
    try:
        data: Any = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache(latest: str | None) -> None:
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps({"checked_at": int(time.time()), "latest": latest}) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def cached_latest_release() -> str | None:
    """Latest release, refreshed from GitHub at most once per ``CHECK_INTERVAL``."""
    cache = _read_cache()
    checked_at = cache.get("checked_at")
    if isinstance(checked_at, (int, float)) and time.time() - checked_at < CHECK_INTERVAL:
        latest = cache.get("latest")
        return latest if isinstance(latest, str) else None
    latest = latest_release()
    _write_cache(latest)
    return latest


def should_check() -> bool:
    """Only notify interactive users: not when disabled, in CI, or piped stderr."""
    if os.environ.get(DISABLE_ENV) or os.environ.get("CI"):
        return False
    try:
        return sys.stderr.isatty()
    except (AttributeError, ValueError):
        return False


def pending_notice() -> str | None:
    """Upgrade notice to show after a command, or ``None``. Never raises."""
    try:
        if not should_check():
            return None
        current = installed_version()
        latest = cached_latest_release()
        if current is None or latest is None:
            return None
        if is_newer(latest, current):
            return upgrade_notice(latest, current)
    except Exception:
        return None
    return None
