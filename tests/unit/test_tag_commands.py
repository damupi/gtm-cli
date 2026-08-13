"""Tests for tag CLI commands (create, update, delete, pause, unpause)."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from gtm_cli.cli.helpers import WorkspaceContext
from gtm_cli.cli.main import State, app
from gtm_cli.utils.errors import ResourceNotFoundError
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
                    "tag",
                    "create",
                    "--name",
                    "Bad",
                    "--html",
                    "<script>inline</script>",
                    "--html-file",
                    str(html_file),
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
                    "tag",
                    "create",
                    "--name",
                    "Full Tag",
                    "--html",
                    "<script>x</script>",
                    "--trigger-id",
                    "295",
                    "--trigger-id",
                    "310",
                    "--folder-id",
                    "409",
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
                    "tag",
                    "create",
                    "--name",
                    "Unlimited",
                    "--html",
                    "<script>x</script>",
                    "--unlimited",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_tag.call_args.kwargs["tag_body"]
        assert body["tagFiringOption"] == "unlimited"

    def test_create_tag_with_notes(self, mock_ctx):
        """--notes sets the notes field on creation."""
        mock_ctx.client.create_tag.return_value = {"tagId": "46", "name": "Noted"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "tag",
                    "create",
                    "--name",
                    "Noted",
                    "--html",
                    "<script>x</script>",
                    "--notes",
                    "Why this tag exists",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_tag.call_args.kwargs["tag_body"]
        assert body["notes"] == "Why this tag exists"

    def test_create_tag_with_consent_type(self, mock_ctx):
        """--consent-type sets consentSettings with consentStatus 'needed'."""
        mock_ctx.client.create_tag.return_value = {"tagId": "47", "name": "Gated"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "tag",
                    "create",
                    "--name",
                    "Gated",
                    "--html",
                    "<script>x</script>",
                    "--consent-type",
                    "ad_storage",
                    "--consent-type",
                    "analytics_storage",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_tag.call_args.kwargs["tag_body"]
        assert body["consentSettings"]["consentStatus"] == "needed"
        values = [c["value"] for c in body["consentSettings"]["consentType"]["list"]]
        assert values == ["ad_storage", "analytics_storage"]

    def test_create_tag_with_param_sets_parameter_array(self, mock_ctx):
        """--param on create populates the parameter array (e.g. required cvt_* fields)."""
        mock_ctx.client.create_tag.return_value = {"tagId": "48", "name": "Intercom"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "tag",
                    "create",
                    "--name",
                    "Intercom",
                    "--type",
                    "cvt_TXZXG",
                    "--param",
                    "method:install",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_tag.call_args.kwargs["tag_body"]
        method_param = next(p for p in body["parameter"] if p["key"] == "method")
        assert method_param["value"] == "install"

    def test_create_tag_with_param_and_html_merges_parameter_array(self, mock_ctx):
        """--param alongside --html appends to the html-derived parameter array."""
        mock_ctx.client.create_tag.return_value = {"tagId": "49", "name": "Combo"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "tag",
                    "create",
                    "--name",
                    "Combo",
                    "--html",
                    "<script>x</script>",
                    "--param",
                    "extraKey:extraValue",
                ],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.create_tag.call_args.kwargs["tag_body"]
        assert next(p for p in body["parameter"] if p["key"] == "html")["value"] == (
            "<script>x</script>"
        )
        assert next(p for p in body["parameter"] if p["key"] == "extraKey")["value"] == (
            "extraValue"
        )

    def test_create_tag_with_invalid_param_format_exits_error(self, mock_ctx):
        """--param without colon separator exits with code 1 on create."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["tag", "create", "--name", "Bad", "--type", "cvt_TXZXG", "--param", "nocolon"],
            )

        assert result.exit_code == 1
        assert "Invalid param format" in result.output
        mock_ctx.client.create_tag.assert_not_called()

    def test_create_tag_with_invalid_consent_type_exits_error(self, mock_ctx):
        """An unrecognized --consent-type value exits with code 1."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "tag",
                    "create",
                    "--name",
                    "Bad Consent",
                    "--html",
                    "<script>x</script>",
                    "--consent-type",
                    "not_a_real_type",
                ],
            )

        assert result.exit_code == 1
        assert "Invalid consent type" in result.output
        mock_ctx.client.create_tag.assert_not_called()


# ---------------------------------------------------------------------------
# update_tag
# ---------------------------------------------------------------------------


_EXISTING_TAG = {
    "tagId": "421",
    "name": "Old Name",
    "type": "html",
    "parameter": [
        {"type": "template", "key": "html", "value": "<script>old</script>"},
        {"type": "boolean", "key": "supportDocumentWrite", "value": "false"},
    ],
    "firingTriggerId": ["295"],
    "parentFolderId": "409",
}


class TestUpdateTag:
    def test_update_name(self, mock_ctx):
        """--name updates the tag name."""
        mock_ctx.client.get_tag.return_value = {**_EXISTING_TAG}
        mock_ctx.client.update_tag.return_value = {**_EXISTING_TAG, "name": "New Name"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--name", "New Name"])

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        assert body["name"] == "New Name"

    def test_update_html_inline(self, mock_ctx):
        """--html replaces the html parameter value."""
        mock_ctx.client.get_tag.return_value = {**_EXISTING_TAG}
        mock_ctx.client.update_tag.return_value = _EXISTING_TAG

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--html", "<script>new</script>"])

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        html_param = next(p for p in body["parameter"] if p["key"] == "html")
        assert html_param["value"] == "<script>new</script>"

    def test_update_html_file(self, mock_ctx, tmp_path):
        """--html-file reads new content from a file."""
        html_file = tmp_path / "new.html"
        html_file.write_text("<script>fromFile</script>")
        mock_ctx.client.get_tag.return_value = {**_EXISTING_TAG}
        mock_ctx.client.update_tag.return_value = _EXISTING_TAG

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--html-file", str(html_file)])

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        html_param = next(p for p in body["parameter"] if p["key"] == "html")
        assert html_param["value"] == "<script>fromFile</script>"

    def test_update_html_and_html_file_mutual_exclusion(self, mock_ctx, tmp_path):
        """Both --html and --html-file exits with code 1."""
        html_file = tmp_path / "f.html"
        html_file.write_text("<script>x</script>")

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                [
                    "tag",
                    "update",
                    "421",
                    "--html",
                    "<script>y</script>",
                    "--html-file",
                    str(html_file),
                ],
            )

        assert result.exit_code == 1
        assert "Cannot specify both" in result.output

    def test_update_trigger_ids_replaces(self, mock_ctx):
        """--trigger-id replaces all existing firing triggers."""
        mock_ctx.client.get_tag.return_value = {**_EXISTING_TAG}
        mock_ctx.client.update_tag.return_value = _EXISTING_TAG

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["tag", "update", "421", "--trigger-id", "300", "--trigger-id", "301"],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        assert body["firingTriggerId"] == ["300", "301"]

    def test_update_folder_id(self, mock_ctx):
        """--folder-id moves the tag to a new folder."""
        mock_ctx.client.get_tag.return_value = {**_EXISTING_TAG}
        mock_ctx.client.update_tag.return_value = _EXISTING_TAG

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--folder-id", "500"])

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        assert body["parentFolderId"] == "500"

    def test_update_no_changes_exits_error(self, mock_ctx):
        """No options specified exits with code 1."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421"])

        assert result.exit_code == 1
        assert "No changes specified" in result.output

    def test_update_tag_not_found(self, mock_ctx):
        """Non-existent tag exits with code 1."""
        mock_ctx.client.get_tag.side_effect = ResourceNotFoundError("Tag", "get tag 999")

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "999", "--name", "X"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_update_param_updates_existing_key(self, mock_ctx):
        """--param updates the value of an existing parameter key."""
        tag = {
            **_EXISTING_TAG,
            "parameter": [
                {"type": "template", "key": "conversionId", "value": "old-id"},
                {"type": "template", "key": "html", "value": "<script>x</script>"},
            ],
        }
        mock_ctx.client.get_tag.return_value = tag
        mock_ctx.client.update_tag.return_value = tag

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--param", "conversionId:new-id"])

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        conv_param = next(p for p in body["parameter"] if p["key"] == "conversionId")
        assert conv_param["value"] == "new-id"
        # Other params remain unchanged
        html_param = next(p for p in body["parameter"] if p["key"] == "html")
        assert html_param["value"] == "<script>x</script>"

    def test_update_param_appends_new_key(self, mock_ctx):
        """--param appends a new entry when the key is not already present."""
        mock_ctx.client.get_tag.return_value = {**_EXISTING_TAG}
        mock_ctx.client.update_tag.return_value = {**_EXISTING_TAG}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--param", "newKey:newValue"])

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        new_param = next((p for p in body["parameter"] if p["key"] == "newKey"), None)
        assert new_param is not None
        assert new_param["value"] == "newValue"
        assert new_param["type"] == "template"

    def test_update_param_invalid_format_exits_error(self, mock_ctx):
        """--param without colon separator exits with code 1."""
        mock_ctx.client.get_tag.return_value = {**_EXISTING_TAG}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--param", "nocolon"])

        assert result.exit_code == 1
        assert "Invalid param format" in result.output

    def test_update_notes_sets_value(self, mock_ctx):
        """--notes sets the notes field on the tag."""
        mock_ctx.client.get_tag.return_value = {**_EXISTING_TAG}
        mock_ctx.client.update_tag.return_value = {**_EXISTING_TAG, "notes": "Workaround for X"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--notes", "Workaround for X"])

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        assert body["notes"] == "Workaround for X"

    def test_update_notes_clears_value(self, mock_ctx):
        """--notes '' clears an existing notes field."""
        tag = {**_EXISTING_TAG, "notes": "Old note"}
        mock_ctx.client.get_tag.return_value = tag
        mock_ctx.client.update_tag.return_value = {**tag, "notes": ""}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--notes", ""])

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        assert body["notes"] == ""

    def test_update_html_inserts_param_when_missing(self, mock_ctx):
        """If tag has no html parameter, one is appended."""
        tag_no_html = {
            "tagId": "421",
            "name": "No HTML",
            "type": "html",
            "parameter": [
                {"type": "boolean", "key": "supportDocumentWrite", "value": "false"},
            ],
        }
        mock_ctx.client.get_tag.return_value = tag_no_html
        mock_ctx.client.update_tag.return_value = tag_no_html

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--html", "<script>new</script>"])

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        html_param = next(p for p in body["parameter"] if p["key"] == "html")
        assert html_param["value"] == "<script>new</script>"

    def test_update_consent_type_sets_consent_settings(self, mock_ctx):
        """--consent-type replaces consentSettings with the given categories."""
        mock_ctx.client.get_tag.return_value = {**_EXISTING_TAG}
        mock_ctx.client.update_tag.return_value = {**_EXISTING_TAG}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["tag", "update", "421", "--consent-type", "functionality_storage"],
            )

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        assert body["consentSettings"]["consentStatus"] == "needed"
        values = [c["value"] for c in body["consentSettings"]["consentType"]["list"]]
        assert values == ["functionality_storage"]

    def test_update_invalid_consent_type_exits_error(self, mock_ctx):
        """An unrecognized --consent-type value exits with code 1."""
        mock_ctx.client.get_tag.return_value = {**_EXISTING_TAG}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(
                app,
                ["tag", "update", "421", "--consent-type", "bogus"],
            )

        assert result.exit_code == 1
        assert "Invalid consent type" in result.output
        mock_ctx.client.update_tag.assert_not_called()

    def test_update_clear_consent_type_removes_consent_settings(self, mock_ctx):
        """--clear-consent-type removes an existing consentSettings block."""
        tag = {
            **_EXISTING_TAG,
            "consentSettings": {
                "consentStatus": "needed",
                "consentType": {
                    "type": "list",
                    "list": [{"type": "template", "value": "ad_storage"}],
                },
            },
        }
        mock_ctx.client.get_tag.return_value = tag
        mock_ctx.client.update_tag.return_value = {**_EXISTING_TAG}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "update", "421", "--clear-consent-type"])

        assert result.exit_code == 0, result.output
        body = mock_ctx.client.update_tag.call_args.kwargs["tag_body"]
        assert "consentSettings" not in body


