"""Authentication CLI commands."""

from typing import Annotated

import typer
from rich.console import Console

from gtm_cli.core.auth import get_auth_manager
from gtm_cli.utils.errors import AuthenticationError, ConfigurationError
from gtm_cli.utils.output import print_error, print_info, print_success

console = Console()


def login(
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to login to",
        ),
    ] = None,
    no_browser: Annotated[
        bool,
        typer.Option(
            "--no-browser",
            help="Use copy/paste flow instead of opening browser",
        ),
    ] = False,
    port: Annotated[
        int,
        typer.Option(
            "--port",
            help="Port for local callback server",
        ),
    ] = 8080,
    status: Annotated[
        bool,
        typer.Option(
            "--status",
            help="Check login status instead of logging in",
        ),
    ] = False,
    no_gcloud: Annotated[
        bool,
        typer.Option(
            "--no-gcloud",
            help="Use OAuth2 client secrets instead of gcloud (requires ~/.config/gtm-cli/client_secrets.json)",
        ),
    ] = False,
) -> None:
    """Authenticate with Google.

    Opens a browser window for OAuth2 authentication. Your credentials are
    stored securely for future use.

    Use --no-browser for headless environments (copies URL for manual auth).
    """
    auth_manager = get_auth_manager()

    if status:
        # Just show login status
        login_status = auth_manager.get_login_status(profile)
        if login_status["logged_in"]:
            email = login_status.get("email", "unknown")
            print_success(f"Logged in as {email} (profile: {login_status['profile']})")
        else:
            print_info(f"Not logged in (profile: {login_status['profile']})")
        return

    try:
        if no_browser:
            print_info("Opening authentication URL...")
            print_info("Please visit the URL below and paste the authorization code.")

        email = auth_manager.login(
            profile_name=profile,
            no_browser=no_browser,
            port=port,
            use_gcloud=False if no_gcloud else None,
        )
        print_success(f"Successfully logged in as {email}")

    except ConfigurationError as e:
        print_error(str(e))
        print_info(
            "To set up OAuth2 authentication:\n"
            "1. Go to https://console.cloud.google.com/apis/credentials\n"
            "2. Create an OAuth 2.0 Client ID (Desktop App)\n"
            "3. Download the JSON and save to ~/.gtm-cli/client_secrets.json"
        )
        raise typer.Exit(1) from None
    except AuthenticationError as e:
        print_error(str(e))
        raise typer.Exit(1) from None


def logout(
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            "-p",
            help="Profile to logout from",
        ),
    ] = None,
) -> None:
    """Remove stored credentials.

    Removes the OAuth2 token for the specified profile.
    """
    auth_manager = get_auth_manager()
    auth_manager.logout(profile)
    profile_name = profile or "default"
    print_success(f"Logged out from profile '{profile_name}'")
