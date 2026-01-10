# gtm-orchestrator

A modern Python CLI for Google Tag Manager API v2, designed for both interactive use and CI/CD automation.

## Features

- Full Google Tag Manager API v2 support
- OAuth2 and service account authentication
- Multi-profile support for managing multiple GTM accounts
- Export/import functionality for backup and migration
- Modern CLI with rich output formatting (JSON, YAML, table)

## Installation

### Using pip

```bash
pip install gtm-orchestrator
```

### Using uv (recommended)

```bash
uv pip install gtm-orchestrator
```

### Verify installation

```bash
gtm --version
```

## Quick Start

### 1. Login

```bash
# Interactive OAuth2 login (opens browser)
gtm login

# For headless environments
gtm login --no-browser
```

### 2. List your accounts and containers

```bash
gtm account list
gtm container list
```

### 3. Work with tags

```bash
gtm tag list
gtm tag get TAG_ID
gtm tag create --file tag.json
```

## Multi-Profile Support

Manage multiple GTM accounts with named profiles:

```bash
# Create a profile
gtm profile create work --account-id 123456789 --container-id GTM-XXXX

# List profiles
gtm profile list

# Switch default profile
gtm profile use work

# Use a specific profile for a command
gtm --profile work tag list
```

## GCP Setup Guide

### Prerequisites

1. A Google Cloud Platform project
2. Tag Manager API enabled
3. A GTM account with containers

### Setup Steps

#### 1. Enable the Tag Manager API

```bash
# Via gcloud CLI
gcloud services enable tagmanager.googleapis.com --project YOUR_PROJECT_ID
```

Or enable via [Google Cloud Console](https://console.cloud.google.com/apis/library/tagmanager.googleapis.com).

#### 2. Create Credentials

**For OAuth2 (Interactive use):**

1. Go to [APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)
2. Click "Create Credentials" > "OAuth Client ID"
3. Select "Desktop App" as application type
4. Download the JSON file as `client_secrets.json`
5. Place it in `~/.gtm-orchestrator/client_secrets.json`

**For Service Account (CI/CD):**

```bash
# Create service account
gcloud iam service-accounts create gtm-orchestrator \
  --display-name="GTM Orchestrator"

# Download key
gcloud iam service-accounts keys create credentials.json \
  --iam-account=gtm-orchestrator@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

Then grant access in Tag Manager:
- Go to Tag Manager > Admin > User Management
- Add the service account email with appropriate permissions

#### 3. Configure gtm-orchestrator

```bash
# Option 1: Environment variable
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Option 2: Config file
mkdir -p ~/.gtm-orchestrator/profiles
cat > ~/.gtm-orchestrator/profiles/default.yaml << EOF
name: default
auth:
  method: oauth
defaults:
  account_id: "123456789"
  container_id: "GTM-XXXX"
EOF
```

#### 4. Verify setup

```bash
gtm account list
```

## Development Setup

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended)

### Setup

```bash
# Clone the repository
git clone https://github.com/OWNER/gtm-orchestrator.git
cd gtm-orchestrator

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv pip install -e ".[dev]"

# Install pre-commit hooks
pre-commit install

# Verify installation
gtm --version
pytest
```

### Development Commands

```bash
# Format code
ruff format src tests

# Lint code
ruff check src tests --fix

# Type check
mypy src

# Run tests
pytest

# Run all checks (before commit)
pre-commit run --all-files
```

## CLI Reference

### Global Options

```bash
gtm [OPTIONS] COMMAND

Options:
  --profile TEXT              Use a specific profile
  --account-id TEXT           Override default account ID
  --container-id TEXT         Override default container ID
  --workspace-id TEXT         Override default workspace ID
  --service-account PATH      Use service account credentials
  --format [json|yaml|table]  Output format
  --verbose                   Enable debug logging
  --dry-run                   Show API calls without executing
  --yes                       Skip confirmation prompts
  --help                      Show help message
```

### Commands

| Command | Description |
|---------|-------------|
| `gtm login` | Authenticate with Google |
| `gtm logout` | Remove stored credentials |
| `gtm profile list` | List all profiles |
| `gtm profile create` | Create a new profile |
| `gtm profile use` | Set default profile |
| `gtm account list` | List GTM accounts |
| `gtm container list` | List containers |
| `gtm workspace list` | List workspaces |
| `gtm tag list` | List tags |
| `gtm trigger list` | List triggers |
| `gtm variable list` | List variables |
| `gtm version list` | List versions |
| `gtm export workspace` | Export workspace to files |
| `gtm import workspace` | Import from files |

## License

MIT License - see [LICENSE](LICENSE) for details.
