"""Profile management CLI commands."""

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from gtm_cli.core.auth import get_auth_manager
from gtm_cli.core.config import Profile, get_config_manager
from gtm_cli.utils.errors import ProfileExistsError, ProfileNotFoundError
from gtm_cli.utils.output import print_error, print_success

app = typer.Typer(help="Manage GTM profiles")
console = Console()


@app.command("list")
def list_profiles() -> None:
    """List all profiles."""
    config_manager = get_config_manager()
    auth_manager = get_auth_manager()
    profiles = config_manager.list_profiles()
    default_profile = config_manager.get_global_config().default_profile

    if not profiles:
        console.print("No profiles found. Create one with: gtm profile create <name>")
        return

    table = Table(title="Profiles")
    table.add_column("", style="cyan", width=3)
    table.add_column("Name", style="bold")
    table.add_column("Account ID")
    table.add_column("Container ID")
    table.add_column("Status")

    for name in profiles:
        profile = config_manager.get_profile(name)
        is_default = "→" if name == default_profile else ""
        login_status = auth_manager.get_login_status(name)

        if login_status["logged_in"]:
            status = f"[green]logged in as {login_status.get('email', 'unknown')}[/green]"
        else:
            status = "[dim]not logged in[/dim]"

        table.add_row(
            is_default,
            name,
            profile.defaults.account_id or "-",
            profile.defaults.container_id or "-",
            status,
        )

    console.print(table)


@app.command("create")
def create_profile(
    name: Annotated[str, typer.Argument(help="Profile name")],
    account_id: Annotated[
        str | None,
        typer.Option("--account-id", "-a", help="Default account ID"),
    ] = None,
    container_id: Annotated[
        str | None,
        typer.Option("--container-id", "-c", help="Default container ID"),
    ] = None,
    auth_method: Annotated[
        str,
        typer.Option("--auth-method", help="Authentication method (oauth or service_account)"),
    ] = "oauth",
    credentials_path: Annotated[
        str | None,
        typer.Option("--credentials-path", help="Path to service account credentials"),
    ] = None,
) -> None:
    """Create a new profile."""
    config_manager = get_config_manager()

    try:
        from gtm_cli.core.config import AuthConfig, DefaultsConfig

        profile = Profile(
            name=name,
            auth=AuthConfig(
                method=auth_method,
                credentials_path=credentials_path,
            ),
            defaults=DefaultsConfig(
                account_id=account_id,
                container_id=container_id,
            ),
        )

        config_manager.save_profile(profile)
        print_success(f"Created profile '{name}'")

        # Set as default if it's the only profile
        if len(config_manager.list_profiles()) == 1:
            config_manager.set_default_profile(name)
            console.print(f"Set '{name}' as default profile")

    except ProfileExistsError:
        print_error(f"Profile '{name}' already exists. Use 'gtm profile show {name}' to view it.")
        raise typer.Exit(1) from None


@app.command("use")
def use_profile(
    name: Annotated[str, typer.Argument(help="Profile name to set as default")],
) -> None:
    """Set the default profile."""
    config_manager = get_config_manager()

    try:
        config_manager.set_default_profile(name)
        print_success(f"Switched default profile to '{name}'")
    except ProfileNotFoundError:
        print_error(f"Profile '{name}' not found. Create it with: gtm profile create {name}")
        raise typer.Exit(1) from None


@app.command("delete")
def delete_profile(
    name: Annotated[str, typer.Argument(help="Profile name to delete")],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation"),
    ] = False,
) -> None:
    """Delete a profile."""
    config_manager = get_config_manager()

    if not yes:
        confirm = typer.confirm(f"Are you sure you want to delete profile '{name}'?")
        if not confirm:
            console.print("Cancelled")
            raise typer.Exit(0)

    try:
        config_manager.delete_profile(name)
        print_success(f"Deleted profile '{name}'")
    except ProfileNotFoundError:
        print_error(f"Profile '{name}' not found")
        raise typer.Exit(1) from None


@app.command("show")
def show_profile(
    name: Annotated[
        str | None,
        typer.Argument(help="Profile name (uses default if not specified)"),
    ] = None,
) -> None:
    """Show profile details."""
    config_manager = get_config_manager()
    auth_manager = get_auth_manager()

    try:
        profile = config_manager.get_profile(name)
        login_status = auth_manager.get_login_status(profile.name)
        default_profile = config_manager.get_global_config().default_profile

        table = Table(title=f"Profile: {profile.name}", show_header=False)
        table.add_column("Field", style="cyan")
        table.add_column("Value")

        table.add_row("Name", profile.name)
        table.add_row("Default", "Yes" if profile.name == default_profile else "No")
        table.add_row("Auth Method", profile.auth.method)
        table.add_row("Credentials Path", profile.auth.credentials_path or "-")
        table.add_row("Scopes", profile.auth.scopes)
        table.add_row("Account ID", profile.defaults.account_id or "-")
        table.add_row("Container ID", profile.defaults.container_id or "-")
        table.add_row("Workspace ID", profile.defaults.workspace_id or "-")

        if login_status["logged_in"]:
            table.add_row("Status", f"[green]Logged in as {login_status.get('email', 'unknown')}[/green]")
        else:
            table.add_row("Status", "[dim]Not logged in[/dim]")

        console.print(table)

    except ProfileNotFoundError:
        print_error(f"Profile '{name}' not found")
        raise typer.Exit(1) from None