# ---------------------------------------------------------------------------
# delete_tag
# ---------------------------------------------------------------------------


class TestDeleteTag:
    def test_delete_tag_success(self, mock_ctx):
        """Tag found and --yes skips prompt; client.delete_tag is called."""
        mock_ctx.client.get_tag.return_value = {"tagId": "100", "name": "Doomed Tag"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "delete", "100"])

        assert result.exit_code == 0, result.output
        mock_ctx.client.delete_tag.assert_called_once()
        call_kwargs = mock_ctx.client.delete_tag.call_args.kwargs
        assert call_kwargs["tag_id"] == "100"

    def test_delete_tag_not_found(self, mock_ctx):
        """Deleting a non-existent tag exits with code 1."""
        mock_ctx.client.get_tag.side_effect = ResourceNotFoundError("Tag", "get tag 999")

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
        mock_ctx.client.get_tag.return_value = tag
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
        mock_ctx.client.get_tag.return_value = tag
        mock_ctx.client.update_tag.return_value = {**tag, "paused": False}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "unpause", "201"])

        assert result.exit_code == 0, result.output
        call_kwargs = mock_ctx.client.update_tag.call_args.kwargs
        assert call_kwargs["tag_body"]["paused"] is False

    def test_pause_tag_not_found_exits_nonzero(self, mock_ctx):
        """Pausing a non-existent tag ID exits with code 1."""
        mock_ctx.client.get_tag.side_effect = ResourceNotFoundError("Tag", "get tag 999")

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "pause", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# get (multi-ID)
# ---------------------------------------------------------------------------


