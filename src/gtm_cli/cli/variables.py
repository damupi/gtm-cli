"""Variable CLI commands."""

from typing import Annotated

import typer

from gtm_cli.cli.helpers import resolve_workspace_context
from gtm_cli.utils.output import confirm, output, print_error, print_info, print_success

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


@app.command("create")
def create_variable(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Variable name"),
    ],
    variable_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Variable type (e.g. v, u, k, jsm)"),
    ],
    json_body: Annotated[
        str | None,
        typer.Option(
            "--json",
            help="Full variable JSON body as inline string or file path (overrides --name/--type)",
        ),
    ] = None,
) -> None:
    """Create a new variable in the workspace.

    Examples:
        gtm variable create --name "DL - event" --type v
        gtm variable create --json '{"name":"DL - event","type":"v","parameter":[{"type":"integer","key":"dataLayerVersion","value":"2"}]}'
        gtm variable create --json ./variable.json
    """
    import json
    from pathlib import Path

    ctx = resolve_workspace_context()

    if json_body is not None:
        p = Path(json_body)
        if p.exists() and p.is_file():
            with open(p) as f:
                body: dict = json.load(f)
        else:
            body = json.loads(json_body)
    else:
        body = {"name": name, "type": variable_type}

    if ctx.state.dry_run:
        print_info(f"[dry-run] Would create variable: {json.dumps(body)}")
        return

    result = ctx.client.create_variable(variable_body=body, **ctx.api_kwargs)
    print_success(f"Created variable '{result.get('name', '')}' (ID: {result.get('variableId', '')})")
    output(result, fmt=ctx.state.output_format)


@app.command("update")
def update_variable(
    variable_id: Annotated[str, typer.Argument(help="Variable ID to update")],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="New variable name"),
    ] = None,
    json_body: Annotated[
        str | None,
        typer.Option(
            "--json",
            help="Full variable JSON body as inline string or file path (overrides --name)",
        ),
    ] = None,
) -> None:
    """Update an existing variable.

    Fetches the current variable, applies changes, and shows a field-level diff
    before calling the API.

    Examples:
        gtm variable update 12345 --name "New Name"
        gtm variable update 12345 --json '{"name":"New Name","type":"v"}'
        gtm variable update 12345 --json ./variable.json
    """
    import json
    from pathlib import Path

    ctx = resolve_workspace_context()

    variables = ctx.client.list_variables(**ctx.api_kwargs)
    variable = next((v for v in variables if v.get("variableId") == variable_id), None)
    if not variable:
        print_error(f"Variable '{variable_id}' not found")
        raise typer.Exit(1)

    if json_body is not None:
        p = Path(json_body)
        if p.exists() and p.is_file():
            with open(p) as f:
                updates = json.load(f)
        else:
            updates = json.loads(json_body)
        body = {**variable, **updates}
    else:
        body = dict(variable)
        if name is not None:
            body["name"] = name

    changed = {k: (variable.get(k), body.get(k)) for k in body if body.get(k) != variable.get(k)}
    if not changed:
        print_info("No changes detected.")
        return

    for field, (old, new) in changed.items():
        print_info(f"  {field}: {old!r} → {new!r}")

    if ctx.state.dry_run:
        print_info("[dry-run] Would update variable, skipping API call.")
        return

    result = ctx.client.update_variable(
        variable_id=variable_id,
        variable_body=body,
        **ctx.api_kwargs,
    )
    print_success(f"Updated variable '{result.get('name', '')}' (ID: {result.get('variableId', '')})")
    output(result, fmt=ctx.state.output_format)


@app.command("delete")
def delete_variable(
    variable_id: Annotated[str, typer.Argument(help="Variable ID to delete")],
) -> None:
    """Delete a variable from the workspace."""
    from gtm_cli.utils.errors import ResourceNotFoundError

    ctx = resolve_workspace_context()

    variables = ctx.client.list_variables(**ctx.api_kwargs)
    variable = next((v for v in variables if v.get("variableId") == variable_id), None)
    if not variable:
        print_error(f"Variable '{variable_id}' not found")
        raise typer.Exit(1)

    variable_name = variable.get("name", variable_id)

    if ctx.state.dry_run:
        print_info(f"[dry-run] Would delete variable '{variable_name}' (ID: {variable_id})")
        return

    if not ctx.state.yes and not confirm(f"Delete variable '{variable_name}' (ID: {variable_id})?"):
        raise typer.Exit(0)

    try:
        ctx.client.delete_variable(variable_id=variable_id, **ctx.api_kwargs)
    except ResourceNotFoundError:
        print_error(f"Variable '{variable_id}' not found")
        raise typer.Exit(1) from None

    print_success(f"Deleted variable '{variable_name}' (ID: {variable_id})")
