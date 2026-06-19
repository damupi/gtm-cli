"""Main CLI entry point for GTM CLI."""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from gtm_cli import __version__
from gtm_cli.utils.output import OutputFormat

# Create the main app
app = typer.Typer(
    name="gtm",
    help=(
        "GTM CLI - Command-line tool for Google Tag Manager API v2\n\n"
        "[bold yellow]IMPORTANT:[/bold yellow] Global flags (-a, -c, -w, -f) must come BEFORE the subcommand.\n\n"
        "  [green]gtm -a 123 -c 456 -w 3 -f json variable list[/green]   ✓ correct\n"
        "  [red]gtm variable list --format json[/red]                    ✗ wrong — 'No such option' error"
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
)

console = Console()
error_console = Console(stderr=True)


# Global state for CLI options
class State:
    """Global state for CLI options."""

    def __init__(self) -> None:
        self.profile: str | None = None
        self.account_id: str | None = None
        self.container_id: str | None = None
        self.workspace_id: str | None = None
        self.service_account: str | None = None
        self.output_format: OutputFormat = OutputFormat.TABLE
        self.verbose: bool = False
        self.dry_run: bool = False
        self.yes: bool = False
        self.authuser: int | None = None


state = State()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"gtm-cli version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Use a specific profile",
            envvar="GTM_PROFILE",
        ),
    ] = None,
    account_id: Annotated[
        str | None,
        typer.Option(
            "--account-id",
            "-a",
            help="Override default account ID",
            envvar="GTM_ACCOUNT_ID",
        ),
    ] = None,
    container_id: Annotated[
        str | None,
        typer.Option(
            "--container-id",
            "-c",
            help="Override default container ID",
            envvar="GTM_CONTAINER_ID",
        ),
    ] = None,
    workspace_id: Annotated[
        str | None,
        typer.Option(
            "--workspace-id",
            "-w",
            help="Override default workspace ID",
            envvar="GTM_WORKSPACE_ID",
        ),
    ] = None,
    service_account: Annotated[
        Path | None,
        typer.Option(
            "--service-account",
            "-s",
            help="Use service account credentials file",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Output format: table (default) / json / yaml / plain (tab-separated, for pipes)",
        ),
    ] = OutputFormat.TABLE,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            "-v",
            help="Enable debug logging",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show API calls without executing",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            "-y",
            help="Skip confirmation prompts",
        ),
    ] = False,
    authuser: Annotated[
        int | None,
        typer.Option(
            "--authuser",
            "-u",
            help="Append authuser=N to GTM URLs (for multi-account Google sessions)",
            envvar="GTM_AUTHUSER",
        ),
    ] = None,
    _version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """GTM CLI - Command-line tool for Google Tag Manager API v2.

    Manage your Google Tag Manager containers, tags, triggers, and variables
    from the command line.

    GTM Hierarchy: Account → Container → Workspace → Tags/Triggers/Variables

    Global flags (-a, -c, -w, -f) MUST go before the subcommand:

        gtm -a 123 -c 456 -w 3 -f json variable list   ✓
        gtm variable list --format json                 ✗  ('No such option' error)

    Quick Start:
        gtm setup              # First-time setup wizard
        gtm login              # Authenticate with Google
        gtm account list       # List your GTM accounts
    """
    from gtm_cli.core.config import get_config_manager

    # Load profile defaults
    config_manager = get_config_manager()
    profile_obj = config_manager.get_profile(profile)

    # CLI options override profile defaults
    state.profile = profile_obj.name
    state.account_id = account_id or profile_obj.defaults.account_id
    state.container_id = container_id or profile_obj.defaults.container_id
    state.workspace_id = workspace_id or profile_obj.defaults.workspace_id
    state.service_account = str(service_account) if service_account else None
    state.output_format = output_format
    state.verbose = verbose
    state.dry_run = dry_run
    state.yes = yes
    state.authuser = authuser


def get_state() -> State:
    """Get the global CLI state."""
    return state


# Import and register subcommands
def register_commands() -> None:
    """Register all subcommands."""
    from gtm_cli.cli import accounts as accounts_cli
    from gtm_cli.cli import auth as auth_cli
    from gtm_cli.cli import containers as containers_cli
    from gtm_cli.cli import init as init_cli
    from gtm_cli.cli import profile as profile_cli
    from gtm_cli.cli import setup as setup_cli
    from gtm_cli.cli import tags as tags_cli
    from gtm_cli.cli import triggers as triggers_cli
    from gtm_cli.cli import variables as variables_cli
    from gtm_cli.cli import versions as versions_cli
    from gtm_cli.cli import workspaces as workspaces_cli

    # Register commands
    app.command(name="init")(init_cli.init)
    app.command(name="setup")(setup_cli.setup)
    app.command(name="login")(auth_cli.login)
    app.command(name="logout")(auth_cli.logout)
    app.add_typer(profile_cli.app, name="profile")
    app.add_typer(accounts_cli.app, name="account")
    app.add_typer(containers_cli.app, name="container")
    app.add_typer(workspaces_cli.app, name="workspace")
    app.add_typer(tags_cli.app, name="tag")
    app.add_typer(triggers_cli.app, name="trigger")
    app.add_typer(variables_cli.app, name="variable")
    app.add_typer(versions_cli.app, name="version")


# Register commands on import
register_commands()


if __name__ == "__main__":
    app()
