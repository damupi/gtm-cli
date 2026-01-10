"""Account CLI commands."""

from typing import Annotated

import typer

from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output

app = typer.Typer(
    help="""Manage GTM accounts.

Accounts are the top level of the GTM hierarchy. Most users have one account.

GTM Hierarchy: Account → Container → Workspace → Tags/Triggers/Variables

Start here to discover your account ID, then drill down to containers.
"""
)


@app.command("list")
def list_accounts() -> None:
    """List all GTM accounts."""
    state = get_state()
    client = get_client()

    accounts = client.list_accounts(
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    # Simplify output
    data = [
        {
            "account_id": acc.get("accountId", ""),
            "name": acc.get("name", ""),
            "share_data": acc.get("shareData", False),
        }
        for acc in accounts
    ]

    output(data, fmt=state.output_format, title="Accounts")


@app.command("get")
def get_account(
    account_id: Annotated[
        str | None,
        typer.Argument(help="Account ID (uses default if not specified)"),
    ] = None,
) -> None:
    """Get details of a specific account."""
    state = get_state()
    client = get_client()

    # Use provided or default account ID
    acc_id = account_id or state.account_id
    if not acc_id:
        typer.echo("Error: No account ID provided. Use --account-id or set a default.")
        raise typer.Exit(1)

    account = client.get_account(
        account_id=acc_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    output(account, fmt=state.output_format)
