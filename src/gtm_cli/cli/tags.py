"""Tag CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output, print_error

if TYPE_CHECKING:
    from gtm_cli.cli.main import State

app = typer.Typer(
    help="""Manage GTM tags.

Tags are the core building blocks in GTM - they define what code runs on your site.

Requires: --account-id, --container-id, --workspace-id (or set defaults in profile)

Example workflow:
    gtm account list                    # Find your account ID
    gtm container list -a ACCOUNT_ID    # Find your container ID
    gtm workspace list -a ACCOUNT_ID -c CONTAINER_ID  # Find workspace ID
    gtm tag list -a ACCOUNT_ID -c CONTAINER_ID -w WORKSPACE_ID
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
def list_tags() -> None:
    """List all tags in the workspace."""
    state = get_state()
    account_id, container_id, workspace_id = _require_ids(state)
    client = get_client()

    tags = client.list_tags(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    data = [
        {
            "tag_id": t.get("tagId", ""),
            "name": t.get("name", ""),
            "type": t.get("type", ""),
        }
        for t in tags
    ]

    output(data, fmt=state.output_format, title="Tags")


@app.command("get")
def get_tag(
    tag_id: Annotated[str, typer.Argument(help="Tag ID")],
) -> None:
    """Get details of a specific tag."""
    state = get_state()
    account_id, container_id, workspace_id = _require_ids(state)
    client = get_client()

    # Note: Full implementation would call client.get_tag()
    # For now, list and filter
    tags = client.list_tags(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    tag = next((t for t in tags if t.get("tagId") == tag_id), None)
    if not tag:
        print_error(f"Tag '{tag_id}' not found")
        raise typer.Exit(1)

    output(tag, fmt=state.output_format)
