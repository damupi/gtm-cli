"""Tag CLI commands."""

import re
from pathlib import Path
from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import WorkspaceContext, add_authuser, resolve_workspace_context
from gtm_cli.utils.errors import ResourceNotFoundError
from gtm_cli.utils.output import (
    confirm,
    output,
    print_error,
    print_info,
    print_success,
    print_warning,
    relative_time,
)


def _get_firing_trigger_names(tag: dict[str, Any], trigger_names: dict[str, str]) -> str:
    """Get comma-separated list of firing trigger names for a tag."""
    trigger_ids = tag.get("firingTriggerId", [])
    names = [str(trigger_names.get(tid, tid)) for tid in trigger_ids]
    return ", ".join(names) if names else ""


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


# Event call patterns: (provider, regex to extract event name + params object)
# These match calls like ttq.track('ViewContent', {content_type: 'product'})
_EVENT_CALL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "TikTok",
        re.compile(
            r"""ttq\.track\(\s*['"](\w+)['"]\s*(?:,\s*(\{[^}]*\}))?\s*\)""",
            re.DOTALL,
        ),
    ),
    (
        "Meta/Facebook",
        re.compile(
            r"""fbq\(\s*['"]track(?:Custom)?['"]\s*,\s*['"]([^'"]+)['"]\s*(?:,\s*(\{[^}]*\}))?\s*\)""",
            re.DOTALL,
        ),
    ),
    (
        "Google Ads",
        re.compile(
            r"""gtag\(\s*['"]event['"]\s*,\s*['"](\w+)['"]\s*(?:,\s*(\{[^}]*\}))?\s*\)""",
            re.DOTALL,
        ),
    ),
    (
        "Snapchat",
        re.compile(
            r"""snaptr\(\s*['"]track['"]\s*,\s*['"](\w+)['"]\s*(?:,\s*(\{[^}]*\}))?\s*\)""",
            re.DOTALL,
        ),
    ),
    (
        "Pinterest",
        re.compile(
            r"""pintrk\(\s*['"]track['"]\s*,\s*['"](\w+)['"]\s*(?:,\s*(\{[^}]*\}))?\s*\)""",
            re.DOTALL,
        ),
    ),
    (
        "Twitter/X",
        re.compile(
            r"""twq\(\s*['"]track['"]\s*,\s*['"](\w+)['"]\s*(?:,\s*(\{[^}]*\}))?\s*\)""",
            re.DOTALL,
        ),
    ),
]

# Regex to extract keys from a JS object literal: {key1: val, key2: val}
# Only match keys at the start of the object or after a comma (avoids matching inside string values).
# Known limitation: can still false-match if a string value contains a comma followed by a
# colon-delimited token, e.g. {label: 'foo, bar: baz'} would extract both 'label' and 'bar'.
# This is inherent to regex-based JS parsing; unlikely in real GTM pixel parameters.
_JS_OBJECT_KEY_RE = re.compile(r"""(?:^|[{,])\s*['"]?(\w+)['"]?\s*:""")


