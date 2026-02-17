"""Variable CLI commands."""

from typing import Annotated

import typer

from gtm_cli.cli.helpers import resolve_workspace_context
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
    ctx = resolve_workspace_context()

    variables = ctx.client.list_variables(**ctx.api_kwargs)

    data = [
        {
            "variable_id": v.get("variableId", ""),
            "name": v.get("name", ""),
            "type": v.get("type", ""),
        }
        for v in variables
    ]

    output(data, fmt=ctx.state.output_format, title="Variables")


@app.command("get")
def get_variable(
    variable_id: Annotated[str, typer.Argument(help="Variable ID")],
) -> None:
    """Get details of a specific variable."""
    ctx = resolve_workspace_context()

    variables = ctx.client.list_variables(**ctx.api_kwargs)

    variable = next((v for v in variables if v.get("variableId") == variable_id), None)
    if not variable:
        print_error(f"Variable '{variable_id}' not found")
        raise typer.Exit(1)

    output(variable, fmt=ctx.state.output_format)
