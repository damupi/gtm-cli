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
    help="GTM CLI - Command-line tool for Google Tag Manager API v2",
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
            help="Output format",
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
    """GTM Orchestrator - CLI for Google Tag Manager API v2.

    Manage your Google Tag Manager containers, tags, triggers, and variables
    from the command line.
    """
    state.profile = profile
    state.account_id = account_id
    state.container_id = container_id
    state.workspace_id = workspace_id
    state.service_account = str(service_account) if service_account else None
    state.output_format = output_format
    state.verbose = verbose
    state.dry_run = dry_run
    state.yes = yes


def get_state() -> State:
    """Get the global CLI state."""
    return state


# Import and register subcommands
def register_commands() -> None:
    """Register all subcommands."""
    from gtm_cli.cli import accounts as accounts_cli
    from gtm_cli.cli import auth as auth_cli
    from gtm_cli.cli import containers as containers_cli
    from gtm_cli.cli import profile as profile_cli
    from gtm_cli.cli import setup as setup_cli
    from gtm_cli.cli import tags as tags_cli
    from gtm_cli.cli import triggers as triggers_cli
    from gtm_cli.cli import variables as variables_cli
    from gtm_cli.cli import versions as versions_cli
    from gtm_cli.cli import workspaces as workspaces_cli

    # Register commands
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
