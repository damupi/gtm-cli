"""Tests for environment CLI commands (list, get, create, delete)."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.main import State, app
from gtm_cli.utils.errors import ResourceNotFoundError
from gtm_cli.utils.output import OutputFormat

runner = CliRunner()

_PATCH_TARGET = "gtm_cli.cli.environments._resolve_container_context"


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


_EXISTING_ENV = {
    "accountId": "a1",
    "containerId": "c1",
    "environmentId": "5",
    "type": "user",
    "name": "Playwright QA",
    "description": "QA env for e2e tests",
    "enableDebug": True,
    "url": "https://example.com",
    "containerVersionId": "3",
    "authorizationCode": "super-secret-code",
    "fingerprint": "12345",
}


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


class TestEnvironmentList:
    def test_list_basic(self, mock_resolve):
        """List environments with projected columns."""
        state, client, account_id, container_id = mock_resolve
        client.list_environments.return_value = [dict(_EXISTING_ENV)]

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "list"])

        assert result.exit_code == 0, result.output
        client.list_environments.assert_called_once()
        call_kwargs = client.list_environments.call_args.kwargs
        assert call_kwargs["account_id"] == account_id
        assert call_kwargs["container_id"] == container_id
        assert "Playwright QA" in result.output

    def test_list_empty(self, mock_resolve):
        """Empty list exits successfully."""
        state, client, account_id, container_id = mock_resolve
        client.list_environments.return_value = []

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "list"])

        assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


class TestEnvironmentGet:
    def test_get_help_warns_auth_code_is_credential(self):
        """--help alone must explain authorizationCode is credential-bearing,
        per this repo's self-documenting-CLI design principle — no external
        doc should be required to know not to leak it."""
        result = runner.invoke(app, ["environment", "get", "--help"])

        assert result.exit_code == 0, result.output
        assert "credential" in result.output.lower()

    def test_get_found(self, mock_resolve):
        """Returns full environment details when found."""
        state, client, account_id, container_id = mock_resolve
        client.get_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "get", "5"])

        assert result.exit_code == 0, result.output
        call_kwargs = client.get_environment.call_args.kwargs
        assert call_kwargs["environment_id"] == "5"

    def test_get_not_found(self, mock_resolve):
        """Non-existent environment exits with code 1."""
        state, client, account_id, container_id = mock_resolve
        client.get_environment.side_effect = ResourceNotFoundError("Environment", "999")

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "get", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_get_table_format_redacts_auth_code(self, mock_resolve):
        """Table/plain output must not leak authorizationCode."""
        state, client, account_id, container_id = mock_resolve
        state.output_format = OutputFormat.TABLE
        client.get_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "get", "5"])

        assert result.exit_code == 0, result.output
        assert "super-secret-code" not in result.output
        assert "redacted" in result.output.lower()

    def test_get_json_format_includes_auth_code(self, mock_resolve):
        """JSON output preserves the real authorizationCode for automation."""
        state, client, account_id, container_id = mock_resolve
        state.output_format = OutputFormat.JSON
        client.get_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "get", "5"])

        assert result.exit_code == 0, result.output
        assert "super-secret-code" in result.output

    def test_get_yaml_format_includes_auth_code(self, mock_resolve):
        """YAML output preserves the real authorizationCode for automation."""
        state, client, account_id, container_id = mock_resolve
        state.output_format = OutputFormat.YAML
        client.get_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "get", "5"])

        assert result.exit_code == 0, result.output
        assert "super-secret-code" in result.output


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestEnvironmentCreate:
    def test_create_help_warns_auth_code_is_credential(self):
        """--help alone must explain authorizationCode is credential-bearing."""
        result = runner.invoke(app, ["environment", "create", "--help"])

        assert result.exit_code == 0, result.output
        assert "credential" in result.output.lower()

    def test_create_with_container_version_id(self, mock_resolve):
        """--container-version-id sets containerVersionId and type=user."""
        state, client, account_id, container_id = mock_resolve
        client.create_environment.return_value = {**_EXISTING_ENV, "environmentId": "6"}

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(
                app,
                [
                    "environment",
                    "create",
                    "--name",
                    "Playwright QA",
                    "--description",
                    "QA env",
                    "--url",
                    "https://example.com",
                    "--container-version-id",
                    "3",
                    "--enable-debug",
                ],
            )

        assert result.exit_code == 0, result.output
        body = client.create_environment.call_args.kwargs["environment_body"]
        assert body["type"] == "user"
        assert body["name"] == "Playwright QA"
        assert body["description"] == "QA env"
        assert body["url"] == "https://example.com"
        assert body["containerVersionId"] == "3"
        assert body["enableDebug"] is True
        assert "workspaceId" not in body

    def test_create_with_workspace_id(self, mock_resolve):
        """--workspace-id sets workspaceId and type=user."""
        state, client, account_id, container_id = mock_resolve
        client.create_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(
                app,
                [
                    "environment",
                    "create",
                    "--name",
                    "Dev sandbox",
                    "--workspace-id",
                    "9",
                ],
            )

        assert result.exit_code == 0, result.output
        body = client.create_environment.call_args.kwargs["environment_body"]
        assert body["type"] == "user"
        assert body["workspaceId"] == "9"
        assert "containerVersionId" not in body

    def test_create_both_flags_errors(self, mock_resolve):
        """Both --container-version-id and --workspace-id -> error, client not called."""
        state, client, account_id, container_id = mock_resolve

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(
                app,
                [
                    "environment",
                    "create",
                    "--name",
                    "X",
                    "--container-version-id",
                    "3",
                    "--workspace-id",
                    "9",
                ],
            )

        assert result.exit_code == 1
        client.create_environment.assert_not_called()

    def test_create_neither_flag_errors(self, mock_resolve):
        """Neither --container-version-id nor --workspace-id -> error, client not called."""
        state, client, account_id, container_id = mock_resolve

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "create", "--name", "X"])

        assert result.exit_code == 1
        client.create_environment.assert_not_called()

    def test_create_dry_run_does_not_call_client(self, mock_resolve):
        """--dry-run reports the action but never calls create_environment."""
        state, client, account_id, container_id = mock_resolve
        state.dry_run = True

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(
                app,
                [
                    "environment",
                    "create",
                    "--name",
                    "Playwright QA",
                    "--container-version-id",
                    "3",
                ],
            )

        assert result.exit_code == 0, result.output
        assert "dry run" in result.output.lower()
        client.create_environment.assert_not_called()

    def test_create_table_format_redacts_auth_code(self, mock_resolve):
        """Table/plain output of the freshly created environment must not leak
        authorizationCode — same rule as `environment get`."""
        state, client, account_id, container_id = mock_resolve
        state.output_format = OutputFormat.TABLE
        client.create_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(
                app,
                ["environment", "create", "--name", "Playwright QA", "--container-version-id", "3"],
            )

        assert result.exit_code == 0, result.output
        assert "super-secret-code" not in result.output
        assert "redacted" in result.output.lower()

    def test_create_json_format_includes_auth_code(self, mock_resolve):
        """JSON output of the freshly created environment preserves authorizationCode."""
        state, client, account_id, container_id = mock_resolve
        state.output_format = OutputFormat.JSON
        client.create_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(
                app,
                ["environment", "create", "--name", "Playwright QA", "--container-version-id", "3"],
            )

        assert result.exit_code == 0, result.output
        assert "super-secret-code" in result.output


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestEnvironmentDelete:
    def test_delete_success(self, mock_resolve):
        """A 'user' type environment can be deleted."""
        state, client, account_id, container_id = mock_resolve
        client.get_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "delete", "5"])

        assert result.exit_code == 0, result.output
        client.delete_environment.assert_called_once()
        assert client.delete_environment.call_args.kwargs["environment_id"] == "5"

    def test_delete_not_found(self, mock_resolve):
        """Non-existent environment exits with code 1."""
        state, client, account_id, container_id = mock_resolve
        client.get_environment.side_effect = ResourceNotFoundError("Environment", "999")

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "delete", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()
        client.delete_environment.assert_not_called()

    @pytest.mark.parametrize("env_type", ["live", "latest", "workspace"])
    def test_delete_refuses_non_user_type(self, mock_resolve, env_type):
        """Refuses to delete live/latest/workspace-linked environments."""
        state, client, account_id, container_id = mock_resolve
        client.get_environment.return_value = {**_EXISTING_ENV, "type": env_type}

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "delete", "5"])

        assert result.exit_code == 1
        client.delete_environment.assert_not_called()

    def test_delete_skips_confirmation_with_yes_flag(self, mock_resolve):
        """--yes skips the confirmation prompt."""
        state, client, account_id, container_id = mock_resolve
        state.yes = False
        client.get_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "delete", "5", "--yes"])

        assert result.exit_code == 0, result.output
        client.delete_environment.assert_called_once()

    def test_delete_skips_confirmation_with_state_yes(self, mock_resolve):
        """state.yes (global --yes) skips the confirmation prompt too."""
        state, client, account_id, container_id = mock_resolve
        state.yes = True
        client.get_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "delete", "5"])

        assert result.exit_code == 0, result.output
        client.delete_environment.assert_called_once()

    def test_delete_aborts_without_confirmation(self, mock_resolve):
        """User declining the confirmation prompt aborts without calling delete."""
        state, client, account_id, container_id = mock_resolve
        state.yes = False
        client.get_environment.return_value = dict(_EXISTING_ENV)

        with (
            patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)),
            patch("gtm_cli.cli.environments.confirm", return_value=False),
        ):
            result = runner.invoke(app, ["environment", "delete", "5"])

        assert result.exit_code == 0
        client.delete_environment.assert_not_called()

    def test_delete_dry_run_does_not_call_client(self, mock_resolve):
        """--dry-run reports the action but never calls delete_environment."""
        state, client, account_id, container_id = mock_resolve
        state.dry_run = True
        client.get_environment.return_value = dict(_EXISTING_ENV)

        with patch(_PATCH_TARGET, return_value=(state, client, account_id, container_id)):
            result = runner.invoke(app, ["environment", "delete", "5"])

        assert result.exit_code == 0, result.output
        assert "dry run" in result.output.lower()
        client.delete_environment.assert_not_called()
