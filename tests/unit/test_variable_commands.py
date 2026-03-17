"""Tests for variable create, update, and delete commands."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.helpers import WorkspaceContext
from gtm_cli.cli.main import State, app
from gtm_cli.utils.errors import ResourceNotFoundError
from gtm_cli.utils.output import OutputFormat

runner = CliRunner()
_PATCH_TARGET = "gtm_cli.cli.variables.resolve_workspace_context"

_EXISTING_VARIABLE = {
    "variableId": "55",
    "name": "DL - event",
    "type": "v",
    "accountId": "a1",
    "containerId": "c1",
    "workspaceId": "ws1",
    "fingerprint": "222",
}


@pytest.fixture
def mock_ctx():
    state = State()
    state.profile = "test"
    state.output_format = OutputFormat.JSON
    state.yes = True
    state.dry_run = False
    client = MagicMock()
    client.list_variables.return_value = [_EXISTING_VARIABLE]
    return WorkspaceContext(
        state=state, client=client, account_id="a1", container_id="c1", workspace_id="ws1"
    )


# ---------------------------------------------------------------------------
# create_variable
# ---------------------------------------------------------------------------


class TestCreateVariable:
    def test_create_variable_flags(self, mock_ctx):
        """--name and --type flags build the body and call create_variable."""
        mock_ctx.client.create_variable.return_value = {"variableId": "99", "name": "DL - click"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app, ["variable", "create", "--name", "DL - click", "--type", "v"]
            )

        assert result.exit_code == 0
        call_kwargs = mock_ctx.client.create_variable.call_args.kwargs
        assert call_kwargs["variable_body"]["name"] == "DL - click"
        assert call_kwargs["variable_body"]["type"] == "v"

    def test_create_variable_json(self, mock_ctx):
        """--json flag sends the raw JSON body."""
        mock_ctx.client.create_variable.return_value = {"variableId": "100", "name": "My Var"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["variable", "create", "--name", "x", "--type", "v",
                 "--json", '{"name":"My Var","type":"jsm"}'],
            )

        assert result.exit_code == 0
        call_kwargs = mock_ctx.client.create_variable.call_args.kwargs
        assert call_kwargs["variable_body"]["name"] == "My Var"
        assert call_kwargs["variable_body"]["type"] == "jsm"

    def test_create_variable_dry_run(self, mock_ctx):
        """--dry-run skips the API call."""
        mock_ctx.state.dry_run = True

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app, ["--dry-run", "variable", "create", "--name", "X", "--type", "v"]
            )

        assert result.exit_code == 0
        mock_ctx.client.create_variable.assert_not_called()


# ---------------------------------------------------------------------------
# update_variable
# ---------------------------------------------------------------------------


class TestUpdateVariable:
    def test_update_variable_name(self, mock_ctx):
        """--name flag renames the variable."""
        updated = {**_EXISTING_VARIABLE, "name": "DL - new"}
        mock_ctx.client.update_variable.return_value = updated

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["variable", "update", "55", "--name", "DL - new"])

        assert result.exit_code == 0
        call_kwargs = mock_ctx.client.update_variable.call_args.kwargs
        assert call_kwargs["variable_id"] == "55"
        assert call_kwargs["variable_body"]["name"] == "DL - new"

    def test_update_variable_json(self, mock_ctx):
        """--json merges into the existing variable body."""
        updated = {**_EXISTING_VARIABLE, "name": "JSON Var", "type": "k"}
        mock_ctx.client.update_variable.return_value = updated

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["variable", "update", "55", "--json", '{"name":"JSON Var","type":"k"}'],
            )

        assert result.exit_code == 0
        call_kwargs = mock_ctx.client.update_variable.call_args.kwargs
        assert call_kwargs["variable_body"]["name"] == "JSON Var"

    def test_update_variable_no_changes(self, mock_ctx):
        """No API call when nothing changes."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app, ["variable", "update", "55", "--name", "DL - event"]
            )

        assert result.exit_code == 0
        mock_ctx.client.update_variable.assert_not_called()

    def test_update_variable_dry_run(self, mock_ctx):
        """--dry-run skips the API call."""
        mock_ctx.state.dry_run = True

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app, ["--dry-run", "variable", "update", "55", "--name", "X"]
            )

        assert result.exit_code == 0
        mock_ctx.client.update_variable.assert_not_called()

    def test_update_variable_not_found(self, mock_ctx):
        """Exit code 1 when variable ID doesn't exist."""
        mock_ctx.client.list_variables.return_value = []

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["variable", "update", "999", "--name", "X"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# delete_variable
# ---------------------------------------------------------------------------


class TestDeleteVariable:
    def test_delete_variable_yes_flag(self, mock_ctx):
        """--yes skips confirmation and calls delete."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["--yes", "variable", "delete", "55"])

        assert result.exit_code == 0
        mock_ctx.client.delete_variable.assert_called_once_with(
            variable_id="55",
            account_id="a1",
            container_id="c1",
            workspace_id="ws1",
            profile_name="test",
            service_account_path=None,
        )

    def test_delete_variable_dry_run(self, mock_ctx):
        """--dry-run skips the API call."""
        mock_ctx.state.dry_run = True

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["--dry-run", "variable", "delete", "55"])

        assert result.exit_code == 0
        mock_ctx.client.delete_variable.assert_not_called()

    def test_delete_variable_not_found(self, mock_ctx):
        """Exit code 1 when variable not found in list."""
        mock_ctx.client.list_variables.return_value = []

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["variable", "delete", "999"])

        assert result.exit_code == 1
        mock_ctx.client.delete_variable.assert_not_called()

    def test_delete_variable_api_not_found(self, mock_ctx):
        """Exit code 1 when API raises ResourceNotFoundError."""
        mock_ctx.client.delete_variable.side_effect = ResourceNotFoundError("variable", "delete")

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["--yes", "variable", "delete", "55"])

        assert result.exit_code == 1
