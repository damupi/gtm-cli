"""Workspace CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output, print_error

if TYPE_CHECKING:
    from gtm_cli.cli.main import State

app = typer.Typer(help="Manage GTM workspaces")


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
def list_workspaces() -> None:
    """List all workspaces in the container."""
    state = get_state()
    account_id, container_id = _require_account_container(state)
    client = get_client()

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
    account_id, container_id = _require_account_container(state)
    client = get_client()

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
