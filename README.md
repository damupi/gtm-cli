# gtm-cli

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

The tag list shows columns matching the GTM web interface:

```bash
gtm tag list                      # sorted by modified (newest first)
gtm tag list --sort name          # alphabetical
gtm tag list --sort folder        # grouped by folder
gtm tag list --sort name --reverse  # Z-A
```

### Piping & Scripting

Output auto-switches to plain tab-separated format when piped:

```bash
# Find paused tags
gtm tag list | grep paused

# Get just tag names
gtm tag list | cut -f1

# Count tags per folder
gtm tag list | cut -f4 | sort | uniq -c

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

# Logout
gtm logout
```

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
| `gtm tag list` | List tags |
| `gtm tag get` | Get tag details |
| `gtm tag audit-consent` | Audit tags for consent configuration issues |
| `gtm trigger list` | List triggers |
| `gtm trigger get` | Get trigger details |
| `gtm variable list` | List variables |
| `gtm variable get` | Get variable details |
| `gtm version list` | List container versions |
| `gtm version get` | Get version details |

## Global Options

```
--profile, -p       Use a specific profile
--account-id, -a    Override default account ID
--container-id, -c  Override default container ID
--workspace-id, -w  Override default workspace ID
--service-account   Use service account credentials file
--format, -f        Output format: json, yaml, table, plain (default: table)
--verbose, -v       Enable debug logging
--dry-run           Show API calls without executing
--yes, -y           Skip confirmation prompts
--authuser, -u      Append authuser=N to GTM URLs (for multi-account Google sessions)
```

## Configuration

Configuration is stored in `~/.gtm-cli/`:

```
~/.gtm-cli/
├── client_secrets.json   # OAuth2 client credentials
├── config.yaml           # Global configuration
├── profiles/             # Named profiles
│   └── default.yaml
└── tokens/               # OAuth2 tokens (auto-managed)
    └── default.json
```

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

## License

MIT License - see [LICENSE](LICENSE) for details.