def _extract_event_calls(html: str) -> list[dict[str, str]]:
    """Extract event tracking calls from HTML content.

    Returns list of dicts with: provider, event, params (comma-separated param names).
    """
    events: list[dict[str, str]] = []
    for provider, pattern in _EVENT_CALL_PATTERNS:
        for match in pattern.finditer(html):
            event_name = match.group(1)
            params_obj = match.group(2) if match.lastindex and match.lastindex >= 2 else None
            param_names: list[str] = []
            if params_obj:
                param_names = _JS_OBJECT_KEY_RE.findall(params_obj)
            events.append(
                {
                    "provider": provider,
                    "event": event_name,
                    "params": ", ".join(param_names) if param_names else "(none)",
                }
            )
    return events


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
            "tag_id": t.get("tagId", ""),
            "name": t.get("name", ""),
            "type": t.get("type", ""),
            "triggers": _get_firing_trigger_names(t, trigger_names),
            "folder": folder_names.get(t.get("parentFolderId"), "-"),
            "modified": relative_time(t.get("fingerprint", "")),
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
        str | None,
        typer.Argument(help="Search query (matches tag name, case-insensitive)"),
    ] = None,
    tag_type: Annotated[
        str | None,
        typer.Option(
            "--type",
            "-t",
            help="Filter by tag type (e.g. html, googtag, awct)",
        ),
    ] = None,
    trigger: Annotated[
        str | None,
        typer.Option(
            "--trigger",
            help="Filter by firing trigger ID or name (substring match)",
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
    """Search tags by name, type, or trigger.

    Case-insensitive substring match on tag names.
    Optionally filter by tag type with --type or by trigger with --trigger.

    Examples:
        gtm tag search tiktok
        gtm tag search pixel --type html
        gtm tag search --trigger 62
        gtm tag search --trigger "Booking"
    """
    if not query and not tag_type and not trigger:
        print_error("Provide a search query, --type, or --trigger")
        raise typer.Exit(1)

    ctx = resolve_workspace_context()

    tags = ctx.client.list_tags(**ctx.api_kwargs)
    folder_names, trigger_names = _build_tag_lookups(ctx)

    # Build reverse lookup: trigger_id -> trigger_name (already have trigger_names)
    # Also build trigger name -> trigger_id for name-based search
    trigger_ids_for_filter: set[str] | None = None
    if trigger:
        trigger_ids_for_filter = set()
        trigger_lower = trigger.lower()
        # Always include numeric ID directly (handles both known and deleted triggers)
        if trigger.isdigit():
            trigger_ids_for_filter.add(trigger)
        # Also do substring match on trigger names
        for tid, tname in trigger_names.items():
            if trigger_lower in tname.lower():
                trigger_ids_for_filter.add(tid)

        if not trigger_ids_for_filter:
            print_warning(f"No triggers matching '{trigger}'")
            raise typer.Exit(0)

    query_lower = query.lower() if query else None
    type_lower = tag_type.lower() if tag_type else None

    matched = []
    for t in tags:
        if query_lower and query_lower not in t.get("name", "").lower():
            continue
        if type_lower and type_lower != t.get("type", "").lower():
            continue
        if exclude_paused and t.get("paused"):
            continue
        if trigger_ids_for_filter is not None:
            tag_trigger_ids = set(t.get("firingTriggerId", []))
            if not tag_trigger_ids & trigger_ids_for_filter:
                continue
        matched.append(t)

    search_desc = query or ""
    if trigger:
        search_desc += f" trigger={trigger}" if search_desc else f"trigger={trigger}"

    if not matched:
        print_warning(f"No tags matching '{search_desc}'" + (f" (type={tag_type})" if tag_type else ""))
        raise typer.Exit(0)

    data = [
        {
            "tag_id": t.get("tagId", ""),
            "name": t.get("name", ""),
            "type": t.get("type", ""),
            "triggers": _get_firing_trigger_names(t, trigger_names),
            "folder": folder_names.get(t.get("parentFolderId"), "-"),
            "paused": "paused" if t.get("paused") else "",
        }
        for t in matched
    ]

    print_success(f"Found {len(matched)} tag(s) matching '{search_desc}':")
    output(data, fmt=ctx.state.output_format, title=f"Search: {search_desc}")


@app.command("get")
def get_tag(
    tag_ids: Annotated[list[str], typer.Argument(help="Tag ID(s) to retrieve")],
) -> None:
    """Get details of one or more tags.

    Examples:
        gtm tag get 298
        gtm tag get 298 302 303 313
        gtm tag get 298 302 --format json
    """
    ctx = resolve_workspace_context()

    if len(tag_ids) == 1:
        try:
            tag = ctx.client.get_tag(tag_id=tag_ids[0], **ctx.api_kwargs)
        except ResourceNotFoundError:
            print_error(f"Tag '{tag_ids[0]}' not found")
            raise typer.Exit(1) from None
        output(tag, fmt=ctx.state.output_format)
        return

    results: list[dict[str, Any]] = []
    failures = 0
    for tid in tag_ids:
        try:
            tag = ctx.client.get_tag(tag_id=tid, **ctx.api_kwargs)
            results.append(tag)
        except ResourceNotFoundError:
            print_error(f"Tag '{tid}' not found")
            failures += 1

    if results:
        output(results, fmt=ctx.state.output_format)
    if failures:
        raise typer.Exit(1)


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
                    "url": add_authuser(tag.get("tagManagerUrl", ""), ctx.state.authuser),
                }
            )
        elif status == "notSet":
            not_set_tags.append(
                {
                    "name": tag.get("name", ""),
                    "type": tag.get("type", ""),
                    "url": add_authuser(tag.get("tagManagerUrl", ""), ctx.state.authuser),
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
    show_params: Annotated[
        bool,
        typer.Option(
            "--params",
            help="Show event parameters sent by each pixel tag",
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
        tag_url = add_authuser(tag.get("tagManagerUrl", ""), ctx.state.authuser)

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

        # Extract event params if requested
        event_params_summary = ""
        if show_params:
            events = _extract_event_calls(html)
            if events:
                parts = [f"{e['event']}({e['params']})" for e in events]
                event_params_summary = "; ".join(parts)

        detail: dict[str, Any] = {
            "name": name,
            "id": tag.get("tagId", ""),
            "triggers": ", ".join(firing_names),
            "pixels": ", ".join(f"{p['provider']} ({p['pixel_id']})" for p in pixels) or "-",
            "loading": ", ".join(async_summary) if async_summary else "no external scripts",
            "paused": "paused" if tag.get("paused") else "",
        }
        if show_params:
            detail["events"] = event_params_summary or "-"
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
        if show_params:
            columns.insert(-1, "events")
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


@app.command("audit-setup-deps")
def audit_setup_deps() -> None:
    """Audit tags for broken setup tag dependencies.

    Finds tags that reference paused or missing setupTags. A setupTag dependency
    on a paused tag is a silent failure -- the dependent tag may not work correctly.

    Tip: Use --authuser N global option to append authuser parameter to URLs.
    """
    ctx = resolve_workspace_context()

    tags = ctx.client.list_tags(**ctx.api_kwargs)

    # Build tag lookup: tag_id -> tag dict
    tag_map: dict[str, dict[str, Any]] = {t.get("tagId", ""): t for t in tags}

    issues: list[dict[str, str]] = []

    def _check_dep_refs(
        tag: dict[str, Any],
        ref_key: str,
        dep_type: str,
        stop_key: str,
    ) -> None:
        tag_name = tag.get("name", "")
        tag_id_val = tag.get("tagId", "")
        tag_url = add_authuser(tag.get("tagManagerUrl", ""), ctx.state.authuser)

        for ref in tag.get(ref_key, []):
            dep_id = ref.get("tagName", "")
            stop_on_failure = ref.get(stop_key, False)
            dep_tag = tag_map.get(dep_id)

            if dep_tag is None:
                issues.append(
                    {
                        "tag": tag_name,
                        "tag_id": tag_id_val,
                        "dep_type": dep_type,
                        "dep_tag_id": dep_id,
                        "dep_tag_name": "(missing)",
                        "issue": f"{dep_type} tag not found",
                        "stop_on_failure": "yes" if stop_on_failure else "no",
                        "url": tag_url,
                    }
                )
            elif dep_tag.get("paused"):
                issues.append(
                    {
                        "tag": tag_name,
                        "tag_id": tag_id_val,
                        "dep_type": dep_type,
                        "dep_tag_id": dep_id,
                        "dep_tag_name": dep_tag.get("name", ""),
                        "issue": f"{dep_type} tag is PAUSED",
                        "stop_on_failure": "yes" if stop_on_failure else "no",
                        "url": tag_url,
                    }
                )

    for tag in tags:
        _check_dep_refs(tag, "setupTag", "setup", "stopOnSetupFailure")
        _check_dep_refs(tag, "teardownTag", "teardown", "stopTeardownOnFailure")

    if not issues:
        print_success("No broken setup/teardown tag dependencies found.")
        raise typer.Exit(0)

    print_warning(f"Found {len(issues)} broken setup/teardown dependency(ies):")
    output(
        issues,
        fmt=ctx.state.output_format,
        columns=[
            "tag", "tag_id", "dep_type", "dep_tag_name", "dep_tag_id",
            "issue", "stop_on_failure", "url",
        ],
        title="Broken Setup/Teardown Dependencies",
    )


@app.command("audit-params")
def audit_params(
    tag_ids: Annotated[
        list[str] | None,
        typer.Argument(help="Specific tag IDs to audit (default: all)"),
    ] = None,
    folder: Annotated[
        list[str] | None,
        typer.Option(
            "--folder",
            help="Filter by folder name (substring match, repeatable)",
        ),
    ] = None,
) -> None:
    """Audit event parameters sent by pixel/tracking tags.

    Parses JavaScript in Custom HTML tags to extract event tracking calls
    (ttq.track, fbq, gtag, snaptr, pintrk, twq) and shows which parameters
    each tag sends.

    Examples:
        gtm tag audit-params
        gtm tag audit-params 298 302 303 313
        gtm tag audit-params --folder tiktok
        gtm tag audit-params --folder tiktok --folder facebook
    """
    ctx = resolve_workspace_context()

    tags = ctx.client.list_tags(**ctx.api_kwargs)
    folder_names, _ = _build_tag_lookups(ctx)

    # Filter to specific tags or folder
    if tag_ids:
        tag_id_set = set(tag_ids)
        tags = [t for t in tags if t.get("tagId", "") in tag_id_set]
    if folder:
        folder_lowers = [f.lower() for f in folder]
        tags = [
            t
            for t in tags
            if any(
                fl in folder_names.get(t.get("parentFolderId", ""), "").lower()
                for fl in folder_lowers
            )
        ]

    # Only Custom HTML tags have parseable JS
    html_tags = [t for t in tags if t.get("type") == "html"]

    if not html_tags:
        print_info("No Custom HTML tags found matching the criteria.")
        raise typer.Exit(0)

    data: list[dict[str, str]] = []
    for tag in html_tags:
        html = _get_tag_html(tag)
        if not html:
            continue
        events = _extract_event_calls(html)
        tag_name = tag.get("name", "")
        tag_id = tag.get("tagId", "")
        tag_folder = folder_names.get(tag.get("parentFolderId", ""), "-")

        if events:
            for ev in events:
                data.append(
                    {
                        "tag": tag_name,
                        "tag_id": tag_id,
                        "folder": tag_folder,
                        "provider": ev["provider"],
                        "event": ev["event"],
                        "params": ev["params"],
                    }
                )
        else:
            # Tag has HTML but no recognized event calls
            pixels = _detect_pixels(html)
            if pixels:
                for p in pixels:
                    data.append(
                        {
                            "tag": tag_name,
                            "tag_id": tag_id,
                            "folder": tag_folder,
                            "provider": p["provider"],
                            "event": "(init only)",
                            "params": "(none)",
                        }
                    )

    if not data:
        print_info("No event tracking calls found in the matched tags.")
        raise typer.Exit(0)

    print_success(f"Found {len(data)} event call(s) across {len(html_tags)} tag(s):")
    output(
        data,
        fmt=ctx.state.output_format,
        columns=["tag", "tag_id", "folder", "provider", "event", "params"],
        title="Event Parameter Audit",
    )


@app.command("compare")
def compare_tags(
    tag_ids: Annotated[
        list[str] | None,
        typer.Argument(help="Tag IDs to compare (2 or more)"),
    ] = None,
    trigger: Annotated[
        str | None,
        typer.Option(
            "--trigger",
            help="Compare all tags sharing this trigger ID",
        ),
    ] = None,
    folder: Annotated[
        list[str] | None,
        typer.Option(
            "--folder",
            help="Compare tags across folders (repeatable, substring match)",
        ),
    ] = None,
) -> None:
    """Compare tags side by side, highlighting differences.

    Compare specific tags by ID, all tags on a trigger, or tags across folders.

    Examples:
        gtm tag compare 298 17
        gtm tag compare --trigger 3
        gtm tag compare --folder tiktok --folder facebook
    """
    if not tag_ids and not trigger and not folder:
        print_error("Provide tag IDs, --trigger, or --folder to compare")
        raise typer.Exit(1)

    ctx = resolve_workspace_context()

    all_tags = ctx.client.list_tags(**ctx.api_kwargs)
    folder_names, trigger_names = _build_tag_lookups(ctx)

    # Resolve which tags to compare
    tags_to_compare: list[dict[str, Any]] = []

    if tag_ids:
        tag_map = {t.get("tagId", ""): t for t in all_tags}
        for tid in tag_ids:
            if tid in tag_map:
                tags_to_compare.append(tag_map[tid])
            else:
                print_error(f"Tag '{tid}' not found")
                raise typer.Exit(1)

    elif trigger:
        for t in all_tags:
            if trigger in t.get("firingTriggerId", []):
                tags_to_compare.append(t)
        if not tags_to_compare:
            trigger_label = trigger_names.get(trigger, trigger)
            print_warning(f"No tags found on trigger '{trigger_label}' (ID: {trigger})")
            raise typer.Exit(0)

    elif folder:
        folder_lowers = [f.lower() for f in folder]
        for t in all_tags:
            tag_folder = folder_names.get(t.get("parentFolderId", ""), "")
            if any(fl in tag_folder.lower() for fl in folder_lowers):
                tags_to_compare.append(t)
        if not tags_to_compare:
            print_warning(f"No tags found in folders matching: {', '.join(folder)}")
            raise typer.Exit(0)

    if len(tags_to_compare) < 2:
        print_warning("Need at least 2 tags to compare")
        raise typer.Exit(0)

    # Extract comparison data for each tag (keyed by tag_id to handle duplicate names)
    comparison: list[dict[str, str]] = []
    all_params: set[str] = set()
    tag_parsed: dict[str, tuple[list[dict[str, str]], list[dict[str, str]]]] = {}

    for tag in tags_to_compare:
        tag_id = tag.get("tagId", "")
        html = _get_tag_html(tag)
        events = _extract_event_calls(html) if html else []
        pixels = _detect_pixels(html) if html else []
        tag_parsed[tag_id] = (events, pixels)
        for ev in events:
            if ev["params"] != "(none)":
                all_params.update(p.strip() for p in ev["params"].split(","))

    # Build comparison table
    for tag in tags_to_compare:
        tag_name = tag.get("name", "")
        tag_id = tag.get("tagId", "")
        events, pixels = tag_parsed.get(tag_id, ([], []))
        trigger_list = _get_firing_trigger_names(tag, trigger_names)
        tag_folder = folder_names.get(tag.get("parentFolderId", ""), "-")

        event_summary = ", ".join(e["event"] for e in events) or "-"
        pixel_summary = ", ".join(f"{p['provider']}" for p in pixels) or "-"

        # Collect params this tag sends
        tag_params: set[str] = set()
        for ev in events:
            if ev["params"] != "(none)":
                tag_params.update(p.strip() for p in ev["params"].split(","))

        row: dict[str, str] = {
            "tag": tag_name,
            "tag_id": tag_id,
            "folder": tag_folder,
            "type": tag.get("type", ""),
            "triggers": trigger_list,
            "pixels": pixel_summary,
            "events": event_summary,
            "paused": "paused" if tag.get("paused") else "",
        }

        # Add param columns
        for param in sorted(all_params):
            row[param] = "✓" if param in tag_params else "-"

        comparison.append(row)

    # Build columns list
    columns = ["tag", "tag_id", "folder", "type", "triggers", "pixels", "events", "paused"]
    columns.extend(sorted(all_params))

    print_success(f"Comparing {len(tags_to_compare)} tags:")
    output(
        comparison,
        fmt=ctx.state.output_format,
        columns=columns,
        title="Tag Comparison",
    )


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
