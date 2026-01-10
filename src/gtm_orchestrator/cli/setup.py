"""Setup wizard for GTM Orchestrator."""

from __future__ import annotations

import random
import shutil
import string
import subprocess
import webbrowser
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from gtm_orchestrator.core.auth import get_auth_manager
from gtm_orchestrator.core.config import get_config_manager
from gtm_orchestrator.utils.output import print_error, print_info, print_success

console = Console()


def _is_gcloud_installed() -> bool:
    """Check if gcloud CLI is installed."""
    return shutil.which("gcloud") is not None


def _run_gcloud(args: list[str], capture: bool = True) -> tuple[bool, str]:
    """Run a gcloud command and return success status and output."""
    try:
        result = subprocess.run(
            ["gcloud", *args],
            capture_output=capture,
            text=True,
            check=False,
        )
        return result.returncode == 0, result.stdout.strip() if capture else ""
    except Exception as e:
        return False, str(e)


def _get_current_project() -> str | None:
    """Get the current gcloud project."""
    success, output = _run_gcloud(["config", "get-value", "project"])
    return output if success and output else None


def _list_projects() -> list[str]:
    """List available GCP projects."""
    success, output = _run_gcloud(["projects", "list", "--format=value(projectId)"])
    if success and output:
        return output.strip().split("\n")
    return []


def _enable_api(project: str) -> bool:
    """Enable Tag Manager API for a project."""
    success, _ = _run_gcloud([
        "services", "enable", "tagmanager.googleapis.com",
        f"--project={project}"
    ], capture=False)
    return success


def _check_api_enabled(project: str) -> bool:
    """Check if Tag Manager API is enabled."""
    success, output = _run_gcloud([
        "services", "list",
        f"--project={project}",
        "--format=value(config.name)",
        "--filter=config.name:tagmanager.googleapis.com"
    ])
    return success and "tagmanager.googleapis.com" in output


