---
name: gtm-cli
description: Interact with Google Tag Manager using the gtm CLI. Use for inspecting or managing accounts, containers, workspaces, versions, environments, tags, triggers, variables, built-in variables, and Custom Templates, including validation and controlled publishing workflows.
---

# GTM CLI (`gtm`)

## Scope

This portable skill provides the non-obvious operating rules and safety constraints that span multiple commands. Use `gtm --help` and nested `gtm <group> <command> --help` output as the authority for the installed version's exact command syntax. Load the relevant file under `references/` only when working with that resource.

Keep company-specific account IDs, naming rules, ticket workflows, and implementation conventions in a separate organization-specific skill. Keep this skill versioned with the CLI and review it whenever command behavior changes.

## Rules

- **Global flags go BEFORE the subcommand** — `-a`, `-c`, `-w`, `-f`, `-y` (and `-u`, `-p`, `-s`, `-v`) are options on `gtm` itself, not on subcommands.
  ```bash
  gtm -a 123456789 -c 8983761 workspace list   # ✓ correct
  gtm workspace list --account-id 123456789     # ✗ wrong — "No such option" error
  ```
- **Check `--help` first** before assuming a subcommand exists or a flag is available — don't guess by analogy (e.g. `tag search` exists, `variable search` does not). Build/update entities via `--param` (key:value), `--param-file` (key:path, `variable` only), or dedicated flags like `--html-file`/`--file`. For nested structures `--param` can't express, `tag update`, `trigger update`, `variable create`, and `variable update` accept `--json-file PATH` (top-level merge patch: supplied arrays replace exactly, omitted fields preserved, identity fields ignored; on `variable create` the patch merges onto the body seeded from `--name`/`--type`) — there is no `--json` inline flag (file only), and `tag create`/`trigger create` still take no JSON at all. `variable create`/`update --json-file` is the only way to build the nested `list`-of-`map` parameters required by Lookup Table (`smm`) / RegEx Table (`remm`) variables.
- **`-y`/`--yes` confirmation skip is inconsistent across resources**: `variable`, `template`, and `environment` mutations expose a subcommand `--yes`; built-in-variable enable/disable do too. `tag` and `trigger` deletion require the global `gtm -y ...` form. The global flag also works for other mutations. Verify the specific nested `--help` instead of assuming.
- **Never use `2>&1`** when piping `gtm` output to a JSON parser (`jq`, `python3`, etc.) — stderr mixed into stdout breaks JSON parsing. Let errors surface naturally.
- **Never wrap `gtm` calls in `subprocess.run()` or Python** — invoke `gtm` directly through the host environment's shell.
- Use `jq` for JSON filtering, not inline Python one-liners.
- **No defensive fallbacks** (`|| fallback`, `2>/dev/null`) — write the correct command once; if it fails, surface the error and fix it.
- **Never run `workspace publish` without explicit user approval** of the exact version name and description — publishing goes live on the container. Run `workspace quick-preview` first, show the proposed name/description, and wait for a clear "yes". Do not infer approval from context.
- **`--dry-run` version-dependent**: as of gtm-cli versions shipping PR #27 (fix: honor --dry-run in all mutating commands), `--dry-run` is honored on every `create`/`update`/`delete`/`publish`/`enable`/`disable` command — it prints "DRY RUN: Would ..." and exits without calling the API. **Before relying on it, verify on a throwaway/reversible resource first** — on gtm-cli versions before that fix, `--dry-run` was silently a no-op and mutating commands executed for real regardless of the flag (confirmed data loss: a `--dry-run -y environment delete` actually deleted the environment). Check `gtm --version` or run one no-op-safe test if in doubt.

---

## Auth check (always first)

```bash
gtm account list
```

- Returns accounts → authenticated, proceed.
- Fails → run `gtm init ~/.config/gtm-cli/client_secrets.json`.

## Global flags (must precede the subcommand)

