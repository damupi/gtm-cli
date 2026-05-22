"""Tests for workspace create and delete CLI commands."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.main import State, app
from gtm_cli.utils.errors import ResourceNotFoundError
from gtm_cli.utils.output import OutputFormat

runner = CliRunner()

_PATCH_CLIENT = "gtm_cli.cli.workspaces.get_client"
_PATCH_STATE = "gtm_cli.cli.workspaces.get_state"
_PATCH_RESOLVE_ACCOUNT = "gtm_cli.cli.workspaces.resolve_account_id"
_PATCH_RESOLVE_CONTAINER = "gtm_cli.cli.workspaces.resolve_container_id"


@pytest.fixture
def mock_state():
    """Build a minimal State with sensible test defaults."""
    state = State()
    state.profile = "test"
    state.output_format = OutputFormat.JSON
    state.yes = False
    state.account_id = "a1"
    state.container_id = "c1"
    state.service_account = None
    return state


@pytest.fixture
def mock_client():
    """Return a MagicMock wired up like GTMClient."""
    return MagicMock()


# ---------------------------------------------------------------------------
# GTMClient unit tests — create_workspace / delete_workspace
# ---------------------------------------------------------------------------


class TestClientCreateWorkspace:
    def test_create_workspace_happy_path(self):
        """create_workspace calls the API with name and description."""
        from gtm_cli.core.client import GTMClient

        client = GTMClient.__new__(GTMClient)
        mock_service = MagicMock()
        mock_service.accounts().containers().workspaces().create().execute.return_value = {
            "workspaceId": "9",
            "name": "cli-test",
            "description": "temp",
        }
        client._service = mock_service
        client._credentials = object()

        with patch.object(client, "_get_service", return_value=mock_service):
            result = client.create_workspace(
                account_id="123",
                container_id="456",
                name="cli-test",
                description="temp",
            )

        assert result["workspaceId"] == "9"
        assert result["name"] == "cli-test"

        call_kwargs = mock_service.accounts().containers().workspaces().create.call_args.kwargs
        assert call_kwargs["parent"] == "accounts/123/containers/456"
        assert call_kwargs["body"] == {"name": "cli-test", "description": "temp"}

    def test_create_workspace_without_description(self):
        """create_workspace omits description key when not provided."""
        from gtm_cli.core.client import GTMClient

        client = GTMClient.__new__(GTMClient)
        mock_service = MagicMock()
        mock_service.accounts().containers().workspaces().create().execute.return_value = {
            "workspaceId": "10",
            "name": "no-desc",
        }

        with patch.object(client, "_get_service", return_value=mock_service):
            client.create_workspace(
                account_id="123",
                container_id="456",
                name="no-desc",
            )

        call_kwargs = mock_service.accounts().containers().workspaces().create.call_args.kwargs
        assert call_kwargs["body"] == {"name": "no-desc"}
        assert "description" not in call_kwargs["body"]


class TestClientDeleteWorkspace:
    def test_delete_workspace_happy_path(self):
        """delete_workspace calls the API with the correct path."""
        from gtm_cli.core.client import GTMClient

        client = GTMClient.__new__(GTMClient)
        mock_service = MagicMock()
        mock_service.accounts().containers().workspaces().delete().execute.return_value = None

        with patch.object(client, "_get_service", return_value=mock_service):
            result = client.delete_workspace(
                account_id="123",
                container_id="456",
                workspace_id="789",
            )

        assert result is None

        call_kwargs = mock_service.accounts().containers().workspaces().delete.call_args.kwargs
        assert call_kwargs["path"] == "accounts/123/containers/456/workspaces/789"


# ---------------------------------------------------------------------------
# CLI command tests — workspace create
# ---------------------------------------------------------------------------


class TestCLIWorkspaceCreate:
    def test_create_happy_path(self, mock_state, mock_client):
        """create command calls client.create_workspace and prints success."""
        mock_client.create_workspace.return_value = {
            "workspaceId": "55",
            "name": "cli-test-DELETEME",
        }

        with (
            patch(_PATCH_STATE, return_value=mock_state),
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_RESOLVE_ACCOUNT, return_value="a1"),
            patch(_PATCH_RESOLVE_CONTAINER, return_value="c1"),
        ):
            result = runner.invoke(app, ["workspace", "create", "--name", "cli-test-DELETEME"])

        assert result.exit_code == 0, result.output
        mock_client.create_workspace.assert_called_once_with(
            account_id="a1",
            container_id="c1",
            name="cli-test-DELETEME",
            description=None,
            profile_name="test",
            service_account_path=None,
        )
        assert "55" in result.output

    def test_create_with_description(self, mock_state, mock_client):
        """--description is forwarded to the client."""
        mock_client.create_workspace.return_value = {
            "workspaceId": "56",
            "name": "w",
            "description": "some desc",
        }

        with (
            patch(_PATCH_STATE, return_value=mock_state),
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_RESOLVE_ACCOUNT, return_value="a1"),
            patch(_PATCH_RESOLVE_CONTAINER, return_value="c1"),
        ):
            result = runner.invoke(
                app,
                ["workspace", "create", "--name", "w", "--description", "some desc"],
            )

        assert result.exit_code == 0, result.output
        call_kwargs = mock_client.create_workspace.call_args.kwargs
        assert call_kwargs["description"] == "some desc"


# ---------------------------------------------------------------------------
# CLI command tests — workspace delete
# ---------------------------------------------------------------------------


class TestCLIWorkspaceDelete:
    def test_delete_with_yes_flag(self, mock_state, mock_client):
        """--yes skips confirmation and calls client.delete_workspace."""
        mock_state.yes = True
        mock_client.get_workspace.return_value = {
            "workspaceId": "99",
            "name": "Doomed Workspace",
        }

        with (
            patch(_PATCH_STATE, return_value=mock_state),
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_RESOLVE_ACCOUNT, return_value="a1"),
            patch(_PATCH_RESOLVE_CONTAINER, return_value="c1"),
        ):
            result = runner.invoke(
                app,
                ["workspace", "delete", "--workspace-id", "99", "--yes"],
            )

        assert result.exit_code == 0, result.output
        mock_client.delete_workspace.assert_called_once_with(
            account_id="a1",
            container_id="c1",
            workspace_id="99",
            profile_name="test",
            service_account_path=None,
        )
        assert "99" in result.output

    def test_delete_aborts_on_no_confirmation(self, mock_state, mock_client):
        """Answering 'n' at the confirmation prompt exits cleanly without deleting."""
        mock_state.yes = False
        mock_client.get_workspace.return_value = {
            "workspaceId": "99",
            "name": "Doomed Workspace",
        }

        with (
            patch(_PATCH_STATE, return_value=mock_state),
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_RESOLVE_ACCOUNT, return_value="a1"),
            patch(_PATCH_RESOLVE_CONTAINER, return_value="c1"),
        ):
            # CliRunner passes 'n\n' as stdin input
            result = runner.invoke(
                app,
                ["workspace", "delete", "--workspace-id", "99"],
                input="n\n",
            )

        assert result.exit_code == 0, result.output
        mock_client.delete_workspace.assert_not_called()

    def test_delete_workspace_not_found(self, mock_state, mock_client):
        """delete exits with code 1 when API raises ResourceNotFoundError."""
        mock_state.yes = True
        mock_client.get_workspace.return_value = {
            "workspaceId": "999",
            "name": "Ghost",
        }
        mock_client.delete_workspace.side_effect = ResourceNotFoundError(
            "Workspace", "delete workspace 999"
        )

        with (
            patch(_PATCH_STATE, return_value=mock_state),
            patch(_PATCH_CLIENT, return_value=mock_client),
            patch(_PATCH_RESOLVE_ACCOUNT, return_value="a1"),
            patch(_PATCH_RESOLVE_CONTAINER, return_value="c1"),
        ):
            result = runner.invoke(
                app,
                ["workspace", "delete", "--workspace-id", "999", "--yes"],
            )

        assert result.exit_code == 1
        mock_client.delete_workspace.assert_called_once()
