"""Tests for template CLI commands (list, get, create, update, delete)."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.helpers import WorkspaceContext
from gtm_cli.cli.main import State, app
from gtm_cli.utils.output import OutputFormat

runner = CliRunner()

_PATCH_TARGET = "gtm_cli.cli.templates.resolve_workspace_context"


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


_EXISTING_TEMPLATE = {
    "templateId": "12",
    "name": "Attribution Cookie",
    "templateData": "const x = 1;",
}


# -- list_templates tests --


def test_list_templates(mock_ctx):
    """Lists templates with id and name."""
    mock_ctx.client.list_templates.return_value = [dict(_EXISTING_TEMPLATE)]

    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(app, ["template", "list"])

    assert result.exit_code == 0, result.output
    mock_ctx.client.list_templates.assert_called_once()


# -- get_template tests --


def test_get_template_found(mock_ctx):
    """Returns template details when found."""
    mock_ctx.client.get_template.return_value = dict(_EXISTING_TEMPLATE)

    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(app, ["template", "get", "12"])

    assert result.exit_code == 0, result.output
    mock_ctx.client.get_template.assert_called_once()
    assert mock_ctx.client.get_template.call_args.kwargs["template_id"] == "12"


def test_get_template_not_found(mock_ctx):
    """Exits with code 1 when the template is missing."""
    mock_ctx.client.get_template.return_value = {}

    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(app, ["template", "get", "999"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


# -- create_template tests --


def test_create_template_from_file(mock_ctx, tmp_path):
    """--file reads .tpl content verbatim into templateData."""
    tpl_file = tmp_path / "attribution-cookie.tpl"
    tpl_file.write_text("const x = require('injectScript');\n")
    mock_ctx.client.create_template.return_value = {"templateId": "13", "name": "Attr"}

    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(
            app,
            ["template", "create", "--name", "Attr", "--file", str(tpl_file)],
        )

    assert result.exit_code == 0, result.output
    body = mock_ctx.client.create_template.call_args.kwargs["template_body"]
    assert body["name"] == "Attr"
    assert body["templateData"] == "const x = require('injectScript');\n"


def test_create_template_missing_file_exits_error(mock_ctx):
    """A nonexistent --file path is rejected before hitting the client."""
    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(
            app,
            ["template", "create", "--name", "Attr", "--file", "/no/such/file.tpl"],
        )

    assert result.exit_code != 0
    mock_ctx.client.create_template.assert_not_called()


# -- update_template tests --


def test_update_template_name(mock_ctx):
    """--name updates the template's display name."""
    mock_ctx.client.get_template.return_value = dict(_EXISTING_TEMPLATE)
    mock_ctx.client.update_template.return_value = {
        **_EXISTING_TEMPLATE,
        "name": "Attribution Cookie v2",
    }

    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(app, ["template", "update", "12", "--name", "Attribution Cookie v2"])

    assert result.exit_code == 0, result.output
    body = mock_ctx.client.update_template.call_args.kwargs["template_body"]
    assert body["name"] == "Attribution Cookie v2"
    # Existing templateData preserved since --file wasn't passed
    assert body["templateData"] == "const x = 1;"


def test_update_template_file(mock_ctx, tmp_path):
    """--file replaces templateData with new file content."""
    tpl_file = tmp_path / "updated.tpl"
    tpl_file.write_text("const y = 2;")
    mock_ctx.client.get_template.return_value = dict(_EXISTING_TEMPLATE)
    mock_ctx.client.update_template.return_value = dict(_EXISTING_TEMPLATE)

    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(app, ["template", "update", "12", "--file", str(tpl_file)])

    assert result.exit_code == 0, result.output
    body = mock_ctx.client.update_template.call_args.kwargs["template_body"]
    assert body["templateData"] == "const y = 2;"


def test_update_template_not_found(mock_ctx):
    """Exits with code 1 when the template doesn't exist."""
    mock_ctx.client.get_template.return_value = {}

    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(app, ["template", "update", "999", "--name", "X"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()


def test_update_template_no_changes_exits_error(mock_ctx):
    """No options specified exits with code 1."""
    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(app, ["template", "update", "12"])

    assert result.exit_code == 1
    assert "No changes specified" in result.output


# -- delete_template tests --


def test_delete_template_success(mock_ctx):
    """Template found and deleted successfully."""
    mock_ctx.client.get_template.return_value = dict(_EXISTING_TEMPLATE)

    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(app, ["template", "delete", "12"])

    assert result.exit_code == 0, result.output
    mock_ctx.client.delete_template.assert_called_once()
    assert mock_ctx.client.delete_template.call_args.kwargs["template_id"] == "12"


def test_delete_template_not_found(mock_ctx):
    """Exits with code 1 when the template doesn't exist."""
    mock_ctx.client.get_template.return_value = {}

    with patch(_PATCH_TARGET, return_value=mock_ctx):
        result = runner.invoke(app, ["template", "delete", "999"])

    assert result.exit_code == 1
    assert "not found" in result.output.lower()
