"""Tests for trigger CLI commands (create, delete)."""

import json
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


def test_create_trigger_custom_event_requires_event_name(mock_ctx):
    """customEvent without --event-name exits with code 1 (no valid customEventFilter)."""
    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(
            app,
            ["trigger", "create", "--name", "CE", "--type", "customEvent"],
        )

    assert result.exit_code == 1
    assert "--event-name" in result.output
    mock_ctx.client.create_trigger.assert_not_called()


def test_create_trigger_custom_event_builds_filter(mock_ctx):
    """customEvent with --event-name builds a valid customEventFilter."""
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
                "--event-name",
                "purchase",
            ],
        )

    assert result.exit_code == 0
    trigger_body = mock_ctx.client.create_trigger.call_args.kwargs["trigger_body"]
    assert trigger_body["customEventFilter"] == [
        {
            "type": "equals",
            "parameter": [
                {"type": "template", "key": "arg0", "value": "{{_event}}"},
                {"type": "template", "key": "arg1", "value": "purchase"},
            ],
        }
    ]


def test_create_trigger_custom_event_with_extra_params(mock_ctx):
    """customEvent still accepts extra --param entries alongside the built filter."""
    mock_ctx.client.create_trigger.return_value = {"triggerId": "104", "name": "CE2"}

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(
            app,
            [
                "trigger",
                "create",
                "--name",
                "CE2",
                "--type",
                "customEvent",
                "--event-name",
                "purchase",
                "--param",
                "someKey:someValue",
            ],
        )

    assert result.exit_code == 0
    trigger_body = mock_ctx.client.create_trigger.call_args.kwargs["trigger_body"]
    assert trigger_body["parameter"] == [
        {"type": "template", "key": "someKey", "value": "someValue"},
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


# -- update_trigger --json-file tests --

_EXISTING_TRIGGER_FULL = {
    "triggerId": "295",
    "name": "Checkout Click",
    "type": "click",
    "filter": [
        {
            "type": "equals",
            "parameter": [
                {"type": "template", "key": "arg0", "value": "{{Page Path}}"},
                {"type": "template", "key": "arg1", "value": "/old-path"},
            ],
        }
    ],
    "customEventFilter": [
        {
            "type": "equals",
            "parameter": [
                {"type": "template", "key": "arg0", "value": "{{_event}}"},
                {"type": "template", "key": "arg1", "value": "old_event"},
            ],
        }
    ],
    "waitForTags": {"type": "boolean", "value": "true"},
}


def test_update_trigger_json_file_replaces_filter_and_custom_event_filter(mock_ctx, tmp_path):
    """--json-file replaces filter and customEventFilter arrays, preserving waitForTags."""
    mock_ctx.client.list_triggers.return_value = [dict(_EXISTING_TRIGGER_FULL)]
    mock_ctx.client.update_trigger.return_value = _EXISTING_TRIGGER_FULL

    new_filter = [
        {
            "type": "equals",
            "parameter": [
                {"type": "template", "key": "arg0", "value": "{{Page Path}}"},
                {"type": "template", "key": "arg1", "value": "/checkout"},
            ],
        }
    ]
    new_custom_event_filter = [
        {
            "type": "equals",
            "parameter": [
                {"type": "template", "key": "arg0", "value": "{{_event}}"},
                {"type": "template", "key": "arg1", "value": "new_event"},
            ],
        }
    ]

    patch_file = tmp_path / "patch.json"
    patch_file.write_text(
        json.dumps({"filter": new_filter, "customEventFilter": new_custom_event_filter})
    )

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "update", "295", "--json-file", str(patch_file)])

    assert result.exit_code == 0, result.output
    body = mock_ctx.client.update_trigger.call_args.kwargs["trigger_body"]
    assert body["filter"] == new_filter
    assert body["customEventFilter"] == new_custom_event_filter
    # Omitted field preserved
    assert body["waitForTags"] == {"type": "boolean", "value": "true"}


def test_update_trigger_json_file_changes_type(mock_ctx, tmp_path):
    """--json-file can change 'type' (e.g. click -> linkClick)."""
    mock_ctx.client.list_triggers.return_value = [dict(_EXISTING_TRIGGER_FULL)]
    mock_ctx.client.update_trigger.return_value = {**_EXISTING_TRIGGER_FULL, "type": "linkClick"}

    patch_file = tmp_path / "patch.json"
    patch_file.write_text(json.dumps({"type": "linkClick"}))

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "update", "295", "--json-file", str(patch_file)])

    assert result.exit_code == 0, result.output
    body = mock_ctx.client.update_trigger.call_args.kwargs["trigger_body"]
    assert body["type"] == "linkClick"


def test_update_trigger_json_file_then_name_applied_on_top(mock_ctx, tmp_path):
    """JSON merge applied first, then --name on top."""
    mock_ctx.client.list_triggers.return_value = [dict(_EXISTING_TRIGGER)]
    mock_ctx.client.update_trigger.return_value = _EXISTING_TRIGGER

    patch_file = tmp_path / "patch.json"
    patch_file.write_text(json.dumps({"name": "From JSON", "type": "linkClick"}))

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(
            app,
            [
                "trigger",
                "update",
                "295",
                "--json-file",
                str(patch_file),
                "--name",
                "From Flag",
            ],
        )

    assert result.exit_code == 0, result.output
    body = mock_ctx.client.update_trigger.call_args.kwargs["trigger_body"]
    assert body["name"] == "From Flag"
    assert body["type"] == "linkClick"


def test_update_trigger_json_file_invalid_json_exits_error(mock_ctx, tmp_path):
    """Malformed JSON exits non-zero with an actionable message."""
    mock_ctx.client.list_triggers.return_value = [dict(_EXISTING_TRIGGER)]

    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json")

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "update", "295", "--json-file", str(bad_file)])

    assert result.exit_code != 0
    assert "Invalid JSON" in result.output
    mock_ctx.client.update_trigger.assert_not_called()


def test_update_trigger_json_file_ignores_identity_fields_with_warning(mock_ctx, tmp_path):
    """Identity fields in the patch are stripped with a warning, not applied."""
    mock_ctx.client.list_triggers.return_value = [dict(_EXISTING_TRIGGER)]
    mock_ctx.client.update_trigger.return_value = _EXISTING_TRIGGER

    patch_file = tmp_path / "patch.json"
    patch_file.write_text(
        json.dumps(
            {
                "triggerId": "999",
                "accountId": "a999",
                "fingerprint": "12345",
                "name": "Safe Rename",
            }
        )
    )

    with patch("gtm_cli.cli.triggers.resolve_workspace_context", return_value=mock_ctx):
        result = runner.invoke(app, ["trigger", "update", "295", "--json-file", str(patch_file)])

    assert result.exit_code == 0, result.output
    assert "Ignoring identity field" in result.output
    body = mock_ctx.client.update_trigger.call_args.kwargs["trigger_body"]
    assert body["triggerId"] == "295"
    assert "accountId" not in body
    assert body["name"] == "Safe Rename"


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
