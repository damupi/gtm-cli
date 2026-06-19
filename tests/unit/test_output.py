"""Tests for output utilities."""

import json
import time
from unittest.mock import patch

from gtm_cli.utils.output import (
    OutputFormat,
    format_json,
    format_plain,
    format_timestamp,
    output,
    relative_time,
)


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


def test_format_json_multiline_js_is_valid():
    """format_json must produce parseable JSON even when a value contains newlines.

    Regression test for: gtm variable get -f json producing invalid JSON for
    jsm variables (literal newlines in the JS body instead of escaped \\n).
    """
    js_body = "function() {\n  var x = {{Page URL}};\n  return x || 'default';\n}"
    data = {"variableId": "495", "name": "CJS - Example", "parameter": [{"key": "javascript", "value": js_body}]}
    result = format_json(data)
    parsed = json.loads(result)  # must not raise
    assert parsed["parameter"][0]["value"] == js_body


def test_output_json_is_machine_parseable(capsys):
    """output(..., fmt=JSON) writes parseable JSON to stdout without Rich markup corruption.

    Rich's console.print() treats square brackets as markup tags, which corrupts
    JSON arrays. output() must use plain print() for JSON format.
    """
    data = [{"variableId": "1", "parameter": [{"key": "javascript", "value": "function() {\n  return true;\n}"}]}]
    with patch("gtm_cli.utils.output.is_interactive", return_value=False):
        output(data, fmt=OutputFormat.JSON)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)  # raises if Rich corrupted the output
    assert parsed[0]["parameter"][0]["value"] == "function() {\n  return true;\n}"


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


# ---------------------------------------------------------------------------
# format_timestamp
# ---------------------------------------------------------------------------


class TestFormatTimestamp:
    def test_format_timestamp_valid(self):
        """Known ms timestamp -> expected 'YYYY-MM-DD HH:MM' string."""
        # 1700000000000 ms = 2023-11-14 22:13:20 UTC
        result = format_timestamp("1700000000000")
        assert result != ""
        # Should contain the date part (time varies by local timezone)
        assert "2023-11-1" in result  # 14 or 15 depending on timezone

    def test_format_timestamp_empty(self):
        """Empty string -> empty string."""
        assert format_timestamp("") == ""

    def test_format_timestamp_invalid(self):
        """Non-numeric string -> empty string."""
        assert format_timestamp("abc") == ""

    def test_format_timestamp_zero(self):
        """Zero timestamp -> epoch date string."""
        result = format_timestamp("0")
        assert result != ""
        assert "1970" in result or "1969" in result  # depends on timezone


# ---------------------------------------------------------------------------
# relative_time
# ---------------------------------------------------------------------------


class TestRelativeTime:
    def test_relative_time_just_now(self):
        """< 60 seconds ago -> 'just now'."""
        now_ms = str(int(time.time() * 1000))
        assert relative_time(now_ms) == "just now"

    def test_relative_time_minutes(self):
        """5 minutes ago -> '5 minutes ago'."""
        five_min_ago = str(int((time.time() - 300) * 1000))
        assert relative_time(five_min_ago) == "5 minutes ago"

    def test_relative_time_one_minute(self):
        """1 minute ago -> '1 minute ago' (singular)."""
        one_min_ago = str(int((time.time() - 60) * 1000))
        assert relative_time(one_min_ago) == "1 minute ago"

    def test_relative_time_hours(self):
        """3 hours ago -> '3 hours ago'."""
        three_hours_ago = str(int((time.time() - 3 * 3600) * 1000))
        assert relative_time(three_hours_ago) == "3 hours ago"

    def test_relative_time_one_hour(self):
        """1 hour ago -> '1 hour ago' (singular)."""
        one_hour_ago = str(int((time.time() - 3600) * 1000))
        assert relative_time(one_hour_ago) == "1 hour ago"

    def test_relative_time_days(self):
        """10 days ago -> '10 days ago'."""
        ten_days_ago = str(int((time.time() - 10 * 86400) * 1000))
        assert relative_time(ten_days_ago) == "10 days ago"

    def test_relative_time_one_day(self):
        """1 day ago -> '1 day ago' (singular)."""
        one_day_ago = str(int((time.time() - 86400) * 1000))
        assert relative_time(one_day_ago) == "1 day ago"

    def test_relative_time_months(self):
        """90 days ago -> '3 months ago'."""
        ninety_days_ago = str(int((time.time() - 90 * 86400) * 1000))
        assert relative_time(ninety_days_ago) == "3 months ago"

    def test_relative_time_years(self):
        """400 days ago -> '1 year ago'."""
        four_hundred_days_ago = str(int((time.time() - 400 * 86400) * 1000))
        assert relative_time(four_hundred_days_ago) == "1 year ago"

    def test_relative_time_empty(self):
        """Empty string -> empty string."""
        assert relative_time("") == ""

    def test_relative_time_invalid(self):
        """Non-numeric string -> empty string."""
        assert relative_time("abc") == ""
