"""Version CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output, print_error

if TYPE_CHECKING:
    from gtm_cli.cli.main import State

app = typer.Typer(help="Manage GTM versions")


def _require_account_container(state: State) -> tuple[str, str]:
    """Validate account and container IDs are set."""
    if not state.account_id:
        print_error("No account ID. Use --account-id or set a default in your profile.")
        raise typer.Exit(1)
    if not state.container_id:
        print_error("No container ID. Use --container-id or set a default in your profile.")
        raise typer.Exit(1)
    return state.account_id, state.container_id


@app.command("list")
def list_versions() -> None:
    """List all versions in the container."""
    state = get_state()
    account_id, container_id = _require_account_container(state)
    client = get_client()

    versions = client.list_versions(
        account_id=account_id,
        container_id=container_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    data = [
        {
            "version_id": v.get("containerVersionId", ""),
            "name": v.get("name", ""),
            "num_tags": v.get("numTags", 0),
            "num_triggers": v.get("numTriggers", 0),
            "num_variables": v.get("numVariables", 0),
        }
        for v in versions
    ]

    output(data, fmt=state.output_format, title="Versions")


@app.command("get")
def get_version(
    version_id: Annotated[str, typer.Argument(help="Version ID")],
) -> None:
    """Get details of a specific version."""
    state = get_state()
    account_id, container_id = _require_account_container(state)
    client = get_client()

    versions = client.list_versions(
        account_id=account_id,
        container_id=container_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    version = next((v for v in versions if v.get("containerVersionId") == version_id), None)
    if not version:
        print_error(f"Version '{version_id}' not found")
        raise typer.Exit(1)

    output(version, fmt=state.output_format)
