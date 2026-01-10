"""Variable CLI commands."""

from typing import Annotated

import typer

from gtm_cli.cli.helpers import (
    resolve_account_id,
    resolve_container_id,
    resolve_workspace_id,
)
from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output, print_error

app = typer.Typer(
    help="""Manage GTM variables.

Variables store dynamic values used by tags and triggers (e.g., page URL, click text).

Auto-detects account/container/workspace if you have only one of each.

Example: gtm variable list
"""
)


@app.command("list")
def list_variables() -> None:
    """List all variables in the workspace."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

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
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

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
