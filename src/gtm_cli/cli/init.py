"""Quick initialization for teammates with shared credentials."""

from __future__ import annotations

import json
import shutil
import urllib.request
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from gtm_cli.core.auth import get_auth_manager
from gtm_cli.core.config import get_config_manager
from gtm_cli.utils.output import print_error, print_info, print_success

console = Console()


def init(
    secrets: Annotated[
        str,
        typer.Argument(help="URL or path to client_secrets.json"),
    ],
    login: Annotated[
        bool,
        typer.Option("--login", "-l", help="Login immediately after init"),
    ] = True,
) -> None:
    """Quick setup for teammates with shared OAuth credentials.

    For teams using a shared OAuth client, this is all you need:

        gtm init https://internal.company.com/client_secrets.json

    This downloads the credentials and logs you in. That's it!
    """
    config_manager = get_config_manager()
    config_manager.ensure_directories()
    secrets_path = config_manager.config_dir / "client_secrets.json"

    # Check if already configured
    if secrets_path.exists():
        overwrite = typer.confirm(f"Credentials already exist at {secrets_path}. Overwrite?")
        if not overwrite:
            print_info("Keeping existing credentials.")
            if login:
                _do_login()
            return

    # Download or copy the secrets file
    source = secrets.strip()

    if source.startswith(("http://", "https://")):
        # Download from URL
        console.print(f"Downloading credentials from [bold]{source}[/bold]...")
        try:
            urllib.request.urlretrieve(source, secrets_path)
            print_success(f"Downloaded to {secrets_path}")
        except Exception as e:
            print_error(f"Failed to download: {e}")
            raise typer.Exit(1) from e
    else:
        # Copy from local path
        source_path = Path(source).expanduser()
        if not source_path.exists():
            print_error(f"File not found: {source_path}")
            raise typer.Exit(1)

        console.print(f"Copying credentials from [bold]{source_path}[/bold]...")
        try:
            shutil.copy(source_path, secrets_path)
            print_success(f"Copied to {secrets_path}")
        except Exception as e:
            print_error(f"Failed to copy: {e}")
            raise typer.Exit(1) from e

    # Verify it's valid JSON with required fields
    try:
        with open(secrets_path) as f:
            data = json.load(f)

        # Check for required OAuth fields
        if "installed" not in data and "web" not in data:
            print_error("Invalid client_secrets.json - missing 'installed' or 'web' key")
            secrets_path.unlink()
            raise typer.Exit(1)

        print_success("Credentials validated")
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        secrets_path.unlink()
        raise typer.Exit(1) from e

    # Login if requested
    if login:
        _do_login()
    else:
        print_info("Run 'gtm login' to authenticate.")


def _do_login() -> None:
    """Perform login flow."""
    console.print()
    console.print("Logging in...")

    auth_manager = get_auth_manager()
    try:
        email = auth_manager.login(use_gcloud=False)
        print_success(f"Logged in as {email}")
        console.print()
        console.print("You're all set! Try: [bold]gtm account list[/bold]")
    except Exception as e:
        print_error(f"Login failed: {e}")
        print_info("You can try again with: gtm login")
        raise typer.Exit(1) from e
