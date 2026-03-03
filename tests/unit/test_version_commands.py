"""Tests for version CLI commands and helper functions."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.main import State, app
from gtm_cli.cli.versions import _compute_diff, _fingerprint_in_range, _parse_date_ms
from gtm_cli.utils.errors import ResourceNotFoundError
from gtm_cli.utils.output import OutputFormat

runner = CliRunner()

_PATCH_TARGET = "gtm_cli.cli.versions._resolve_container_context"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_resolve():
    """Build a controlled container context tuple (state, client, account_id, container_id)."""
    state = State()
    state.profile = "test"
    state.output_format = OutputFormat.JSON
    state.service_account = None
    state.yes = True
    client = MagicMock()
    return state, client, "a1", "c1"


# ===========================================================================
# Pure function tests: _compute_diff
# ===========================================================================


class TestComputeDiff:
    def test_diff_tags_added(self):
        """v1 has no tags, v2 has 2 tags -> 2 'added' entries."""
        v1 = {"tag": [], "trigger": [], "variable": []}
        v2 = {
            "tag": [
                {"tagId": "1", "name": "Tag A", "fingerprint": "100"},
                {"tagId": "2", "name": "Tag B", "fingerprint": "200"},
            ],
            "trigger": [],
            "variable": [],
        }
        changes = _compute_diff(v1, v2)

        assert len(changes) == 2
        assert all(c["status"] == "added" for c in changes)
        assert all(c["type"] == "tag" for c in changes)
        names = {c["name"] for c in changes}
        assert names == {"Tag A", "Tag B"}

    def test_diff_tags_removed(self):
        """v1 has 2 tags, v2 has none -> 2 'removed' entries."""
        v1 = {
            "tag": [
                {"tagId": "1", "name": "Tag A", "fingerprint": "100"},
                {"tagId": "2", "name": "Tag B", "fingerprint": "200"},
            ],
            "trigger": [],
            "variable": [],
        }
        v2 = {"tag": [], "trigger": [], "variable": []}
        changes = _compute_diff(v1, v2)

        assert len(changes) == 2
        assert all(c["status"] == "removed" for c in changes)

    def test_diff_tags_modified(self):
        """Same tagId but different fingerprint -> 'modified'."""
        v1 = {"tag": [{"tagId": "1", "name": "Tag A", "fingerprint": "100"}]}
        v2 = {"tag": [{"tagId": "1", "name": "Tag A", "fingerprint": "999"}]}
        changes = _compute_diff(v1, v2)

        assert len(changes) == 1
        assert changes[0]["status"] == "modified"
        assert changes[0]["type"] == "tag"
        assert changes[0]["id"] == "1"

    def test_diff_no_changes(self):
        """Identical versions -> empty list."""
        v1 = {"tag": [{"tagId": "1", "name": "Tag A", "fingerprint": "100"}]}
        v2 = {"tag": [{"tagId": "1", "name": "Tag A", "fingerprint": "100"}]}
        changes = _compute_diff(v1, v2)

        assert changes == []

    def test_diff_mixed_resources(self):
        """Changes across tags, triggers, and variables simultaneously."""
        v1 = {
            "tag": [{"tagId": "1", "name": "Tag A", "fingerprint": "100"}],
            "trigger": [{"triggerId": "10", "name": "Trigger X", "fingerprint": "300"}],
            "variable": [{"variableId": "20", "name": "Var P", "fingerprint": "400"}],
        }
        v2 = {
            "tag": [
                {"tagId": "1", "name": "Tag A", "fingerprint": "100"},
                {"tagId": "2", "name": "Tag B", "fingerprint": "200"},
            ],
            "trigger": [],
            "variable": [{"variableId": "20", "name": "Var P", "fingerprint": "999"}],
        }
        changes = _compute_diff(v1, v2)

        statuses = {(c["type"], c["status"]) for c in changes}
        assert ("tag", "added") in statuses
        assert ("trigger", "removed") in statuses
        assert ("variable", "modified") in statuses
        assert len(changes) == 3


# ===========================================================================
# Pure function tests: _parse_date_ms
# ===========================================================================


class TestParseDateMs:
    def test_parse_valid_date(self):
        """'2025-06-15' -> exact UTC ms timestamp."""
        ms = _parse_date_ms("2025-06-15")
        # 2025-06-15T00:00:00Z = 1749945600 seconds = 1749945600000 ms
        assert ms == 1_749_945_600_000

    def test_parse_invalid_date_exits(self):
        """'not-a-date' -> Exit (typer.Exit wraps as click.exceptions.Exit)."""
        from click.exceptions import Exit

        with pytest.raises(Exit):
            _parse_date_ms("not-a-date")

    def test_parse_end_of_day(self):
        """end_of_day=True adds time to end of day (23:59:59.999)."""
        start_ms = _parse_date_ms("2025-06-15", end_of_day=False)
        end_ms = _parse_date_ms("2025-06-15", end_of_day=True)

        # end_of_day should be later than start of day
        assert end_ms > start_ms
        # The difference should be approximately 24 hours minus 1 ms
        diff = end_ms - start_ms
        almost_24h = 24 * 60 * 60 * 1000 - 1
        assert diff == almost_24h


# ===========================================================================
# Pure function tests: _fingerprint_in_range
# ===========================================================================


class TestFingerprintInRange:
    def test_in_range(self):
        """Fingerprint between since and until -> True."""
        assert _fingerprint_in_range("500", since_ms=100, until_ms=1000) is True

    def test_before_since(self):
        """Fingerprint < since_ms -> False."""
        assert _fingerprint_in_range("50", since_ms=100, until_ms=1000) is False

    def test_after_until(self):
        """Fingerprint > until_ms -> False."""
        assert _fingerprint_in_range("1500", since_ms=100, until_ms=1000) is False

    def test_empty_fingerprint(self):
        """Empty string -> False."""
        assert _fingerprint_in_range("", since_ms=100, until_ms=1000) is False

    def test_no_bounds(self):
        """Both None -> True (any fingerprint is in range)."""
        assert _fingerprint_in_range("500", since_ms=None, until_ms=None) is True

    def test_only_since(self):
        """Only since_ms set -> True if fp >= since."""
        assert _fingerprint_in_range("500", since_ms=100, until_ms=None) is True
        assert _fingerprint_in_range("50", since_ms=100, until_ms=None) is False

    def test_only_until(self):
        """Only until_ms set -> True if fp <= until."""
        assert _fingerprint_in_range("500", since_ms=None, until_ms=1000) is True
        assert _fingerprint_in_range("1500", since_ms=None, until_ms=1000) is False

    def test_exact_boundary_since(self):
        """Fingerprint exactly equal to since_ms -> True."""
        assert _fingerprint_in_range("100", since_ms=100, until_ms=1000) is True

    def test_exact_boundary_until(self):
        """Fingerprint exactly equal to until_ms -> True."""
        assert _fingerprint_in_range("1000", since_ms=100, until_ms=1000) is True

    def test_non_numeric_fingerprint(self):
        """Non-numeric fingerprint -> False."""
        assert _fingerprint_in_range("abc", since_ms=100, until_ms=1000) is False


# ===========================================================================
# Command-level tests: version get
# ===========================================================================


class TestVersionGet:
    def test_version_get_success(self, mock_resolve):
        """Successful get returns version data."""
        state, client, account_id, container_id = mock_resolve
        client.get_version.return_value = {
            "containerVersionId": "5",
            "name": "v5",
            "fingerprint": "1700000000000",
        }

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["version", "get", "5"])

        assert result.exit_code == 0, result.output
        client.get_version.assert_called_once()
        call_kwargs = client.get_version.call_args.kwargs
        assert call_kwargs["version_id"] == "5"
        assert call_kwargs["account_id"] == account_id
        assert call_kwargs["container_id"] == container_id

    def test_version_get_not_found(self, mock_resolve):
        """Non-existent version exits with code 1."""
        state, client, account_id, container_id = mock_resolve
        client.get_version.side_effect = ResourceNotFoundError("Version", "999")

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["version", "get", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


# ===========================================================================
# Command-level tests: version list
# ===========================================================================


class TestVersionList:
    def test_version_list_success(self, mock_resolve):
        """List returns all versions in a table/JSON."""
        state, client, account_id, container_id = mock_resolve
        client.list_versions.return_value = [
            {
                "containerVersionId": "1",
                "name": "v1",
                "numericFingerprint": "1600000000000",
                "numTags": 5,
                "numTriggers": 2,
                "numVariables": 3,
            },
            {
                "containerVersionId": "2",
                "name": "v2",
                "numericFingerprint": "1700000000000",
                "numTags": 6,
                "numTriggers": 2,
                "numVariables": 3,
            },
        ]

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["version", "list"])

        assert result.exit_code == 0, result.output
        client.list_versions.assert_called_once()
        # Both versions should appear in output
        assert "v1" in result.output
        assert "v2" in result.output

    def test_version_list_with_since_filters(self, mock_resolve):
        """--since filters out versions before the date."""
        state, client, account_id, container_id = mock_resolve
        client.list_versions.return_value = [
            {
                "containerVersionId": "1",
                "name": "old",
                "numericFingerprint": "1600000000000",
                "numTags": 5,
                "numTriggers": 2,
                "numVariables": 3,
            },
            {
                "containerVersionId": "2",
                "name": "new",
                "numericFingerprint": "1700000000000",
                "numTags": 6,
                "numTriggers": 2,
                "numVariables": 3,
            },
        ]

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            # 1600000000000 ms = 2020-09-13 UTC, 1700000000000 ms = 2023-11-14 UTC
            # --since 2023-01-01 should exclude old (2020) and include new (2023-11)
            result = runner.invoke(app, ["version", "list", "--since", "2023-01-01"])

        assert result.exit_code == 0, result.output
        assert "new" in result.output
        assert "old" not in result.output

    def test_version_list_empty(self, mock_resolve):
        """Empty list returns successfully with no data."""
        state, client, account_id, container_id = mock_resolve
        client.list_versions.return_value = []

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["version", "list"])

        assert result.exit_code == 0, result.output


# ===========================================================================
# Command-level tests: version diff
# ===========================================================================


class TestVersionDiff:
    def test_diff_shows_changes(self, mock_resolve):
        """Diff between two versions with tag changes shows output."""
        state, client, account_id, container_id = mock_resolve
        ver1 = {
            "tag": [{"tagId": "1", "name": "Tag A", "fingerprint": "100"}],
            "trigger": [],
            "variable": [],
        }
        ver2 = {
            "tag": [
                {"tagId": "1", "name": "Tag A", "fingerprint": "999"},
                {"tagId": "2", "name": "Tag B", "fingerprint": "200"},
            ],
            "trigger": [],
            "variable": [],
        }
        client.get_version.side_effect = [ver1, ver2]

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["version", "diff", "1", "2"])

        assert result.exit_code == 0, result.output
        # Should contain both the modified and added changes
        assert "modified" in result.output
        assert "added" in result.output

    def test_diff_no_changes(self, mock_resolve):
        """Identical versions show 'no differences' warning."""
        state, client, account_id, container_id = mock_resolve
        ver1 = {
            "tag": [{"tagId": "1", "name": "Tag A", "fingerprint": "100"}],
            "trigger": [],
            "variable": [],
        }
        ver2 = {
            "tag": [{"tagId": "1", "name": "Tag A", "fingerprint": "100"}],
            "trigger": [],
            "variable": [],
        }
        client.get_version.side_effect = [ver1, ver2]

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["version", "diff", "1", "2"])

        assert result.exit_code == 0, result.output
        assert "no differences" in result.output.lower()

    def test_diff_v1_not_found(self, mock_resolve):
        """First version not found -> exit code 1."""
        state, client, account_id, container_id = mock_resolve
        client.get_version.side_effect = ResourceNotFoundError("Version", "1")

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["version", "diff", "1", "2"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_diff_v2_not_found(self, mock_resolve):
        """Second version not found -> exit code 1."""
        state, client, account_id, container_id = mock_resolve
        ver1 = {"tag": [], "trigger": [], "variable": []}
        client.get_version.side_effect = [ver1, ResourceNotFoundError("Version", "2")]

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["version", "diff", "1", "2"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()
