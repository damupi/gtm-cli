"""Workspace CLI commands."""

from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import (
    resolve_account_id,
    resolve_container_id,
    resolve_workspace_id,
)
from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output, print_error, print_info, print_success, print_warning

app = typer.Typer(
    help="""Manage GTM workspaces.

Workspaces are where you edit tags, triggers, and variables before publishing.
Every container has a "Default Workspace" with ID 1.

Auto-detects account/container if you have only one of each.

Example: gtm workspace list
"""
)


@app.command("list")
def list_workspaces() -> None:
    """List all workspaces in the container."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)

    workspaces = client.list_workspaces(
        account_id=account_id,
        container_id=container_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    data = [
        {
            "workspace_id": w.get("workspaceId", ""),
            "name": w.get("name", ""),
            "description": w.get("description", ""),
        }
        for w in workspaces
    ]

    output(data, fmt=state.output_format, title="Workspaces")


@app.command("get")
def get_workspace(
    workspace_id: Annotated[
        str | None,
        typer.Argument(help="Workspace ID (uses default if not specified)"),
    ] = None,
) -> None:
    """Get details of a specific workspace."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)

    wid = workspace_id or state.workspace_id
    if not wid:
        print_error("No workspace ID provided. Use --workspace-id or set a default.")
        raise typer.Exit(1)

    workspace = client.get_workspace(
        account_id=account_id,
        container_id=container_id,
        workspace_id=wid,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    output(workspace, fmt=state.output_format)


@app.command("status")
def workspace_status() -> None:
    """Show pending changes in the workspace.

    Lists all modified tags, triggers, variables, and folders that haven't
    been published yet.
    """
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

    status = client.get_workspace_status(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    changes = status.get("workspaceChange", [])
    conflicts = status.get("mergeConflict", [])

    if conflicts:
        print_warning(f"Found {len(conflicts)} merge conflict(s) that must be resolved first!")

    if not changes:
        print_info("No pending changes in workspace.")
        return

    # Group changes by type
    data = []
    for change in changes:
        change_type = change.get("changeStatus", "unknown")
        # Determine what was changed (tag, trigger, variable, or folder)
        entity_type = "unknown"
        entity_name = ""
        if "tag" in change:
            entity_type = "tag"
            entity_name = change["tag"].get("name", "")
        elif "trigger" in change:
            entity_type = "trigger"
            entity_name = change["trigger"].get("name", "")
        elif "variable" in change:
            entity_type = "variable"
            entity_name = change["variable"].get("name", "")
        elif "folder" in change:
            entity_type = "folder"
            entity_name = change["folder"].get("name", "")

        data.append({
            "type": entity_type,
            "name": entity_name,
            "change": change_type,
        })

    print_info(f"Found {len(changes)} pending change(s):")
    output(data, fmt=state.output_format, title="Pending Changes")


def _generate_change_summary(changes: list[dict[str, Any]]) -> str:
    """Generate a summary of changes for version notes."""
    # Group changes by type and action
    by_type: dict[str, dict[str, list[str]]] = {}
    for change in changes:
        change_status = change.get("changeStatus", "unknown")
        # Determine what was changed
        for entity_type in ["tag", "trigger", "variable", "folder"]:
            if entity_type in change:
                entity_name = change[entity_type].get("name", "unnamed")
                if entity_type not in by_type:
                    by_type[entity_type] = {}
                if change_status not in by_type[entity_type]:
                    by_type[entity_type][change_status] = []
                by_type[entity_type][change_status].append(entity_name)
                break

    # Build summary
    parts = []
    action_verbs = {
        "added": "Added",
        "deleted": "Deleted",
        "updated": "Updated",
        "changeStatusUnspecified": "Modified",
    }
    for entity_type, actions in by_type.items():
        for action, names in actions.items():
            verb = action_verbs.get(action, action.capitalize())
            if len(names) <= 3:
                parts.append(f"{verb} {entity_type}(s): {', '.join(names)}")
            else:
                parts.append(f"{verb} {len(names)} {entity_type}(s)")

    return "; ".join(parts) if parts else "Workspace changes"


@app.command("publish")
def workspace_publish(
    name: Annotated[
        str | None,
        typer.Option(
            "--name",
            "-n",
            help="Version name",
        ),
    ] = None,
    notes: Annotated[
        str | None,
        typer.Option(
            "--notes",
            help="Version notes describing what changed",
        ),
    ] = None,
) -> None:
    """Create a version from workspace changes and publish it.

    This creates a new container version from all pending workspace changes,
    then publishes it to make it live.

    Shows pending changes and prompts for version name and notes.

    Example: gtm workspace publish
    Example: gtm workspace publish --name "v1.2" --notes "Fixed consent settings"
    """
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

    # First check for pending changes
    status = client.get_workspace_status(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    changes = status.get("workspaceChange", [])
    conflicts = status.get("mergeConflict", [])

    if conflicts:
        print_error(f"Cannot publish: {len(conflicts)} merge conflict(s) must be resolved first!")
        raise typer.Exit(1)

    if not changes:
        print_warning("No pending changes to publish.")
        raise typer.Exit(0)

    # Show pending changes
    print_info(f"Found {len(changes)} pending change(s):")
    change_data = []
    for change in changes:
        change_type = change.get("changeStatus", "unknown")
        entity_type = "unknown"
        entity_name = ""
        for etype in ["tag", "trigger", "variable", "folder"]:
            if etype in change:
                entity_type = etype
                entity_name = change[etype].get("name", "")
                break
        change_data.append({"type": entity_type, "name": entity_name, "change": change_type})
    output(change_data, fmt=state.output_format, title="Changes to Publish")

    # Generate suggested notes from changes
    suggested_notes = _generate_change_summary(changes)

    # Prompt for name and notes if not provided (unless --yes flag)
    version_name = name
    version_notes = notes

    if not state.yes:
        if not version_name:
            version_name = typer.prompt("Version name (optional)", default="", show_default=False)
            if not version_name:
                version_name = None
        if not version_notes:
            version_notes = typer.prompt(
                "Version notes",
                default=suggested_notes,
            )

        # Confirm publish
        if not typer.confirm("Publish this version?", default=True):
            print_info("Cancelled.")
            raise typer.Exit(0)
    else:
        # With --yes, use suggested notes if none provided
        if not version_notes:
            version_notes = suggested_notes

    print_info(f"Creating version from {len(changes)} change(s)...")

    # Create version
    result = client.create_version(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        name=version_name,
        notes=version_notes,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    # Check for compiler errors
    if "compilerError" in result:
        print_error("Version creation failed with compiler errors:")
        output(result["compilerError"], fmt=state.output_format)
        raise typer.Exit(1)

    version = result.get("containerVersion", {})
    version_id = version.get("containerVersionId")

    if not version_id:
        print_error("Failed to create version - no version ID returned")
        raise typer.Exit(1)

    print_info(f"Created version {version_id}, publishing...")

    # Publish the version
    publish_result = client.publish_version(
        account_id=account_id,
        container_id=container_id,
        version_id=version_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    published_version = publish_result.get("containerVersion", {})
    print_success(
        f"Published version {published_version.get('containerVersionId')} "
        f"({published_version.get('name', 'unnamed')})"
    )
