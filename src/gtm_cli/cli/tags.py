"""Tag CLI commands."""

import re
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
from gtm_cli.utils.output import output, print_error, print_info, print_success, print_warning


def _add_authuser(url: str, authuser: int | None) -> str:
    """Add authuser parameter to GTM URL if specified.

    Inserts before the hash fragment: example.com/?authuser=1#/path
    """
    if not url or authuser is None:
        return url
    if "#" in url:
        base, fragment = url.split("#", 1)
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}authuser={authuser}#{fragment}"
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}authuser={authuser}"


def _get_firing_trigger_names(tag: dict[str, Any], trigger_names: dict[str, str]) -> str:
    """Get comma-separated list of firing trigger names for a tag."""
    trigger_ids = tag.get("firingTriggerId", [])
    names = [str(trigger_names.get(tid, tid)) for tid in trigger_ids]
    return ", ".join(names) if names else ""


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


# --- Pixel audit helpers ---

# Known pixel patterns: (display name, regex for pixel ID extraction)
_PIXEL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("TikTok", re.compile(r"""ttq\.load\(\s*['"]([A-Z0-9]+)['"]\s*\)""")),
    ("Meta/Facebook", re.compile(r"""fbq\(\s*['"]init['"]\s*,\s*['"](\d+)['"]\s*\)""")),
    ("Google Ads", re.compile(r"""gtag\(\s*['"]config['"]\s*,\s*['"]([A-Z0-9-]+)['"]\s*\)""")),
    ("Snapchat", re.compile(r"""snaptr\(\s*['"]init['"]\s*,\s*['"]([a-f0-9-]+)['"]\s*\)""")),
    ("Pinterest", re.compile(r"""pintrk\(\s*['"]load['"]\s*,\s*['"](\d+)['"]\s*\)""")),
    ("Twitter/X", re.compile(r"""twq\(\s*['"]init['"]\s*,\s*['"]([a-z0-9]+)['"]\s*\)""")),
    ("LinkedIn", re.compile(r"""_linkedin_partner_id\s*=\s*['"](\d+)['"]""")),
]


