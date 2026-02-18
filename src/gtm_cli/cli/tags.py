"""Tag CLI commands."""

import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import WorkspaceContext, resolve_workspace_context
from gtm_cli.utils.errors import ResourceNotFoundError
from gtm_cli.utils.output import (
    confirm,
    output,
    print_error,
    print_info,
    print_success,
    print_warning,
)


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


def _resolve_html_content(
    html: str | None,
    html_file: Path | None,
) -> str | None:
    """Resolve HTML content from inline string or file path.

    Raises typer.Exit(1) if both are specified.
    Returns None if neither is specified.
    """
    if html is not None and html_file is not None:
        print_error("Cannot specify both --html and --html-file")
        raise typer.Exit(1)
    if html_file:
        return html_file.read_text()
    return html


def _build_tag_lookups(
    ctx: WorkspaceContext,
) -> tuple[dict[str, str], dict[str, str]]:
    """Build folder and trigger name lookup dicts for display."""
    folders = ctx.client.list_folders(**ctx.api_kwargs)
    folder_names: dict[str, str] = {
        f.get("folderId", ""): f.get("name", "") for f in folders
    }

    triggers = ctx.client.list_triggers(**ctx.api_kwargs)
    trigger_names: dict[str, str] = {
        t.get("triggerId", ""): t.get("name", "") for t in triggers
    }
    return folder_names, trigger_names


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
    ctx = resolve_workspace_context()

    tags = ctx.client.list_tags(**ctx.api_kwargs)
    folder_names, trigger_names = _build_tag_lookups(ctx)

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

    output(data, fmt=ctx.state.output_format, title="Tags")


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
    ctx = resolve_workspace_context()

    tags = ctx.client.list_tags(**ctx.api_kwargs)

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

    folder_names, trigger_names = _build_tag_lookups(ctx)

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
    output(data, fmt=ctx.state.output_format, title=f"Search: {query}")


