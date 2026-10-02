# Agent Instructions

## Project

gtm-cli is a Python CLI for Google Tag Manager API v2, built with Typer. It manages GTM accounts, containers, workspaces, tags, triggers, variables, templates, versions, environments, and built-in variables.

See [README.md](README.md) for command documentation, examples, and authentication setup. Use the repository-owned `skills/gtm-cli/` asset for non-obvious AI-agent usage patterns.

## Development commands

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run all checks
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

`make check` requires globally installed tools. Prefer `uv run --extra dev` so checks use the project's environment.

## Architecture

- **Entry point:** `src/gtm_cli/cli/main.py` creates the Typer app, defines the global `State`, and registers subcommand groups.
- **Commands:** each module under `src/gtm_cli/cli/` creates a `typer.Typer()` and registers it in `main.py`.
- **Workspace context:** `cli/helpers.py` provides `resolve_workspace_context()`, which resolves account, container, and workspace IDs into a frozen `WorkspaceContext`.
- **API client:** `core/client.py` contains `GTMClient`, wraps `googleapiclient.discovery`, and converts HTTP failures to typed exceptions.
- **Output:** `utils/output.py` supports JSON, YAML, Rich tables, and tab-separated plain output. Table output automatically becomes plain output when piped.
- **Authentication:** `core/auth.py` handles OAuth2 and service accounts. `core/config.py` stores YAML profiles under `~/.gtm-cli/profiles/`. Use `gtm login --no-gcloud` to force the OAuth client-secrets flow.

## Testing

Tests use `typer.testing.CliRunner`:

- Mock `resolve_workspace_context` with a `WorkspaceContext` containing a `MagicMock` client.
- Invoke commands with `runner.invoke(app, [...])`.
- Assert exit code, output, and API-client call arguments.
- Patch the helper in the command module, for example `gtm_cli.cli.tags.resolve_workspace_context`.

Relevant suites include `tests/unit/test_tag_commands.py`, `test_trigger_commands.py`, `test_variable_commands.py`, and `test_workspace_context.py`.

## Code style

- Ruff line length: 100.
- Strict mypy with `disallow_untyped_defs`.
- Google API libraries have targeted type-checking relaxations in `pyproject.toml`.
- Pre-commit runs Ruff lint/format, mypy, and standard repository checks.

## Design principle: keep the CLI self-explanatory

Every command and option must be usable correctly from its nested `--help` output alone.

- Disambiguate related options in `help=` text.
- Add runnable examples for non-trivial commands.
- Fix missing capabilities in the CLI instead of documenting fragile workarounds.
- Validate input locally and return actionable errors.
- Do not duplicate exact option references in the skill or agent. Those assets should cover only cross-command behavior, workflow, and safety.

## Key conventions

- GTM resource IDs are strings.
- Global flags such as `-a`, `-c`, `-w`, and `-f` precede the subcommand.
- Preserve GTM `{{variableName}}` references verbatim in JavaScript and HTML.
- Pass multi-line JavaScript or HTML through file options, not inline `--param` values.
- Tag Additional Consent Checks use top-level `consentSettings` via `--consent-type`; they are not tag parameters.
- JSON-file updates are top-level merge patches. Supplied arrays replace existing arrays, omitted fields remain, identity fields are ignored, and explicit command flags apply after the patch.
- GTM permits at most three workspaces per container.

## Available resource commands

| Group | Commands |
|-------|----------|
| `gtm account` | `list`, `get` |
| `gtm container` | `list`, `get` |
| `gtm workspace` | `list`, `get`, `status`, `publish`, `create`, `delete`, `quick-preview`, `preview` |
| `gtm tag` | `list`, `search`, `get`, `compare`, `create`, `update`, `pause`, `unpause`, `delete`, `audit-consent`, `audit-pixels`, `audit-setup-deps`, `audit-params` |
| `gtm template` | `list`, `get`, `create`, `update`, `delete` |
| `gtm trigger` | `list`, `get`, `create`, `update`, `delete` |
| `gtm variable` | `list`, `get`, `types`, `create`, `update`, `delete`, `revert` |
| `gtm version` | `list`, `get`, `diff` |
| `gtm environment` | `list`, `get`, `create`, `delete` |
| `gtm built-in-variable` | `list`, `enable`, `disable` |

Treat nested `--help` as authoritative if this table ever disagrees with the executable.

## Issue tracking

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work atomically
bd close <id>         # Complete work
bd sync               # Sync with git
```

## Non-Interactive Shell Commands

**ALWAYS use non-interactive flags** with file operations to avoid hanging on confirmation prompts.

Shell commands like `cp`, `mv`, and `rm` may be aliased to include `-i` (interactive) mode on some systems, causing the agent to hang indefinitely waiting for y/n input.

**Use these forms instead:**
```bash
# Force overwrite without prompting
cp -f source dest           # NOT: cp source dest
mv -f source dest           # NOT: mv source dest
rm -f file                  # NOT: rm file

# For recursive operations
rm -rf directory            # NOT: rm -r directory
cp -rf source dest          # NOT: cp -r source dest
```

**Other commands that may prompt:**
- `scp` - use `-o BatchMode=yes` for non-interactive
- `ssh` - use `-o BatchMode=yes` to fail instead of prompting
- `apt-get` - use `-y` flag
- `brew` - use `HOMEBREW_NO_AUTO_UPDATE=1` env var

## Portable AI capability assets

This repository ships tool-agnostic guidance for AI coding environments:

- `skills/gtm-cli/SKILL.md` – portable Agent Skill for safe and correct CLI usage
- `skills/gtm-cli/references/` – detailed resource guidance loaded only when needed
- `agents/google-tag-manager-admin.md` – portable GTM administration agent prompt

Do not assume the user runs Claude Code, Pi, or any other specific agent host. Do not add an installer that writes to a product-specific directory.

When a user asks to make these assets available in their AI environment:

1. Inspect or ask which host and configuration format they use.
2. Read that host's local documentation before changing configuration.
3. Explain the target files and any metadata adaptation required.
4. Ask before writing outside this repository or replacing an existing skill or agent.
5. Copy or link the assets only after approval, following the host's native conventions.
6. Preserve the prompt body and safety gates. Adapt only unsupported metadata or capability declarations.
7. Report where each asset was placed and how the user can verify discovery.

The repository copies are canonical. Update them in the same change as any CLI behavior they document; do not treat an installed copy in a particular AI tool as the source of truth.

### AI asset release checklist

Whenever a change adds, removes, renames, or alters a command, option, output shape, confirmation behavior, credential rule, or mutation workflow:

- Review `skills/gtm-cli/SKILL.md` for stale cross-command rules and examples.
- Review the relevant file under `skills/gtm-cli/references/`.
- Review `agents/google-tag-manager-admin.md` for affected workflow or safety assumptions.
- Update `README.md` and the command table in this file when applicable.
- Check all documented examples against the current nested `--help` output.
- Keep organization-specific IDs, naming rules, and ticket workflows out of the portable assets.

<!-- BEGIN BEADS INTEGRATION -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Version-controlled: Built on Dolt with cell-level merge
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd automatically syncs with git:

- Exports to `.beads/issues.jsonl` after changes (5s debounce)
- Imports from JSONL when newer (e.g., after `git pull`)
- No manual export/import needed!

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BEADS INTEGRATION -->
