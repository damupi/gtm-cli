"""Typer integration tests for the gtm upgrade command and update notice."""

import json
import re
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from gtm_cli.cli.main import app
from gtm_cli.core import update

runner = CliRunner()

_PATCH = "gtm_cli.cli.upgrade"


def _completed(stdout="", returncode=0, stderr=""):
    return MagicMock(stdout=stdout, stderr=stderr, returncode=returncode)


def test_upgrade_help_documents_flags():
    result = runner.invoke(app, ["upgrade", "--help"])
    assert result.exit_code == 0
    plain_output = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", result.stdout)
    assert "--check" in plain_output
    assert "--yes" in plain_output
    assert "--json" in plain_output


def test_upgrade_check_reports_available_update():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
    ):
        result = runner.invoke(app, ["upgrade", "--check"])
    assert result.exit_code == 0
    assert "Installed: gtm-cli 1.2.0" in result.stdout
    assert "Latest release: 1.3.0" in result.stdout
    assert "Update available: yes" in result.stdout
    assert "uv tool install --force X@v1.3.0" in result.stdout


def test_upgrade_check_reports_up_to_date():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.3.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
    ):
        result = runner.invoke(app, ["upgrade", "--check"])
    assert result.exit_code == 0
    assert "Update available: no" in result.stdout
    assert "uv tool install --force X@v1.3.0" in result.stdout


def test_upgrade_check_json_output():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
    ):
        result = runner.invoke(app, ["upgrade", "--check", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {
        "installed": "1.2.0",
        "latest": "1.3.0",
        "update_available": True,
        "upgrade_command": "uv tool install --force X@v1.3.0",
    }


def test_upgrade_check_handles_unknown_latest():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value=None),
    ):
        result = runner.invoke(app, ["upgrade", "--check"])
    assert result.exit_code == 0
    assert "Latest release: unknown" in result.stdout
    assert "Update available: unknown" in result.stdout


def test_upgrade_json_alone_is_check_only():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
        patch(f"{_PATCH}.perform_upgrade") as perform,
    ):
        result = runner.invoke(app, ["upgrade", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["update_available"] is True
    assert payload["upgrade_command"] == "uv tool install --force X@v1.3.0"
    perform.assert_not_called()


def test_upgrade_check_renders_command_literally_despite_markup_chars():
    weird = "git -C /tmp/[bold]weird[/bold] pull  # editable install"
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.upgrade_command", return_value=weird),
    ):
        result = runner.invoke(app, ["upgrade", "--check"])
    assert result.exit_code == 0
    assert "[bold]weird[/bold]" in result.stdout


def test_upgrade_yes_executes_perform_upgrade():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.install_info", return_value={"kind": "uv", "path": ""}),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
        patch(f"{_PATCH}.perform_upgrade", return_value=_completed("Installed")) as perform,
    ):
        result = runner.invoke(app, ["upgrade", "--yes"])
    assert result.exit_code == 0
    assert "gtm-cli 1.2.0 → 1.3.0" in result.stdout
    assert "Upgraded gtm-cli to 1.3.0." in result.stdout
    perform.assert_called_once_with("1.3.0")


def test_upgrade_global_yes_flag_is_honored():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.install_info", return_value={"kind": "uv", "path": ""}),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
        patch(f"{_PATCH}.perform_upgrade", return_value=_completed()) as perform,
    ):
        result = runner.invoke(app, ["-y", "upgrade"])
    assert result.exit_code == 0
    perform.assert_called_once_with("1.3.0")


def test_upgrade_prompts_and_cancels_without_confirmation():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.install_info", return_value={"kind": "uv", "path": ""}),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
        patch(f"{_PATCH}.perform_upgrade") as perform,
    ):
        result = runner.invoke(app, ["upgrade"], input="n\n")
    assert result.exit_code == 0
    assert "Upgrade cancelled." in result.stdout
    perform.assert_not_called()


def test_upgrade_proceeds_when_confirmed():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.install_info", return_value={"kind": "pip", "path": ""}),
        patch(f"{_PATCH}.upgrade_command", return_value="python -m pip install X@v1.3.0"),
        patch(f"{_PATCH}.perform_upgrade", return_value=_completed()) as perform,
    ):
        result = runner.invoke(app, ["upgrade"], input="y\n")
    assert result.exit_code == 0
    perform.assert_called_once_with("1.3.0")


