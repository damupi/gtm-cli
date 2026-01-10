"""Tag CLI commands."""

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
    help="""Manage GTM tags.

Tags are the core building blocks in GTM - they define what code runs on your site.

Auto-detects account/container/workspace if you have only one of each.

Example: gtm tag list
"""
)


@app.command("list")
def list_tags() -> None:
    """List all tags in the workspace."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

    tags = client.list_tags(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    # Build folder lookup for names
    folders = client.list_folders(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )
    folder_names = {f.get("folderId"): f.get("name") for f in folders}

    data = [
        {
            "tag_id": t.get("tagId", ""),
            "name": t.get("name", ""),
            "type": t.get("type", ""),
            "paused": "paused" if t.get("paused") else "",
            "folder": folder_names.get(t.get("parentFolderId"), ""),
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
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

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