def setup() -> None:
    """Interactive setup wizard for GTM Orchestrator.

    Guides you through:
    1. GCP project selection/creation
    2. Enabling Tag Manager API
    3. OAuth consent screen setup
    4. Creating OAuth credentials
    5. Logging in
    """
    console.print(Panel.fit(
        "[bold blue]GTM Orchestrator Setup Wizard[/bold blue]\n\n"
        "This wizard will help you set up authentication for GTM Orchestrator.\n"
        "You'll need a Google Cloud Platform account.",
        title="Welcome",
    ))
    console.print()

    # Step 1: Check gcloud
    console.print("[bold]Step 1:[/bold] Checking prerequisites...")

    if not _is_gcloud_installed():
        print_error("gcloud CLI is not installed.")
        console.print("\nInstall it from: [link]https://cloud.google.com/sdk/docs/install[/link]")
        console.print("Then run [bold]gtm setup[/bold] again.")
        raise typer.Exit(1)

    print_success("gcloud CLI is installed")

    # Check if logged into gcloud
    success, account = _run_gcloud(["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
    if not success or not account:
        print_info("You need to login to gcloud first.")
        console.print("\nRunning: [bold]gcloud auth login[/bold]")
        subprocess.run(["gcloud", "auth", "login"], check=False)
        success, account = _run_gcloud(["auth", "list", "--filter=status:ACTIVE", "--format=value(account)"])
        if not account:
            print_error("gcloud login failed. Please run 'gcloud auth login' manually.")
            raise typer.Exit(1)

    print_success(f"Logged into gcloud as {account.split(chr(10))[0]}")
    console.print()

    # Step 2: Select/create project
    console.print("[bold]Step 2:[/bold] GCP Project setup...")
    console.print("""
[dim]We recommend creating a dedicated project for GTM Orchestrator.
This keeps your OAuth credentials isolated and makes it easy to
manage or remove later.[/dim]
""")

    current_project = _get_current_project()
    projects = _list_projects()

    # Default: create new project (recommended)
    create_new = Confirm.ask(
        "Create a new dedicated project? [bold](recommended)[/bold]",
        default=True
    )

    project: str | None = None

    if not create_new:
        # User wants to use existing project
        if current_project:
            use_current = Confirm.ask(
                f"Use current project [bold]{current_project}[/bold]?",
                default=True
            )
            if use_current:
                project = current_project

        if not project and projects:
            console.print("\nAvailable projects:")
            for i, p in enumerate(projects[:10], 1):
                console.print(f"  {i}. {p}")
            if len(projects) > 10:
                console.print(f"  ... and {len(projects) - 10} more")

            choice = Prompt.ask(
                "\nEnter project ID or number",
                default=projects[0] if projects else ""
            )

            if choice.isdigit() and 1 <= int(choice) <= len(projects):
                project = projects[int(choice) - 1]
            elif choice:
                project = choice

    if not project:
        # Create new project with readable name and unique ID
        suffix = "".join(random.choices(string.digits, k=6))
        default_id = f"gtm-orchestrator-{suffix}"
        project_name = "GTM Orchestrator"

        console.print(f"[dim]Creating project '{project_name}' with unique ID...[/dim]")
        project_id = Prompt.ask(
            "Project ID (must be globally unique)",
            default=default_id
        )
        console.print(f"\nCreating project [bold]{project_name}[/bold] ({project_id})...")
        success, _ = _run_gcloud([
            "projects", "create", project_id,
            f"--name={project_name}"
        ], capture=False)
        if not success:
            print_error("Failed to create project. The ID may already be taken.")
            console.print("\nYou can either:")
            console.print("  1. Try again with a different ID")
            console.print("  2. Create manually: [link]https://console.cloud.google.com/projectcreate[/link]")
            project_id = Prompt.ask("\nEnter project ID (or paste one you created)")
        project = project_id

    # At this point, project must be set
    assert project is not None, "Project ID must be set"

    # Set as current project
    _run_gcloud(["config", "set", "project", project])
    print_success(f"Using project: {project}")
    console.print()

    # Step 3: Enable Tag Manager API
    console.print("[bold]Step 3:[/bold] Enabling Tag Manager API...")

    if _check_api_enabled(project):
        print_success("Tag Manager API is already enabled")
    else:
        console.print("Enabling Tag Manager API...")
        if _enable_api(project):
            print_success("Tag Manager API enabled")
        else:
            print_error("Failed to enable API automatically.")
            console.print(f"\nEnable it manually: [link]https://console.cloud.google.com/apis/library/tagmanager.googleapis.com?project={project}[/link]")
            Prompt.ask("Press Enter after enabling the API")

    console.print()

    # Step 4: OAuth Consent Screen
    console.print("[bold]Step 4:[/bold] OAuth Consent Screen setup...")
    console.print("""
This step requires manual configuration in the Google Cloud Console.

[bold]Instructions:[/bold]
1. Click the link below to open the OAuth consent screen
2. Select [bold]External[/bold] user type (or Internal if using Workspace)
3. Fill in the required fields:
   - App name: [bold]GTM Orchestrator[/bold] (or any name)
   - User support email: [bold]Your email[/bold]
   - Developer contact: [bold]Your email[/bold]
4. Click [bold]Save and Continue[/bold] through the scopes page
5. Add yourself as a [bold]Test User[/bold] (your email)
6. Click [bold]Save and Continue[/bold]
""")

    consent_url = f"https://console.cloud.google.com/apis/credentials/consent?project={project}"
    console.print(f"[link]{consent_url}[/link]\n")

    if Confirm.ask("Open in browser?", default=True):
        webbrowser.open(consent_url)

    Prompt.ask("Press Enter after completing OAuth consent screen setup")
    print_success("OAuth consent screen configured")
    console.print()

    # Step 5: Create OAuth Credentials
    console.print("[bold]Step 5:[/bold] Create OAuth credentials...")
    console.print("""
[bold]Instructions:[/bold]
1. Click the link below to open the Credentials page
2. Click [bold]+ CREATE CREDENTIALS[/bold] → [bold]OAuth client ID[/bold]
3. Application type: [bold]Desktop app[/bold]
4. Name: [bold]GTM Orchestrator[/bold] (or any name)
5. Click [bold]Create[/bold]
6. Click [bold]DOWNLOAD JSON[/bold]
""")

    creds_url = f"https://console.cloud.google.com/apis/credentials?project={project}"
    console.print(f"[link]{creds_url}[/link]\n")

    if Confirm.ask("Open in browser?", default=True):
        webbrowser.open(creds_url)

    config_manager = get_config_manager()
    secrets_path = config_manager.config_dir / "client_secrets.json"
    config_manager.ensure_directories()

    console.print("\n[bold]Save the downloaded JSON file to:[/bold]")
    console.print(f"  {secrets_path}\n")

    # Check common download locations
    download_paths = [
        Path.home() / "Downloads",
        Path.home() / "Desktop",
    ]

    while True:
        if secrets_path.exists():
            print_success(f"Found credentials at {secrets_path}")
            break

        # Check for downloaded file
        for dl_path in download_paths:
            if dl_path.exists():
                for f in dl_path.glob("client_secret*.json"):
                    console.print(f"\nFound: [bold]{f}[/bold]")
                    if Confirm.ask("Move this file to the correct location?", default=True):
                        shutil.move(str(f), str(secrets_path))
                        print_success(f"Moved to {secrets_path}")
                        break
                else:
                    continue
                break

        if secrets_path.exists():
            break

        if not Confirm.ask("\nCredentials file not found. Continue checking?", default=True):
            print_error(f"Please save the credentials to: {secrets_path}")
            print_info("Then run 'gtm login' to complete setup.")
            raise typer.Exit(1)

    console.print()

    # Step 6: Login
    console.print("[bold]Step 6:[/bold] Logging in...")

    if Confirm.ask("Login now?", default=True):
        auth_manager = get_auth_manager()
        try:
            email = auth_manager.login(use_gcloud=False)
            print_success(f"Successfully logged in as {email}")
        except Exception as e:
            print_error(f"Login failed: {e}")
            print_info("You can try again with: gtm login")
            raise typer.Exit(1) from e

    console.print()
    console.print(Panel.fit(
        "[bold green]Setup Complete![/bold green]\n\n"
        "You can now use GTM Orchestrator:\n\n"
        "  [bold]gtm account list[/bold]      - List your GTM accounts\n"
        "  [bold]gtm container list[/bold]    - List containers\n"
        "  [bold]gtm tag list[/bold]          - List tags\n"
        "  [bold]gtm --help[/bold]            - See all commands",
        title="🎉 Success",
    ))