| Flag | Short | Description |
|------|-------|-------------|
| `--account-id` | `-a` | GTM account ID |
| `--container-id` | `-c` | GTM container ID (numeric, not GTM-XXXX) |
| `--workspace-id` | `-w` | GTM workspace ID |
| `--format` | `-f` | Output format: `json`, `yaml`, `table`, `plain` |
| `--yes` | `-y` | Skip confirmation prompts globally; required before `tag`/`trigger` deletion because those delete subcommands have no local `--yes` |
| `--dry-run` | | Preview a mutating command without calling the API — see the `--dry-run` rule above about verifying it's actually honored on your installed version |

---

## Accounts & containers

```bash
gtm account list
gtm -a 123456789 account get

gtm -a 123456789 container list
gtm -a 123456789 -c 8983761 container get
```

The numeric `containerId` is used in all subsequent calls. `publicId` is the human-readable `GTM-XXXX` code.

## Workspaces

```bash
gtm -a 123456789 -c 8983761 workspace list
gtm -a 123456789 -c 8983761 workspace get 3           # workspace_id is optional — omit to use the default
gtm -a 123456789 -c 8983761 -w 3 workspace status
gtm -a 123456789 -c 8983761 -w 3 workspace status --detail   # include consent-setting specifics
gtm -a 123456789 -c 8983761 -w 3 workspace publish --name "v42 Description" --notes "What changed"
gtm -a 123456789 -c 8983761 -w 3 workspace quick-preview     # server-side compile check — no version created, no browser
gtm -a 123456789 -c 8983761 -w 3 -f json workspace quick-preview   # full API response (compilerError, syncStatus, simulated containerVersion)
gtm -a 123456789 -c 8983761 -w 3 workspace preview           # opens GTM preview mode in the browser (Tag Assistant URL — NOT a validation)
gtm -u 1 workspace preview                                    # authuser for multi-account Google sessions

# create / delete take --account-id/-a and --container-id/-c as THEIR OWN subcommand
# flags too (in addition to the usual global ones) — an exception to the "global flags
# only" rule, because you may want to target a different container without changing
# your profile default.
gtm workspace create --name "My Feature" --description "Work for Q3 campaign"
gtm workspace create --container-id 8983761 --name "quick-picker"
gtm workspace delete --workspace-id 1000796 --container-id 8983761        # --workspace-id is required here, not positional
gtm workspace delete --workspace-id 1000796 --container-id 8983761 --yes  # this subcommand DOES take its own --yes
```

> **Limit:** GTM allows max **3 workspaces** per container — `workspace create` checks the count and stops before hitting the API if already at 3. Delete an existing workspace first.
> **Deleting a workspace is irreversible.**

`workspace status` returns a `workspaceChange` array where each entry's `changeStatus` is `added`, `deleted`, or `updated`.

### Validate before publishing — `workspace quick-preview`

`workspace quick-preview` calls the API's `quick_preview` endpoint: it compiles the workspace server-side into a simulated container version and reports validation errors **without creating a version and without opening a browser**. Exits non-zero when the workspace fails to compile, so it can gate scripts. Don't confuse it with `workspace preview`, which only opens the Tag Assistant preview URL and validates nothing.

**Always run `workspace quick-preview` after making workspace changes and before `workspace publish`.** If it fails, fix the reported errors instead of publishing.

## Built-in variables

```bash
gtm -a 123456789 -c 8983761 -w 3 built-in-variable list
gtm -a 123456789 -c 8983761 -w 3 built-in-variable enable analyticsSessionId analyticsSessionNumber analyticsClientId
gtm -a 123456789 -c 8983761 -w 3 built-in-variable disable analyticsSessionId
```

- Types are the API's camelCase enums (`analyticsSessionId`, `clickUrl`, `pageUrl`, …) — pass them verbatim; multiple types per call are fine.
- `enable`/`disable` are workspace mutations and prompt for confirmation – skip with either the global `gtm -y ...` form or their subcommand `--yes` option.
- Built-ins referenced in tags/triggers as `{{Click URL}}` etc. must be enabled in the workspace or the container won't resolve them.

## Versions

