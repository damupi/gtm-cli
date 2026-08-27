"""Environment CLI commands."""

from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import resolve_account_id, resolve_container_id
from gtm_cli.cli.main import State, get_state
from gtm_cli.core.client import GTMClient, get_client
from gtm_cli.utils.errors import ResourceNotFoundError
from gtm_cli.utils.output import (
    OutputFormat,
    confirm,
    output,
    print_dry_run,
    print_error,
    print_info,
    print_success,
)

app = typer.Typer(
    help="""Manage GTM environments (accounts.containers.environments).

Environments are container-scoped (account + container only — not workspace-
scoped), similar to `gtm version`. Each environment points at either a
published container version or a live workspace, and is used to generate
Preview/Publish links for QA, staging, etc.

Auto-detects account/container if you have only one of each.

Example: gtm environment list
"""
)

_NON_USER_TYPES = {"live", "latest", "workspace"}

_AUTH_CODE_REDACTED = "<redacted, use --format json to view>"


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


def _redact_auth_code(environment: dict[str, Any], state: State) -> dict[str, Any]:
    """Redact authorizationCode in table/plain output; JSON/YAML keep the real value."""
    if state.output_format not in (OutputFormat.JSON, OutputFormat.YAML) and environment.get(
        "authorizationCode"
    ):
        return {**environment, "authorizationCode": _AUTH_CODE_REDACTED}
    return environment


@app.command("list")
def list_environments() -> None:
    """List all environments in the container.

    Examples:
        gtm environment list
        gtm -a 123 -c 456 environment list -f json
    """
    state, client, account_id, container_id = _resolve_container_context()

    environments = client.list_environments(
        account_id=account_id,
        container_id=container_id,
        **_api_kwargs(state),
    )

    data = [
        {
            "environment_id": e.get("environmentId", ""),
            "name": e.get("name", ""),
            "type": e.get("type", ""),
            "url": e.get("url", ""),
            "enable_debug": e.get("enableDebug", False),
        }
        for e in environments
    ]

    output(data, fmt=state.output_format, title="Environments")


@app.command("get")
def get_environment(
    environment_id: Annotated[str, typer.Argument(help="Environment ID")],
) -> None:
    """Get full details of a specific environment.

    In table/plain output, the sensitive `authorizationCode` field is redacted.
    Use `--format json` or `--format yaml` to view the real value.

    Examples:
        gtm environment get 5
        gtm -f json environment get 5
    """
    state, client, account_id, container_id = _resolve_container_context()

    try:
        environment = client.get_environment(
            account_id=account_id,
            container_id=container_id,
            environment_id=environment_id,
            **_api_kwargs(state),
        )
    except ResourceNotFoundError:
        print_error(f"Environment '{environment_id}' not found")
        raise typer.Exit(1) from None

    environment = _redact_auth_code(environment, state)

    output(environment, fmt=state.output_format)


@app.command("create")
def create_environment(
    name: Annotated[str, typer.Option("--name", "-n", help="Environment display name")],
    description: Annotated[
        str | None,
        typer.Option("--description", help="Environment description"),
    ] = None,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Default URL opened when previewing this environment"),
    ] = None,
    enable_debug: Annotated[
        bool,
        typer.Option(
            "--enable-debug",
            help="Enable Preview/Debug mode by default for this environment",
        ),
    ] = False,
    container_version_id: Annotated[
        str | None,
        typer.Option(
            "--container-version-id",
            help=(
                "Pin this environment to a published container version (mutually exclusive "
                "with --workspace-id). Sets the top-level containerVersionId field; the "
                "environment will always serve that specific version."
            ),
        ),
    ] = None,
    workspace_id: Annotated[
        str | None,
        typer.Option(
            "--workspace-id",
            help=(
                "Point this environment at a live workspace (mutually exclusive with "
                "--container-version-id). Sets the top-level workspaceId field; the "
                "environment will always serve the workspace's current (unpublished) state."
            ),
        ),
    ] = None,
) -> None:
    """Create a new environment in the container.

    Exactly one of --container-version-id or --workspace-id must be given.

    In table/plain output, the sensitive `authorizationCode` field returned by
    the API is redacted (same rule as `environment get`). Use `--format json`
    or `--format yaml` to capture it — needed for Tag Assistant / automation.

    Examples:
        gtm environment create --name "Playwright QA" --description "QA env" \\
            --url "https://example.com" --container-version-id 3 --enable-debug
        gtm environment create --name "Dev sandbox" --workspace-id 9
        gtm -f json environment create --name "CI env" --workspace-id 9   # to capture authorizationCode
    """
    state, client, account_id, container_id = _resolve_container_context()

    if container_version_id and workspace_id:
        print_error("Specify only one of --container-version-id or --workspace-id, not both.")
        raise typer.Exit(1)
    if not container_version_id and not workspace_id:
        print_error(
            "One of --container-version-id or --workspace-id is required to create an environment."
        )
        raise typer.Exit(1)

    environment_body: dict[str, Any] = {
        "name": name,
        "type": "user",
        "enableDebug": enable_debug,
    }
    if description is not None:
        environment_body["description"] = description
    if url is not None:
        environment_body["url"] = url
    if container_version_id is not None:
        environment_body["containerVersionId"] = container_version_id
    if workspace_id is not None:
        environment_body["workspaceId"] = workspace_id

    if state.dry_run:
        print_dry_run(f"create environment '{name}' in container {container_id}")
        raise typer.Exit(0)

    result = client.create_environment(
        account_id=account_id,
        container_id=container_id,
        environment_body=environment_body,
        **_api_kwargs(state),
    )

    environment_id = result.get("environmentId", "")
    print_success(f"Created environment '{name}' (ID: {environment_id})")
    if state.output_format not in (OutputFormat.JSON, OutputFormat.YAML) and result.get(
        "authorizationCode"
    ):
        print_info("authorizationCode redacted — use --format json/yaml to view it.")
    output(_redact_auth_code(result, state), fmt=state.output_format)


@app.command("delete")
def delete_environment(
    environment_id: Annotated[str, typer.Argument(help="Environment ID to delete")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Delete an environment from the container.

    Only user-created environments (type "user") can be deleted. The
    auto-managed `live`, `latest`, and `workspace`-linked environments are
    refused.

    Examples:
        gtm environment delete 5
        gtm environment delete 5 --yes
    """
    state, client, account_id, container_id = _resolve_container_context()

    try:
        environment = client.get_environment(
            account_id=account_id,
            container_id=container_id,
            environment_id=environment_id,
            **_api_kwargs(state),
        )
    except ResourceNotFoundError:
        print_error(f"Environment '{environment_id}' not found")
        raise typer.Exit(1) from None

    env_type = environment.get("type", "")
    if env_type in _NON_USER_TYPES:
        print_error(
            f"Cannot delete environment '{environment_id}': it is a '{env_type}' environment "
            "managed automatically by GTM. Only user-created environments can be deleted."
        )
        raise typer.Exit(1)

    env_name = environment.get("name", environment_id)

    if (
        not state.yes
        and not yes
        and not confirm(f"Delete environment '{env_name}' (ID: {environment_id})?")
    ):
        raise typer.Exit(0)

    if state.dry_run:
        print_dry_run(f"delete environment '{env_name}' (ID: {environment_id})")
        raise typer.Exit(0)

    client.delete_environment(
        account_id=account_id,
        container_id=container_id,
        environment_id=environment_id,
        **_api_kwargs(state),
    )
    print_success(f"Deleted environment '{env_name}' (ID: {environment_id})")
