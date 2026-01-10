"""Tag CLI commands."""

from datetime import datetime
from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import (
    resolve_account_id,
    resolve_container_id,
    resolve_workspace_id,
)
from gtm_cli.cli.main import get_state
from gtm_cli.core.client import get_client
from gtm_cli.utils.output import output, print_error, print_success, print_warning


def _relative_time(fingerprint: str) -> str:
    """Convert fingerprint timestamp to relative time like '3 days ago'."""
    if not fingerprint:
        return ""
    try:
        ts = int(fingerprint) / 1000
        dt = datetime.fromtimestamp(ts)
        now = datetime.now()
        diff = now - dt

        seconds = diff.total_seconds()
        if seconds < 60:
            return "just now"
        minutes = seconds / 60
        if minutes < 60:
            n = int(minutes)
            return f"{n} minute{'s' if n != 1 else ''} ago"
        hours = minutes / 60
        if hours < 24:
            n = int(hours)
            return f"{n} hour{'s' if n != 1 else ''} ago"
        days = hours / 24
        if days < 30:
            n = int(days)
            return f"{n} day{'s' if n != 1 else ''} ago"
        months = days / 30
        if months < 12:
            n = int(months)
            return f"{n} month{'s' if n != 1 else ''} ago"
        years = days / 365
        n = int(years)
        return f"{n} year{'s' if n != 1 else ''} ago"
    except (ValueError, OSError):
        return ""


app = typer.Typer(
    help="""Manage GTM tags.

Tags are the core building blocks in GTM - they define what code runs on your site.

Auto-detects account/container/workspace if you have only one of each.

Example: gtm tag list
"""
)


@app.command("list")
def list_tags(
    sort: Annotated[
        str,
        typer.Option(
            "--sort",
            "-s",
            help="Sort by: name, type, triggers, folder, modified (default: modified)",
        ),
    ] = "modified",
    reverse: Annotated[
        bool,
        typer.Option(
            "--reverse",
            "-r",
            help="Reverse sort order",
        ),
    ] = False,
) -> None:
    """List all tags in the workspace."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

    tags = client.list_tags(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    # Build folder lookup for names
    folders = client.list_folders(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )
    folder_names = {f.get("folderId"): f.get("name") for f in folders}

    # Build trigger lookup for names
    triggers = client.list_triggers(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )
    trigger_names = {t.get("triggerId"): t.get("name") for t in triggers}

    def get_firing_triggers(tag: dict[str, Any]) -> str:
        """Get comma-separated list of firing trigger names."""
        trigger_ids = tag.get("firingTriggerId", [])
        names = [str(trigger_names.get(tid, tid)) for tid in trigger_ids]
        return ", ".join(names) if names else ""

    data = [
        {
            "name": t.get("name", ""),
            "type": t.get("type", ""),
            "triggers": get_firing_triggers(t),
            "folder": folder_names.get(t.get("parentFolderId"), "-"),
            "modified": _relative_time(t.get("fingerprint", "")),
            "paused": "paused" if t.get("paused") else "",
            "_fingerprint": t.get("fingerprint", "0"),  # for sorting
        }
        for t in tags
    ]

    # Sort data
    sort_key = sort.lower()
    if sort_key == "modified":
        # Sort by fingerprint (newer first by default)
        data.sort(key=lambda x: x.get("_fingerprint", "0"), reverse=not reverse)
    elif sort_key in ("name", "type", "folder", "triggers"):
        data.sort(key=lambda x: x.get(sort_key, "").lower(), reverse=reverse)

    # Remove internal sort field before output
    for item in data:
        item.pop("_fingerprint", None)

    output(data, fmt=state.output_format, title="Tags")


@app.command("get")
def get_tag(
    tag_id: Annotated[str, typer.Argument(help="Tag ID")],
) -> None:
    """Get details of a specific tag."""
    state = get_state()
    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

    # Note: Full implementation would call client.get_tag()
    # For now, list and filter
    tags = client.list_tags(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    tag = next((t for t in tags if t.get("tagId") == tag_id), None)
    if not tag:
        print_error(f"Tag '{tag_id}' not found")
        raise typer.Exit(1)

    output(tag, fmt=state.output_format)


@app.command("audit-consent")
def audit_consent(
    show_all: Annotated[
        bool,
        typer.Option(
            "--all",
            "-a",
            help="Show all tags with non-standard consent (including 'notSet')",
        ),
    ] = False,
) -> None:
    """Audit tags for consent configuration issues.

    Finds tags with "Additional Consent Required" set, which may cause issues
    if the tag already has built-in consent handling.

    By default, shows only tags with explicit consent requirements ('needed').
    Use --all to include tags with 'notSet' consent status.

    Tip: Use --authuser N global option to append authuser parameter to URLs.
    """
    state = get_state()

    def add_authuser(url: str) -> str:
        """Add authuser parameter to GTM URL if specified.

        Inserts before the hash fragment: example.com/?authuser=1#/path
        """
        if not url or state.authuser is None:
            return url
        # Insert authuser before the hash fragment
        if "#" in url:
            base, fragment = url.split("#", 1)
            separator = "&" if "?" in base else "?"
            return f"{base}{separator}authuser={state.authuser}#{fragment}"
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}authuser={state.authuser}"

    client = get_client()
    account_id = resolve_account_id(state, client)
    container_id = resolve_container_id(state, client, account_id)
    workspace_id = resolve_workspace_id(state, client, account_id, container_id)

    tags = client.list_tags(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )

    # Categorize tags by consent status
    needed_tags: list[dict[str, Any]] = []
    not_set_tags: list[dict[str, Any]] = []
    not_needed_tags: list[dict[str, Any]] = []

    for tag in tags:
        consent = tag.get("consentSettings", {})
        status = consent.get("consentStatus", "notNeeded")

        if status == "needed":
            consent_types = consent.get("consentType", {}).get("list", [])
            types_list = [c.get("value", "") for c in consent_types]
            needed_tags.append({
                "name": tag.get("name", ""),
                "type": tag.get("type", ""),
                "consent_required": ", ".join(types_list),
                "url": add_authuser(tag.get("tagManagerUrl", "")),
            })
        elif status == "notSet":
            not_set_tags.append({
                "name": tag.get("name", ""),
                "type": tag.get("type", ""),
                "url": add_authuser(tag.get("tagManagerUrl", "")),
            })
        else:
            not_needed_tags.append(tag)

    # Output results
    if needed_tags:
        print_warning(f"Found {len(needed_tags)} tag(s) with EXPLICIT additional consent required:")
        output(
            needed_tags,
            fmt=state.output_format,
            columns=["name", "type", "consent_required", "url"],
            title="Tags with Additional Consent Required",
        )
    else:
        print_success("No tags with explicit additional consent requirements found.")

    if show_all and not_set_tags:
        print_warning(f"\nFound {len(not_set_tags)} tag(s) with consent 'notSet':")
        output(
            not_set_tags,
            fmt=state.output_format,
            columns=["name", "type", "url"],
            title="Tags with Consent Not Set",
        )

    # Summary
    print("\n--- Summary ---")
    print(f"Total tags: {len(tags)}")
    print(f"  Consent required (needs review): {len(needed_tags)}")
    print(f"  Consent not set: {len(not_set_tags)}")
    print(f"  No additional consent: {len(not_needed_tags)}")
