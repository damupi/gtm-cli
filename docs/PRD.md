# PRD — gtm-cli fork (damupi)

## Background

This is a fork of [oppianmatt/gtm-cli](https://github.com/oppianmatt/gtm-cli), a Python CLI for the Google Tag Manager API v2. The upstream project covers read operations well but has two gaps we need to address.

## Goals

1. Fix a config bug affecting output format
2. Add write operations (create, update, delete) for tags, triggers, and variables
3. Contribute both improvements back to upstream via PRs

---

## Phase 1 — Bug Fix: output_format ignored (ready to PR upstream)

### Problem
`~/.gtm-cli/config.yaml` supports `output.format: json` but it is never applied. The default in `src/gtm_cli/cli/main.py:106` is hardcoded to `OutputFormat.TABLE`, overriding whatever the user set in config.

### Fix (already implemented locally)
- Changed `output_format` parameter default from `OutputFormat.TABLE` to `None`
- In the callback, when `output_format is None`, read `config_manager.get_global_config().output.format`
- Falls back to `table` if config is absent

### Deliverable
- Clean commit following Conventional Commits: `fix: read output format default from config.yaml`
- Unit test covering the config-driven default
- PR to `oppianmatt/gtm-cli`

---

## Phase 2 — Write Operations

### Problem
The CLI has no `create`, `update`, or `delete` commands for tags, triggers, or variables. All write operations require the GTM web UI or direct API calls.

### Scope

#### Tags
```
gtm tag create   --name <name> --type <type> [--json <payload>] [--trigger <id>...]
gtm tag update   <tag-id> [--name <name>] [--json <payload>]
gtm tag delete   <tag-id>
```

#### Triggers
```
gtm trigger create  --name <name> --type <type> [--json <payload>]
gtm trigger update  <trigger-id> [--name <name>] [--json <payload>]
gtm trigger delete  <trigger-id>
```

#### Variables
```
gtm variable create  --name <name> --type <type> [--json <payload>]
gtm variable update  <variable-id> [--name <name>] [--json <payload>]
gtm variable delete  <variable-id>
```

### Input strategy

GTM entity payloads are complex (tag type + parameters array + consent settings). Two input modes:

**`--json <file-or-inline>`** — pass the full entity spec as a JSON object. Most flexible, supports all tag types.

**Named flags** — `--name`, `--type`, `--trigger` for the most common fields. Convenience shortcut for simple cases.

Both modes send the payload to the GTM API via the existing `GTMClient`.

### Confirmation prompts
`delete` commands require confirmation unless `--yes` / `-y` is passed (already a global flag).
`update` shows a diff of changed fields before applying.

### Implementation pattern (per entity)

1. Add API method to `core/client.py`:
   - `create_tag(account_id, container_id, workspace_id, body) -> dict`
   - `update_tag(account_id, container_id, workspace_id, tag_id, body) -> dict`
   - `delete_tag(account_id, container_id, workspace_id, tag_id) -> None`

2. Add CLI commands to `cli/tags.py` following the existing `list` / `get` pattern:
   - Use `get_state()`, `resolve_*` helpers, `get_client()`
   - Output via `output()` / `print_success()` / `print_error()`

3. Write tests in `tests/unit/` — mock `GTMClient` methods

4. Repeat for triggers (`cli/triggers.py`) and variables (`cli/variables.py`)

### GTM API reference

| Operation | Method | Endpoint |
|-----------|--------|----------|
| Create tag | `POST` | `accounts/{a}/containers/{c}/workspaces/{w}/tags` |
| Update tag | `PUT` | `accounts/{a}/containers/{c}/workspaces/{w}/tags/{tagId}` |
| Delete tag | `DELETE` | `accounts/{a}/containers/{c}/workspaces/{w}/tags/{tagId}` |
| Create trigger | `POST` | `accounts/{a}/containers/{c}/workspaces/{w}/triggers` |
| Update trigger | `PUT` | `accounts/{a}/containers/{c}/workspaces/{w}/triggers/{triggerId}` |
| Delete trigger | `DELETE` | `accounts/{a}/containers/{c}/workspaces/{w}/triggers/{triggerId}` |
| Create variable | `POST` | `accounts/{a}/containers/{c}/workspaces/{w}/variables` |
| Update variable | `PUT` | `accounts/{a}/containers/{c}/workspaces/{w}/variables/{variableId}` |
| Delete variable | `DELETE` | `accounts/{a}/containers/{c}/workspaces/{w}/variables/{variableId}` |

---

## Delivery

| Phase | Commit type | Target |
|-------|-------------|--------|
| 1 — config fix | `fix:` | PR to upstream + damupi fork |
| 2a — tag write ops | `feat:` | damupi fork → propose upstream when stable |
| 2b — trigger write ops | `feat:` | damupi fork |
| 2c — variable write ops | `feat:` | damupi fork |

## Non-goals

- No MCP layer
- No publishing / version management (already covered by `gtm version` commands)
- No template creation (out of scope for this fork)
