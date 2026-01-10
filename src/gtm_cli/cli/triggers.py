"""Trigger CLI commands."""

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
    help="""Manage GTM triggers.

Triggers define WHEN your tags fire (e.g., page view, click, form submit).

Auto-detects account/container/workspace if you have only one of each.

Example: gtm trigger list
"""
)


@app.command("list")
def list_triggers() -> None:
    """List all triggers in the workspace."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

    triggers = client.list_triggers(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    data = [
        {
            "trigger_id": t.get("triggerId", ""),
            "name": t.get("name", ""),
            "type": t.get("type", ""),
        }
        for t in triggers
    ]

    output(data, fmt=state.output_format, title="Triggers")


@app.command("get")
def get_trigger(
    trigger_id: Annotated[str, typer.Argument(help="Trigger ID")],
) -> None:
    """Get details of a specific trigger."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

    triggers = client.list_triggers(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    trigger = next((t for t in triggers if t.get("triggerId") == trigger_id), None)
    if not trigger:
        print_error(f"Trigger '{trigger_id}' not found")
        raise typer.Exit(1)

    output(trigger, fmt=state.output_format)
