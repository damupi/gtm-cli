"""Tests for WorkspaceContext and resolve_workspace_context."""

from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock, patch

from gtm_cli.cli.helpers import WorkspaceContext, resolve_workspace_context


def _make_state(profile="my-profile", service_account="/path/to/sa.json"):
    state = MagicMock()
    state.profile = profile
    state.service_account = service_account
    return state


class TestWorkspaceContextApiKwargs:
    def test_returns_dict_with_all_keys(self):
        ctx = WorkspaceContext(
            state=_make_state(),
            client=MagicMock(),
            account_id="a1",
            container_id="c1",
            workspace_id="ws1",
        )

        result = ctx.api_kwargs

        assert result == {
            "account_id": "a1",
            "container_id": "c1",
            "workspace_id": "ws1",
            "profile_name": "my-profile",
            "service_account_path": "/path/to/sa.json",
        }

    def test_cached_property_returns_same_object(self):
        ctx = WorkspaceContext(
            state=_make_state(),
            client=MagicMock(),
            account_id="a1",
            container_id="c1",
            workspace_id="ws1",
        )

        first = ctx.api_kwargs
        second = ctx.api_kwargs

        assert first is second


class TestWorkspaceContextFrozen:
    def test_cannot_modify_fields(self):
        ctx = WorkspaceContext(
            state=_make_state(),
            client=MagicMock(),
            account_id="a1",
            container_id="c1",
            workspace_id="ws1",
        )

        try:
            ctx.account_id = "a2"
            raise AssertionError("Expected FrozenInstanceError")
        except FrozenInstanceError:
            pass


class TestResolveWorkspaceContext:
    @patch("gtm_cli.cli.helpers.resolve_workspace_id", return_value="ws1")
    @patch("gtm_cli.cli.helpers.resolve_container_id", return_value="c1")
    @patch("gtm_cli.cli.helpers.resolve_account_id", return_value="a1")
    @patch("gtm_cli.core.client.get_client")
    @patch("gtm_cli.cli.main.get_state")
    def test_wires_state_client_and_ids(
        self,
        mock_get_state,
        mock_get_client,
        mock_resolve_account,
        mock_resolve_container,
        mock_resolve_workspace,
    ):
        fake_state = _make_state()
        fake_client = MagicMock()
        mock_get_state.return_value = fake_state
        mock_get_client.return_value = fake_client

        ctx = resolve_workspace_context()

        assert ctx.state is fake_state
        assert ctx.client is fake_client
        assert ctx.account_id == "a1"
        assert ctx.container_id == "c1"
        assert ctx.workspace_id == "ws1"

        mock_resolve_account.assert_called_once_with(fake_state, fake_client)
        mock_resolve_container.assert_called_once_with(fake_state, fake_client, "a1")
        mock_resolve_workspace.assert_called_once_with(fake_state, fake_client, "a1", "c1")


class TestWorkspacePreview:
    @patch("gtm_cli.cli.workspaces.webbrowser.open")
    @patch("gtm_cli.cli.workspaces.resolve_workspace_context")
    def test_opens_correct_preview_url(self, mock_ctx, mock_open):
        ctx = WorkspaceContext(
            state=_make_state(),
            client=MagicMock(),
            account_id="123",
            container_id="456",
            workspace_id="7",
        )
        ctx.state.authuser = None
        mock_ctx.return_value = ctx

        from gtm_cli.cli.workspaces import workspace_preview

        workspace_preview()

        expected = (
            "https://tagmanager.google.com/#/container"
            "/accounts/123/containers/456/workspaces/7/preview"
        )
        mock_open.assert_called_once_with(expected)

    @patch("gtm_cli.cli.workspaces.webbrowser.open")
    @patch("gtm_cli.cli.workspaces.resolve_workspace_context")
    def test_adds_authuser_to_url(self, mock_ctx, mock_open):
        ctx = WorkspaceContext(
            state=_make_state(),
            client=MagicMock(),
            account_id="123",
            container_id="456",
            workspace_id="7",
        )
        ctx.state.authuser = 2
        mock_ctx.return_value = ctx

        from gtm_cli.cli.workspaces import workspace_preview

        workspace_preview()

        url = mock_open.call_args[0][0]
        assert "?authuser=2#" in url
