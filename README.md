# gtm-cli

[![CI](https://github.com/oppianmatt/gtm-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/oppianmatt/gtm-cli/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern Python CLI for Google Tag Manager API v2.

## Features

- **Easy setup** - Interactive wizard handles GCP configuration
- **Smart defaults** - Auto-detects account/container/workspace when you have only one
- **Team-friendly** - Share OAuth credentials for quick teammate onboarding
- **Multi-profile** - Manage multiple GTM accounts with named profiles
- **Flexible auth** - OAuth2 for interactive use, service accounts for CI/CD
- **Rich output** - JSON, YAML, or formatted tables (auto-switches to plain for piping)
- **Unix-friendly** - Pipe output to grep, awk, cut, etc.

## Installation

```bash
pip install gtm-cli
```

Verify installation:

```bash
gtm --version
```

## Quick Start

### First-time Setup (Admin)

Run the interactive setup wizard:

```bash
gtm setup
```

This guides you through:
1. Creating a GCP project (or using existing)
2. Enabling the Tag Manager API
3. Configuring OAuth consent screen
4. Creating OAuth credentials
5. Logging in

### Teammate Onboarding

If someone on your team has already set up OAuth credentials (Internal consent screen), you just need:

```bash
gtm init https://your-internal-url/client_secrets.json
```

Or with a local file:

```bash
gtm init ~/shared/client_secrets.json
```

Skip the automatic login step with `--no-login`:

```bash
gtm init https://your-internal-url/client_secrets.json --no-login
```

That's it! One command downloads the credentials and logs you in.

### Basic Usage

```bash
# List your GTM accounts
gtm account list

# List containers (auto-detects account if you have only one)
gtm container list

# List tags (auto-detects account/container/workspace)
gtm tag list

# If you have multiple containers, specify which one
gtm -c GTM-XXXX tag list

# Different output formats
gtm account list --format json
gtm account list --format yaml
```

### Tag List

The tag list shows tag ID, name, type, triggers, folder, modified time, and paused status:

```bash
gtm tag list                      # sorted by modified (newest first)
gtm tag list --sort name          # alphabetical
gtm tag list --sort folder        # grouped by folder
gtm tag list --sort name --reverse  # Z-A
```

### Tag Management

```bash
# Search tags by name, type, or trigger
gtm tag search tiktok
gtm tag search pixel --type html
gtm tag search facebook --exclude-paused
gtm tag search --trigger 62              # All tags on trigger ID 62
gtm tag search --trigger "Booking"       # All tags on triggers matching "Booking"

# Get one or more tags
gtm tag get 298
gtm tag get 298 302 303 313 --format json

# Compare tags side by side
gtm tag compare 298 17                   # Compare two tags by ID
gtm tag compare --trigger 62             # Compare all tags on a trigger
gtm tag compare --folder tiktok --folder facebook  # Compare across folders

# Create a Custom HTML tag
gtm tag create --name "My Tag" --html '<script>console.log("hi")</script>'
gtm tag create --name "My Tag" --html-file pixel.html --trigger-id 295

# Update a tag
gtm tag update 421 --html-file loader.html
gtm tag update 420 --name "TikTok Stub v2"

# Pause/unpause tags
gtm tag pause 304
gtm tag unpause 298 302 303

# Audit tags for issues
gtm tag audit-consent            # Find consent configuration problems
gtm tag audit-pixels             # Find pixel loading issues
gtm tag audit-pixels --params    # Include event parameters in audit
gtm tag audit-params             # Show event params per tag
gtm tag audit-params --folder tiktok     # Filter by folder
gtm tag audit-setup-deps         # Find broken setup/teardown dependencies
```

### Trigger Management

```bash
# Create a trigger with parameters
gtm trigger create --name "Timer 5s" --type timer --param interval:5000 --param limit:1
gtm trigger create --name "Page View" --type pageview

# Delete a trigger
gtm trigger delete 312
```

### Workspace Management

```bash
# List and inspect workspaces
gtm workspace list
gtm workspace get 1000815

# Create a new workspace
gtm workspace create --name "my-feature"
gtm workspace create --name "my-feature" --description "Work for Q3 campaign"

# Delete a workspace (prompts for confirmation unless --yes)
gtm workspace delete --workspace-id 1000796 --container-id 8983761
gtm workspace delete --workspace-id 1000796 --container-id 8983761 --yes

# Show pending unpublished changes
gtm workspace status
gtm workspace status --detail     # Include consent settings info

# Publish workspace changes as a new version
gtm workspace publish
gtm workspace publish --name "v1.2" --notes "Fixed consent settings"

# Open workspace preview in browser
gtm workspace preview
gtm -u 1 workspace preview       # With authuser for multi-account sessions
```

### Versions

Inspect published container versions and compare changes:

```bash
# List versions with publish dates
gtm version list

# Filter versions by date range (useful for incident investigation)
gtm version list --since 2025-06-01
gtm version list --since 2025-06-01 --until 2025-06-30

# Get full details of a specific version (all tags, triggers, variables)
gtm version get 42

# Compare two versions to see what changed
gtm version diff 42 43
```

### Piping & Scripting

Output auto-switches to plain tab-separated format when piped:

```bash
# Find paused tags
gtm tag list | grep paused

# Get just tag names (column 2)
gtm tag list | cut -f2

# Count tags per folder
gtm tag list | cut -f5 | sort | uniq -c

# Use with jq for JSON processing
gtm tag list --format json | jq '.[].name'
```

## Multi-Profile Support

Profiles store default account/container/workspace IDs. OAuth tokens are shared across all profiles (you only need to login once).

```bash
# Create a profile with default IDs
gtm profile create work --account-id 123456 --container-id GTM-XXXX

# Now commands use those defaults automatically
gtm profile use work
gtm tag list  # Uses work profile's account/container

# List profiles
gtm profile list

# Use a specific profile for a command
gtm --profile work tag list
```

## Authentication

### OAuth2 (Interactive)

Best for local development and interactive use:

```bash
# Login (opens browser)
gtm login

# Check login status
gtm login --status

# Login without opening browser (for headless/SSH environments)
gtm login --no-browser

# Login using OAuth2 client secrets instead of gcloud (bypasses gcloud auto-detection)
gtm login --no-gcloud

# Logout
gtm logout
```

> **Note:** By default `gtm login` uses gcloud if it is installed. If gcloud is unavailable or you prefer OAuth2 client secrets, use `--no-gcloud`. Place your client secrets file at `~/.config/gtm-cli/client_secrets.json` before running.

### Service Account (CI/CD)

Best for automation and CI/CD pipelines:

```bash
# Create service account
gcloud iam service-accounts create gtm-cli --display-name="GTM CLI"

# Download key
gcloud iam service-accounts keys create credentials.json \
  --iam-account=gtm-cli@YOUR_PROJECT.iam.gserviceaccount.com

# Use with gtm-cli
gtm --service-account credentials.json account list

# Or set environment variable
export GOOGLE_APPLICATION_CREDENTIALS=credentials.json
gtm account list
```

Remember to grant the service account access in Tag Manager:
- Go to Tag Manager > Admin > User Management
- Add the service account email with appropriate permissions

## Commands

| Command | Description |
|---------|-------------|
| `gtm setup` | Interactive first-time setup wizard |
| `gtm init <url>` | Quick setup with shared credentials |
| `gtm login` | Authenticate with Google |
| `gtm logout` | Remove stored credentials |
| `gtm profile list` | List all profiles |
| `gtm profile create` | Create a new profile |
| `gtm profile use` | Set default profile |
| `gtm profile show` | Show current profile details |
| `gtm profile delete` | Delete a profile |
| `gtm account list` | List GTM accounts |
| `gtm account get` | Get account details |
| `gtm container list` | List containers |
| `gtm container get` | Get container details |
| `gtm workspace list` | List workspaces |
| `gtm workspace get` | Get workspace details |
| `gtm workspace create` | Create a new workspace |
| `gtm workspace delete` | Delete a workspace |
| `gtm workspace status` | Show pending changes |
| `gtm workspace publish` | Create version and publish |
| `gtm workspace preview` | Open workspace preview in browser |
| `gtm tag list` | List tags (with tag ID, type, triggers, folder, modified) |
| `gtm tag get` | Get details of one or more tags |
| `gtm tag search` | Search tags by name, type, or trigger |
| `gtm tag compare` | Compare tags side by side (by ID, trigger, or folder) |
| `gtm tag create` | Create a new tag |
| `gtm tag update` | Update an existing tag |
| `gtm tag pause` | Pause one or more tags |
| `gtm tag unpause` | Unpause one or more tags |
| `gtm tag delete` | Delete a tag |
| `gtm tag audit-consent` | Audit tags for consent configuration issues |
| `gtm tag audit-pixels` | Audit pixel/script loading issues (with optional `--params`) |
| `gtm tag audit-params` | Audit event parameters sent by tracking tags |
| `gtm tag audit-setup-deps` | Find broken setup/teardown tag dependencies |
| `gtm trigger list` | List triggers |
| `gtm trigger get` | Get trigger details |
| `gtm trigger create` | Create a new trigger |
| `gtm trigger delete` | Delete a trigger |
| `gtm variable list` | List variables |
| `gtm variable get` | Get variable details |
| `gtm version list` | List container versions (with publish date) |
| `gtm version get` | Get full version details (all tags, triggers, variables) |
| `gtm version diff` | Show what changed between two published versions |

## Global Options

```
--profile, -p       Use a specific profile (env: GTM_PROFILE)
--account-id, -a    Override default account ID (env: GTM_ACCOUNT_ID)
--container-id, -c  Override default container ID (env: GTM_CONTAINER_ID)
--workspace-id, -w  Override default workspace ID (env: GTM_WORKSPACE_ID)
--service-account   Use service account credentials file
--format, -f        Output format: json, yaml, table, plain (default: table)
--verbose, -v       Enable debug logging
--dry-run           Show API calls without executing
--yes, -y           Skip confirmation prompts
--authuser, -u      Append authuser=N to GTM URLs (env: GTM_AUTHUSER)
```

Environment variables can be used instead of flags for common options:

```bash
export GTM_PROFILE=work
export GTM_CONTAINER_ID=GTM-XXXX
gtm tag list  # Uses work profile and GTM-XXXX container
```

## Configuration

Configuration is stored in `~/.gtm-cli/`:

```
~/.gtm-cli/
├── client_secrets.json   # OAuth2 client credentials (default path)
├── config.yaml           # Global configuration
├── profiles/             # Named profiles
│   └── default.yaml
└── tokens/               # OAuth2 tokens (auto-managed)
    └── default.json
```

You can also place the client secrets file at `~/.config/gtm-cli/client_secrets.json` if you prefer to follow the XDG convention used by other tools (e.g. gafour).

## Development

### Setup

```bash
git clone https://github.com/oppianmatt/gtm-cli.git
cd gtm-cli

# Create venv and install
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install
```

### Commands

```bash
# Lint
ruff check src/

# Type check
mypy src/

# Format
ruff format src/

# Run all checks
pre-commit run --all-files
```

### Commit Convention

This project uses [Conventional Commits](https://www.conventionalcommits.org/) for automatic versioning:

| Prefix | Description | Version Bump |
|--------|-------------|--------------|
| `feat:` | New feature | Minor (1.x.0) |
| `fix:` | Bug fix | Patch (1.0.x) |
| `docs:` | Documentation only | Patch |
| `refactor:` | Code refactoring | Patch |
| `perf:` | Performance improvement | Patch |
| `chore:` | Maintenance (no release) | None |
| `ci:` | CI/CD changes (no release) | None |

Examples:
```bash
git commit -m "feat: add workspace publish command"
git commit -m "fix: correct authuser URL placement"
git commit -m "docs: update README with new commands"
```

### Release Process

Releases are automated with [Release Please](https://github.com/googleapis/release-please):

1. Push commits to `main` using conventional commit messages
2. Release Please automatically creates/updates a "Release PR"
3. The PR accumulates changes and updates the changelog
4. When you merge the Release PR:
   - Version is bumped in `pyproject.toml` and `__init__.py`
   - GitHub Release is created with changelog
   - Package is published to PyPI

## License

MIT License - see [LICENSE](LICENSE) for details.