_SCRIPT_TAG_RE = re.compile(r"<script\b([^>]*)>", re.IGNORECASE)
_SCRIPT_SRC_RE = re.compile(r"""src\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)
_CREATE_SCRIPT_RE = re.compile(r"""createElement\(\s*['"]script['"]\s*\)""", re.IGNORECASE)


def _get_tag_html(tag: dict[str, Any]) -> str:
    """Extract HTML content from a tag's parameters."""
    for param in tag.get("parameter", []):
        if param.get("key") == "html":
            return str(param.get("value", ""))
    return ""


def _check_async_loading(html: str) -> list[dict[str, str]]:
    """Check script loading in HTML for async patterns.

    Detects two patterns:
    1. Static <script src="..."> tags - checks for async/defer attributes
    2. Dynamic script creation (createElement("script")) - checks .async property

    Returns list of findings with script src/description and async status.
    """
    findings: list[dict[str, str]] = []

    # Pattern 1: Static <script src="..."> tags
    for match in _SCRIPT_TAG_RE.finditer(html):
        attrs = match.group(1)
        has_async = bool(re.search(r"\basync\b", attrs, re.IGNORECASE))
        has_defer = bool(re.search(r"\bdefer\b", attrs, re.IGNORECASE))

        src_match = _SCRIPT_SRC_RE.search(attrs)
        src = src_match.group(1) if src_match else "(inline)"

        if src == "(inline)":
            continue

        findings.append(
            {
                "src": src,
                "async": "yes" if has_async else "NO",
                "defer": "yes" if has_defer else "no",
                "method": "static",
            }
        )

    # Pattern 2: Dynamic script creation via createElement
    # Matches patterns like: el.async=!0 or el.async=true or el.async = true
    # NOTE: This is a heuristic — .async detection searches the entire HTML string,
    # not scoped to the createElement block. Multiple dynamic scripts in one tag
    # could cause false results.
    if _CREATE_SCRIPT_RE.search(html):
        # Check if .async is set to true (common patterns: .async=!0, .async=true, .async = true)
        async_set = bool(re.search(r"\.\s*async\s*=\s*(!0|true|1)", html))
        # Try to find the src being set
        dynamic_src_match = re.search(r"""\.\s*src\s*=\s*['"]([^'"]+)['"]""", html)
        # Also match concatenated src: .src = url + "..." or .src = r + "?"
        src_desc = dynamic_src_match.group(1) if dynamic_src_match else "(dynamic)"

        findings.append(
            {
                "src": src_desc,
                "async": "yes" if async_set else "NO",
                "defer": "n/a",
                "method": "dynamic",
            }
        )

    return findings


def _detect_pixels(html: str) -> list[dict[str, str]]:
    """Detect known pixel installations in HTML content."""
    found: list[dict[str, str]] = []
    for name, id_pattern in _PIXEL_PATTERNS:
        id_match = id_pattern.search(html)
        if id_match:
            found.append({"provider": name, "pixel_id": id_match.group(1)})
    return found


def _is_all_pages_trigger(trigger_name: str) -> bool:
    """Check if a trigger name looks like an all-pages trigger (heuristic, substring match)."""
    normalized = trigger_name.lower().strip()
    return (
        "all pages" in normalized
        or "all_pages" in normalized
        or normalized in ("pageview", "page view")
    )


# --- CLI commands ---

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
    trigger_names = {t.get("triggerId", ""): t.get("name", "") for t in triggers}

    data = [
        {
            "name": t.get("name", ""),
            "type": t.get("type", ""),
            "triggers": _get_firing_trigger_names(t, trigger_names),
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


@app.command("search")
def search_tags(
    query: Annotated[
        str,
        typer.Argument(help="Search query (matches tag name, case-insensitive)"),
    ],
    tag_type: Annotated[
        str | None,
        typer.Option(
            "--type",
            "-t",
            help="Filter by tag type (e.g. html, googtag, awct)",
        ),
    ] = None,
    exclude_paused: Annotated[
        bool,
        typer.Option(
            "--exclude-paused",
            help="Exclude paused tags from results",
        ),
    ] = False,
) -> None:
    """Search tags by name or type.

    Case-insensitive substring match on tag names.
    Optionally filter by tag type with --type.

    Examples:
        gtm tag search tiktok
        gtm tag search pixel --type html
        gtm tag search facebook --type html
    """
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

    query_lower = query.lower()
    type_lower = tag_type.lower() if tag_type else None

    matched = [
        t
        for t in tags
        if query_lower in t.get("name", "").lower()
        and (type_lower is None or type_lower == t.get("type", "").lower())
        and (not exclude_paused or not t.get("paused"))
    ]

    if not matched:
        print_warning(f"No tags matching '{query}'" + (f" (type={tag_type})" if tag_type else ""))
        raise typer.Exit(0)

    # Build lookups
    folders = client.list_folders(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )
    folder_names = {f.get("folderId"): f.get("name") for f in folders}

    triggers = client.list_triggers(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )
    trigger_names = {t.get("triggerId", ""): t.get("name", "") for t in triggers}

    data = [
        {
            "name": t.get("name", ""),
            "type": t.get("type", ""),
            "id": t.get("tagId", ""),
            "triggers": _get_firing_trigger_names(t, trigger_names),
            "folder": folder_names.get(t.get("parentFolderId"), "-"),
            "paused": "paused" if t.get("paused") else "",
        }
        for t in matched
    ]

    print_success(f"Found {len(matched)} tag(s) matching '{query}':")
    output(data, fmt=state.output_format, title=f"Search: {query}")


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
            needed_tags.append(
                {
                    "name": tag.get("name", ""),
                    "type": tag.get("type", ""),
                    "consent_required": ", ".join(types_list),
                    "url": _add_authuser(tag.get("tagManagerUrl", ""), state.authuser),
                }
            )
        elif status == "notSet":
            not_set_tags.append(
                {
                    "name": tag.get("name", ""),
                    "type": tag.get("type", ""),
                    "url": _add_authuser(tag.get("tagManagerUrl", ""), state.authuser),
                }
            )
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


@app.command("audit-pixels")
def audit_pixels(
    show_html: Annotated[
        bool,
        typer.Option(
            "--show-html",
            help="Show the raw HTML content of each tag",
        ),
    ] = False,
) -> None:
    """Audit pixel and script tags for loading issues.

    Inspects Custom HTML tags for common performance problems:

    \b
    - Scripts loaded without async/defer attributes
    - Duplicate pixel installations (same pixel ID in multiple tags)
    - Pixel tags firing on all pages (may be unnecessary for event tags)
    - Detection of known pixels: TikTok, Meta, Google Ads, Snapchat, Pinterest, Twitter/X, LinkedIn

    Based on vendor best practices:
    - Load base pixel once only (via GTM or hardcoded, not both)
    - Load external scripts with async attribute
    - Fire event tags only on relevant pages

    Tip: Use --authuser N global option to append authuser parameter to URLs.
    """
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

    triggers = client.list_triggers(
        account_id=account_id,
        container_id=container_id,
        workspace_id=workspace_id,
        profile_name=state.profile,
        service_account_path=state.service_account,
    )
    trigger_names = {t.get("triggerId", ""): t.get("name", "") for t in triggers}

    # Collect findings
    sync_scripts: list[dict[str, str]] = []
    pixel_map: dict[str, list[str]] = {}  # pixel_id -> [tag names]
    all_page_pixels: list[dict[str, str]] = []
    tag_details: list[dict[str, Any]] = []

    html_tags = [t for t in tags if t.get("type") == "html"]

    if not html_tags:
        print_info("No Custom HTML tags found in this workspace.")
        raise typer.Exit(0)

    for tag in html_tags:
        name = tag.get("name", "")
        html = _get_tag_html(tag)
        tag_url = _add_authuser(tag.get("tagManagerUrl", ""), state.authuser)

        if not html:
            continue

        # Resolve trigger names for this tag
        firing_ids = tag.get("firingTriggerId", [])
        firing_names = [str(trigger_names.get(tid, tid)) for tid in firing_ids]
        fires_on_all = any(_is_all_pages_trigger(n) for n in firing_names)

        # Check async loading
        script_findings = _check_async_loading(html)
        for sf in script_findings:
            if sf["async"] == "NO":
                sync_scripts.append(
                    {
                        "tag": name,
                        "script_src": sf["src"],
                        "method": sf.get("method", "static"),
                        "async": sf["async"],
                        "defer": sf["defer"],
                        "url": tag_url,
                    }
                )

        # Detect known pixels
        pixels = _detect_pixels(html)
        for p in pixels:
            key = f"{p['provider']}:{p['pixel_id']}"
            pixel_map.setdefault(key, []).append(name)

            if fires_on_all:
                all_page_pixels.append(
                    {
                        "tag": name,
                        "provider": p["provider"],
                        "pixel_id": p["pixel_id"],
                        "triggers": ", ".join(firing_names),
                        "url": tag_url,
                    }
                )

        # Build detail row
        async_summary = []
        for sf in script_findings:
            status = "async" if sf["async"] == "yes" else "SYNC"
            async_summary.append(f"{sf.get('method', 'static')}:{status}")

        detail: dict[str, Any] = {
            "name": name,
            "id": tag.get("tagId", ""),
            "triggers": ", ".join(firing_names),
            "pixels": ", ".join(f"{p['provider']} ({p['pixel_id']})" for p in pixels) or "-",
            "loading": ", ".join(async_summary) if async_summary else "no external scripts",
            "paused": "paused" if tag.get("paused") else "",
        }
        if show_html:
            detail["html"] = html
        tag_details.append(detail)

    # --- Output findings ---
    has_issues = False

    # 1. Sync script loading
    if sync_scripts:
        has_issues = True
        print_warning(f"\n{len(sync_scripts)} script(s) loaded WITHOUT async attribute:")
        output(
            sync_scripts,
            fmt=state.output_format,
            columns=["tag", "script_src", "method", "async", "defer", "url"],
            title="Scripts Missing async",
        )
        print_info("Fix: Add 'async' attribute to <script> tags loading external resources.")

    # 2. Duplicate pixels
    duplicates = {k: v for k, v in pixel_map.items() if len(v) > 1}
    if duplicates:
        has_issues = True
        dup_data = [
            {
                "pixel": key,
                "count": len(tag_list),
                "tags": ", ".join(tag_list),
            }
            for key, tag_list in duplicates.items()
        ]
        print_warning(f"\n{len(duplicates)} pixel(s) loaded in MULTIPLE tags:")
        output(
            dup_data,
            fmt=state.output_format,
            columns=["pixel", "count", "tags"],
            title="Duplicate Pixel Installations",
        )
        print_info(
            "Fix: Load each pixel base code once only. Remove duplicates or use GTM's built-in templates."
        )

    # 3. All-page pixel firing
    if all_page_pixels:
        has_issues = True
        print_warning(f"\n{len(all_page_pixels)} pixel tag(s) firing on ALL PAGES:")
        output(
            all_page_pixels,
            fmt=state.output_format,
            columns=["tag", "provider", "pixel_id", "triggers", "url"],
            title="Pixels Firing on All Pages",
        )
        print_info(
            "Review: Base pixel on all pages is normal. Event tags (ViewContent, Purchase) should fire only on relevant pages."
        )

    if not has_issues:
        print_success("No pixel loading issues found.")

    # 4. Full detail table
    if tag_details:
        print(f"\n--- Custom HTML Tags ({len(tag_details)}) ---")
        columns = ["name", "id", "triggers", "pixels", "loading", "paused"]
        if show_html:
            columns.append("html")
        output(
            tag_details,
            fmt=state.output_format,
            columns=columns,
            title="Custom HTML Tag Details",
        )

    # Summary
    print("\n--- Summary ---")
    print(f"Custom HTML tags scanned: {len(html_tags)}")
    print(f"Scripts without async: {len(sync_scripts)}")
    print(f"Duplicate pixel installations: {len(duplicates)}")
    print(f"Pixels firing on all pages: {len(all_page_pixels)}")
    if pixel_map:
        print("Detected pixels:")
        for key, tag_list in pixel_map.items():
            print(f"  {key} -> {', '.join(tag_list)}")
