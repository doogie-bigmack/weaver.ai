#!/bin/bash
# Run linting checks in Docker

docker run --rm -v $(pwd):/app -w /app python:3.12-slim bash -c "
pip install -q ruff black mypy httpx pydantic pydantic-settings fastapi pyyaml pyjwt &&
echo '=== Running ruff ===' &&
ruff check . 2>&1 | head -30 &&
echo '=== Running black ===' &&
black --check . 2>&1 | head -30 &&
echo '=== Running mypy ===' &&
mypy weaver_ai --ignore-missing-imports 2>&1 | head -30
"