def test_upgrade_already_current_does_nothing():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.3.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.perform_upgrade") as perform,
    ):
        result = runner.invoke(app, ["upgrade", "--yes"])
    assert result.exit_code == 0
    assert "already up to date" in result.stdout
    perform.assert_not_called()


def test_upgrade_without_latest_release_is_actionable():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value=None),
    ):
        result = runner.invoke(app, ["upgrade", "--yes"])
    assert result.exit_code != 0
    assert "Could not determine the latest gtm-cli release" in result.stderr


def test_upgrade_editable_prints_git_pull_without_prompting():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.install_info", return_value={"kind": "editable", "path": "/src/gtm-cli"}),
        patch(
            f"{_PATCH}.upgrade_command",
            return_value="git -C /src/gtm-cli pull  # editable install: update your checkout",
        ),
        patch(f"{_PATCH}.perform_upgrade") as perform,
    ):
        result = runner.invoke(app, ["upgrade", "--yes"])
    assert result.exit_code == 0
    assert "Editable install detected" in result.stdout
    assert "git -C /src/gtm-cli pull" in result.stdout
    perform.assert_not_called()


def test_upgrade_failure_is_reported_with_nonzero_exit():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.install_info", return_value={"kind": "uv", "path": ""}),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
        patch(f"{_PATCH}.perform_upgrade", side_effect=update.UpgradeError("boom")),
    ):
        result = runner.invoke(app, ["upgrade", "--yes"])
    assert result.exit_code != 0
    assert "boom" in result.stderr


def test_upgrade_failure_escapes_markup_like_detail():
    with (
        patch(f"{_PATCH}.installed_version", return_value="1.2.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.install_info", return_value={"kind": "uv", "path": ""}),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
        patch(
            f"{_PATCH}.perform_upgrade",
            side_effect=update.UpgradeError("failed at [bold]/tmp/weird[/bold]"),
        ),
    ):
        result = runner.invoke(app, ["upgrade", "--yes"])
    assert result.exit_code != 0
    assert "[bold]/tmp/weird[/bold]" in result.stderr


def test_upgrade_uses_installed_version_fallback():
    with (
        patch(f"{_PATCH}.installed_version", return_value=None),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.install_info", return_value={"kind": "uv", "path": ""}),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
        patch(f"{_PATCH}.perform_upgrade", return_value=_completed()),
    ):
        result = runner.invoke(app, ["upgrade", "--check"])
    assert result.exit_code == 0
    assert "Installed: gtm-cli" in result.stdout


# ── Automatic notice wiring ───────────────────────────────────────────────────


def test_normal_command_prints_pending_notice_on_stderr():
    with patch(
        "gtm_cli.cli.main.pending_notice",
        return_value="A new release of gtm-cli is available: 1.2.0 → 1.3.0",
    ):
        result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "A new release of gtm-cli is available" in result.stderr
    assert "A new release" not in result.stdout


def test_upgrade_command_does_not_print_background_notice():
    with (
        patch("gtm_cli.cli.main.pending_notice") as notice,
        patch(f"{_PATCH}.installed_version", return_value="1.3.0"),
        patch(f"{_PATCH}.latest_release", return_value="1.3.0"),
        patch(f"{_PATCH}.upgrade_command", return_value="uv tool install --force X@v1.3.0"),
    ):
        result = runner.invoke(app, ["upgrade", "--check"])
    assert result.exit_code == 0
    notice.assert_not_called()


def test_version_flag_still_reports_installed_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "gtm-cli version" in result.stdout


def test_version_group_is_preserved():
    result = runner.invoke(app, ["version", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout


# ── Notice rendering safety ───────────────────────────────────────────────────


def test_notice_render_failure_does_not_fail_command():
    with (
        patch("gtm_cli.cli.main.pending_notice", return_value="a notice"),
        patch(
            "gtm_cli.cli.main.error_console.print",
            side_effect=RuntimeError("stderr closed"),
        ),
    ):
        result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0


def test_notice_with_bracket_path_is_not_interpreted_as_markup():
    with patch("gtm_cli.cli.main.pending_notice", return_value="run gtm [bold]upgrade[/bold]"):
        result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0
    assert "[bold]upgrade[/bold]" in result.stderr