class TestGetTag:
    def test_get_single_tag(self, mock_ctx):
        """Single tag ID returns that tag."""
        mock_ctx.client.get_tag.return_value = {"tagId": "298", "name": "Test Tag"}

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "get", "298"])

        assert result.exit_code == 0, result.output
        mock_ctx.client.get_tag.assert_called_once()

    def test_get_multiple_tags(self, mock_ctx):
        """Multiple tag IDs returns all tags."""
        mock_ctx.client.get_tag.side_effect = [
            {"tagId": "298", "name": "Tag A"},
            {"tagId": "302", "name": "Tag B"},
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "get", "298", "302"])

        assert result.exit_code == 0, result.output
        assert mock_ctx.client.get_tag.call_count == 2

    def test_get_tag_not_found(self, mock_ctx):
        """Non-existent tag ID exits with code 1."""
        mock_ctx.client.get_tag.side_effect = ResourceNotFoundError("Tag", "get tag 999")

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "get", "999"])

        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_get_multiple_partial_failure(self, mock_ctx):
        """Some tags found, some not — still exits 1."""
        mock_ctx.client.get_tag.side_effect = [
            {"tagId": "298", "name": "Tag A"},
            ResourceNotFoundError("Tag", "get tag 999"),
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "get", "298", "999"])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# search (with --trigger)
# ---------------------------------------------------------------------------


