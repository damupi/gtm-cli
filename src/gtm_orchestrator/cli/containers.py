"""Container CLI commands."""

from typing import Annotated

import typer

from gtm_orchestrator.cli.main import get_state
from gtm_orchestrator.core.client import get_client
from gtm_orchestrator.utils.output import output, print_error

app = typer.Typer(help="Manage GTM containers")


@app.command("list")
def list_containers() -> None:
    """List all containers in the account."""
    state = get_state()
    client = get_client()

    if not state.account_id:
        print_error("No account ID. Use --account-id or set a default in your profile.")
        raise typer.Exit(1)

    containers = client.list_containers(
        account_id=state.account_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    data = [
        {
            "container_id": c.get("containerId", ""),
            "public_id": c.get("publicId", ""),
            "name": c.get("name", ""),
            "usage_context": ", ".join(c.get("usageContext", [])),
        }
        for c in containers
    ]

    output(data, fmt=state.output_format, title="Containers")


@app.command("get")
def get_container(
    container_id: Annotated[
        str | None,
        typer.Argument(help="Container ID (uses default if not specified)"),
    ] = None,
) -> None:
    """Get details of a specific container."""
    state = get_state()
    client = get_client()

    if not state.account_id:
        print_error("No account ID. Use --account-id or set a default in your profile.")
        raise typer.Exit(1)

    cid = container_id or state.container_id
    if not cid:
        print_error("No container ID provided. Use --container-id or set a default.")
        raise typer.Exit(1)

    container = client.get_container(
        account_id=state.account_id,
        container_id=cid,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    output(container, fmt=state.output_format)
