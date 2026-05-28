"""Variable CLI commands."""

from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import resolve_workspace_context
from gtm_cli.utils.output import confirm, output, print_error, print_success

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

    variable = ctx.client.get_variable(variable_id=variable_id, **ctx.api_kwargs)
    if not variable:
        print_error(f"Variable '{variable_id}' not found")
        raise typer.Exit(1)

    output(variable, fmt=ctx.state.output_format)


@app.command("create")
def create_variable(
    name: Annotated[str, typer.Option("--name", "-n", help="Variable name")],
    variable_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Variable type (e.g. v, u, k, jsm, smm, remm)"),
    ],
    param: Annotated[
        list[str] | None,
        typer.Option(
            "--param",
            help="Parameter as key:value (repeatable, e.g. --param name:gtm.elementId)",
        ),
    ] = None,
    notes: Annotated[str | None, typer.Option("--notes", help="Optional notes")] = None,
) -> None:
    """Create a new variable in the workspace.

    Parameters are passed as key:value pairs via --param.

    Examples:
        gtm variable create --name "Page URL" --type u
        gtm variable create --name "Click ID" --type v --param name:gtm.elementId
    """
    ctx = resolve_workspace_context()

    variable_body: dict[str, Any] = {
        "name": name,
        "type": variable_type,
    }

    if param:
        parameters = []
        for p in param:
            if ":" not in p:
                print_error(f"Invalid param format '{p}'. Use key:value (e.g. name:gtm.elementId)")
                raise typer.Exit(1)
            key, value = p.split(":", 1)
            parameters.append({"type": "template", "key": key, "value": value})
        variable_body["parameter"] = parameters

    if notes:
        variable_body["notes"] = notes

    result = ctx.client.create_variable(variable_body=variable_body, **ctx.api_kwargs)

    variable_id = result.get("variableId", "")
    print_success(f"Created variable '{name}' (ID: {variable_id})")
    output(result, fmt=ctx.state.output_format)


@app.command("update")
def update_variable(
    variable_id: Annotated[str, typer.Argument(help="Variable ID to update")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New variable name")] = None,
    variable_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="New variable type"),
    ] = None,
    param: Annotated[
        list[str] | None,
        typer.Option(
            "--param",
            help="Replacement parameters as key:value (repeatable, replaces all existing params)",
        ),
    ] = None,
    notes: Annotated[str | None, typer.Option("--notes", help="Notes to set on the variable")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Update an existing variable in the workspace."""
    ctx = resolve_workspace_context()

    variable = ctx.client.get_variable(variable_id=variable_id, **ctx.api_kwargs)
    if not variable:
        print_error(f"Variable '{variable_id}' not found")
        raise typer.Exit(1)

    variable_name = variable.get("name", variable_id)

    if not ctx.state.yes and not yes and not confirm(f"Update variable '{variable_name}' (ID: {variable_id})?"):
        raise typer.Exit(0)

    updated_body: dict[str, Any] = dict(variable)

    if name is not None:
        updated_body["name"] = name
    if variable_type is not None:
        updated_body["type"] = variable_type
    if param is not None:
        parameters = []
        for p in param:
            if ":" not in p:
                print_error(f"Invalid param format '{p}'. Use key:value (e.g. name:gtm.elementId)")
                raise typer.Exit(1)
            key, value = p.split(":", 1)
            parameters.append({"type": "template", "key": key, "value": value})
        updated_body["parameter"] = parameters
    if notes is not None:
        updated_body["notes"] = notes

    result = ctx.client.update_variable(
        variable_id=variable_id, variable_body=updated_body, **ctx.api_kwargs
    )

    print_success(f"Updated variable '{updated_body.get('name', variable_name)}' (ID: {variable_id})")
    output(result, fmt=ctx.state.output_format)


@app.command("delete")
def delete_variable(
    variable_id: Annotated[str, typer.Argument(help="Variable ID to delete")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Delete a variable from the workspace."""
    ctx = resolve_workspace_context()

    variable = ctx.client.get_variable(variable_id=variable_id, **ctx.api_kwargs)
    if not variable:
        print_error(f"Variable '{variable_id}' not found")
        raise typer.Exit(1)

    variable_name = variable.get("name", variable_id)

    if not ctx.state.yes and not yes and not confirm(f"Delete variable '{variable_name}' (ID: {variable_id})?"):
        raise typer.Exit(0)

    ctx.client.delete_variable(variable_id=variable_id, **ctx.api_kwargs)
    print_success(f"Deleted variable '{variable_name}' (ID: {variable_id})")


@app.command("revert")
def revert_variable(
    variable_id: Annotated[str, typer.Argument(help="Variable ID to revert")],
    fingerprint: Annotated[
        str | None,
        typer.Option("--fingerprint", help="Optional fingerprint for optimistic concurrency"),
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Revert workspace changes for a variable."""
    ctx = resolve_workspace_context()

    if not ctx.state.yes and not yes and not confirm(f"Revert workspace changes for variable '{variable_id}'?"):
        raise typer.Exit(0)

    result = ctx.client.revert_variable(
        variable_id=variable_id, fingerprint=fingerprint, **ctx.api_kwargs
    )

    reverted = result.get("variable", result)
    reverted_name = reverted.get("name", variable_id) if isinstance(reverted, dict) else variable_id
    print_success(f"Reverted variable '{reverted_name}' (ID: {variable_id})")
    output(reverted, fmt=ctx.state.output_format)
