# Test Agents

This directory contains test agents and experimental implementations used during Weaver AI development. These are **NOT** intended for end users.

## Directory Structure

### `multiagent/`
Multi-agent orchestration demos and tests:
- `event_mesh_demo.py` - Redis event mesh demonstration with capability-based routing

### `security/`
Security testing and penetration testing agents:
- `pentest_gpt.py` - Full penetration testing workflow with GPT models
- `pentest_gpt5.py` - Advanced pentest with GPT-5 capabilities

### `integrations/`
Integration testing with external systems:

**SailPoint (`integrations/sailpoint/`):**
- `demo_gpt.py` - SailPoint IIQ integration demo with GPT
- `test_mcp.py` - MCP server integration tests
- `test_server.py` - Real SailPoint server connection tests

**Powder Finder (`integrations/powder_finder/`):**
- `pentest_real.py` - Real-world penetration testing
- `pentest_detailed.py` - Detailed pentest with comprehensive reporting

### `performance/`
Performance testing and benchmarking:
- `cache_test.py` - Redis caching performance validation
- `context7_test.py` - Context7 MCP server integration performance

## Usage

These agents are for **internal testing only**. For user-facing examples, see the `examples/` directory.

```bash
# Run a test agent
PYTHONPATH=. python agents/multiagent/event_mesh_demo.py

# Run performance tests
PYTHONPATH=. python agents/performance/cache_test.py
```

## Note

Files in this directory may have dependencies on specific test environments or external services. They are not guaranteed to work without proper configuration.
