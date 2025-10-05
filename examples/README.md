# Weaver AI Examples

This directory contains **user-facing examples** demonstrating different features of the Weaver AI framework.

## 🚀 Quick Start Examples

### Basic Examples

**`simple_agent.py`** - Simplest possible agent:
```bash
PYTHONPATH=. python examples/simple_agent.py
```
The easiest way to create an AI agent with Weaver - just a few lines of code!

**`01_simple_qa.py`** - Simple Q&A agent:
```bash
PYTHONPATH=. python examples/01_simple_qa.py
```
Basic question-answering agent demonstrating the `@agent` decorator.

**`simple_api_demo.py`** - Simple API usage:
```bash
PYTHONPATH=. python examples/simple_api_demo.py
```
Demonstrates the Simple API for quick agent development.

### Advanced Examples

**`robust_agent.py`** - Production-ready agent:
```bash
PYTHONPATH=. python examples/robust_agent.py
```
Shows best practices including:
- Error handling and retry logic
- Fallback strategies
- Input validation
- Comprehensive logging

**`02_analysis_pipeline.py`** - Analysis pipeline:
```bash
PYTHONPATH=. python examples/02_analysis_pipeline.py
```
Multi-step analysis workflow with data processing.

**`multiagent_flow.py`** - Complete multi-agent system:
```bash
PYTHONPATH=. python examples/multiagent_flow.py
```
Demonstrates:
- Capability-based routing
- Agent coordination via Redis event mesh
- Complex multi-agent workflows
- Event publishing and subscription

### Security & Compliance

**`signed_telemetry_demo.py`** - Cryptographically signed audit trails:
```bash
PYTHONPATH=. python examples/signed_telemetry_demo.py
```
Demonstrates tamper-evident logging for compliance (GDPR, SOX, HIPAA, PCI DSS).

## 📚 Learning Path

1. **Start here**: `simple_agent.py` - Learn the basics
2. **Next**: `01_simple_qa.py` - Understand the `@agent` decorator
3. **Then**: `robust_agent.py` - Production best practices
4. **Advanced**: `multiagent_flow.py` - Multi-agent orchestration
5. **Security**: `signed_telemetry_demo.py` - Compliance features

## 🔧 Requirements

```bash
# Install Weaver AI
pip install -e .

# Set up environment
export OPENAI_API_KEY=your-key-here
export WEAVER_MODEL_PROVIDER=openai
export WEAVER_MODEL_NAME=gpt-4
```

## 📖 Documentation

For comprehensive documentation, see:
- [Main README](../README.md)
- [Architecture Docs](../docs/architecture/)
- [API Reference](../docs/architecture/README.md#api-reference)

## 🤝 Contributing

Have a great example to share? Please submit a PR! Make sure your example:
- Is well-documented with comments
- Follows the existing code style
- Includes a docstring explaining what it demonstrates
- Can run standalone with minimal configuration
