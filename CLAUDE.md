# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

gtm-cli is a Python CLI for Google Tag Manager API v2, built with Typer. It manages GTM accounts, containers, workspaces, tags, triggers, variables, and versions.

See [README.md](README.md) for full command documentation, usage examples, and authentication setup.
See [docs/AI-USAGE.md](docs/AI-USAGE.md) for AI agent usage patterns and non-obvious behaviors.

## Commands

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run all checks (lint + type check + tests)
uv run --extra dev ruff check src/ tests/
uv run --extra dev mypy src/
uv run --extra dev pytest tests/ -v

# Run a single test file or test
uv run --extra dev pytest tests/unit/test_tag_commands.py -v
uv run --extra dev pytest tests/unit/test_tag_commands.py::TestSearchTags::test_search_by_trigger_id -v

# Format
uv run --extra dev ruff format src/ tests/
uv run --extra dev ruff check --fix src/ tests/
```

Note: `make check` exists but requires tools installed globally. Use `uv run --extra dev` prefix to run via the project's venv.

## Architecture

**Entry point:** `src/gtm_cli/cli/main.py` — creates the Typer `app`, defines global `State` class (holds CLI options), registers all subcommand groups via `register_commands()`.

**Command pattern:** Each command module (`cli/tags.py`, `cli/triggers.py`, etc.) creates its own `typer.Typer()` instance, defines commands as decorated functions, and gets registered in `main.py` via `app.add_typer()`.

**WorkspaceContext:** Most commands need account/container/workspace IDs. `cli/helpers.py` provides `resolve_workspace_context()` which auto-detects IDs when the user has only one of each, returning a frozen `WorkspaceContext` dataclass. Commands unpack it as `ctx.client.list_tags(**ctx.api_kwargs)`.

**API client:** `core/client.py` — `GTMClient` wraps Google's `googleapiclient.discovery` service. All methods accept `profile_name` and `service_account_path` kwargs. HTTP errors are converted to typed exceptions (`ResourceNotFoundError`, `PermissionDeniedError`, `APIError`).

**Output:** `utils/output.py` — `output()` dispatches to JSON, YAML, table (Rich), or plain (tab-separated) format. Table auto-switches to plain when stdout is piped.

**Auth:** `core/auth.py` handles OAuth2 and service accounts. `core/config.py` manages profiles stored as YAML in `~/.gtm-cli/profiles/`. `gtm login` auto-detects gcloud; use `--no-gcloud` to force OAuth2 client secrets flow (requires `~/.config/gtm-cli/client_secrets.json` or `~/.gtm-cli/client_secrets.json`).

## Testing

Tests use `typer.testing.CliRunner` to invoke commands. The standard pattern:
- Mock `resolve_workspace_context` to return a `WorkspaceContext` with a `MagicMock` client
- Invoke via `runner.invoke(app, ["tag", "search", ...])`
- Assert exit code, output text, and mock call args

Patch target for workspace context: `"gtm_cli.cli.tags.resolve_workspace_context"` (adjust module path per command file).

Test files per module:
- `tests/unit/test_tag_commands.py`
- `tests/unit/test_trigger_commands.py`
- `tests/unit/test_variable_commands.py`
- `tests/unit/test_workspace_context.py`

## Code Style

- Line length: 100 (ruff)
- Strict mypy with `disallow_untyped_defs`
- Google API libs have relaxed type checking (configured in pyproject.toml)
- Pre-commit hooks: ruff lint/format + mypy + standard checks

## Key Conventions

- `tag_id`, `trigger_id`, `variable_id` etc. are strings (GTM API returns them as strings)
- Commands that modify/delete require `--yes` or interactive confirmation via `confirm()`
- The `--authuser` global option appends `?authuser=N` to GTM URLs for multi-account Google sessions
- Global flags (`-a`, `-c`, `-w`, `-f`) must come **before** the subcommand — they belong to `gtm`, not to the subcommand
- Audit commands (`audit-consent`, `audit-pixels`, `audit-params`, `audit-setup-deps`) analyze API data with heuristics and return categorized findings
- Tag HTML is extracted via `_get_tag_html()` helper; pixel detection and event parameter extraction use compiled regex patterns in `tags.py`
- GTM variable references in JS/HTML use `{{variableName}}` syntax — always pass these through verbatim

## Available commands (current)

| Group | Commands |
|-------|----------|
| `gtm account` | `list`, `get` |
| `gtm container` | `list`, `get` |
| `gtm workspace` | `list`, `get`, `status`, `create`, `delete`, `preview`, `publish` |
| `gtm tag` | `list`, `get`, `search`, `create`, `update`, `delete`, `revert`, `audit-consent`, `audit-pixels`, `audit-params`, `audit-setup-deps` |
| `gtm trigger` | `list`, `get`, `create`, `update`, `delete`, `revert` |
| `gtm variable` | `list`, `get`, `types`, `create`, `update`, `delete`, `revert` |
| `gtm version` | `list`, `get`, `publish`, `revert` |

## Multi-line JS/HTML parameters

Never pass JavaScript or HTML inline via `--param` — shell quoting silently corrupts multi-line strings. Use `--param-file` instead:

```bash
# ✓ correct
gtm variable update 123 --param-file javascript:/tmp/my_var.js

# ✗ wrong — shell corrupts multi-line JS silently
gtm variable update 123 --param 'javascript:function() { ... }'
```

The CLI enforces this: passing a `javascript` or `html` key with newlines via `--param` exits with an error and redirects to `--param-file`.

## Workspace limit

GTM enforces a maximum of **3 workspaces** per container. `workspace create` checks the existing count and errors before hitting the API if already at 3.

## GTM UI deep-links

`variable create`, `variable update`, and `workspace create` print a `Review:` link after every write. The URL pattern is:

```
https://tagmanager.google.com/#/container/accounts/{accountId}/containers/{containerId}/workspaces/{workspaceId}/variables/{variableId}
```

`containerId` in URLs is the numeric ID, not `GTM-XXXX`.
