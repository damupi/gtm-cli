.PHONY: install dev lint type-check format test check clean build

# Install for users from the current checkout
install:
	uv tool install .

# Install with dev dependencies
dev:
	uv sync --extra dev
	uv run --locked pre-commit install

# Lint code
lint:
	uv run --locked ruff check src/ tests/

# Type check
type-check:
	uv run --locked mypy src/

# Format code
format:
	uv run --locked ruff format src/ tests/
	uv run --locked ruff check src/ tests/ --fix

# Run tests
test:
	uv run --locked pytest

# Run tests with coverage
test-cov:
	uv run --locked pytest --cov=gtm_cli --cov-report=html --cov-report=term-missing

# Run all checks (lint, type-check, test)
check: lint type-check test

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build package
build: clean
	uv build

# Show help
help:
	@echo "Available targets:"
	@echo "  install    - Install package"
	@echo "  dev        - Install with dev dependencies + pre-commit hooks"
	@echo "  lint       - Run ruff linter"
	@echo "  type-check - Run mypy type checker"
	@echo "  format     - Format code with ruff"
	@echo "  test       - Run tests"
	@echo "  test-cov   - Run tests with coverage report"
	@echo "  check      - Run all checks (lint, type-check, test)"
	@echo "  clean      - Remove build artifacts"
	@echo "  build      - Build package"