@app.command("get")
def get_tag(
    tag_id: Annotated[str, typer.Argument(help="Tag ID")],
) -> None:
    """Get details of a specific tag."""
    ctx = resolve_workspace_context()

    try:
        tag = ctx.client.get_tag(tag_id=tag_id, **ctx.api_kwargs)
    except ResourceNotFoundError:
        print_error(f"Tag '{tag_id}' not found")
        raise typer.Exit(1) from None

    output(tag, fmt=ctx.state.output_format)


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
    ctx = resolve_workspace_context()

    tags = ctx.client.list_tags(**ctx.api_kwargs)

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
                    "url": _add_authuser(tag.get("tagManagerUrl", ""), ctx.state.authuser),
                }
            )
        elif status == "notSet":
            not_set_tags.append(
                {
                    "name": tag.get("name", ""),
                    "type": tag.get("type", ""),
                    "url": _add_authuser(tag.get("tagManagerUrl", ""), ctx.state.authuser),
                }
            )
        else:
            not_needed_tags.append(tag)

    # Output results
    if needed_tags:
        print_warning(f"Found {len(needed_tags)} tag(s) with EXPLICIT additional consent required:")
        output(
            needed_tags,
            fmt=ctx.state.output_format,
            columns=["name", "type", "consent_required", "url"],
            title="Tags with Additional Consent Required",
        )
    else:
        print_success("No tags with explicit additional consent requirements found.")

    if show_all and not_set_tags:
        print_warning(f"\nFound {len(not_set_tags)} tag(s) with consent 'notSet':")
        output(
            not_set_tags,
            fmt=ctx.state.output_format,
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
    ctx = resolve_workspace_context()

    tags = ctx.client.list_tags(**ctx.api_kwargs)

    triggers = ctx.client.list_triggers(**ctx.api_kwargs)
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
        tag_url = _add_authuser(tag.get("tagManagerUrl", ""), ctx.state.authuser)

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
    fmt = ctx.state.output_format
    has_issues = False

    # 1. Sync script loading
    if sync_scripts:
        has_issues = True
        print_warning(f"\n{len(sync_scripts)} script(s) loaded WITHOUT async attribute:")
        output(
            sync_scripts,
            fmt=fmt,
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
            fmt=fmt,
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
            fmt=fmt,
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
            fmt=fmt,
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


@app.command("create")
def create_tag(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Tag name"),
    ],
    tag_type: Annotated[
        str,
        typer.Option("--type", "-t", help="Tag type (default: html)"),
    ] = "html",
    html: Annotated[
        str | None,
        typer.Option("--html", help="Inline HTML content for Custom HTML tags"),
    ] = None,
    html_file: Annotated[
        Path | None,
        typer.Option(
            "--html-file",
            help="Path to file containing HTML content",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    trigger_id: Annotated[
        list[str] | None,
        typer.Option("--trigger-id", help="Firing trigger ID (repeatable)"),
    ] = None,
    folder_id: Annotated[
        str | None,
        typer.Option("--folder-id", help="Parent folder ID"),
    ] = None,
    once_per_event: Annotated[
        bool,
        typer.Option("--once-per-event/--unlimited", help="Fire once per event (default: once)"),
    ] = True,
) -> None:
    """Create a new tag in the workspace.

    For Custom HTML tags, provide content via --html or --html-file.

    Examples:
        gtm tag create --name "My Tag" --html '<script>console.log("hi")</script>'
        gtm tag create --name "My Tag" --html-file pixel.html --trigger-id 295 --folder-id 409
    """
    ctx = resolve_workspace_context()

    html_content = _resolve_html_content(html, html_file)

    if tag_type == "html" and not html_content:
        print_error("Custom HTML tags require --html or --html-file")
        raise typer.Exit(1)

    # Build tag body
    tag_body: dict[str, Any] = {
        "name": name,
        "type": tag_type,
    }

    if html_content:
        tag_body["parameter"] = [
            {"type": "template", "key": "html", "value": html_content},
            {"type": "boolean", "key": "supportDocumentWrite", "value": "false"},
        ]

    if trigger_id:
        tag_body["firingTriggerId"] = trigger_id

    if folder_id:
        tag_body["parentFolderId"] = folder_id

    tag_body["tagFiringOption"] = "oncePerEvent" if once_per_event else "unlimited"

    result = ctx.client.create_tag(tag_body=tag_body, **ctx.api_kwargs)

    created_id = result.get("tagId", "")
    print_success(f"Created tag '{name}' (ID: {created_id})")
    output(result, fmt=ctx.state.output_format)


@app.command("update")
def update_tag(
    tag_id: Annotated[str, typer.Argument(help="Tag ID to update")],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="New tag name"),
    ] = None,
    html: Annotated[
        str | None,
        typer.Option("--html", help="New inline HTML content"),
    ] = None,
    html_file: Annotated[
        Path | None,
        typer.Option(
            "--html-file",
            help="Path to file containing new HTML content",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
    trigger_id: Annotated[
        list[str] | None,
        typer.Option(
            "--trigger-id",
            help="Replace ALL firing trigger IDs (repeatable; clears existing triggers)",
        ),
    ] = None,
    folder_id: Annotated[
        str | None,
        typer.Option("--folder-id", help="Move to folder ID"),
    ] = None,
) -> None:
    """Update an existing tag in the workspace.

    Fetches the current tag, applies changes, and saves. Only specified
    fields are changed; everything else is preserved.

    Examples:
        gtm tag update 421 --html-file loader.html
        gtm tag update 420 --name "TikTok Stub v2"
        gtm tag update 421 --trigger-id 295 --trigger-id 296
    """
    ctx = resolve_workspace_context()

    if all(v is None for v in (name, html, html_file, trigger_id, folder_id)):
        print_error("No changes specified. Use --name, --html, --html-file, --trigger-id, or --folder-id.")
        raise typer.Exit(1)

    html_content = _resolve_html_content(html, html_file)

    # Fetch current tag
    try:
        tag = ctx.client.get_tag(tag_id=tag_id, **ctx.api_kwargs)
    except ResourceNotFoundError:
        print_error(f"Tag '{tag_id}' not found")
        raise typer.Exit(1) from None

    # Apply changes
    if name is not None:
        tag["name"] = name

    if html_content is not None:
        for p in tag.get("parameter", []):
            if p.get("key") == "html":
                p["value"] = html_content
                break
        else:
            tag.setdefault("parameter", []).append(
                {"type": "template", "key": "html", "value": html_content}
            )

    if trigger_id is not None:
        tag["firingTriggerId"] = trigger_id

    if folder_id is not None:
        tag["parentFolderId"] = folder_id

    result = ctx.client.update_tag(tag_id=tag_id, tag_body=tag, **ctx.api_kwargs)
    print_success(f"Updated tag '{result.get('name', tag_id)}' (ID: {tag_id})")
    output(result, fmt=ctx.state.output_format)


def _set_tag_paused(tag_ids: list[str], paused: bool) -> None:
    """Set paused state on one or more tags."""
    ctx = resolve_workspace_context()

    action = "Pausing" if paused else "Unpausing"
    failures = 0
    for tid in tag_ids:
        try:
            tag = ctx.client.get_tag(tag_id=tid, **ctx.api_kwargs)
        except ResourceNotFoundError:
            print_error(f"Tag '{tid}' not found")
            failures += 1
            continue

        tag["paused"] = paused
        result = ctx.client.update_tag(tag_id=tid, tag_body=tag, **ctx.api_kwargs)
        print_success(f"{action} tag '{result.get('name', tid)}' (ID: {tid})")

    if failures:
        raise typer.Exit(1)


@app.command("pause")
def pause_tag(
    tag_ids: Annotated[list[str], typer.Argument(help="Tag ID(s) to pause")],
) -> None:
    """Pause one or more tags.

    Examples:
        gtm tag pause 304
        gtm tag pause 298 302 303
    """
    _set_tag_paused(tag_ids, paused=True)


@app.command("unpause")
def unpause_tag(
    tag_ids: Annotated[list[str], typer.Argument(help="Tag ID(s) to unpause")],
) -> None:
    """Unpause one or more tags.

    Examples:
        gtm tag unpause 304
        gtm tag unpause 298 302 303
    """
    _set_tag_paused(tag_ids, paused=False)


@app.command("delete")
def delete_tag(
    tag_id: Annotated[str, typer.Argument(help="Tag ID to delete")],
) -> None:
    """Delete a tag from the workspace."""
    ctx = resolve_workspace_context()

    try:
        tag = ctx.client.get_tag(tag_id=tag_id, **ctx.api_kwargs)
    except ResourceNotFoundError:
        print_error(f"Tag '{tag_id}' not found")
        raise typer.Exit(1) from None

    tag_name = tag.get("name", tag_id)
    if not ctx.state.yes and not confirm(f"Delete tag '{tag_name}' (ID: {tag_id})?"):
        raise typer.Exit(0)

    ctx.client.delete_tag(tag_id=tag_id, **ctx.api_kwargs)
    print_success(f"Deleted tag '{tag_name}' (ID: {tag_id})")
