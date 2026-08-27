"""Built-in variable CLI commands."""

from typing import Annotated

import typer

from gtm_cli.cli.helpers import resolve_workspace_context
from gtm_cli.utils.output import confirm, output, print_dry_run, print_success

app = typer.Typer(
    help="""Manage GTM built-in variables.

Built-in variables (e.g. Page URL, Click ID, GA4 Session ID) are pre-created,
non-customizable variables that GTM ships with — they must be individually
enabled before tags/triggers can reference them.

Auto-detects account/container/workspace if you have only one of each.

Example: gtm built-in-variable list
"""
)


@app.command("list")
def list_built_in_variables() -> None:
    """List all currently enabled built-in variables in the workspace."""
    ctx = resolve_workspace_context()

    variables = ctx.client.list_built_in_variables(**ctx.api_kwargs)

    data = [
        {
            "name": v.get("name", ""),
            "type": v.get("type", ""),
        }
        for v in variables
    ]

    output(data, fmt=ctx.state.output_format, title="Enabled Built-In Variables")


@app.command("enable")
def enable_built_in_variables(
    types: Annotated[
        list[str],
        typer.Argument(
            help="Built-in variable type(s) to enable (repeatable positional args). "
            "Use the exact camelCase API enum value, e.g. pageUrl, clickUrl, "
            "analyticsSessionId, analyticsSessionNumber, analyticsClientId — not the "
            "display name shown in the GTM UI."
        ),
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Enable one or more built-in variables in the workspace.

    This is a workspace mutation and requires confirmation (or --yes / the
    global -y flag).

    Examples:
        gtm built-in-variable enable analyticsSessionId
        gtm built-in-variable enable analyticsSessionId analyticsSessionNumber analyticsClientId
    """
    ctx = resolve_workspace_context()

    if (
        not ctx.state.yes
        and not yes
        and not confirm(f"Enable built-in variable(s): {', '.join(types)}?")
    ):
        raise typer.Exit(0)

    if ctx.state.dry_run:
        print_dry_run(f"enable built-in variable(s): {', '.join(types)}")
        raise typer.Exit(0)

    result = ctx.client.enable_built_in_variables(types=types, **ctx.api_kwargs)

    enabled_names = ", ".join(v.get("name", v.get("type", "")) for v in result) or ", ".join(types)
    print_success(f"Enabled built-in variable(s): {enabled_names}")
    output(result, fmt=ctx.state.output_format, title="Enabled Built-In Variables")


@app.command("disable")
def disable_built_in_variables(
    types: Annotated[
        list[str],
        typer.Argument(
            help="Built-in variable type(s) to disable (repeatable positional args). "
            "Use the exact camelCase API enum value (see 'gtm built-in-variable list')."
        ),
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt"),
    ] = False,
) -> None:
    """Disable one or more built-in variables in the workspace.

    This is a workspace mutation and requires confirmation (or --yes / the
    global -y flag). Disabling a built-in variable still referenced by a tag
    or trigger will break that reference in GTM.

    Examples:
        gtm built-in-variable disable analyticsSessionId
        gtm built-in-variable disable clickUrl clickText
    """
    ctx = resolve_workspace_context()

    if (
        not ctx.state.yes
        and not yes
        and not confirm(f"Disable built-in variable(s): {', '.join(types)}?")
    ):
        raise typer.Exit(0)

    if ctx.state.dry_run:
        print_dry_run(f"disable built-in variable(s): {', '.join(types)}")
        raise typer.Exit(0)

    ctx.client.disable_built_in_variables(types=types, **ctx.api_kwargs)

    print_success(f"Disabled built-in variable(s): {', '.join(types)}")
