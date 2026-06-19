"""Variable CLI commands."""

from pathlib import Path
from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import add_authuser, resolve_workspace_context
from gtm_cli.utils.output import (
    OutputFormat,
    confirm,
    output,
    print_error,
    print_info,
    print_success,
)

app = typer.Typer(
    help="""Manage GTM variables.

Variables store dynamic values used by tags and triggers (e.g., page URL, click text).

Auto-detects account/container/workspace if you have only one of each.

Example: gtm variable list
"""
)

# GTM variable type registry — used by `gtm variable types`
_VARIABLE_TYPES: list[dict[str, str]] = [
    {"type": "v", "name": "Data Layer Variable", "key_params": "name, dataLayerVersion"},
    {"type": "u", "name": "URL", "key_params": "component (PATH|HOST|QUERY|FRAGMENT|PORT|PROTOCOL|FULL_URL)"},
    {"type": "k", "name": "First-Party Cookie", "key_params": "name"},
    {"type": "c", "name": "Constant", "key_params": "value"},
    {"type": "j", "name": "JavaScript Variable", "key_params": "name"},
    {"type": "jsm", "name": "Custom JavaScript", "key_params": "javascript  ← always use --param-file"},
    {"type": "e", "name": "Auto-Event Variable", "key_params": "varType"},
    {"type": "r", "name": "HTTP Referrer", "key_params": "component"},
    {"type": "smm", "name": "Lookup Table", "key_params": "input, map"},
    {"type": "remm", "name": "RegEx Table", "key_params": "input, map"},
    {"type": "aev", "name": "Element Visibility", "key_params": "selectorType, selector"},
    {"type": "vis", "name": "Visibility State", "key_params": "selectorType, selector"},
    {"type": "d", "name": "DOM Element", "key_params": "selectorType, selector"},
    {"type": "f", "name": "HTTP Referrer (full)", "key_params": "(none)"},
    {"type": "gas", "name": "Google Analytics Settings", "key_params": "trackingId"},
]

_GTM_VAR_BASE = "https://tagmanager.google.com/#/container/accounts/{account_id}/containers/{container_id}/workspaces/{workspace_id}/variables/{variable_id}"


def _gtm_variable_url(ctx: Any, variable_id: str) -> str:
    url = _GTM_VAR_BASE.format(
        account_id=ctx.account_id,
        container_id=ctx.container_id,
        workspace_id=ctx.workspace_id,
        variable_id=variable_id,
    )
    return add_authuser(url, ctx.state.authuser)


def _parse_param_files(param_file: list[str] | None) -> dict[str, str]:
    """Parse --param-file entries (key:path) and read file contents verbatim.

    Args:
        param_file: List of "key:path" strings where path is a file to read.

    Returns:
        Mapping of parameter key to file content (preserves all whitespace).

    Raises:
        typer.Exit: If format is invalid or a file cannot be read.
    """
    result: dict[str, str] = {}
    if not param_file:
        return result
    for entry in param_file:
        if ":" not in entry:
            print_error(
                f"Invalid --param-file format '{entry}'. Use key:path (e.g. javascript:script.js)"
            )
            raise typer.Exit(1)
        key, path_str = entry.split(":", 1)
        file_path = Path(path_str)
        if not file_path.exists():
            print_error(f"File not found for --param-file '{key}': {path_str}")
            raise typer.Exit(1)
        result[key] = file_path.read_text()
    return result


def _guard_inline_code(param_map: dict[str, str]) -> None:
    """Error if a javascript or html parameter value contains newlines.

    Inline multi-line JS/HTML passed via --param is corrupted by shell quoting.
    Redirect the user to --param-file before the write happens.
    """
    for key, value in param_map.items():
        if key in ("javascript", "html") and "\n" in value:
            print_error(
                f"--param {key}: multi-line value detected. "
                f"Shell quoting will corrupt this. "
                f"Use --param-file {key}:/path/to/file instead."
            )
            raise typer.Exit(1)


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


@app.command("types")
def variable_types() -> None:
    """List all GTM variable types and their key parameters.

    Use the Type column as the value for --type when creating or updating variables.
    """
    output(_VARIABLE_TYPES, fmt=OutputFormat.TABLE, title="Variable Types")


