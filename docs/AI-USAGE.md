# gtm-cli — AI Agent Usage Guide

Reference for AI agents using the `gtm` CLI. Covers the non-obvious behaviors that `--help` does not explain.

---

## The one rule that breaks everything if missed

**Global flags (`-a`, `-c`, `-w`, `-f`) must go BEFORE the subcommand.**

They are options on `gtm` itself, not on subcommands. Subcommands accept no flags except `--help`.

```bash
# ✓ correct
gtm -a 3116374124 -c 8983761 workspace list
gtm -a 3116374124 -c 8983761 -w 3 -f json variable list

# ✗ wrong — "No such option" error
gtm workspace list --account-id 3116374124
gtm variable list --format json
```

| Flag | Short | Description |
|------|-------|-------------|
| `--account-id` | `-a` | GTM account ID (numeric) |
| `--container-id` | `-c` | GTM container ID (numeric, not GTM-XXXX) |
| `--workspace-id` | `-w` | GTM workspace ID |
| `--format` | `-f` | `json` / `yaml` / `table` / `plain` |

---

## Auth

```bash
gtm account list        # returns accounts → authenticated
```

If unauthenticated:
```bash
gtm init ~/.config/gtm-cli/client_secrets.json
```

---

## Discover commands

The CLI is self-describing. When unsure whether a subcommand or flag exists:

```bash
gtm --help
gtm variable --help
gtm variable update --help
```

Do not guess syntax by analogy. `tag search` exists; `variable search` does not.

---

## Never use Python or 2>&1

```bash
# ✓ correct — pipe clean stdout to jq
gtm -a 123 -c 456 -w 3 -f json variable list | jq '.[].name'

# ✗ wrong — stderr mixed into stdout breaks JSON
gtm variable list --format json 2>&1 | jq ...

# ✗ wrong — never wrap in subprocess.run() or python3 -c
python3 -c "import subprocess; subprocess.run(['gtm', ...])"
```

---

## GTM variable references in JavaScript

Inside JS/HTML, GTM variables are referenced with **double curly brackets**: `{{variableName}}`. These are resolved by GTM at runtime. Always pass them through verbatim — never escape or modify them.

```javascript
function() {
  var deviceType = {{CJS - deviceType}};
  var containerId = {{Container ID}};
  return deviceType === 'm';
}
```

When writing a JS body to a temp file for `--param-file`, `{{...}}` references must be preserved exactly.

---

## Custom JavaScript variables — always use `--param-file`

**Never pass JavaScript inline via `--param` or `--json`.** Shell quoting silently corrupts multi-line strings. The CLI will succeed but the variable body will be broken.

```bash
# ✓ correct — write JS to a file, pass via --param-file
cat > /tmp/my_var.js << 'EOF'
function() {
  var x = window.something;
  return x || 'default';
}
EOF
gtm -a 123 -c 456 -w 3 variable update 789 --param-file javascript:/tmp/my_var.js

# ✗ wrong — shell corrupts multi-line JS silently
gtm variable update 789 --param 'javascript:function() { ... }'
gtm variable update 789 --json '{"parameter": [{"key": "javascript", "value": "function() {...}"}]}'
```

This applies to both `variable create` and `variable update` for `jsm` (Custom JavaScript) type variables.

---

## Variable types

| Type | Name | Key parameter(s) |
|------|------|-----------------|
| `v` | Data Layer Variable | `name`, `dataLayerVersion` |
| `u` | URL | `component` (`PATH`, `HOST`, `QUERY`) |
| `k` | First-Party Cookie | `name` |
| `c` | Constant | `value` |
| `j` | JavaScript Variable | `name` (global JS variable) |
| `jsm` | Custom JavaScript | `javascript` — use `--param-file` |
| `e` | Auto-Event Variable | `varType` (`ELEMENT`, `ATTRIBUTE`, etc.) |
| `r` | HTTP Referrer | `component` |
| `smm` | Lookup Table | `input`, `map` |

---

## Typical workflow

```bash
# 1. Find account and numeric container ID
gtm account list
gtm -a 3116374124 container list       # note numeric ID, not GTM-XXXX

# 2. Check workspaces (max 3 per container)
gtm -a 3116374124 -c 8983761 workspace list

# 3. Create a workspace
gtm -a 3116374124 -c 8983761 workspace create --name "My workspace" --description "https://..."

# 4. Inspect entities in a workspace
gtm -a 3116374124 -c 8983761 -w 3 -f json variable list
gtm -a 3116374124 -c 8983761 -w 3 variable get 789

# 5. Update a Custom JS variable
cat > /tmp/updated.js << 'EOF'
function() {
  // your code here
}
EOF
gtm -a 3116374124 -c 8983761 -w 3 variable update 789 --param-file javascript:/tmp/updated.js

# 6. Check pending changes before publishing
gtm -a 3116374124 -c 8983761 -w 3 workspace status

# 7. Publish (only with explicit user approval)
gtm -a 3116374124 -c 8983761 -w 3 workspace publish --name "v42 — description of change"
```

---

## GTM UI deep links

After any write operation, give the user a review link:

| Resource | URL pattern |
|----------|-------------|
| Workspace | `https://tagmanager.google.com/#/container/accounts/{accountId}/containers/{containerId}/workspaces/{workspaceId}` |
| Variable | `https://tagmanager.google.com/#/container/accounts/{accountId}/containers/{containerId}/workspaces/{workspaceId}/variables/{variableId}` |
| Version | `https://tagmanager.google.com/#/container/accounts/{accountId}/containers/{containerId}/versions/{versionId}` |

`containerId` in the URL is the numeric ID, not `GTM-XXXX`.

---

## Workspace limit

GTM enforces a maximum of **3 workspaces** per container. Always check count before creating:

```bash
gtm -a 3116374124 -c 8983761 workspace list
```

If at 3, stop and ask the user to delete one before proceeding.
