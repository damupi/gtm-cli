"""Self-upgrade command for GitHub-tag installations of gtm-cli."""

from __future__ import annotations

import json
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from gtm_cli import __version__
from gtm_cli.cli.main import get_state
from gtm_cli.core.update import (
    UpgradeError,
    install_info,
    installed_version,
    is_newer,
    latest_release,
    perform_upgrade,
    upgrade_command,
)
from gtm_cli.utils.output import print_error

console = Console(markup=False, highlight=False)


def _print_check(
    current: str,
    latest: str | None,
    update_available: bool,
    command: str | None,
    as_json: bool,
) -> None:
    if as_json:
        typer.echo(
            json.dumps(
                {
                    "installed": current,
                    "latest": latest,
                    "update_available": update_available,
                    "upgrade_command": command,
                },
                indent=2,
            )
        )
        return
    console.print(f"Installed: gtm-cli {current}")
    if latest is None:
        console.print(
            "Latest release: unknown (could not reach GitHub Releases or the public git tag list)."
        )
        console.print("Update available: unknown")
        return
    console.print(f"Latest release: {latest}")
    console.print(f"Update available: {'yes' if update_available else 'no'}")
    console.print(f"To upgrade, run: {command}")


def upgrade(
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Report installed/latest versions and the exact upgrade command, then exit",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip the confirmation prompt before modifying the installation",
        ),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Print the check result as JSON (implies --check; never upgrades)",
        ),
    ] = False,
) -> None:
    """Upgrade gtm-cli to the latest stable GitHub release.

    gtm-cli is distributed only through ``vX.Y.Z`` GitHub tags; the ``gtm-cli``
    package on PyPI is unrelated. This command discovers the latest stable
    release from the public GitHub Releases API (falling back to public HTTPS
    ``git ls-remote``) and reinstalls it with the same method as the current
    copy: ``uv tool install --force`` or ``pip install --upgrade`` against a
    tag-pinned ``git+https://github.com/damupi/gtm-cli@vX.Y.Z`` URL.

    Editable checkouts are never modified: you get a valid ``git pull``
    command instead.

    Examples:
        gtm upgrade --check
        gtm upgrade --check --json
        gtm upgrade
        gtm upgrade --yes
    """
    state = get_state()
    current = installed_version() or __version__
    latest = latest_release()
    update_available = is_newer(latest, current)
    command = upgrade_command(latest) if latest is not None else None

    if check or as_json:
        _print_check(current, latest, update_available, command, as_json)
        return

    if latest is None:
        print_error(
            "Could not determine the latest gtm-cli release from GitHub. "
            "Check your network connection and try again."
        )
        raise typer.Exit(1)

    if not update_available:
        console.print(f"gtm-cli is already up to date ({current}; latest release {latest}).")
        return

    if install_info()["kind"] == "editable":
        console.print("Editable install detected; gtm-cli will not modify your checkout.")
        console.print(f"Update it with: {command}")
        return

    console.print(f"gtm-cli {current} → {latest}")
    console.print(f"Will run: {command}")

    if not (yes or state.yes) and not typer.confirm("Proceed with the upgrade?"):
        console.print("Upgrade cancelled.")
        raise typer.Exit(0)

    try:
        perform_upgrade(latest)
    except UpgradeError as exc:
        print_error(escape(str(exc)))
        raise typer.Exit(1) from exc

    console.print(f"Upgraded gtm-cli to {latest}.")
