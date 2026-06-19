"""Trigger CLI commands."""

from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import resolve_workspace_context
from gtm_cli.utils.output import confirm, output, print_error, print_success

# Timer triggers use top-level fields, not the parameter array
_TIMER_TOP_LEVEL_KEYS = frozenset({"interval", "limit", "eventName"})

app = typer.Typer(
    help="""Manage GTM triggers.

Triggers define WHEN your tags fire (e.g., page view, click, form submit).

Auto-detects account/container/workspace if you have only one of each.

Example: gtm trigger list
"""
)


@app.command("list")
def list_triggers() -> None:
    """List all triggers in the workspace."""
    ctx = resolve_workspace_context()

    triggers = ctx.client.list_triggers(**ctx.api_kwargs)

    data = [
        {
            "trigger_id": t.get("triggerId", ""),
            "name": t.get("name", ""),
            "type": t.get("type", ""),
        }
        for t in triggers
    ]

    output(data, fmt=ctx.state.output_format, title="Triggers")


@app.command("get")
def get_trigger(
    trigger_id: Annotated[str, typer.Argument(help="Trigger ID")],
) -> None:
    """Get details of a specific trigger."""
    ctx = resolve_workspace_context()

    triggers = ctx.client.list_triggers(**ctx.api_kwargs)

    trigger = next((t for t in triggers if t.get("triggerId") == trigger_id), None)
    if not trigger:
        print_error(f"Trigger '{trigger_id}' not found")
        raise typer.Exit(1)

    output(trigger, fmt=ctx.state.output_format)


@app.command("create")
def create_trigger(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Trigger name"),
    ],
    trigger_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Trigger type (e.g. timer, customEvent, pageview)"),
    ],
    param: Annotated[
        list[str] | None,
        typer.Option(
            "--param",
            help="Type-specific parameter as key:value (repeatable, e.g. --param interval:5000)",
        ),
    ] = None,
) -> None:
    """Create a new trigger in the workspace.

    Parameters are passed as key:value pairs via --param.

    Examples:
        gtm trigger create --name "Timer 5s" --type timer --param interval:5000 --param limit:1
        gtm trigger create --name "Page View" --type pageview
    """
    ctx = resolve_workspace_context()

    trigger_body: dict[str, Any] = {
        "name": name,
        "type": trigger_type,
    }

    if param:
        parameters = []
        for p in param:
            if ":" not in p:
                print_error(f"Invalid param format '{p}'. Use key:value (e.g. interval:5000)")
                raise typer.Exit(1)
            key, value = p.split(":", 1)
            if trigger_type == "timer" and key in _TIMER_TOP_LEVEL_KEYS:
                trigger_body[key] = {"type": "template", "value": value}
            else:
                parameters.append({"type": "template", "key": key, "value": value})
        if parameters:
            trigger_body["parameter"] = parameters

    # Timer triggers always need eventName
    if trigger_type == "timer" and "eventName" not in trigger_body:
        trigger_body["eventName"] = {"type": "template", "value": "gtm.timer"}

    result = ctx.client.create_trigger(trigger_body=trigger_body, **ctx.api_kwargs)

    trigger_id = result.get("triggerId", "")
    print_success(f"Created trigger '{name}' (ID: {trigger_id})")
    output(result, fmt=ctx.state.output_format)


@app.command("update")
def update_trigger(
    trigger_id: Annotated[str, typer.Argument(help="Trigger ID to update")],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="New trigger name"),
    ] = None,
) -> None:
    """Update an existing trigger in the workspace.

    Fetches the current trigger, applies changes, and saves. Only specified
    fields are changed; everything else is preserved.

    Examples:
        gtm trigger update 295 --name "All Pages - New"
    """
    ctx = resolve_workspace_context()

    if not name:
        print_error("No changes specified. Use --name to rename the trigger.")
        raise typer.Exit(1)

    triggers = ctx.client.list_triggers(**ctx.api_kwargs)
    trigger = next((t for t in triggers if t.get("triggerId") == trigger_id), None)
    if not trigger:
        print_error(f"Trigger '{trigger_id}' not found")
        raise typer.Exit(1)

    if name:
        trigger["name"] = name

    result = ctx.client.update_trigger(
        trigger_id=trigger_id, trigger_body=trigger, **ctx.api_kwargs
    )
    print_success(f"Updated trigger '{result.get('name', trigger_id)}' (ID: {trigger_id})")
    output(result, fmt=ctx.state.output_format)


@app.command("delete")
def delete_trigger(
    trigger_id: Annotated[str, typer.Argument(help="Trigger ID to delete")],
) -> None:
    """Delete a trigger from the workspace."""
    ctx = resolve_workspace_context()

    triggers = ctx.client.list_triggers(**ctx.api_kwargs)
    trigger = next((t for t in triggers if t.get("triggerId") == trigger_id), None)
    if not trigger:
        print_error(f"Trigger '{trigger_id}' not found")
        raise typer.Exit(1)

    trigger_name = trigger.get("name", trigger_id)
    if not ctx.state.yes and not confirm(f"Delete trigger '{trigger_name}' (ID: {trigger_id})?"):
        raise typer.Exit(0)

    ctx.client.delete_trigger(trigger_id=trigger_id, **ctx.api_kwargs)
    print_success(f"Deleted trigger '{trigger_name}' (ID: {trigger_id})")