@app.command("create")
def create_variable(
    name: Annotated[str, typer.Option("--name", "-n", help="Variable name")],
    variable_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Variable type (e.g. jsm, v, u, k, c). Run 'gtm variable types' for the full list.",
        ),
    ],
    param: Annotated[
        list[str] | None,
        typer.Option(
            "--param",
            help=(
                "Parameter as key:value (repeatable, e.g. --param name:gtm.elementId). "
                "WARNING: do not use for multi-line JS/HTML — shell quoting corrupts strings. "
                "Use --param-file instead."
            ),
        ),
    ] = None,
    param_file: Annotated[
        list[str] | None,
        typer.Option(
            "--param-file",
            help=(
                "Parameter as key:path (repeatable). Reads file content verbatim as the value. "
                "Use for multi-line JS/HTML (e.g. --param-file javascript:script.js). "
                "Overrides --param for the same key."
            ),
        ),
    ] = None,
    notes: Annotated[str | None, typer.Option("--notes", help="Optional notes")] = None,
) -> None:
    """Create a new variable in the workspace.

    Run 'gtm variable types' to see all available types and their parameters.

    For Custom JavaScript variables (type: jsm), always use --param-file to supply
    the code from a file — passing JS inline via --param corrupts multi-line code silently.

    GTM variable references inside parameter values use double curly brackets:
    {{variableName}}. These are passed through verbatim — do not escape them.

    Examples:

      # URL variable
      gtm variable create --name "Page URL" --type u

      # Data layer variable
      gtm variable create --name "Click ID" --type v --param name:gtm.elementId

      # Custom JavaScript (always use --param-file for JS code)
      gtm variable create --name "My JS Var" --type jsm --param-file javascript:myscript.js
    """
    ctx = resolve_workspace_context()

    variable_body: dict[str, Any] = {
        "name": name,
        "type": variable_type,
    }

    file_values = _parse_param_files(param_file)

    if param or file_values:
        param_map: dict[str, str] = {}
        if param:
            for p in param:
                if ":" not in p:
                    print_error(
                        f"Invalid param format '{p}'. Use key:value (e.g. name:gtm.elementId)"
                    )
                    raise typer.Exit(1)
                key, value = p.split(":", 1)
                param_map[key] = value
        _guard_inline_code(param_map)
        # param_file values override --param values for the same key
        param_map.update(file_values)
        variable_body["parameter"] = [
            {"type": "template", "key": k, "value": v} for k, v in param_map.items()
        ]

    if notes:
        variable_body["notes"] = notes

    result = ctx.client.create_variable(variable_body=variable_body, **ctx.api_kwargs)

    variable_id = result.get("variableId", "")
    file_hint = (
        "  [" + ", ".join(f"{k} ← {Path(pf.split(':', 1)[1]).name}" for pf in (param_file or []) for k in [pf.split(":", 1)[0]]) + "]"
        if param_file else ""
    )
    print_success(f"Created variable '{name}' (ID: {variable_id}){file_hint}")
    review_url = _gtm_variable_url(ctx, variable_id)
    print_info(f"Review: {review_url}")
    output(result, fmt=ctx.state.output_format)


