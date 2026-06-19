"""Tests for trigger CLI commands (create, delete)."""

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


# -- create_trigger tests --


def test_create_trigger_pageview(mock_ctx):
    """Simple pageview trigger calls client.create_trigger with correct body."""
    mock_ctx.client.create_trigger.return_value = {"triggerId": "100", "name": "PV"}

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "create", "--name", "PV", "--type", "pageview"])

    assert result.exit_code == 0
    mock_ctx.client.create_trigger.assert_called_once()
    call_kwargs = mock_ctx.client.create_trigger.call_args
    trigger_body = call_kwargs.kwargs["trigger_body"]
    assert trigger_body == {"name": "PV", "type": "pageview"}


def test_create_trigger_timer_with_params(mock_ctx):
    """Timer with --param interval and limit sets top-level fields, not parameter array."""
    mock_ctx.client.create_trigger.return_value = {"triggerId": "101", "name": "T"}

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(
            app,
            [
                "trigger",
                "create",
                "--name",
                "T",
                "--type",
                "timer",
                "--param",
                "interval:5000",
                "--param",
                "limit:1",
            ],
        )

    assert result.exit_code == 0
    trigger_body = mock_ctx.client.create_trigger.call_args.kwargs["trigger_body"]

    # Top-level fields for timer
    assert trigger_body["interval"] == {"type": "template", "value": "5000"}
    assert trigger_body["limit"] == {"type": "template", "value": "1"}
    # Timer always gets eventName
    assert trigger_body["eventName"] == {"type": "template", "value": "gtm.timer"}
    # No parameter array since all params went top-level
    assert "parameter" not in trigger_body


def test_create_trigger_timer_default_event_name(mock_ctx):
    """Timer without explicit eventName gets gtm.timer default."""
    mock_ctx.client.create_trigger.return_value = {"triggerId": "102", "name": "T2"}

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "create", "--name", "T2", "--type", "timer"])

    assert result.exit_code == 0
    trigger_body = mock_ctx.client.create_trigger.call_args.kwargs["trigger_body"]
    assert trigger_body["eventName"] == {"type": "template", "value": "gtm.timer"}


def test_create_trigger_invalid_param_format(mock_ctx):
    """--param without colon exits with code 1."""
    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(
            app,
            [
                "trigger",
                "create",
                "--name",
                "Bad",
                "--type",
                "pageview",
                "--param",
                "nocolon",
            ],
        )

    assert result.exit_code == 1


def test_create_trigger_custom_event_with_params(mock_ctx):
    """customEvent with --param puts entries in the parameters array."""
    mock_ctx.client.create_trigger.return_value = {"triggerId": "103", "name": "CE"}

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(
            app,
            [
                "trigger",
                "create",
                "--name",
                "CE",
                "--type",
                "customEvent",
                "--param",
                "eventName:purchase",
            ],
        )

    assert result.exit_code == 0
    trigger_body = mock_ctx.client.create_trigger.call_args.kwargs["trigger_body"]
    assert trigger_body["parameter"] == [
        {"type": "template", "key": "eventName", "value": "purchase"},
    ]


# -- update_trigger tests --


_EXISTING_TRIGGER = {
    "triggerId": "295",
    "name": "All Pages",
    "type": "pageview",
}


def test_update_trigger_success(mock_ctx):
    """--name renames the trigger and calls client.update_trigger."""
    mock_ctx.client.list_triggers.return_value = [dict(_EXISTING_TRIGGER)]
    mock_ctx.client.update_trigger.return_value = {**_EXISTING_TRIGGER, "name": "All Pages v2"}

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "update", "295", "--name", "All Pages v2"])

    assert result.exit_code == 0, result.output
    mock_ctx.client.update_trigger.assert_called_once()
    call_kwargs = mock_ctx.client.update_trigger.call_args.kwargs
    assert call_kwargs["trigger_id"] == "295"
    assert call_kwargs["trigger_body"]["name"] == "All Pages v2"


def test_update_trigger_not_found(mock_ctx):
    """Trigger not in list exits with code 1."""
    mock_ctx.client.list_triggers.return_value = [dict(_EXISTING_TRIGGER)]

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "update", "999", "--name", "X"])

    assert result.exit_code == 1
    assert "not found" in result.output


def test_update_trigger_no_changes(mock_ctx):
    """No options specified exits with code 1."""
    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "update", "295"])

    assert result.exit_code == 1
    assert "No changes specified" in result.output


# -- delete_trigger tests --


def test_delete_trigger_success(mock_ctx):
    """Trigger found and deleted successfully."""
    mock_ctx.client.list_triggers.return_value = [
        {"triggerId": "200", "name": "Old Trigger"},
    ]

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "delete", "200"])

    assert result.exit_code == 0
    mock_ctx.client.delete_trigger.assert_called_once()
    call_kwargs = mock_ctx.client.delete_trigger.call_args.kwargs
    assert call_kwargs["trigger_id"] == "200"


def test_delete_trigger_not_found(mock_ctx):
    """Trigger not in list exits with code 1 and error message."""
    mock_ctx.client.list_triggers.return_value = [
        {"triggerId": "200", "name": "Other"},
    ]

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "delete", "999"])

    assert result.exit_code == 1
    assert "not found" in result.output
