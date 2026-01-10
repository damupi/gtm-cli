"""Tests for output utilities."""

import json

from gtm_cli.utils.output import OutputFormat, format_json, format_plain


def test_format_json_list():
    """Test JSON output formatting for list."""
    data = [{"name": "test", "value": 123}]
    result = format_json(data)
    parsed = json.loads(result)
    assert parsed == data


def test_format_json_dict():
    """Test JSON output for single item."""
    data = {"name": "test", "value": 123}
    result = format_json(data)
    parsed = json.loads(result)
    assert parsed == data


def test_format_plain():
    """Test plain (TSV) output formatting."""
    data = [
        {"name": "tag1", "type": "html"},
        {"name": "tag2", "type": "script"},
    ]
    result = format_plain(data)
    lines = result.strip().split("\n")
    assert len(lines) == 2
    assert "tag1" in lines[0]
    assert "tag2" in lines[1]


def test_format_plain_with_columns():
    """Test plain output with specific columns."""
    data = [
        {"name": "tag1", "type": "html", "extra": "ignored"},
    ]
    result = format_plain(data, columns=["name", "type"])
    assert "tag1\thtml" in result
    assert "ignored" not in result


def test_format_plain_empty_list():
    """Test formatting empty list."""
    data: list[dict[str, str]] = []
    result = format_plain(data)
    assert result == ""


def test_output_format_enum():
    """Test OutputFormat enum values."""
    assert OutputFormat.JSON.value == "json"
    assert OutputFormat.YAML.value == "yaml"
    assert OutputFormat.TABLE.value == "table"
    assert OutputFormat.PLAIN.value == "plain"
