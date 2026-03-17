"""Trigger CLI commands."""

from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import resolve_workspace_context
from gtm_cli.utils.output import confirm, output, print_error, print_info, print_success

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


@app.command("update")
def update_trigger(
    trigger_id: Annotated[str, typer.Argument(help="Trigger ID to update")],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="New trigger name"),
    ] = None,
    json_body: Annotated[
        str | None,
        typer.Option(
            "--json",
            help="Full trigger JSON body as inline string or file path (overrides --name)",
        ),
    ] = None,
) -> None:
    """Update an existing trigger.

    Fetches the current trigger, applies changes, and shows a field-level diff
    before calling the API.

    Examples:
        gtm trigger update 12345 --name "New Name"
        gtm trigger update 12345 --json '{"name":"New Name","type":"pageview"}'
        gtm trigger update 12345 --json ./trigger.json
    """
    import json
    from pathlib import Path

    ctx = resolve_workspace_context()

    triggers = ctx.client.list_triggers(**ctx.api_kwargs)
    trigger = next((t for t in triggers if t.get("triggerId") == trigger_id), None)
    if not trigger:
        print_error(f"Trigger '{trigger_id}' not found")
        raise typer.Exit(1)

    if json_body is not None:
        p = Path(json_body)
        if p.exists() and p.is_file():
            with open(p) as f:
                updates = json.load(f)
        else:
            updates = json.loads(json_body)
        body = {**trigger, **updates}
    else:
        body = dict(trigger)
        if name is not None:
            body["name"] = name

    changed = {k: (trigger.get(k), body.get(k)) for k in body if body.get(k) != trigger.get(k)}
    if not changed:
        print_info("No changes detected.")
        return

    for field, (old, new) in changed.items():
        print_info(f"  {field}: {old!r} → {new!r}")

    if ctx.state.dry_run:
        print_info("[dry-run] Would update trigger, skipping API call.")
        return

    result = ctx.client.update_trigger(
        trigger_id=trigger_id,
        trigger_body=body,
        **ctx.api_kwargs,
    )
    print_success(f"Updated trigger '{result.get('name', '')}' (ID: {result.get('triggerId', '')})")
    output(result, fmt=ctx.state.output_format)
