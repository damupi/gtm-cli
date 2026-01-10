"""Version CLI commands."""

from typing import Annotated

import typer

from gtm_cli.cli.helpers import resolve_account_id, resolve_container_id
from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output, print_error

app = typer.Typer(
    help="""Manage GTM container versions.

Versions are published snapshots of your container. Each publish creates a new version.

Auto-detects account/container if you have only one of each.

Example: gtm version list
"""
)


@app.command("list")
def list_versions() -> None:
    """List all versions in the container."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)

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
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)

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
