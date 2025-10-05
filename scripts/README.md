# Operational Scripts

This directory contains scripts for validation, deployment, and operational tasks.

## Directory Structure

### `validation/`
Scripts for validating framework functionality:
- `validate_framework.py` - Run full framework validation with real GPT models
- `validate_ci.py` - Validate GitHub Actions CI/CD configuration
- `verify_phase2.py` - Verify Phase 2 model integration

### `deployment/`
Deployment verification and helper scripts:
- `verify_docker.py` - Verify Docker build and deployment

## Usage

### Validation Scripts

```bash
# Validate the entire framework
python scripts/validation/validate_framework.py

# Verify CI/CD configuration
python scripts/validation/validate_ci.py

# Verify specific phase
python scripts/validation/verify_phase2.py
```

### Deployment Scripts

```bash
# Verify Docker setup
python scripts/deployment/verify_docker.py
```

## CI/CD Integration

Many of these scripts are used in GitHub Actions workflows. See `.github/workflows/` for integration examples.

## Requirements

- Python 3.12+
- Valid API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
- Docker (for deployment scripts)
- Access to test environments

## Note

These scripts may modify system state or consume API credits. Use with caution in production environments.
