"""Tests for built-in variable CLI commands (list, enable, disable)."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.helpers import WorkspaceContext
from gtm_cli.cli.main import State, app
from gtm_cli.utils.output import OutputFormat

runner = CliRunner()


@pytest.fixture
def mock_ctx():
    state = State()
    state.profile = "test"
    state.output_format = OutputFormat.JSON
    state.yes = True
    client = MagicMock()
    ctx = WorkspaceContext(
        state=state,
        client=client,
        account_id="a1",
        container_id="c1",
        workspace_id="ws1",
    )
    return ctx


# -- list --


def test_list_built_in_variables(mock_ctx):
    """list calls client.list_built_in_variables and outputs name/type."""
    mock_ctx.client.list_built_in_variables.return_value = [
        {"type": "pageUrl", "name": "Page URL"},
        {"type": "analyticsSessionId", "name": "GA4 Session ID"},
    ]

    with patch("gtm_cli.cli.built_in_variables.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["built-in-variable", "list"])

    assert result.exit_code == 0, result.output
    mock_ctx.client.list_built_in_variables.assert_called_once()
    assert "pageUrl" in result.output
    assert "analyticsSessionId" in result.output


# -- enable --


def test_enable_built_in_variables_single_type(mock_ctx):
    """enable with a single type and --yes (state.yes=True) calls client.enable_built_in_variables."""
    mock_ctx.client.enable_built_in_variables.return_value = [
        {"type": "analyticsSessionId", "name": "GA4 Session ID"},
    ]

    with patch("gtm_cli.cli.built_in_variables.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["built-in-variable", "enable", "analyticsSessionId"])

    assert result.exit_code == 0, result.output
    mock_ctx.client.enable_built_in_variables.assert_called_once()
    call_kwargs = mock_ctx.client.enable_built_in_variables.call_args.kwargs
    assert call_kwargs["types"] == ["analyticsSessionId"]


def test_enable_built_in_variables_multiple_types(mock_ctx):
    """enable accepts multiple types in one call."""
    mock_ctx.client.enable_built_in_variables.return_value = [
        {"type": "analyticsSessionId", "name": "GA4 Session ID"},
        {"type": "analyticsSessionNumber", "name": "GA4 Session Number"},
        {"type": "analyticsClientId", "name": "GA4 Client ID"},
    ]

    with patch("gtm_cli.cli.built_in_variables.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(
            app,
            [
                "built-in-variable",
                "enable",
                "analyticsSessionId",
                "analyticsSessionNumber",
                "analyticsClientId",
            ],
        )

    assert result.exit_code == 0, result.output
    call_kwargs = mock_ctx.client.enable_built_in_variables.call_args.kwargs
    assert call_kwargs["types"] == [
        "analyticsSessionId",
        "analyticsSessionNumber",
        "analyticsClientId",
    ]


def test_enable_built_in_variables_requires_confirmation(mock_ctx):
    """Without --yes and state.yes False, prompts for confirmation; declining aborts."""
    mock_ctx.state.yes = False

    with (
        patch("gtm_cli.cli.built_in_variables.resolve_workspace_context", return_value=mock_ctx),
        patch("gtm_cli.cli.built_in_variables.confirm", return_value=False),
    ):
        result = runner.invoke(app, ["built-in-variable", "enable", "clickUrl"])

    assert result.exit_code == 0
    mock_ctx.client.enable_built_in_variables.assert_not_called()


def test_enable_built_in_variables_confirmed_via_prompt(mock_ctx):
    """Confirming the prompt proceeds with the enable call."""
    mock_ctx.state.yes = False
    mock_ctx.client.enable_built_in_variables.return_value = [
        {"type": "clickUrl", "name": "Click URL"}
    ]

    with (
        patch("gtm_cli.cli.built_in_variables.resolve_workspace_context", return_value=mock_ctx),
        patch("gtm_cli.cli.built_in_variables.confirm", return_value=True),
    ):
        result = runner.invoke(app, ["built-in-variable", "enable", "clickUrl"])

    assert result.exit_code == 0, result.output
    mock_ctx.client.enable_built_in_variables.assert_called_once()


def test_enable_built_in_variables_yes_flag_skips_prompt(mock_ctx):
    """--yes on the command skips the confirmation prompt even if state.yes is False."""
    mock_ctx.state.yes = False
    mock_ctx.client.enable_built_in_variables.return_value = [
        {"type": "clickUrl", "name": "Click URL"}
    ]

    with patch("gtm_cli.cli.built_in_variables.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["built-in-variable", "enable", "clickUrl", "--yes"])

    assert result.exit_code == 0, result.output
    mock_ctx.client.enable_built_in_variables.assert_called_once()


# -- disable --


def test_disable_built_in_variables_single_type(mock_ctx):
    """disable calls client.disable_built_in_variables with the given type."""
    with patch("gtm_cli.cli.built_in_variables.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["built-in-variable", "disable", "analyticsSessionId"])

    assert result.exit_code == 0, result.output
    mock_ctx.client.disable_built_in_variables.assert_called_once()
    call_kwargs = mock_ctx.client.disable_built_in_variables.call_args.kwargs
    assert call_kwargs["types"] == ["analyticsSessionId"]


def test_disable_built_in_variables_multiple_types(mock_ctx):
    """disable accepts multiple types in one call."""
    with patch("gtm_cli.cli.built_in_variables.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["built-in-variable", "disable", "clickUrl", "clickText"])

    assert result.exit_code == 0, result.output
    call_kwargs = mock_ctx.client.disable_built_in_variables.call_args.kwargs
    assert call_kwargs["types"] == ["clickUrl", "clickText"]


def test_disable_built_in_variables_requires_confirmation(mock_ctx):
    """Without --yes and state.yes False, declining the prompt aborts."""
    mock_ctx.state.yes = False

    with (
        patch("gtm_cli.cli.built_in_variables.resolve_workspace_context", return_value=mock_ctx),
        patch("gtm_cli.cli.built_in_variables.confirm", return_value=False),
    ):
        result = runner.invoke(app, ["built-in-variable", "disable", "clickUrl"])

    assert result.exit_code == 0
    mock_ctx.client.disable_built_in_variables.assert_not_called()