_SAMPLE_TAGS = [
    {"tagId": "1", "name": "TikTok ViewContent", "type": "html", "firingTriggerId": ["62"]},
    {"tagId": "2", "name": "FB ViewContent", "type": "html", "firingTriggerId": ["62"]},
    {"tagId": "3", "name": "TikTok Purchase", "type": "html", "firingTriggerId": ["70"]},
]


class TestSearchTags:
    def test_search_by_trigger_id(self, mock_ctx):
        """--trigger filters tags by trigger ID."""
        mock_ctx.client.list_tags.return_value = _SAMPLE_TAGS
        mock_ctx.client.list_folders.return_value = []
        mock_ctx.client.list_triggers.return_value = [
            {"triggerId": "62", "name": "Campsite detail"},
            {"triggerId": "70", "name": "Booking"},
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "search", "--trigger", "62"])

        assert result.exit_code == 0, result.output
        assert "2 tag(s)" in result.output

    def test_search_by_trigger_name(self, mock_ctx):
        """--trigger with name substring matches triggers."""
        mock_ctx.client.list_tags.return_value = _SAMPLE_TAGS
        mock_ctx.client.list_folders.return_value = []
        mock_ctx.client.list_triggers.return_value = [
            {"triggerId": "62", "name": "Campsite detail"},
            {"triggerId": "70", "name": "Booking"},
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "search", "--trigger", "Campsite"])

        assert result.exit_code == 0, result.output
        assert "2 tag(s)" in result.output

    def test_search_requires_query_or_filter(self, mock_ctx):
        """No query and no filter exits with error."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "search"])

        assert result.exit_code == 1

    def test_search_by_name_and_trigger(self, mock_ctx):
        """Combining query and --trigger intersects results."""
        mock_ctx.client.list_tags.return_value = _SAMPLE_TAGS
        mock_ctx.client.list_folders.return_value = []
        mock_ctx.client.list_triggers.return_value = [
            {"triggerId": "62", "name": "Campsite detail"},
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "search", "TikTok", "--trigger", "62"])

        assert result.exit_code == 0, result.output
        assert "1 tag(s)" in result.output


# ---------------------------------------------------------------------------
# audit-setup-deps
# ---------------------------------------------------------------------------


class TestAuditSetupDeps:
    def test_no_issues(self, mock_ctx):
        """Clean tags with no setup deps reports success."""
        mock_ctx.client.list_tags.return_value = [
            {"tagId": "1", "name": "Tag A"},
            {"tagId": "2", "name": "Tag B"},
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "audit-setup-deps"])

        assert result.exit_code == 0, result.output
        assert "No broken" in result.output

    def test_paused_setup_tag(self, mock_ctx):
        """Tag referencing a paused setupTag is flagged."""
        mock_ctx.client.list_tags.return_value = [
            {"tagId": "304", "name": "Base Pixel", "paused": True},
            {
                "tagId": "308",
                "name": "Login Event",
                "setupTag": [{"tagName": "304", "stopOnSetupFailure": True}],
            },
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "audit-setup-deps"])

        assert result.exit_code == 0, result.output
        assert "1 broken" in result.output
        assert "PAUSED" in result.output

    def test_missing_setup_tag(self, mock_ctx):
        """Tag referencing a non-existent setupTag is flagged."""
        mock_ctx.client.list_tags.return_value = [
            {
                "tagId": "308",
                "name": "Login Event",
                "setupTag": [{"tagName": "999", "stopOnSetupFailure": False}],
            },
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "audit-setup-deps"])

        assert result.exit_code == 0, result.output
        assert "1 broken" in result.output
        assert "not found" in result.output

    def test_paused_teardown_tag(self, mock_ctx):
        """Tag referencing a paused teardownTag is flagged with correct dep_type."""
        mock_ctx.client.list_tags.return_value = [
            {"tagId": "400", "name": "Cleanup Tag", "paused": True},
            {
                "tagId": "401",
                "name": "Main Tag",
                "teardownTag": [{"tagName": "400", "stopTeardownOnFailure": False}],
            },
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "audit-setup-deps"])

        assert result.exit_code == 0, result.output
        assert "1 broken" in result.output
        assert "teardown" in result.output.lower()

    def test_both_setup_and_teardown_broken(self, mock_ctx):
        """Tag with both broken setup and teardown reports 2 issues."""
        mock_ctx.client.list_tags.return_value = [
            {"tagId": "500", "name": "Setup Tag", "paused": True},
            {"tagId": "501", "name": "Teardown Tag", "paused": True},
            {
                "tagId": "502",
                "name": "Main Tag",
                "setupTag": [{"tagName": "500", "stopOnSetupFailure": True}],
                "teardownTag": [{"tagName": "501", "stopTeardownOnFailure": False}],
            },
        ]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "audit-setup-deps"])

        assert result.exit_code == 0, result.output
        assert "2 broken" in result.output
        assert "setup" in result.output.lower()
        assert "teardown" in result.output.lower()


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


class TestCompareTags:
    def test_compare_by_ids(self, mock_ctx):
        """Compare two tags by ID shows comparison table."""
        mock_ctx.client.list_tags.return_value = [
            {
                "tagId": "298",
                "name": "TikTok VC",
                "type": "html",
                "firingTriggerId": ["62"],
                "parameter": [
                    {
                        "key": "html",
                        "value": "ttq.track('ViewContent', {content_type: 'product'});",
                    }
                ],
            },
            {
                "tagId": "17",
                "name": "FB VC",
                "type": "html",
                "firingTriggerId": ["62"],
                "parameter": [
                    {
                        "key": "html",
                        "value": "fbq('track', 'ViewContent', {content_name: 'test'});",
                    }
                ],
            },
        ]
        mock_ctx.client.list_folders.return_value = []
        mock_ctx.client.list_triggers.return_value = [{"triggerId": "62", "name": "Detail"}]

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "compare", "298", "17"])

        assert result.exit_code == 0, result.output
        assert "Comparing 2 tags" in result.output

    def test_compare_needs_two_tags(self, mock_ctx):
        """Single tag can't be compared."""
        mock_ctx.client.list_tags.return_value = [
            {"tagId": "298", "name": "Tag A", "type": "html"},
        ]
        mock_ctx.client.list_folders.return_value = []
        mock_ctx.client.list_triggers.return_value = []

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "compare", "298"])

        assert result.exit_code == 0
        assert "at least 2" in result.output.lower()

    def test_compare_requires_args(self, mock_ctx):
        """No arguments exits with error."""
        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = runner.invoke(app, ["tag", "compare"])

        assert result.exit_code == 1
