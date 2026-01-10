"""Output formatting utilities for GTM Orchestrator."""

import json
from enum import Enum
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

console = Console()
error_console = Console(stderr=True)


class OutputFormat(str, Enum):
    """Supported output formats."""

    JSON = "json"
    YAML = "yaml"
    TABLE = "table"


def format_json(data: Any) -> str:
    """Format data as JSON."""
    return json.dumps(data, indent=2, default=str)


def format_yaml(data: Any) -> str:
    """Format data as YAML."""
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def format_table(
    data: list[dict[str, Any]],
    columns: list[str] | None = None,
    title: str | None = None,
) -> Table:
    """Format data as a Rich table.

    Args:
        data: List of dictionaries to display
        columns: Column names to display (defaults to all keys from first item)
        title: Optional table title
    """
    table = Table(title=title, show_header=True, header_style="bold cyan")

    if not data:
        table.add_column("No data")
        return table

    # Determine columns from data if not specified
    if columns is None:
        columns = list(data[0].keys())

    for col in columns:
        table.add_column(col.replace("_", " ").title())

    for row in data:
        values = [str(row.get(col, "")) for col in columns]
        table.add_row(*values)

    return table


def output(
    data: Any,
    fmt: OutputFormat = OutputFormat.TABLE,
    columns: list[str] | None = None,
    title: str | None = None,
) -> None:
    """Output data in the specified format.

    Args:
        data: Data to output (dict, list, or any JSON-serializable object)
        fmt: Output format (json, yaml, or table)
        columns: For table format, which columns to display
        title: For table format, optional title
    """
    if fmt == OutputFormat.JSON:
        console.print(format_json(data))
    elif fmt == OutputFormat.YAML:
        console.print(format_yaml(data))
    elif fmt == OutputFormat.TABLE:
        if isinstance(data, list):
            table = format_table(data, columns=columns, title=title)
            console.print(table)
        elif isinstance(data, dict):
            # Single item - display as key-value pairs
            table = Table(show_header=False)
            table.add_column("Field", style="cyan")
            table.add_column("Value")
            for key, value in data.items():
                table.add_row(key.replace("_", " ").title(), str(value))
            console.print(table)
        else:
            console.print(data)


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]✓[/green] {message}")


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    error_console.print(f"[red]✗[/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[yellow]![/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[blue]ℹ[/blue] {message}")


def confirm(message: str, default: bool = False) -> bool:
    """Ask for confirmation.

    Args:
        message: The confirmation message
        default: Default value if user just presses Enter

    Returns:
        True if confirmed, False otherwise
    """
    from rich.prompt import Confirm

    return Confirm.ask(message, default=default)
