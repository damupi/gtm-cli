"""Trigger CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output, print_error

if TYPE_CHECKING:
    from gtm_cli.cli.main import State

app = typer.Typer(
    help="""Manage GTM triggers.

Triggers define WHEN your tags fire (e.g., page view, click, form submit).

Requires: --account-id, --container-id, --workspace-id (or set defaults in profile)

Example: gtm trigger list -a 123456 -c GTM-XXXX -w 1
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
def list_triggers() -> None:
    """List all triggers in the workspace."""
    state = get_state()
    account_id, container_id, workspace_id = _require_ids(state)
    client = get_client()

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
    account_id, container_id, workspace_id = _require_ids(state)
    client = get_client()

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
