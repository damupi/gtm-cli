"""Custom Template CLI commands."""

from pathlib import Path
from typing import Annotated, Any

import typer

from gtm_cli.cli.helpers import resolve_workspace_context
from gtm_cli.utils.output import confirm, output, print_error, print_success

app = typer.Typer(
    help="""Manage GTM Custom Templates (sandboxed JS .tpl).

Custom Templates wrap sandboxed JavaScript with a declared permission model
(cookie access, injected-script domains, etc.), unlike Custom HTML tags which
have unrestricted window/document access.

Auto-detects account/container/workspace if you have only one of each.

Example: gtm template list
"""
)


@app.command("list")
def list_templates() -> None:
    """List all Custom Templates in the workspace."""
    ctx = resolve_workspace_context()

    templates = ctx.client.list_templates(**ctx.api_kwargs)

    data = [
        {
            "template_id": t.get("templateId", ""),
            "name": t.get("name", ""),
        }
        for t in templates
    ]

    output(data, fmt=ctx.state.output_format, title="Templates")


@app.command("get")
def get_template(
    template_id: Annotated[str, typer.Argument(help="Template ID")],
) -> None:
    """Get details of a specific Custom Template."""
    ctx = resolve_workspace_context()

    template = ctx.client.get_template(template_id=template_id, **ctx.api_kwargs)
    if not template:
        print_error(f"Template '{template_id}' not found")
        raise typer.Exit(1)

    output(template, fmt=ctx.state.output_format)


@app.command("create")
def create_template(
    name: Annotated[
        str,
        typer.Option("--name", "-n", help="Template display name"),
    ],
    file: Annotated[
        Path,
        typer.Option(
            "--file",
            help="Path to the .tpl file containing the template's sandboxed JS content",
            exists=True,
            dir_okay=False,
        ),
    ],
) -> None:
    """Create a new Custom Template in the workspace from a .tpl file.

    Examples:
        gtm template create --name "Attribution Cookie" --file attribution-cookie.tpl
    """
    ctx = resolve_workspace_context()

    template_body: dict[str, Any] = {
        "name": name,
        "templateData": file.read_text(),
    }

    result = ctx.client.create_template(template_body=template_body, **ctx.api_kwargs)

    template_id = result.get("templateId", "")
    print_success(f"Created template '{name}' (ID: {template_id})")
    output(result, fmt=ctx.state.output_format)


@app.command("update")
def update_template(
    template_id: Annotated[str, typer.Argument(help="Template ID to update")],
    name: Annotated[
        str | None,
        typer.Option("--name", "-n", help="New template display name"),
    ] = None,
    file: Annotated[
        Path | None,
        typer.Option(
            "--file",
            help="Path to a .tpl file with new sandboxed JS content",
            exists=True,
            dir_okay=False,
        ),
    ] = None,
) -> None:
    """Update an existing Custom Template in the workspace.

    Fetches the current template, applies changes, and saves. Only specified
    fields are changed; everything else is preserved.

    Examples:
        gtm template update 12 --file attribution-cookie-v2.tpl
        gtm template update 12 --name "Attribution Cookie v2"
    """
    ctx = resolve_workspace_context()

    if name is None and file is None:
        print_error("No changes specified. Use --name and/or --file.")
        raise typer.Exit(1)

    template = ctx.client.get_template(template_id=template_id, **ctx.api_kwargs)
    if not template:
        print_error(f"Template '{template_id}' not found")
        raise typer.Exit(1)

    if name is not None:
        template["name"] = name

    if file is not None:
        template["templateData"] = file.read_text()

    result = ctx.client.update_template(
        template_id=template_id, template_body=template, **ctx.api_kwargs
    )
    print_success(f"Updated template '{result.get('name', template_id)}' (ID: {template_id})")
    output(result, fmt=ctx.state.output_format)


@app.command("delete")
def delete_template(
    template_id: Annotated[str, typer.Argument(help="Template ID to delete")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation prompt")] = False,
) -> None:
    """Delete a Custom Template from the workspace."""
    ctx = resolve_workspace_context()

    template = ctx.client.get_template(template_id=template_id, **ctx.api_kwargs)
    if not template:
        print_error(f"Template '{template_id}' not found")
        raise typer.Exit(1)

    template_name = template.get("name", template_id)

    if (
        not ctx.state.yes
        and not yes
        and not confirm(f"Delete template '{template_name}' (ID: {template_id})?")
    ):
        raise typer.Exit(0)

    ctx.client.delete_template(template_id=template_id, **ctx.api_kwargs)
    print_success(f"Deleted template '{template_name}' (ID: {template_id})")
