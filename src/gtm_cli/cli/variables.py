"""Variable CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output, print_error

if TYPE_CHECKING:
    from gtm_cli.cli.main import State

app = typer.Typer(
    help="""Manage GTM variables.

Variables store dynamic values used by tags and triggers (e.g., page URL, click text).

Requires: --account-id, --container-id, --workspace-id (or set defaults in profile)

Example: gtm variable list -a 123456 -c GTM-XXXX -w 1
"""
)


def _require_ids(state: State) -> tuple[str, str, str]:
    """Validate required IDs are set."""
    if not state.account_id:
        print_error("No account ID. Use --account-id or set a default.")
        raise typer.Exit(1)
    if not state.container_id:
        print_error("No container ID. Use --container-id or set a default.")
        raise typer.Exit(1)
    if not state.workspace_id:
        print_error("No workspace ID. Use --workspace-id or set a default.")
        raise typer.Exit(1)
    return state.account_id, state.container_id, state.workspace_id


@app.command("list")
def list_variables() -> None:
    """List all variables in the workspace."""
    state = get_state()
    account_id, container_id, workspace_id = _require_ids(state)
    client = get_client()

    variables = client.list_variables(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    data = [
        {
            "variable_id": v.get("variableId", ""),
            "name": v.get("name", ""),
            "type": v.get("type", ""),
        }
        for v in variables
    ]

    output(data, fmt=state.output_format, title="Variables")


@app.command("get")
def get_variable(
    variable_id: Annotated[str, typer.Argument(help="Variable ID")],
) -> None:
    """Get details of a specific variable."""
    state = get_state()
    account_id, container_id, workspace_id = _require_ids(state)
    client = get_client()

    variables = client.list_variables(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    variable = next((v for v in variables if v.get("variableId") == variable_id), None)
    if not variable:
        print_error(f"Variable '{variable_id}' not found")
        raise typer.Exit(1)

    output(variable, fmt=state.output_format)
