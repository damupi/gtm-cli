"""Version CLI commands."""

from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import resolve_account_id, resolve_container_id
from gtm_cli.cli.main import State, get_state
from gtm_cli.core.client import GTMClient, get_client
from gtm_cli.utils.errors import ResourceNotFoundError
from gtm_cli.utils.output import (
    OutputFormat,
    output,
    print_error,
    print_info,
    print_warning,
)

app = typer.Typer(
    help="""Manage GTM container versions.

The GTM API exposes stored version headers and full version snapshots, but not an
authoritative publication timestamp or publish/re-publish history. Do not use this
command group to infer whether a deployment happened within a date range.

Auto-detects account/container if you have only one of each.

Example: gtm version list
"""
)


def _resolve_container_context() -> tuple[State, GTMClient, str, str]:
    """Resolve state, client, account_id, container_id."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    return state, client, account_id, container_id


def _api_kwargs(state: State) -> dict[str, Any]:
    """Build common API kwargs from state."""
    return {
        "profile_name": state.profile,
        "service_account_path": state.service_account,
    }


@app.command("list")
def list_versions() -> None:
    """List stored version headers in the container.

    The GTM API version-header response does not provide an authoritative publication
    timestamp or publish/re-publish history. This command therefore does not display a
    publication date or offer date filters. A missing date cannot be interpreted as
    evidence that no deployment occurred.

    Example:
        gtm version list
    """
    state, client, account_id, container_id = _resolve_container_context()

    versions = client.list_versions(
        account_id=account_id,
        container_id=container_id,
        **_api_kwargs(state),
    )

    data = [
        {
            "version_id": v.get("containerVersionId", ""),
            "name": v.get("name", ""),
            "num_tags": v.get("numTags", 0),
            "num_triggers": v.get("numTriggers", 0),
            "num_variables": v.get("numVariables", 0),
        }
        for v in versions
    ]

    output(data, fmt=state.output_format, title="Versions")


@app.command("get")
def get_version(
    version_id: Annotated[str, typer.Argument(help="Version ID")],
) -> None:
    """Get full details of a specific version.

    Returns all tags, triggers, variables, and metadata for the version.
    """
    state, client, account_id, container_id = _resolve_container_context()

    try:
        version = client.get_version(
            account_id=account_id,
            container_id=container_id,
            version_id=version_id,
            **_api_kwargs(state),
        )
    except ResourceNotFoundError:
        print_error(f"Version '{version_id}' not found")
        raise typer.Exit(1) from None

    output(version, fmt=state.output_format)


@app.command("diff")
def diff_versions(
    v1: Annotated[str, typer.Argument(help="First version ID")],
    v2: Annotated[str, typer.Argument(help="Second version ID")],
) -> None:
    """Show what changed between two container versions.

    Compares tags, triggers, and variables to find additions, removals,
    and modifications. Useful for incident investigation.

    Examples:
        gtm version diff 42 43
        gtm version diff 100 105 -f json
    """
    state, client, account_id, container_id = _resolve_container_context()
    kwargs = {
        "account_id": account_id,
        "container_id": container_id,
        **_api_kwargs(state),
    }

    try:
        ver1 = client.get_version(version_id=v1, **kwargs)
    except ResourceNotFoundError:
        print_error(f"Version '{v1}' not found")
        raise typer.Exit(1) from None

    try:
        ver2 = client.get_version(version_id=v2, **kwargs)
    except ResourceNotFoundError:
        print_error(f"Version '{v2}' not found")
        raise typer.Exit(1) from None

    changes = _compute_diff(ver1, ver2)

    if not changes:
        print_warning(f"No differences found between version {v1} and {v2}.")
        return

    output(changes, fmt=state.output_format, title=f"Diff: v{v1} → v{v2}")

    # Summary
    added = sum(1 for c in changes if c["status"] == "added")
    removed = sum(1 for c in changes if c["status"] == "removed")
    modified = sum(1 for c in changes if c["status"] == "modified")
    if state.output_format == OutputFormat.TABLE:
        print_info(f"{added} added, {removed} removed, {modified} modified")


def _compute_diff(ver1: dict[str, Any], ver2: dict[str, Any]) -> list[dict[str, str]]:
    """Compute differences between two version snapshots."""
    changes: list[dict[str, str]] = []

    resource_types = [
        ("tag", "tag", "tagId"),
        ("trigger", "trigger", "triggerId"),
        ("variable", "variable", "variableId"),
    ]

    for resource_type, key, id_field in resource_types:
        items1 = {item[id_field]: item for item in ver1.get(key, []) if id_field in item}
        items2 = {item[id_field]: item for item in ver2.get(key, []) if id_field in item}

        ids1 = set(items1.keys())
        ids2 = set(items2.keys())

        for item_id in sorted(ids2 - ids1):
            item = items2[item_id]
            changes.append(
                {
                    "status": "added",
                    "type": resource_type,
                    "name": item.get("name", ""),
                    "id": item_id,
                }
            )

        for item_id in sorted(ids1 - ids2):
            item = items1[item_id]
            changes.append(
                {
                    "status": "removed",
                    "type": resource_type,
                    "name": item.get("name", ""),
                    "id": item_id,
                }
            )

        for item_id in sorted(ids1 & ids2):
            old = items1[item_id]
            new = items2[item_id]
            if old.get("fingerprint") != new.get("fingerprint"):
                changes.append(
                    {
                        "status": "modified",
                        "type": resource_type,
                        "name": new.get("name", ""),
                        "id": item_id,
                    }
                )

    return changes
