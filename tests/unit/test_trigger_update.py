"""Tests for trigger update command."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.helpers import WorkspaceContext
from gtm_cli.cli.main import State, app
from gtm_cli.utils.output import OutputFormat

runner = CliRunner()
_PATCH_TARGET = "gtm_cli.cli.triggers.resolve_workspace_context"

_EXISTING_TRIGGER = {
    "triggerId": "99",
    "name": "Old Name",
    "type": "pageview",
    "accountId": "a1",
    "containerId": "c1",
    "workspaceId": "ws1",
    "fingerprint": "111",
}


@pytest.fixture
def mock_ctx():
    state = State()
    state.profile = "test"
    state.output_format = OutputFormat.JSON
    state.yes = True
    state.dry_run = False
    client = MagicMock()
    client.list_triggers.return_value = [_EXISTING_TRIGGER]
    return WorkspaceContext(
        state=state, client=client, account_id="a1", container_id="c1", workspace_id="ws1"
    )


class TestUpdateTrigger:
    def test_update_trigger_name(self, mock_ctx):
        """--name flag renames the trigger."""
        updated = {**_EXISTING_TRIGGER, "name": "New Name"}
        mock_ctx.client.update_trigger.return_value = updated

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["trigger", "update", "99", "--name", "New Name"])

        assert result.exit_code == 0
        mock_ctx.client.update_trigger.assert_called_once()
        call_kwargs = mock_ctx.client.update_trigger.call_args.kwargs
        assert call_kwargs["trigger_id"] == "99"
        assert call_kwargs["trigger_body"]["name"] == "New Name"

    def test_update_trigger_json_body(self, mock_ctx):
        """--json flag replaces fields from inline JSON."""
        updated = {**_EXISTING_TRIGGER, "name": "JSON Name", "type": "customEvent"}
        mock_ctx.client.update_trigger.return_value = updated

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["trigger", "update", "99", "--json", '{"name":"JSON Name","type":"customEvent"}'],
            )

        assert result.exit_code == 0
        call_kwargs = mock_ctx.client.update_trigger.call_args.kwargs
        assert call_kwargs["trigger_body"]["name"] == "JSON Name"
        assert call_kwargs["trigger_body"]["type"] == "customEvent"

    def test_update_trigger_no_changes(self, mock_ctx):
        """No API call made when nothing changes."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app, ["trigger", "update", "99", "--name", "Old Name"]
            )

        assert result.exit_code == 0
        mock_ctx.client.update_trigger.assert_not_called()

    def test_update_trigger_dry_run(self, mock_ctx):
        """--dry-run skips the API call."""
        mock_ctx.state.dry_run = True

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["--dry-run", "trigger", "update", "99", "--name", "X"])

        assert result.exit_code == 0
        mock_ctx.client.update_trigger.assert_not_called()

    def test_update_trigger_not_found(self, mock_ctx):
        """Exit code 1 when trigger ID doesn't exist."""
        mock_ctx.client.list_triggers.return_value = []

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["trigger", "update", "999", "--name", "X"])

        assert result.exit_code == 1
