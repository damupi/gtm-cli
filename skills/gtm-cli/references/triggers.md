# Triggers

```bash
gtm trigger <command> [flags]
```

> **`get`, `update`, `delete` take a positional ID — not a `--trigger-id` flag.** Run `gtm trigger <command> --help` if unsure.
> **On create there is no `--json` flag.** Config goes through `--param` (flat `key:value`, repeatable) or, for `customEvent` triggers, the dedicated `--event-name` flag.
> **`trigger update` supports `--name` and `--json-file`.** `--json-file PATH` merges the file's top-level fields onto the fetched trigger: supplied arrays (`filter`, `customEventFilter`, `autoEventFilter`, …) REPLACE the existing array exactly; omitted fields are preserved; `type` can be changed (e.g. `click` → `linkClick`). Identity fields (`accountId`, `triggerId`, `path`, `fingerprint`, …) in the file are ignored with a warning, so a patch derived from an edited `gtm -f json trigger get` dump just works. The merge applies first, then `--name` on top.

## Commands

| Command | Description |
|---------|-------------|
| `trigger list` | List all triggers in the workspace |
| `trigger get <trigger-id>` | Get full details of a specific trigger |
| `trigger create` | Create a new trigger |
| `trigger update <trigger-id>` | Update a trigger: `--name` and/or `--json-file` merge patch (filters, type, …) |
| `trigger delete <trigger-id>` | Delete a trigger (prompts for confirmation unless global `-y`) |

## Options

### `trigger create`

| Flag | Default | Description |
|------|---------|-------------|
| `--name`, `-n` | *(required)* | Trigger name |
| `--type`, `-t` | *(required)* | Trigger type (e.g. `timer`, `customEvent`, `pageview`) |
| `--param` | *(repeatable)* | Type-specific `key:value`. For `timer`, keys in `{interval, limit, eventName}` are placed top-level automatically; other keys go into the `parameter` array |
| `--event-name` | — | **Required when `--type customEvent`.** Builds the `customEventFilter` the API needs — do not try to pass the event name via `--param eventName:...`, the API rejects that |

`timer` triggers always get `eventName: gtm.timer` by default unless overridden via `--param eventName:...`.

### `trigger update`

| Flag | Default | Description |
|------|---------|-------------|
| `--name`, `-n` | — | New trigger name (applied after the `--json-file` merge, if both given) |
| `--json-file` | — | Path to a JSON object with only the fields to change; arrays replace exactly, omitted fields preserved |

### `trigger delete`

No subcommand flags. Confirmation prompt is skipped with the **global** `-y`/`--yes` flag (before `trigger`, not after `delete`):
```bash
gtm -y trigger delete 2147479553     # ✓ correct
gtm trigger delete 2147479553 --yes  # ✗ wrong — no such option on this subcommand
```

## Common trigger types

| Type | Description |
|------|-------------|
| `pageview` | Page View (DOM ready) |
| `windowLoaded` | Window Loaded |
| `domReady` | DOM Ready |
| `click` | All Elements Click |
| `linkClick` | Just Links Click |
| `formSubmission` | Form Submission |
| `customEvent` | Custom Event (dataLayer push) — needs `--event-name` |
| `historyChange` | History Change (SPA navigation) |
| `scrollDepth` | Scroll Depth |
| `timer` | Timer |
| `youTubeVideo` | YouTube Video |

## Response structure

### `trigger list`

```json
[
  {
    "trigger_id": "2147479553",
    "name": "All Pages",
    "type": "pageview"
  }
]
```

### `trigger get` (full object)

```json
{
  "triggerId": "2147479553",
  "name": "All Pages",
  "type": "pageview",
  "fingerprint": "1710234567890",
  "path": "accounts/123456789/containers/8983761/workspaces/3/triggers/2147479553"
}
```

### `customEvent` trigger body (what `--event-name` builds)

```json
{
  "name": "Event - my_event",
  "type": "customEvent",
  "customEventFilter": [
    {
      "type": "equals",
      "parameter": [
        { "type": "template", "key": "arg0", "value": "{{_event}}" },
        { "type": "template", "key": "arg1", "value": "my_event" }
      ]
    }
  ]
}
```

## Examples

```bash
# List all triggers
gtm -f json trigger list

# Get full details
gtm trigger get 2147479553

# Create an All Pages pageview trigger
gtm trigger create --name "All Pages" --type pageview

# Create a Timer trigger
gtm trigger create --name "Timer 5s" --type timer --param interval:5000 --param limit:1

# Create a Custom Event trigger — always use --event-name, not --param eventName:...
gtm trigger create --name "Event - my_event" --type customEvent --event-name my_event

# Rename a trigger
gtm trigger update 2147479553 --name "All Pages (Renamed)"

# Update a trigger's filters (and optionally type) via a JSON merge patch.
# The file contains ONLY the fields to change; arrays replace exactly.
cat > /tmp/trigger-patch.json << 'EOF'
{
  "type": "linkClick",
  "filter": [
    {
      "type": "matchRegex",
      "parameter": [
        { "type": "template", "key": "arg0", "value": "{{Click URL}}" },
        { "type": "template", "key": "arg1", "value": "instagram\\.com|facebook\\.com" },
        { "type": "boolean", "key": "ignore_case", "value": "true" }
      ]
    }
  ]
}
EOF
gtm trigger update 79 --json-file /tmp/trigger-patch.json

# Delete a trigger (confirmation prompt — global -y to skip)
gtm trigger delete 2147479553
gtm -y trigger delete 2147479553
```
