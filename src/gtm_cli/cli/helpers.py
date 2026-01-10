"""Shared helper functions for CLI commands."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from gtm_cli.utils.output import print_error, print_info

if TYPE_CHECKING:
    from gtm_cli.cli.main import State
    from gtm_cli.core.client import GTMClient


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
