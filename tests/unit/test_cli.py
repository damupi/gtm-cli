"""Tests for CLI commands."""

from typer.testing import CliRunner

from gtm_cli.cli.main import app

runner = CliRunner()


def test_version():
    """Test --version flag."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "gtm-cli version" in result.stdout


def test_help():
    """Test --help flag."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "GTM CLI" in result.stdout
    assert "account" in result.stdout
    assert "container" in result.stdout
    assert "tag" in result.stdout


def test_tag_help():
    """Test tag subcommand help."""
    result = runner.invoke(app, ["tag", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "search" in result.stdout
    assert "get" in result.stdout
    assert "audit-consent" in result.stdout
    assert "audit-pixels" in result.stdout


def test_version_help():
    """Test version subcommand help."""
    result = runner.invoke(app, ["version", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "get" in result.stdout
    assert "diff" in result.stdout


def test_workspace_help():
    """Test workspace subcommand help."""
    result = runner.invoke(app, ["workspace", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "status" in result.stdout
    assert "publish" in result.stdout
