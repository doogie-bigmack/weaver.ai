# Weaver AI

[![CI Pipeline](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/ci.yml/badge.svg)](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/ci.yml)
[![Security Scan](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/security.yml/badge.svg)](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/security.yml)
[![Release](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/release.yml/badge.svg)](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/release.yml)
[![Pre-commit](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/doogie-bigmack/weaver.ai/actions/workflows/pre-commit.yml)

Experimental A2A-compliant agent framework using Pydantic Agents and MCP.

## Development

```bash
pip install -e .[dev]
pre-commit install
pytest
```

SBOM: `cyclonedx-bom -o sbom/sbom.json`

## CI/CD

This project uses GitHub Actions for continuous integration and deployment:

- **CI Pipeline**: Runs on every push and PR - linting, testing, security scanning, Docker builds
- **Security Scan**: Daily vulnerability scanning with pip-audit, safety, and bandit
- **Release**: Automated releases with Docker images pushed to GitHub Container Registry
- **Pre-commit**: Validates code formatting and linting on PRs

### Running Tests Locally

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=weaver_ai --cov-report=term-missing

# Run linting
ruff check .
black --check .
mypy weaver_ai

# Run security checks
pip-audit
```

### Docker

```bash
# Build and test
make test

# Run demo
make demo
```