@app.command("update")
def update_variable(
    variable_id: Annotated[str, typer.Argument(help="Variable ID to update")],
    name: Annotated[str | None, typer.Option("--name", "-n", help="New variable name")] = None,
    variable_type: Annotated[
        str | None,
        typer.Option("--type", "-t", help="New variable type. Run 'gtm variable types' for options."),
    ] = None,
    param: Annotated[
        list[str] | None,
        typer.Option(
            "--param",
            help=(
                "Upsert a parameter as key:value (repeatable). Updates matching key or appends. "
                "WARNING: do not use for multi-line JS/HTML — shell quoting corrupts strings. "
                "Use --param-file instead."
            ),
        ),
    ] = None,
    param_file: Annotated[
        list[str] | None,
        typer.Option(
            "--param-file",
            help=(
                "Upsert a parameter from a file as key:path (repeatable). Reads file content "
                "verbatim — preserves all whitespace, line breaks, and {{variableName}} references. "
                "Use for multi-line JS/HTML (e.g. --param-file javascript:script.js). "
                "Overrides --param for the same key."
            ),
        ),
    ] = None,
    notes: Annotated[
        str | None, typer.Option("--notes", help="Notes to set on the variable")
    ] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Update an existing variable in the workspace.

    Fetches the current variable, applies changes, and saves. Only specified
    fields are changed; everything else is preserved.

    For Custom JavaScript variables (type: jsm), always use --param-file to supply
    the code from a file — passing JS inline via --param corrupts multi-line code silently.

    GTM variable references inside parameter values use double curly brackets:
    {{variableName}}. These are passed through verbatim — do not escape them.

    Examples:

      # Rename a variable
      gtm variable update 123 --name "New Name"

      # Update a simple parameter
      gtm variable update 123 --param name:gtm.elementId

      # Update a Custom JavaScript variable body (always use --param-file for JS)
      gtm variable update 123 --param-file javascript:/tmp/my_var.js

      # Update notes
      gtm variable update 123 --notes "Updated by WEBDATA-123"
    """
    ctx = resolve_workspace_context()

    variable = ctx.client.get_variable(variable_id=variable_id, **ctx.api_kwargs)
    if not variable:
        print_error(f"Variable '{variable_id}' not found")
        raise typer.Exit(1)

    variable_name = variable.get("name", variable_id)

    if (
        not ctx.state.yes
        and not yes
        and not confirm(f"Update variable '{variable_name}' (ID: {variable_id})?")
    ):
        raise typer.Exit(0)

    updated_body: dict[str, Any] = dict(variable)

    if name is not None:
        updated_body["name"] = name
    if variable_type is not None:
        updated_body["type"] = variable_type
    if param is not None or param_file is not None:
        file_values = _parse_param_files(param_file)

        upsert_map: dict[str, str] = {}
        if param is not None:
            for p in param:
                if ":" not in p:
                    print_error(
                        f"Invalid param format '{p}'. Use key:value (e.g. name:gtm.elementId)"
                    )
                    raise typer.Exit(1)
                key, value = p.split(":", 1)
                upsert_map[key] = value
        _guard_inline_code(upsert_map)
        # param_file values override --param values for the same key
        upsert_map.update(file_values)

        existing_params: list[dict[str, Any]] = list(updated_body.get("parameter", []))
        for entry in existing_params:
            if entry.get("key") in upsert_map:
                entry["value"] = upsert_map.pop(entry["key"])
        # Append any keys not already present
        for k, v in upsert_map.items():
            existing_params.append({"type": "template", "key": k, "value": v})
        updated_body["parameter"] = existing_params

    if notes is not None:
        updated_body["notes"] = notes

    result = ctx.client.update_variable(
        variable_id=variable_id, variable_body=updated_body, **ctx.api_kwargs
    )

    final_name = updated_body.get("name", variable_name)
    file_hint = (
        "  [" + ", ".join(f"{pf.split(':', 1)[0]} ← {Path(pf.split(':', 1)[1]).name}" for pf in (param_file or [])) + "]"
        if param_file else ""
    )
    print_success(f"Updated variable '{final_name}' (ID: {variable_id}){file_hint}")
    review_url = _gtm_variable_url(ctx, variable_id)
    print_info(f"Review: {review_url}")
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

    if (
        not ctx.state.yes
        and not yes
        and not confirm(f"Delete variable '{variable_name}' (ID: {variable_id})?")
    ):
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

    if (
        not ctx.state.yes
        and not yes
        and not confirm(f"Revert workspace changes for variable '{variable_id}'?")
    ):
        raise typer.Exit(0)

    result = ctx.client.revert_variable(
        variable_id=variable_id, fingerprint=fingerprint, **ctx.api_kwargs
    )

    reverted = result.get("variable", result)
    reverted_name = reverted.get("name", variable_id) if isinstance(reverted, dict) else variable_id
    print_success(f"Reverted variable '{reverted_name}' (ID: {variable_id})")
    output(reverted, fmt=ctx.state.output_format)
