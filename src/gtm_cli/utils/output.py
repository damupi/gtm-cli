"""Output formatting utilities for GTM CLI."""

import json
import sys
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import yaml
from rich.console import Console
from rich.table import Table

console = Console()
error_console = Console(stderr=True)


def is_interactive() -> bool:
    """Check if stdout is an interactive terminal."""
    return sys.stdout.isatty()


class OutputFormat(str, Enum):
    """Supported output formats."""

    JSON = "json"
    YAML = "yaml"
    TABLE = "table"
    PLAIN = "plain"  # Tab-separated, no headers - good for piping


def format_json(data: Any) -> str:
    """Format data as JSON."""
    return json.dumps(data, indent=2, default=str)


def format_yaml(data: Any) -> str:
    """Format data as YAML."""
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


def format_plain(data: list[dict[str, Any]], columns: list[str] | None = None) -> str:
    """Format data as tab-separated values (no headers).

    Good for piping to grep, awk, cut, etc.
    """
    if not data:
        return ""

    if columns is None:
        columns = list(data[0].keys())

    lines = []
    for row in data:
        values = [str(row.get(col, "")).replace("\t", " ") for col in columns]
        lines.append("\t".join(values))
    return "\n".join(lines)


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
        fmt: Output format (json, yaml, table, or plain)
        columns: For table format, which columns to display
        title: For table format, optional title

    If stdout is not a TTY (piped), TABLE format auto-switches to PLAIN.
    """
    # Auto-switch to plain when piping (unless explicit format requested)
    if fmt == OutputFormat.TABLE and not is_interactive():
        fmt = OutputFormat.PLAIN

    if fmt == OutputFormat.JSON:
        # Use print() not console.print() — Rich treats [] as markup tags and corrupts JSON
        print(format_json(data))
    elif fmt == OutputFormat.YAML:
        # Same: bypass Rich to avoid markup interpretation
        print(format_yaml(data), end="")
    elif fmt == OutputFormat.PLAIN:
        if isinstance(data, list):
            print(format_plain(data, columns=columns))
        elif isinstance(data, dict):
            # Single item - output as key=value pairs
            for key, value in data.items():
                print(f"{key}\t{value}")
        else:
            print(data)
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
    """Print an info message. Suppressed when stdout is not a TTY (piping)."""
    if is_interactive():
        console.print(f"[blue]ℹ[/blue] {message}")


def _ago(n: int, unit: str) -> str:
    """Format '3 days ago' with correct pluralization."""
    return f"{n} {unit}{'s' if n != 1 else ''} ago"


def relative_time(fingerprint: str) -> str:
    """Convert fingerprint timestamp (ms since epoch) to relative time like '3 days ago'."""
    if not fingerprint:
        return ""
    try:
        ts = int(fingerprint) / 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        now = datetime.now(tz=timezone.utc)
        seconds = (now - dt).total_seconds()

        if seconds < 60:
            return "just now"
        minutes = seconds / 60
        if minutes < 60:
            return _ago(int(minutes), "minute")
        hours = minutes / 60
        if hours < 24:
            return _ago(int(hours), "hour")
        days = hours / 24
        if days < 30:
            return _ago(int(days), "day")
        if days < 365:
            return _ago(int(days / 30), "month")
        return _ago(int(days / 365), "year")
    except (ValueError, OSError):
        return ""


def format_timestamp(fingerprint: str) -> str:
    """Convert fingerprint timestamp (ms since epoch) to local datetime string."""
    if not fingerprint:
        return ""
    try:
        ts = int(fingerprint) / 1000
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return ""


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
