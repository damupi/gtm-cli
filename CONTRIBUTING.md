# Contributing to gtm-cli

Thanks for your interest in contributing!

## Development Setup

```bash
# Clone the repo
git clone https://github.com/damupi/gtm-cli.git
cd gtm-cli

# Install locked dev dependencies (creates .venv)
uv sync --extra dev

# Install pre-commit hooks
uv run --locked pre-commit install
```

Or using the Makefile:

```bash
make dev
```

## Development Workflow

### Running Checks

```bash
# Run all checks
make check

# Or individually:
make lint        # Ruff linter
make type-check  # Mypy
make test        # Pytest
make format      # Auto-fix formatting
```

### Making Changes

1. Create a branch: `git checkout -b my-feature`
2. Make your changes
3. Run checks: `make check`
4. Commit using [conventional commits](#commit-messages)
5. Push and open a PR

### Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/) for automatic versioning:

```bash
feat: add new command        # → Minor version bump (1.x.0)
fix: correct bug             # → Patch version bump (1.0.x)
docs: update readme          # → Patch version bump
refactor: improve code       # → Patch version bump
chore: update deps           # → No release
ci: fix workflow             # → No release
```

Examples:
```bash
git commit -m "feat: add workspace sync command"
git commit -m "fix: handle empty tag list"
git commit -m "docs: add examples for publish command"
```

## Project Structure

```
src/gtm_cli/
├── cli/           # CLI commands (typer)
│   ├── main.py    # Root CLI + global options
│   ├── tags.py    # gtm tag commands
│   └── ...
├── core/          # Core functionality
│   ├── auth.py    # Authentication
│   ├── client.py  # GTM API client
│   └── config.py  # Configuration
└── utils/         # Utilities
    ├── output.py  # Output formatting
    └── errors.py  # Error handling
```

## Adding a New Command

1. Add API method to `core/client.py` if needed
2. Create or update CLI in `cli/<resource>.py`
3. Register in `cli/main.py` if new file
4. Update README.md with new command
5. Add tests

## Questions?

Open an issue or discussion on GitHub.
