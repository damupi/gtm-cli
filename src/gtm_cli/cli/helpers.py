"""Shared helper functions for CLI commands."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from gtm_cli.utils.output import print_error, print_info, print_warning

if TYPE_CHECKING:
    from gtm_cli.cli.main import State
    from gtm_cli.core.client import GTMClient


@dataclass(frozen=True)
class WorkspaceContext:
    """Resolved workspace context with state, client, and IDs."""

    state: State
    client: GTMClient
    account_id: str
    container_id: str
    workspace_id: str

    @cached_property
    def api_kwargs(self) -> dict[str, Any]:
        """Common kwargs for workspace-scoped client methods."""
        return {
            "account_id": self.account_id,
            "container_id": self.container_id,
            "workspace_id": self.workspace_id,
            "profile_name": self.state.profile,
            "service_account_path": self.state.service_account,
        }


def resolve_workspace_context() -> WorkspaceContext:
    """Resolve state, client, and workspace IDs in one call.

    Replaces the common 5-line boilerplate at the top of every workspace-scoped command.
    """
    from gtm_cli.cli.main import get_state
    from gtm_cli.core.client import get_client

    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)
    return WorkspaceContext(
        state=state,
        client=client,
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
    )


def add_authuser(url: str, authuser: int | None) -> str:
    """Add authuser parameter to GTM URL if specified.

    Inserts before the hash fragment: example.com/?authuser=1#/path
    """
    if not url or authuser is None:
        return url
    if "#" in url:
        base, fragment = url.split("#", 1)
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}authuser={authuser}#{fragment}"
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}authuser={authuser}"


def resolve_account_id(state: State, client: GTMClient) -> str:
    """Resolve account ID from state or auto-detect if only one account.

    If account_id is set in state, returns it.
    If user has exactly one account, auto-selects it.
    If user has multiple accounts, shows error with available accounts.
    """
    if state.account_id:
        return state.account_id

    # Try to auto-detect if user has only one account
    accounts = client.list_accounts(
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    if len(accounts) == 1:
        account_id = str(accounts[0].get("accountId", ""))
        print_info(f"Using account: {accounts[0].get('name')} ({account_id})")
        return account_id

    if len(accounts) == 0:
        print_error("No GTM accounts found for this user.")
        raise typer.Exit(1)

    # Multiple accounts - user must specify
    print_error("Multiple accounts found. Please specify --account-id:")
    for acc in accounts:
        print_error(f"  {acc.get('accountId')}: {acc.get('name')}")
    raise typer.Exit(1)


def resolve_container_id(state: State, client: GTMClient, account_id: str) -> str:
    """Resolve container ID from state or auto-detect if only one container.

    If container_id is set in state, returns it (resolving publicId to containerId if needed).
    If account has exactly one container, auto-selects it.
    If account has multiple containers, shows error with available containers.

    Note: The API uses internal containerId (numeric), but users typically know the
    publicId (GTM-XXXX). This function accepts either format but always returns
    the internal containerId for API use.
    """
    containers = client.list_containers(
        account_id=account_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    if state.container_id:
        # Check if it's a publicId (GTM-XXXX) and resolve to containerId
        for c in containers:
            if c.get("publicId") == state.container_id:
                return str(c.get("containerId", ""))
            if c.get("containerId") == state.container_id:
                return state.container_id
        # Not found - return as-is and let API error handle it
        return state.container_id

    if len(containers) == 1:
        container_id = str(containers[0].get("containerId", ""))
        public_id = containers[0].get("publicId", "")
        print_info(f"Using container: {containers[0].get('name')} ({public_id})")
        return container_id

    if len(containers) == 0:
        print_error("No containers found in this account.")
        raise typer.Exit(1)

    # Multiple containers - user must specify (show publicId which users know)
    print_error("Multiple containers found. Please specify --container-id:")
    for c in containers:
        print_error(f"  {c.get('publicId')}: {c.get('name')}")
    raise typer.Exit(1)


def load_json_merge_patch(json_file: Path, identity_fields: frozenset[str]) -> dict[str, Any]:
    """Read and validate a --json-file merge patch.

    The file must contain a single JSON object with only the fields to change.
    Identity fields the user must not patch (accountId, containerId, workspaceId,
    tagId/triggerId, path, fingerprint) are stripped with a warning rather than
    causing an error, since they're commonly present if the file was produced by
    editing a `gtm tag get`/`gtm trigger get` dump.

    Args:
        json_file: Path to the JSON file to read
        identity_fields: Top-level keys to strip (with a warning) if present

    Returns:
        The parsed patch dict, with identity fields removed

    Raises:
        typer.Exit: If the file can't be read, isn't valid JSON, or the top-level
            value isn't a JSON object
    """
    try:
        text = json_file.read_text()
    except OSError as e:
        print_error(f"Cannot read --json-file '{json_file}': {e}")
        raise typer.Exit(1) from e

    try:
        patch = json.loads(text)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON in --json-file '{json_file}': {e}")
        raise typer.Exit(1) from e

    if not isinstance(patch, dict):
        print_error(
            f"--json-file '{json_file}' must contain a JSON object at the top level "
            f"(got {type(patch).__name__})"
        )
        raise typer.Exit(1)

    ignored = sorted(k for k in identity_fields if k in patch)
    if ignored:
        print_warning(
            f"Ignoring identity field(s) in --json-file (not patchable): {', '.join(ignored)}"
        )
        for key in ignored:
            patch.pop(key)

    return patch


def apply_json_merge_patch(entity: dict[str, Any], patch: dict[str, Any]) -> None:
    """Merge a JSON patch onto an entity in place.

    Only the top-level fields present in `patch` are changed. Arrays (parameter,
    filter, customEventFilter, firingTriggerId, etc.) fully REPLACE the existing
    array — there is no per-element merge. Fields omitted from `patch` are left
    untouched on `entity`.
    """
    for key, value in patch.items():
        entity[key] = value


def resolve_workspace_id(
    state: State, client: GTMClient, account_id: str, container_id: str
) -> str:
    """Resolve workspace ID from state or auto-detect.

    If workspace_id is set in state, returns it.
    Otherwise auto-selects default workspace (ID "1") if it exists.
    If no default workspace, shows available workspaces.
    """
    if state.workspace_id:
        return state.workspace_id

    # Try to get workspaces
    workspaces = client.list_workspaces(
        account_id=account_id,
        container_id=container_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    if len(workspaces) == 0:
        print_error("No workspaces found in this container.")
        raise typer.Exit(1)

    # Check for default workspace (ID "1")
    default_ws = next((w for w in workspaces if w.get("workspaceId") == "1"), None)
    if default_ws:
        print_info(f"Using workspace: {default_ws.get('name')} (1)")
        return "1"

    # If only one workspace, use it
    if len(workspaces) == 1:
        workspace_id = str(workspaces[0].get("workspaceId", ""))
        print_info(f"Using workspace: {workspaces[0].get('name')} ({workspace_id})")
        return workspace_id

    # Multiple workspaces - user must specify
    print_error("Multiple workspaces found. Please specify --workspace-id:")
    for w in workspaces:
        print_error(f"  {w.get('workspaceId')}: {w.get('name')}")
    raise typer.Exit(1)
