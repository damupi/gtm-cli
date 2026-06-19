"""Tests for variable CLI commands (create, update, delete, revert)."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.helpers import WorkspaceContext
from gtm_cli.cli.main import State, app
from gtm_cli.utils.output import OutputFormat

runner = CliRunner()

_PATCH_TARGET = "gtm_cli.cli.variables.resolve_workspace_context"


@pytest.fixture
def mock_ctx():
    """Build a controlled WorkspaceContext with a mock client and state."""
    state = State()
    state.profile = "test"
    state.output_format = OutputFormat.JSON
    state.yes = True  # skip confirmation prompts
    client = MagicMock()
    ctx = WorkspaceContext(
        state=state,
        client=client,
        account_id="a1",
        container_id="c1",
        workspace_id="ws1",
    )
    return ctx


# ---------------------------------------------------------------------------
# create_variable
# ---------------------------------------------------------------------------


class TestCreateVariable:
    def test_create_variable_inline_param(self, mock_ctx):
        """--param key:value is included in the variable body."""
        mock_ctx.client.create_variable.return_value = {"variableId": "10", "name": "Click ID"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "create",
                    "--name",
                    "Click ID",
                    "--type",
                    "v",
                    "--param",
                    "name:gtm.elementId",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_variable.call_args.kwargs["variable_body"]
        assert body["name"] == "Click ID"
        assert body["type"] == "v"
        params = {p["key"]: p["value"] for p in body["parameter"]}
        assert params["name"] == "gtm.elementId"

    def test_create_variable_param_file_reads_verbatim(self, mock_ctx, tmp_path):
        """--param-file reads file content exactly — no wrapping or trimming."""
        long_js = (
            "function() {\n"
            "  var bwrSize = { width: window.innerWidth || (body && body.clientWidth) || 0,"
            " height: window.innerHeight || (body && body.clientHeight) || 0 };\n"
            "  return bwrSize;\n"
            "}"
        )
        js_file = tmp_path / "script.js"
        js_file.write_text(long_js)
        mock_ctx.client.create_variable.return_value = {"variableId": "11", "name": "JS Var"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "create",
                    "--name",
                    "JS Var",
                    "--type",
                    "jsm",
                    "--param-file",
                    f"javascript:{js_file}",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_variable.call_args.kwargs["variable_body"]
        params = {p["key"]: p["value"] for p in body["parameter"]}
        assert params["javascript"] == long_js, "File content must be passed byte-for-byte"

    def test_create_variable_param_file_overrides_param(self, mock_ctx, tmp_path):
        """When both --param and --param-file set the same key, --param-file wins."""
        js_file = tmp_path / "override.js"
        js_file.write_text("function() { return 'from_file'; }")
        mock_ctx.client.create_variable.return_value = {"variableId": "12", "name": "Override"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "create",
                    "--name",
                    "Override",
                    "--type",
                    "jsm",
                    "--param",
                    "javascript:from_param",
                    "--param-file",
                    f"javascript:{js_file}",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_variable.call_args.kwargs["variable_body"]
        params = {p["key"]: p["value"] for p in body["parameter"]}
        assert params["javascript"] == "function() { return 'from_file'; }"

    def test_create_variable_param_file_missing_file(self, mock_ctx):
        """--param-file with a nonexistent path exits with code 1."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "create",
                    "--name",
                    "Bad",
                    "--type",
                    "jsm",
                    "--param-file",
                    "javascript:/nonexistent/path/script.js",
                ],
            )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_create_variable_param_file_invalid_format(self, mock_ctx):
        """--param-file entry without a colon exits with code 1."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "create",
                    "--name",
                    "Bad",
                    "--type",
                    "jsm",
                    "--param-file",
                    "nocolon",
                ],
            )

        assert result.exit_code == 1
        assert "invalid" in result.output.lower()


# ---------------------------------------------------------------------------
# update_variable
# ---------------------------------------------------------------------------


class TestUpdateVariable:
    def _existing_variable(self) -> dict:
        """Minimal variable dict returned by get_variable."""
        return {
            "variableId": "99",
            "name": "My JS Var",
            "type": "jsm",
            "parameter": [
                {"type": "template", "key": "javascript", "value": "function() { return 1; }"}
            ],
        }

    def test_update_variable_param_file_preserves_whitespace(self, mock_ctx, tmp_path):
        """--param-file passes JS content verbatim with no line-wrapping."""
        long_js = (
            "function() {\n"
            "  var bwrSize = { width: window.innerWidth || (body && body.clientWidth) || 0,"
            " height: window.innerHeight || (body && body.clientHeight) || 0 };\n"
            "  return JSON.stringify(bwrSize);\n"
            "}"
        )
        # Sanity check: the JS line is longer than 100 chars
        lines = long_js.splitlines()
        assert any(len(line) > 100 for line in lines), "Test JS must contain a long line"

        js_file = tmp_path / "myscript.js"
        js_file.write_text(long_js)

        existing = self._existing_variable()
        mock_ctx.client.get_variable.return_value = existing
        mock_ctx.client.update_variable.return_value = {**existing, "name": "My JS Var"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "update",
                    "99",
                    "--param-file",
                    f"javascript:{js_file}",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_variable.call_args.kwargs["variable_body"]
        params = {p["key"]: p["value"] for p in body["parameter"]}
        assert params["javascript"] == long_js, (
            "JS value must be passed byte-for-byte identical — no wrapping allowed"
        )

    def test_update_variable_param_file_upserts_existing_key(self, mock_ctx, tmp_path):
        """--param-file updates an existing parameter key in-place."""
        new_js = "function() { return 'updated'; }"
        js_file = tmp_path / "new.js"
        js_file.write_text(new_js)

        existing = self._existing_variable()
        mock_ctx.client.get_variable.return_value = existing
        mock_ctx.client.update_variable.return_value = existing

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["variable", "update", "99", "--param-file", f"javascript:{js_file}", "--yes"],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_variable.call_args.kwargs["variable_body"]
        # Should still be exactly one parameter entry for 'javascript'
        js_params = [p for p in body["parameter"] if p["key"] == "javascript"]
        assert len(js_params) == 1
        assert js_params[0]["value"] == new_js

    def test_update_variable_param_file_appends_new_key(self, mock_ctx, tmp_path):
        """--param-file appends a new parameter when the key does not exist yet."""
        js_file = tmp_path / "extra.js"
        js_file.write_text("function() { return 'extra'; }")

        existing = self._existing_variable()
        mock_ctx.client.get_variable.return_value = existing
        mock_ctx.client.update_variable.return_value = existing

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["variable", "update", "99", "--param-file", f"newkey:{js_file}", "--yes"],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_variable.call_args.kwargs["variable_body"]
        param_keys = [p["key"] for p in body["parameter"]]
        assert "javascript" in param_keys  # original preserved
        assert "newkey" in param_keys  # new key appended

    def test_update_variable_param_file_overrides_param_same_key(self, mock_ctx, tmp_path):
        """When both --param and --param-file set the same key, --param-file wins."""
        js_file = tmp_path / "winner.js"
        js_file.write_text("function() { return 'file_wins'; }")

        existing = self._existing_variable()
        mock_ctx.client.get_variable.return_value = existing
        mock_ctx.client.update_variable.return_value = existing

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "update",
                    "99",
                    "--param",
                    "javascript:param_value",
                    "--param-file",
                    f"javascript:{js_file}",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_variable.call_args.kwargs["variable_body"]
        params = {p["key"]: p["value"] for p in body["parameter"]}
        assert params["javascript"] == "function() { return 'file_wins'; }"

    def test_update_variable_inline_param_upserts(self, mock_ctx):
        """--param key:value upserts the parameter, preserving other params."""
        existing = self._existing_variable()
        mock_ctx.client.get_variable.return_value = existing
        mock_ctx.client.update_variable.return_value = existing

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["variable", "update", "99", "--param", "javascript:newval", "--yes"],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_variable.call_args.kwargs["variable_body"]
        params = {p["key"]: p["value"] for p in body["parameter"]}
        assert params["javascript"] == "newval"

    def test_update_variable_param_file_missing_file(self, mock_ctx):
        """--param-file with a nonexistent path exits with code 1."""
        existing = self._existing_variable()
        mock_ctx.client.get_variable.return_value = existing

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "update",
                    "99",
                    "--param-file",
                    "javascript:/nonexistent/file.js",
                    "--yes",
                ],
            )

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_update_variable_param_file_invalid_format(self, mock_ctx):
        """--param-file entry without a colon exits with code 1."""
        existing = self._existing_variable()
        mock_ctx.client.get_variable.return_value = existing

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["variable", "update", "99", "--param-file", "nocolon", "--yes"],
            )

        assert result.exit_code == 1
        assert "invalid" in result.output.lower()

    def test_update_variable_name_only(self, mock_ctx):
        """--name updates the variable name without touching parameters."""
        existing = self._existing_variable()
        updated = {**existing, "name": "Renamed"}
        mock_ctx.client.get_variable.return_value = existing
        mock_ctx.client.update_variable.return_value = updated

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["variable", "update", "99", "--name", "Renamed", "--yes"],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_variable.call_args.kwargs["variable_body"]
        assert body["name"] == "Renamed"
        # Parameters untouched
        assert body["parameter"] == existing["parameter"]