```bash
# List published versions (lightweight — no full tag/trigger/variable lists)
gtm -a 123456789 -c 8983761 -f json version list

# Filter by publish date (useful for incident investigation)
gtm -a 123456789 -c 8983761 version list --since 2025-06-01
gtm -a 123456789 -c 8983761 version list --since 2025-06-01 --until 2025-06-30

# Full version snapshot (includes complete tag[], trigger[], variable[] arrays)
# version_id is positional, not a --version-id flag
gtm -a 123456789 -c 8983761 version get 42

# Diff two published versions — additions/removals/modifications across
# tags, triggers, and variables. Also useful for incident investigation.
gtm -a 123456789 -c 8983761 version diff 42 43
gtm -a 123456789 -c 8983761 version diff 100 105 -f json
```

`version list` returns lightweight headers (`numTags`, `numTriggers`, `numVariables` counts, no entity arrays). `version get` returns the full snapshot: `tag[]`, `trigger[]`, `variable[]`. To **publish** a new version, use `workspace publish` above — there's no `version create`.

## Environments

Container-scoped (`-a`/`-c` only — **no** `-w`/`--workspace-id`). Used to link a container version or a live workspace to a stable, user-defined URL/environment (e.g. for pre-production QA before promoting a version to Live).

```bash
gtm -a 123456789 -c 8983761 environment list
gtm -a 123456789 -c 8983761 environment get 5

# create: exactly ONE of --container-version-id / --workspace-id is required — giving
# both or neither fails locally before any API call
gtm -a 123456789 -c 8983761 environment create \
  --name "Playwright QA" --description "Automated tracking QA" \
  --url "https://www.example.com/" --container-version-id 42 --enable-debug

gtm -a 123456789 -c 8983761 environment create \
  --name "Live workspace preview" --workspace-id 3

gtm -a 123456789 -c 8983761 environment delete 5
gtm -a 123456789 -c 8983761 environment delete 5 --yes
# The global form also works:
gtm -a 123456789 -c 8983761 -y environment delete 5
```

- No `environment update` or `environment reauthorize` — not implemented (issue #24 scoped list/get/create/delete only).
- `environment delete` refuses non-`user` environments (`live`, `latest`, auto-managed `workspace` type) with an error — only environments you created yourself can be deleted.
- `environment get` and `environment create` in `table`/`plain` format **redact `authorizationCode`**; use `-f json` or `-f yaml` to see the real value (needed for Tag Assistant / automation URLs).
- **`authorizationCode` is a credential — never paste the real value into a commit, PR/issue comment, chat report, or any other persisted artifact.** Default to redacted (table/plain) output when demonstrating or verifying behavior; only use `-f json`/`-f yaml` when the real value is actually needed for the task at hand (e.g. building a Tag Assistant URL), and don't echo that output anywhere it gets committed or posted.

---

## Typical workflow

```bash
# 1. Find the account and container
gtm account list
gtm -a 123456789 container list

# 2. Check workspaces (confirm < 3 exist)
gtm -a 123456789 -c 8983761 -f json workspace list

# 3. Inspect current workspace state
gtm -a 123456789 -c 8983761 -w 3 workspace status
gtm -a 123456789 -c 8983761 -w 3 -f json tag list
gtm -a 123456789 -c 8983761 -w 3 -f json trigger list
gtm -a 123456789 -c 8983761 -w 3 -f json variable list

# 4. Validate the workspace compiles (after any changes, before publish)
gtm -a 123456789 -c 8983761 -w 3 workspace quick-preview

# 5. Publish — ONLY with explicit user approval of the exact version name and
#    description, and only after quick-preview passed. Never publish on inferred
#    or prior-context approval; stop and ask for a clear "yes" first.
gtm -a 123456789 -c 8983761 -w 3 workspace publish --name "v43 Feature description"

# 6. Verify
gtm -a 123456789 -c 8983761 -f json version list
```

---

## Specific tasks

- **Tags** (list, search, compare, get, create, update, pause/unpause, delete, audit-*) — [references/tags.md](references/tags.md)
- **Triggers** (list, get, create, update [`--name` and `--json-file` for filters/type], delete) — [references/triggers.md](references/triggers.md)
- **Variables** (list, get [clean "not found" error, no traceback], types, create [`--json-file` for nested params], update [`--json-file`, same merge semantics], delete, revert) — [references/variables.md](references/variables.md)
- **Custom Templates** (sandboxed JS `.tpl`: list, get, create, update, delete) — [references/templates.md](references/templates.md)
