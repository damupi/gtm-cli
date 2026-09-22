"""Tests for variable CLI commands (create, update, delete, revert)."""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.helpers import WorkspaceContext
from gtm_cli.cli.main import State, app
from gtm_cli.utils.errors import ResourceNotFoundError
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
# get_variable
# ---------------------------------------------------------------------------


class TestGetVariable:
    def test_get_variable_not_found(self, mock_ctx):
        """A nonexistent/deleted variable ID exits cleanly with an actionable message.

        Regression test: previously ResourceNotFoundError propagated uncaught and
        printed a raw Python traceback instead of a clean CLI error.
        """
        mock_ctx.client.get_variable.side_effect = ResourceNotFoundError(
            "Variable", "get variable 999"
        )

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["variable", "get", "999"])

        assert result.exit_code == 1
        assert "Variable '999' not found" in result.output
        assert "Traceback" not in result.output


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

    def test_create_variable_json_file_merges_before_flags(self, mock_ctx, tmp_path):
        """--json-file merges onto the freshly built body (name/type), --notes applied on top."""
        mock_ctx.client.create_variable.return_value = {"variableId": "13", "name": "Lookup"}

        patch_file = tmp_path / "patch.json"
        patch_file.write_text(
            json.dumps(
                {
                    "parameter": [
                        {
                            "type": "list",
                            "key": "map",
                            "list": [
                                {
                                    "type": "map",
                                    "map": [
                                        {
                                            "type": "template",
                                            "key": "key",
                                            "value": "somehost\\.com",
                                        },
                                        {
                                            "type": "template",
                                            "key": "value",
                                            "value": "G-XXXXXXX",
                                        },
                                    ],
                                }
                            ],
                        }
                    ]
                }
            )
        )

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "create",
                    "--name",
                    "Lookup",
                    "--type",
                    "smm",
                    "--json-file",
                    str(patch_file),
                    "--notes",
                    "Added by WEBDATA-123",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_variable.call_args.kwargs["variable_body"]
        assert body["name"] == "Lookup"
        assert body["type"] == "smm"
        assert body["notes"] == "Added by WEBDATA-123"
        # JSON-seeded nested list/map parameter is preserved since --notes doesn't
        # touch the parameter array.
        assert body["parameter"] == [
            {
                "type": "list",
                "key": "map",
                "list": [
                    {
                        "type": "map",
                        "map": [
                            {"type": "template", "key": "key", "value": "somehost\\.com"},
                            {"type": "template", "key": "value", "value": "G-XXXXXXX"},
                        ],
                    }
                ],
            }
        ]

    def test_create_variable_json_file_invalid_json_exits_error(self, mock_ctx, tmp_path):
        """Malformed JSON in --json-file exits non-zero with an actionable message."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json")

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "create",
                    "--name",
                    "Bad",
                    "--type",
                    "smm",
                    "--json-file",
                    str(bad_file),
                ],
            )

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output
        mock_ctx.client.create_variable.assert_not_called()


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

    def test_update_variable_dry_run_does_not_call_client(self, mock_ctx):
        """--dry-run prints a DRY RUN message and skips the actual update_variable call."""
        mock_ctx.state.dry_run = True
        existing = {"variableId": "99", "name": "My Var", "type": "c", "parameter": []}
        mock_ctx.client.get_variable.return_value = existing

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["variable", "update", "99", "--name", "New Name"])

        assert result.exit_code == 0, result.output
        assert "dry run" in result.output.lower()
        mock_ctx.client.update_variable.assert_not_called()

    def test_update_variable_json_file_replaces_nested_parameter_preserves_omitted(
        self, mock_ctx, tmp_path
    ):
        """--json-file replaces the parameter array wholesale and preserves omitted fields."""
        existing = {
            **self._existing_variable(),
            "notes": "existing notes",
        }
        mock_ctx.client.get_variable.return_value = dict(existing)
        mock_ctx.client.update_variable.return_value = existing

        patch_file = tmp_path / "patch.json"
        patch_file.write_text(
            json.dumps(
                {
                    "parameter": [
                        {
                            "type": "list",
                            "key": "map",
                            "list": [
                                {
                                    "type": "map",
                                    "map": [
                                        {
                                            "type": "template",
                                            "key": "key",
                                            "value": "somehost\\.com",
                                        },
                                        {
                                            "type": "template",
                                            "key": "value",
                                            "value": "G-XXXXXXX",
                                        },
                                    ],
                                }
                            ],
                        }
                    ]
                }
            )
        )

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["variable", "update", "99", "--json-file", str(patch_file), "--yes"],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_variable.call_args.kwargs["variable_body"]
        # New parameter array fully replaces the old one
        assert body["parameter"] == [
            {
                "type": "list",
                "key": "map",
                "list": [
                    {
                        "type": "map",
                        "map": [
                            {"type": "template", "key": "key", "value": "somehost\\.com"},
                            {"type": "template", "key": "value", "value": "G-XXXXXXX"},
                        ],
                    }
                ],
            }
        ]
        # Omitted fields preserved
        assert body["notes"] == "existing notes"

    def test_update_variable_json_file_then_flags_applied_on_top(self, mock_ctx, tmp_path):
        """--json-file merge is applied first, then --name flag on top."""
        existing = self._existing_variable()
        mock_ctx.client.get_variable.return_value = dict(existing)
        mock_ctx.client.update_variable.return_value = existing

        patch_file = tmp_path / "patch.json"
        patch_file.write_text(json.dumps({"name": "From JSON", "notes": "from json"}))

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "variable",
                    "update",
                    "99",
                    "--json-file",
                    str(patch_file),
                    "--name",
                    "From Flag",
                    "--yes",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_variable.call_args.kwargs["variable_body"]
        assert body["name"] == "From Flag"
        assert body["notes"] == "from json"

    def test_update_variable_json_file_invalid_json_exits_error(self, mock_ctx, tmp_path):
        """Malformed JSON in --json-file exits non-zero with an actionable message."""
        mock_ctx.client.get_variable.return_value = self._existing_variable()

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json")

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app, ["variable", "update", "99", "--json-file", str(bad_file), "--yes"]
            )

        assert result.exit_code != 0
        assert "Invalid JSON" in result.output
        assert bad_file.name in result.output
        mock_ctx.client.update_variable.assert_not_called()

    def test_update_variable_json_file_non_object_top_level_exits_error(self, mock_ctx, tmp_path):
        """A JSON array (not object) at the top level exits non-zero."""
        mock_ctx.client.get_variable.return_value = self._existing_variable()

        bad_file = tmp_path / "list.json"
        bad_file.write_text(json.dumps([1, 2, 3]))

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app, ["variable", "update", "99", "--json-file", str(bad_file), "--yes"]
            )

        assert result.exit_code != 0
        assert "JSON object" in result.output
        mock_ctx.client.update_variable.assert_not_called()

    def test_update_variable_json_file_ignores_identity_fields_with_warning(
        self, mock_ctx, tmp_path
    ):
        """Identity fields in the patch are stripped (not applied) with a warning, not an error."""
        existing = self._existing_variable()
        mock_ctx.client.get_variable.return_value = dict(existing)
        mock_ctx.client.update_variable.return_value = existing

        patch_file = tmp_path / "patch.json"
        patch_file.write_text(
            json.dumps(
                {
                    "variableId": "999",
                    "accountId": "a999",
                    "containerId": "c999",
                    "workspaceId": "ws999",
                    "fingerprint": "12345",
                    "notes": "safe field",
                }
            )
        )

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app, ["variable", "update", "99", "--json-file", str(patch_file), "--yes"]
            )

        assert result.exit_code == 0, result.output
        assert "Ignoring identity field" in result.output
        body = mock_ctx.client.update_variable.call_args.kwargs["variable_body"]
        assert body["variableId"] == "99"  # untouched, not overwritten with "999"
        assert "accountId" not in body
        assert body["notes"] == "safe field"


# ---------------------------------------------------------------------------
# create_variable dry-run
# ---------------------------------------------------------------------------


class TestCreateVariableDryRun:
    def test_create_variable_dry_run_does_not_call_client(self, mock_ctx):
        """--dry-run prints a DRY RUN message and skips the actual create_variable call."""
        mock_ctx.state.dry_run = True

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["variable", "create", "--name", "My Var", "--type", "c"])

        assert result.exit_code == 0, result.output
        assert "dry run" in result.output.lower()
        mock_ctx.client.create_variable.assert_not_called()


# ---------------------------------------------------------------------------
# delete_variable
# ---------------------------------------------------------------------------


class TestDeleteVariable:
    def test_delete_variable_success(self, mock_ctx):
        """Variable found and deleted successfully."""
        mock_ctx.client.get_variable.return_value = {"variableId": "99", "name": "Doomed"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["variable", "delete", "99"])

        assert result.exit_code == 0, result.output
        mock_ctx.client.delete_variable.assert_called_once()

    def test_delete_variable_dry_run_does_not_call_client(self, mock_ctx):
        """--dry-run still validates the variable exists but skips the actual delete."""
        mock_ctx.state.dry_run = True
        mock_ctx.client.get_variable.return_value = {"variableId": "99", "name": "Doomed"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["variable", "delete", "99"])

        assert result.exit_code == 0, result.output
        assert "dry run" in result.output.lower()
        mock_ctx.client.delete_variable.assert_not_called()


# ---------------------------------------------------------------------------
# revert_variable
# ---------------------------------------------------------------------------


class TestRevertVariable:
    def test_revert_variable_success(self, mock_ctx):
        """Revert calls client.revert_variable and prints success."""
        mock_ctx.client.revert_variable.return_value = {"variable": {"name": "Reverted Var"}}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["variable", "revert", "99"])

        assert result.exit_code == 0, result.output
        mock_ctx.client.revert_variable.assert_called_once()

    def test_revert_variable_dry_run_does_not_call_client(self, mock_ctx):
        """--dry-run prints a DRY RUN message and skips the actual revert_variable call."""
        mock_ctx.state.dry_run = True

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["variable", "revert", "99"])

        assert result.exit_code == 0, result.output
        assert "dry run" in result.output.lower()
        mock_ctx.client.revert_variable.assert_not_called()
