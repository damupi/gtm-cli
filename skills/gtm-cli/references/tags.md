# Tags

```bash
gtm tag <command> [flags]
```

> **`get`, `update`, `delete` take a positional ID — not a `--tag-id` flag.** Run `gtm tag <command> --help` if unsure.
> **`tag create` has no `--json` flag** — config goes through `--param` (upsert key:value into the `parameter` array) or dedicated flags (`--html`, `--html-file`, `--trigger-id`, `--folder-id`, `--notes`, `--consent-type`). `--param-file` exists on `variable`, not on `tag`.
> **`tag update` additionally supports `--json-file PATH`** for nested structures `--param` can't express (e.g. GA4 `userProperties` list/map values): merges the file's top-level fields onto the fetched tag; supplied arrays (`parameter`, …) REPLACE exactly; omitted fields (consentSettings, firing/blocking triggers, firingOption, …) are preserved. Identity fields (`accountId`, `tagId`, `path`, `fingerprint`, …) are ignored with a warning. Merge applies first, then other flags (`--name`, `--param`, …) layer on top.
> **`--consent-type` is NOT `--param`.** `--consent-type` sets the Tag resource's top-level `consentSettings` field (GTM UI: Advanced Settings → Consent Settings → Additional Consent Checks) — the gate that blocks the tag from firing until the listed consent categories are granted. `--param` only touches the tag's own `parameter` array (e.g. a tag's own Consent Mode signal values like `analytics_storage:denied`). These are unrelated GTM concepts that happen to share vocabulary — don't use one flag to try to set the other.

## Commands

| Command | Description |
|---------|-------------|
| `tag list` | List all tags in the workspace |
| `tag search [query]` | Case-insensitive name search, or `--trigger`/`--type` filter |
| `tag get <tag-id>` | Get full details of a specific tag |
| `tag compare <id> <id>` | Compare two tags, or `--trigger`/`--folder` groups, side by side |
| `tag create` | Create a new tag |
| `tag update <tag-id>` | Update an existing tag (merges changes — only specified fields change) |
| `tag pause <tag-id>...` | Pause one or more tags |
| `tag unpause <tag-id>...` | Unpause one or more tags |
| `tag delete <tag-id>` | Delete a tag (prompts for confirmation unless global `-y`) |
| `tag audit-consent` | Find tags with consent configuration issues |
| `tag audit-pixels` | Audit Custom HTML tags for async loading and duplicate pixels |
| `tag audit-params` | Show event parameters sent by tracking tags |
| `tag audit-setup-deps` | Find broken setup/teardown tag dependencies |

## Options

### `tag list`

| Flag | Default | Description |
|------|---------|-------------|
| `--sort`, `-s` | `modified` | Sort by: `name`, `type`, `triggers`, `folder`, `modified` |
| `--reverse`, `-r` | false | Reverse sort order |

### `tag search`

| Flag | Default | Description |
|------|---------|-------------|
| `--type`, `-t` | *(none)* | Filter by tag type (e.g. `html`, `googtag`) |
| `--trigger` | *(none)* | Filter by firing trigger ID or name (substring match) |
| `--exclude-paused` | false | Exclude paused tags |

### `tag create`

| Flag | Default | Description |
|------|---------|-------------|
| `--name`, `-n` | *(required)* | Tag name |
| `--type`, `-t` | `html` | Tag type |
| `--html` | — | Inline HTML content for Custom HTML tags |
| `--html-file` | — | Path to file with HTML content (mutually exclusive with `--html`) |
| `--trigger-id` | *(repeatable)* | Firing trigger ID |
| `--folder-id` | — | Parent folder ID |
| `--once-per-event` / `--unlimited` | once-per-event | Tag firing option |
| `--param` | *(repeatable)* | Set `key:value` into the `parameter` array. **Required for Community/Custom Template tags** (`--type cvt_*`) that have required template fields — the API rejects the create with no fallback to the template's own `defaultValue` when the field is absent |
| `--notes` | — | Notes describing the tag |
| `--consent-type` | *(repeatable)* | Additional Consent Check category — sets top-level `consentSettings`, not a `parameter`. One of: `ad_storage`, `ad_user_data`, `ad_personalization`, `analytics_storage`, `functionality_storage`, `personalization_storage`, `security_storage` |

### `tag update`

| Flag | Default | Description |
|------|---------|-------------|
| `--name`, `-n` | — | New tag name |
| `--html` / `--html-file` | — | Replace HTML content (mutually exclusive) |
| `--trigger-id` | *(repeatable)* | **Replaces ALL** firing trigger IDs — not additive |
| `--folder-id` | — | Move to folder ID |
| `--clear-setup-tag` | false | Remove all setupTag dependencies |
| `--clear-teardown-tag` | false | Remove all teardownTag dependencies |
| `--param` | *(repeatable)* | Upsert `key:value` into the `parameter` array (updates matching key, appends if new) |
| `--json-file` | — | Path to a JSON object with only the fields to change; arrays replace exactly, omitted fields preserved (see note above) |
| `--notes` | — | Set notes (pass `--notes ''` to clear) |
| `--consent-type` | *(repeatable)* | **Replaces ALL** Additional Consent Check categories — sets top-level `consentSettings`, not additive, not a `parameter`. Same 7 values as `tag create` above |
| `--clear-consent-type` | false | Remove Additional Consent Checks entirely (consent status reverts to "not needed") |

### `tag delete`

No subcommand flags. Confirmation prompt is skipped with the **global** `-y`/`--yes` flag (before `tag`, not after `delete`):
```bash
gtm -y tag delete 421     # ✓ correct — global flag before subcommand
gtm tag delete 421 --yes  # ✗ wrong — no such option on this subcommand
```

## Common tag types

| Type | Description |
|------|-------------|
| `html` | Custom HTML tag |
| `googtag` | Google tag (gtag.js) |
| `awct` | Google Ads Conversion Tracking |
| `sp` | Google Ads Remarketing |
| `flc` | Floodlight Counter |
| `fls` | Floodlight Sales |
| `ua` | Universal Analytics (legacy) |

## Response structure

### `tag list` / `tag search`

```json
[
  {
    "name": "GA4 - Pageview",
    "type": "googtag",
    "triggers": "All Pages",
    "folder": "-",
    "modified": "2 days ago",
    "paused": ""
  }
]
```

### `tag get` (full object)

```json
{
  "tagId": "42",
  "name": "GA4 - Pageview",
  "type": "googtag",
  "parameter": [
    { "type": "template", "key": "measurementId", "value": "G-XXXXXXXXXX" }
  ],
  "firingTriggerId": ["2147479553"],
  "tagFiringOption": "oncePerEvent",
  "notes": "Optional free-text notes"
}
```

## Examples

```bash
# List all tags
gtm -f json tag list --sort name

# Search for TikTok tags
gtm tag search tiktok

# Search for Custom HTML tags containing "pixel"
gtm tag search pixel --type html

# All tags firing on a given trigger
gtm tag search --trigger 62
gtm tag search --trigger "Booking"

# Get full details
gtm tag get 42

# Compare two tags, or all tags in given folders
gtm tag compare 298 17
gtm tag compare --folder tiktok --folder facebook

# Create a Custom HTML tag
gtm tag create --name "Meta Pixel - Base" --html-file pixel.html --trigger-id 2147479553 --folder-id 409

# Create with inline HTML (single-line only — see variables.md shell-quoting warning)
gtm tag create --name "Test" --html '<script>console.log("hi")</script>'

# Create a Community/Custom Template tag (cvt_*) — --param sets required template fields
# (e.g. the Intercom template's required "method" SELECT param); the API rejects the
# create with no way to fix up afterward if a required field is left unset
gtm tag create --name "Intercom" --type cvt_TXZXG --param method:install --trigger-id 2147479553

# Rename a tag
gtm tag update 42 --name "Meta Pixel - Base (Updated)"

# Update a config parameter (e.g. Consent Mode signal) without touching HTML
gtm tag update 508 --param wait_for_update:500
gtm tag update 508 --param command:update --param analytics_storage:denied

# Set Additional Consent Checks (top-level consentSettings, NOT --param) — tag won't
# fire until the listed categories are granted
gtm tag create --name "Intercom" --html-file intercom.html --consent-type functionality_storage
gtm tag update 421 --consent-type ad_storage --consent-type analytics_storage
gtm tag update 421 --clear-consent-type

# Replace all firing triggers
gtm tag update 421 --trigger-id 295 --trigger-id 296

# Set / clear notes
gtm tag update 421 --notes "Workaround for consent gate; see WEBDATA-983"
gtm tag update 421 --notes ''

# Pause / unpause
gtm tag pause 304
gtm tag unpause 298 302 303

# Delete (confirmation prompt — global -y to skip)
gtm tag delete 42
gtm -y tag delete 42

# Audit tags for issues
gtm tag audit-consent
gtm tag audit-pixels
gtm tag audit-params
gtm tag audit-setup-deps
```
