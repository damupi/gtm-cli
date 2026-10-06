# Variables

```bash
gtm variable <command> [flags]
```

> **`get`, `update`, `delete` take a positional ID — not a `--variable-id` flag.** Run `gtm variable <command> --help` if unsure.
> **There is no inline `--json` flag** — but `create`/`update` accept `--json-file PATH` for nested structures (see below). Simple config goes through `--param` (key:value) / `--param-file` (key:path, for multi-line JS/HTML).
> **`variable get` on a nonexistent ID prints a clean `Variable '<id>' not found` error and exits 1** — no raw traceback.

## Commands

| Command | Description |
|---------|-------------|
| `variable list` | List all variables in the workspace |
| `variable get <variable-id>` | Get full details of a specific variable |
| `variable create` | Create a new variable |
| `variable update <variable-id>` | Update an existing variable (merges changes) |
| `variable delete <variable-id>` | Delete a variable (prompts for confirmation unless `--yes`) |

## Options

### `variable create` / `variable update`

Run `gtm variable create --help` / `gtm variable update --help` for the full flag reference.

> **CRITICAL — shell quoting:** Never pass JavaScript or HTML inline via `--param javascript:<code>`. The shell corrupts multi-line strings before Python receives them. Always write JS/HTML to a file and use `--param-file javascript:<path>`.

> **`--json-file PATH`** — top-level merge patch, for structures `--param`/`--param-file` can't express (they only upsert flat key:value entries into the `parameter` array). The file need only contain the fields to change; arrays (e.g. `parameter`) REPLACE wholesale; omitted fields are preserved; identity fields (`accountId`, `containerId`, `workspaceId`, `variableId`, `path`, `fingerprint`) in the file are ignored with a warning, not an error. Applied FIRST, then any `--param`/`--param-file`/`--name`/`--notes` flags are applied on top (on `create`, those flags fully rebuild `parameter` from scratch, so combining `--json-file` with `--param` on `create` lets `--param` clobber the JSON-seeded array — don't combine them on `create` if the JSON already seeds `parameter`). This is the only way to build the nested `list`-of-`map` structure required by Lookup Table (`smm`) / RegEx Table (`remm`) variables.

### `variable delete` / `variable update` / `variable revert`

| Flag | Default | Description |
|------|---------|-------------|
| `--yes`, `-y` | false | Skip confirmation prompt (this one **is** a subcommand flag, unlike `tag`/`trigger`/`template` delete) |

`variable revert` also takes `--fingerprint TEXT` for optimistic concurrency.

## Common variable types

| Type | Description | Key parameter |
|------|-------------|---------------|
| `v` | Data Layer Variable | `name` (DL key), `dataLayerVersion` (`1` or `2`; create/type-conversion default: `2`) |
| `u` | URL | `component` (e.g. `PATH`, `HOST`, `QUERY`) |
| `k` | First-Party Cookie | `name` (cookie name) |
| `c` | Constant | `value` |
| `j` | JavaScript Variable | `name` (global variable name) |
| `jsm` | Custom JavaScript | `javascript` (function body) |
| `e` | Auto-Event Variable | `varType` (e.g. `ELEMENT`, `ATTRIBUTE`) |
| `r` | HTTP Referrer | `component` |
| `smm` | Lookup Table | `input`, `map` |
| `gas` | Google Analytics Settings (legacy) | `trackingId` |

## Response structure

### `variable list`

```json
[
  {
    "variable_id": "12",
    "name": "DLV - event",
    "type": "v"
  }
]
```

### `variable get` (full object)

```json
{
  "variableId": "12",
  "name": "DLV - event",
  "type": "v",
  "parameter": [
    { "type": "integer", "key": "dataLayerVersion", "value": "2" },
    { "type": "template", "key": "name", "value": "event" }
  ],
  "fingerprint": "1710234567890",
  "path": "accounts/123456789/containers/8983761/workspaces/3/variables/12"
}
```

## Examples

```bash
# List all variables
gtm -f json variable list

# Get full details
gtm variable get 12

# Create a Data Layer Variable (dataLayerVersion defaults to integer Version 2)
gtm variable create --name "DLV - event" --type v --param name:event

# Select Version 1 explicitly (only 1 or 2 are accepted)
gtm variable create --name "DLV - legacy event" --type v \
  --param dataLayerVersion:1 --param name:event

# Existing DLV updates preserve an omitted version; set it only when intended
gtm variable update 12 --param dataLayerVersion:2

# Create a Constant variable
gtm variable create --name "CONST - GA4 ID" --type c --param value:G-XXXXXXXXXX

# Create a Custom JavaScript variable — always use --param-file for JS content
# (never embed JS inline in --json or --param: shell quoting corrupts multi-line strings)
cat > /tmp/jsv_page_type.js << 'EOF'
function() {
  return document.body.dataset.pageType || 'unknown';
}
EOF
gtm variable create --name "JSV - Page Type" --type jsm --param-file javascript:/tmp/jsv_page_type.js

# Update a Custom JavaScript variable body
cat > /tmp/updated.js << 'EOF'
function() {
  // GTM {{variableName}} references pass through verbatim — do not escape them
  var deviceType = {{CJS - deviceType}};
  return deviceType;
}
EOF
gtm variable update 12 --param-file javascript:/tmp/updated.js

# Update a variable name only (no JS involved — --param is safe for simple scalar values)
gtm variable update 12 --name "DLV - event (renamed)"

# Delete a variable
gtm variable delete 12 --yes

# Build a Lookup Table (smm) with a nested list-of-map parameter --param can't express
cat > /tmp/lookup_row.json << 'EOF'
{
  "parameter": [
    {
      "type": "list",
      "key": "map",
      "list": [
        {
          "type": "map",
          "map": [
            {"type": "template", "key": "key", "value": "somehost\\.com"},
            {"type": "template", "key": "value", "value": "G-XXXXXXX"}
          ]
        }
      ]
    }
  ]
}
EOF
gtm variable create --name "RegEx Table - Host to Measurement ID" --type smm --json-file /tmp/lookup_row.json

# Add another row later — the file must include ALL rows (arrays replace wholesale, no per-element merge)
gtm variable update 12 --json-file /tmp/lookup_rows_updated.json
```
