# Weaver AI Agent Framework

This repository hosts a lightweight, self-contained implementation of a secure,
A2A-compliant agent framework.  It mimics a modern stack built around Pydantic
models, FastAPI-style routing, and MCP-based tool calls while avoiding external
dependencies via small local stubs.

## Key Components
- **weaver_ai/**: core package containing settings, models, agent orchestration,
  A2A envelope logic, security modules, and a minimal gateway.
- **tests/**: pytest suite exercising arithmetic tool use, gateway behaviour,
  security features, and A2A/MCP interoperability.
- **fastapi/, pydantic/, jwt/, yaml/**: extremely small shim libraries that
  provide only the features needed for the tests.

## Developer Guidance
- Target Python 3.12+ and keep the code concise and type-annotated.
- Run `ruff check weaver_ai tests` and
  `PYTHONPATH=$PWD python -m pytest` before committing changes.
- When expanding the framework, preserve the minimal, secure-by-default design
  and update tests to cover new behaviour.

