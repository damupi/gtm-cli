.PHONY: install dev lint type-check format test check clean build

# Install for users
install:
	pip install -e .

# Install with dev dependencies
dev:
	pip install -e ".[dev]"
	pre-commit install

# Lint code
lint:
	ruff check src/ tests/

# Type check
type-check:
	mypy src/

# Format code
format:
	ruff format src/ tests/
	ruff check src/ tests/ --fix

# Run tests
test:
	pytest

# Run tests with coverage
test-cov:
	pytest --cov=gtm_cli --cov-report=html --cov-report=term-missing

# Run all checks (lint, type-check, test)
check: lint type-check test

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build package
build: clean
	python -m build

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
