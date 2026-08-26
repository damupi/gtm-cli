# FEATURE — Make the CLI self-documenting (eliminate external skill dependency)

## Goal

An agent or engineer should be able to use `gtm` effectively using only `--help` output — no external skill file, no wiki, no mental overhead. The CLI should teach itself.

## Current gaps

### 1. Shell quoting warning missing from `--help`

The `--param` flag help text doesn't warn that it's unsafe for multi-line JS/HTML. An agent that reads `--help` will reach for `--param javascript:<code>` and corrupt the variable silently.

**Fix:** add a warning to the `--param` help string and/or the command docstring:

```python
typer.Option(
    "--param",
    help=(
        "Parameter as key:value (repeatable). "
        "WARNING: do not use for multi-line JS/HTML — shell quoting corrupts strings. "
        "Use --param-file instead."
    ),
)
```

Also add to the command docstring of `update` / `create`:

```
⚠  For Custom JavaScript variables, always use --param-file javascript:<path>.
   Passing JS inline via --param or --json corrupts multi-line code silently.
```

---

### 2. No examples in `--help` for the most common JS/HTML pattern

The `--help` output shows flags but no examples. Rich CLI help should show the canonical workflow inline.

**Fix:** add an `epilog` to the Typer command with copy-paste examples:

```python
@app.command("update", epilog="""
Examples:

  # Rename a variable
  gtm variable update 123 --name "New Name"

  # Update a Custom JavaScript variable body (always use --param-file for JS)
  cat > /tmp/my_var.js << 'EOF'
  function() { return document.title; }
  EOF
  gtm variable update 123 --param-file javascript:/tmp/my_var.js

  # Update notes
  gtm variable update 123 --notes "Updated by WEBDATA-123"
""")
```

---

### 3. No `variable types` subcommand

Agents and engineers frequently need to know what `--type` value to use and what parameters each type requires. Currently this requires reading source code or external docs.

**Fix:** add `gtm variable types` that prints the type registry:

```
$ gtm variable types

Type   Name                       Key parameters
-----  -------------------------  ---------------------------
v      Data Layer Variable        name, dataLayerVersion
u      URL                        component (PATH|HOST|QUERY)
k      First-Party Cookie         name
c      Constant                   value
j      JavaScript Variable        name
jsm    Custom JavaScript          javascript (use --param-file)
e      Auto-Event Variable        varType
r      HTTP Referrer              component
smm    Lookup Table               input, map
```

This makes the `--type` flag fully self-explaining without any external reference.

---

### 4. Silent success on corrupted JS write

When `--param javascript:<inline>` is used with multi-line code, the CLI succeeds but the variable is broken. No warning is emitted.

**Fix:** detect when a `--param` value for a `jsm`/`html` key contains newlines and emit a warning — or refuse with an error and redirect to `--param-file`:

```python
for key, value in param_map.items():
    if key in ("javascript", "html") and "\n" in value:
        print_error(
            f"--param {key}: multi-line value detected. "
            f"Use --param-file {key}:/path/to/file.js to avoid shell corruption."
        )
        raise typer.Exit(1)
```

This turns a silent corrupt-and-succeed into a clear actionable error.

---

### 5. `--param-file` path shown in success output

When a variable is updated via `--param-file`, the success message only shows the variable name. Showing which file was used helps with audit trails.

**Fix:**

```
✓ Updated variable 'CJS - IsBot' (ID: 1018) [javascript ← /tmp/isbot.js]
```

---

### 6. `workspace status` output doesn't link to GTM UI

After every write operation, agents need to give the user a review link. Currently they construct it manually from IDs.

**Fix:** print the GTM UI deep-link automatically after any create/update/delete:

```
✓ Updated variable 'CJS - IsBot' (ID: 1018)
  Review: https://tagmanager.google.com/#/container/accounts/3116374124/containers/8983761/workspaces/1000831/variables/1018
```

---

## Priority

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 4 | Error on inline JS/HTML in `--param` | Low | High — prevents silent corruption |
| 1 | Shell quoting warning in `--help` | Low | High — agents read `--help` first |
| 3 | `gtm variable types` subcommand | Medium | High — eliminates the types reference doc |
| 2 | Epilog examples in `--help` | Low | Medium — copy-paste patterns reduce errors |
| 6 | GTM UI link in success output | Low | Medium — agents stop constructing links manually |
| 5 | Source file in success output | Low | Low — nice audit trail |

## Related

- `BUG-variable-code-line-wrapping.md` — root cause this doc addresses
- `PRD.md` Phase 2 — write operations (same surface area)
