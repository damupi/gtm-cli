"""Tests for tag CLI commands (create, delete, pause, unpause)."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.helpers import WorkspaceContext
from gtm_cli.cli.main import State, app
from gtm_cli.utils.output import OutputFormat

runner = CliRunner()

_PATCH_TARGET = "gtm_cli.cli.tags.resolve_workspace_context"


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
# create_tag
# ---------------------------------------------------------------------------


class TestCreateTag:
    def test_create_tag_html_inline(self, mock_ctx):
        """Inline --html content is sent in the tag body."""
        mock_ctx.client.create_tag.return_value = {"tagId": "42", "name": "My Tag"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["tag", "create", "--name", "My Tag", "--html", "<script>x</script>"],
            )

        assert result.exit_code == 0, result.output
        mock_ctx.client.create_tag.assert_called_once()
        body = mock_ctx.client.create_tag.call_args.kwargs["tag_body"]
        assert body["name"] == "My Tag"
        assert body["type"] == "html"
        # HTML content stored in parameter list
        html_param = next(p for p in body["parameter"] if p["key"] == "html")
        assert html_param["value"] == "<script>x</script>"

    def test_create_tag_html_file(self, mock_ctx, tmp_path):
        """--html-file reads content from the given path."""
        html_file = tmp_path / "pixel.html"
        html_file.write_text("<script>fromFile</script>")
        mock_ctx.client.create_tag.return_value = {"tagId": "43", "name": "File Tag"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["tag", "create", "--name", "File Tag", "--html-file", str(html_file)],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_tag.call_args.kwargs["tag_body"]
        html_param = next(p for p in body["parameter"] if p["key"] == "html")
        assert html_param["value"] == "<script>fromFile</script>"

    def test_create_tag_html_and_html_file_mutual_exclusion(self, mock_ctx, tmp_path):
        """Providing both --html and --html-file exits with code 1."""
        html_file = tmp_path / "pixel.html"
        html_file.write_text("<script>x</script>")

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "tag", "create",
                    "--name", "Bad",
                    "--html", "<script>inline</script>",
                    "--html-file", str(html_file),
                ],
            )

        assert result.exit_code == 1
        assert "Cannot specify both" in result.output

    def test_create_tag_html_type_requires_content(self, mock_ctx):
        """--type html without --html or --html-file exits with code 1."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["tag", "create", "--name", "No Content", "--type", "html"],
            )

        assert result.exit_code == 1
        assert "require" in result.output.lower()

    def test_create_tag_with_triggers_and_folder(self, mock_ctx):
        """--trigger-id and --folder-id are included in the tag body."""
        mock_ctx.client.create_tag.return_value = {"tagId": "44", "name": "Full Tag"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "tag", "create",
                    "--name", "Full Tag",
                    "--html", "<script>x</script>",
                    "--trigger-id", "295",
                    "--trigger-id", "310",
                    "--folder-id", "409",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_tag.call_args.kwargs["tag_body"]
        assert body["firingTriggerId"] == ["295", "310"]
        assert body["parentFolderId"] == "409"

    def test_create_tag_unlimited_firing(self, mock_ctx):
        """--unlimited sets tagFiringOption to 'unlimited'."""
        mock_ctx.client.create_tag.return_value = {"tagId": "45", "name": "Unlimited"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "tag", "create",
                    "--name", "Unlimited",
                    "--html", "<script>x</script>",
                    "--unlimited",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_tag.call_args.kwargs["tag_body"]
        assert body["tagFiringOption"] == "unlimited"


# ---------------------------------------------------------------------------
# delete_tag
# ---------------------------------------------------------------------------


class TestDeleteTag:
    def test_delete_tag_success(self, mock_ctx):
        """Tag found and --yes skips prompt; client.delete_tag is called."""
        mock_ctx.client.list_tags.return_value = [
            {"tagId": "100", "name": "Doomed Tag"},
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "delete", "100"])

        assert result.exit_code == 0, result.output
        mock_ctx.client.delete_tag.assert_called_once()
        call_kwargs = mock_ctx.client.delete_tag.call_args.kwargs
        assert call_kwargs["tag_id"] == "100"

    def test_delete_tag_not_found(self, mock_ctx):
        """Deleting a non-existent tag exits with code 1."""
        mock_ctx.client.list_tags.return_value = [
            {"tagId": "100", "name": "Other Tag"},
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "delete", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# pause / unpause
# ---------------------------------------------------------------------------


class TestPauseUnpause:
    def test_pause_tag(self, mock_ctx):
        """Pause sets paused=True and calls update_tag."""
        tag = {"tagId": "200", "name": "Pausable", "paused": False}
        mock_ctx.client.list_tags.return_value = [tag]
        mock_ctx.client.update_tag.return_value = {**tag, "paused": True}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "pause", "200"])

        assert result.exit_code == 0, result.output
        mock_ctx.client.update_tag.assert_called_once()
        call_kwargs = mock_ctx.client.update_tag.call_args.kwargs
        assert call_kwargs["tag_id"] == "200"
        assert call_kwargs["tag_body"]["paused"] is True

    def test_unpause_tag(self, mock_ctx):
        """Unpause sets paused=False and calls update_tag."""
        tag = {"tagId": "201", "name": "Paused Tag", "paused": True}
        mock_ctx.client.list_tags.return_value = [tag]
        mock_ctx.client.update_tag.return_value = {**tag, "paused": False}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "unpause", "201"])

        assert result.exit_code == 0, result.output
        call_kwargs = mock_ctx.client.update_tag.call_args.kwargs
        assert call_kwargs["tag_body"]["paused"] is False

    def test_pause_tag_not_found_exits_nonzero(self, mock_ctx):
        """Pausing a non-existent tag ID exits with code 1."""
        mock_ctx.client.list_tags.return_value = [
            {"tagId": "200", "name": "Other"},
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "pause", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()
