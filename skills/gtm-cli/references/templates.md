# Custom Templates

```bash
gtm template <command> [flags]
```

Custom Templates wrap sandboxed JavaScript with a declared permission model (cookie access, injected-script domains, etc.), unlike Custom HTML tags which have unrestricted `window`/`document` access. Use this group to create/import a `.tpl` (e.g. a GTM Community Template Gallery export) as a real sandboxed template instead of downgrading it to Custom HTML.

> **`get`, `update`, `delete` take a positional ID — not a `--template-id` flag.**
> **`create`/`update` always read the `.tpl` content from a file via `--file`** — there is no inline flag, since template bodies are large multi-line sandboxed JS.

## Commands

| Command | Description |
|---------|-------------|
| `template list` | List all Custom Templates in the workspace |
| `template get <template-id>` | Get full details (including `templateData`) of a specific template |
| `template create` | Create a new Custom Template from a `.tpl` file |
| `template update <template-id>` | Update a template's name and/or `.tpl` content |
| `template delete <template-id>` | Delete a template (prompts for confirmation unless `--yes` or global `-y`) |

## Options

### `template create`

| Flag | Default | Description |
|------|---------|-------------|
| `--name`, `-n` | *(required)* | Template display name |
| `--file` | *(required)* | Path to the `.tpl` file (must exist) |

### `template update`

| Flag | Default | Description |
|------|---------|-------------|
| `--name`, `-n` | — | New display name |
| `--file` | — | Path to a `.tpl` file with new content (replaces `templateData` entirely) |

At least one of `--name`/`--file` is required.

### `template delete`

Confirmation can be skipped with the subcommand `--yes`/`-y` option or the global `-y` flag:
```bash
gtm template delete 12 --yes
gtm -y template delete 12
```

## Response structure

### `template list`

```json
[
  { "template_id": "12", "name": "Attribution Cookie" }
]
```

### `template get` (full object)

```json
{
  "templateId": "12",
  "name": "Attribution Cookie",
  "templateData": "___INFO___\n{...}\n___SANDBOXED_JS_FOR_SERVER___\n...",
  "fingerprint": "1710234567890",
  "path": "accounts/123456789/containers/8983761/workspaces/3/templates/12"
}
```

## Examples

```bash
# List all Custom Templates
gtm -f json template list

# Get full details (including the raw .tpl content)
gtm template get 12

# Create from a downloaded .tpl (e.g. a Community Template Gallery export)
gtm template create --name "Attribution Cookie" --file attribution-cookie.tpl

# Update content after editing the .tpl locally
gtm template update 12 --file attribution-cookie-v2.tpl

# Rename only
gtm template update 12 --name "Attribution Cookie v2"

# Delete (confirmation prompt – --yes or global -y to skip)
gtm template delete 12
gtm template delete 12 --yes
gtm -y template delete 12
```
