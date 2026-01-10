"""Workspace CLI commands."""

from typing import Annotated

import typer

from gtm_cli.cli.helpers import resolve_account_id, resolve_container_id
from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output, print_error

app = typer.Typer(
    help="""Manage GTM workspaces.

Workspaces are where you edit tags, triggers, and variables before publishing.
Every container has a "Default Workspace" with ID 1.

Auto-detects account/container if you have only one of each.

Example: gtm workspace list
"""
)


@app.command("list")
def list_workspaces() -> None:
    """List all workspaces in the container."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)

    workspaces = client.list_workspaces(
        account_id=account_id,
        container_id=container_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    data = [
        {
            "workspace_id": w.get("workspaceId", ""),
            "name": w.get("name", ""),
            "description": w.get("description", ""),
        }
        for w in workspaces
    ]

    output(data, fmt=state.output_format, title="Workspaces")


@app.command("get")
def get_workspace(
    workspace_id: Annotated[
        str | None,
        typer.Argument(help="Workspace ID (uses default if not specified)"),
    ] = None,
) -> None:
    """Get details of a specific workspace."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)

    wid = workspace_id or state.workspace_id
    if not wid:
        print_error("No workspace ID provided. Use --workspace-id or set a default.")
        raise typer.Exit(1)

    workspace = client.get_workspace(
        account_id=account_id,
        container_id=container_id,
        workspace_id=wid,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    output(workspace, fmt=state.output_format)
