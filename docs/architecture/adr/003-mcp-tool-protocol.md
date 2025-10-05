# ADR-003: Model Context Protocol for Tools

**Status**: Accepted
**Date**: 2024-09-10
**Decision Makers**: Architecture Team
**Technical Story**: Tool integration standardization

## Context

Weaver AI agents need to interact with external systems and tools (web search, databases, APIs, etc.). We needed a standardized way to:

1. **Discover** available tools
2. **Execute** tools with type-safe parameters
3. **Secure** tool access with authentication and authorization
4. **Extend** the framework with custom tools
5. **Integrate** third-party tool providers

### Forces at Play

1. **Standardization**: Need common protocol for all tool integrations
2. **Security**: Tools can access sensitive data and perform dangerous operations
3. **Extensibility**: Developers should easily add custom tools
4. **Type Safety**: Prevent runtime errors from incorrect tool usage
5. **Interoperability**: Work with external tool providers
6. **Versioning**: Handle tool version changes gracefully

### Existing Approaches

- **OpenAI Function Calling**: Proprietary to OpenAI, JSON Schema-based
- **LangChain Tools**: Python-specific, no cross-language support
- **Custom RPC**: Full control but requires designing from scratch
- **Model Context Protocol (MCP)**: Emerging standard by Anthropic

## Decision

**We will adopt the Model Context Protocol (MCP) as our standard for tool integration.**

### What is MCP?

Model Context Protocol is an open standard that provides a universal way for AI systems to access tools, data sources, and integrations. Key features:

- **Server-Client Architecture**: Tools run as MCP servers, agents connect as clients
- **JSON-RPC 2.0**: Standard protocol for communication
- **Schema Discovery**: Tools self-describe their inputs/outputs
- **Security**: Built-in authentication with JWT signatures
- **Language Agnostic**: Works across Python, JavaScript, Go, etc.

### Implementation in Weaver AI

**1. Tool Base Classes** (`weaver_ai/tools/base.py`):

```python
class Tool(BaseModel):
    """Base class for all MCP tools."""
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    required_scopes: list[str]

    async def execute(
        self,
        context: ToolExecutionContext,
        **kwargs
    ) -> ToolResult:
        """Execute the tool."""
        raise NotImplementedError
```

**2. Tool Registry** (`weaver_ai/tools/registry.py`):

```python
class ToolRegistry:
    """Centralized tool discovery and management."""

    def register(self, tool: Tool) -> None:
        """Register a tool for discovery."""

    def get(self, name: str) -> Tool:
        """Get tool by name."""

    def list_by_capability(self, capability: ToolCapability) -> list[Tool]:
        """List tools by capability."""
```

**3. MCP Server** (`weaver_ai/mcp.py`):

```python
class MCPServer:
    """MCP server for exposing Weaver AI tools."""

    def __init__(self, name: str, signing_key: str):
        self.name = name
        self.signing_key = signing_key
        self.nonce_cache = set()  # Prevent replay attacks

    def call(self, tool_name: str, params: dict) -> dict:
        """Execute tool with MCP protocol."""
        # 1. Validate nonce (prevent replay)
        # 2. Execute tool
        # 3. Sign response with HMAC
        # 4. Return ToolResult
```

**4. MCP Client** (`weaver_ai/mcp.py`):

```python
class MCPClient:
    """MCP client for calling tools."""

    def __init__(self, server: MCPServer, verify_key: str):
        self.server = server
        self.verify_key = verify_key

    async def call(self, tool_name: str, params: dict) -> ToolResult:
        """Call tool via MCP protocol."""
        # 1. Generate nonce
        # 2. Call server
        # 3. Verify response signature
        # 4. Return result
```

### Built-in Tools

Weaver AI ships with these MCP-compliant tools:

| Tool | Capability | Sensitivity | Approval Required |
|------|------------|-------------|-------------------|
| web_search | WEB_SEARCH | Low | No |
| documentation | DOCUMENTATION | Low | No |
| sailpoint_iiq | API_CALL | High | No |
| python_eval | CODE_EXECUTION | High | Yes |
| database_query | DATABASE | High | Yes |

### Tool Configuration (`weaver_ai/policies/tools.yaml`)

```yaml
web_search:
  required_scopes:
    - tool:web_search
  sensitivity: low
  rate_limit: 60  # per minute
  requires_approval: false

database_query:
  required_scopes:
    - tool:database
  sensitivity: high
  rate_limit: 30
  requires_approval: true  # Admin must approve
```

## Consequences

### Positive

1. **Standardization**: Industry-standard protocol, not proprietary
2. **Interoperability**: Can integrate third-party MCP servers
3. **Security**: Built-in JWT signing and nonce protection
4. **Extensibility**: Easy to add new tools following same pattern
5. **Type Safety**: JSON Schema for tool inputs/outputs
6. **Discovery**: Tools self-describe their capabilities
7. **Future-Proof**: Emerging standard with industry backing
8. **Cross-Language**: Can call tools written in any language

### Negative

1. **Complexity**: More complex than simple function calls
2. **Overhead**: JSON-RPC adds latency (~1-2ms)
3. **Learning Curve**: Developers need to learn MCP spec
4. **Immature Standard**: MCP is still evolving
5. **Limited Tooling**: Fewer debugging tools than HTTP
6. **Documentation**: MCP docs not as comprehensive as alternatives

### Neutral

1. **Dependency**: Tied to MCP specification evolution
2. **Migration**: Future MCP changes may require updates
3. **Vendor Lock-in**: Limited to MCP-compatible tools (mitigated by adapter pattern)

## Alternatives Considered

### Alternative 1: OpenAI Function Calling

**Description**: Use OpenAI's function calling JSON format

**Pros**:
- Well-documented
- Tight integration with OpenAI models
- Large community

**Cons**:
- Proprietary to OpenAI
- No security layer
- Python-only
- No cross-provider support

**Why not chosen**: Vendor lock-in, not a true protocol

### Alternative 2: LangChain Tools

**Description**: Use LangChain's tool abstraction

**Pros**:
- Mature ecosystem
- Many pre-built tools
- Good documentation

**Cons**:
- Python-only
- Tightly coupled to LangChain
- No built-in security
- Heavy dependencies

**Why not chosen**: Too heavy, not language-agnostic

### Alternative 3: Custom RPC Protocol

**Description**: Design our own tool invocation protocol

**Pros**:
- Full control
- Optimized for our use case
- No external dependencies

**Cons**:
- Reinventing the wheel
- No interoperability
- Maintenance burden
- No third-party tools

**Why not chosen**: Better to adopt standard than create one

### Alternative 4: GraphQL

**Description**: Use GraphQL for tool execution

**Pros**:
- Mature standard
- Type system
- Good tooling

**Cons**:
- Query language overkill for tool calls
- No built-in security for tools
- Heavier than needed
- Primarily for data fetching, not actions

**Why not chosen**: Over-engineered for tool execution

## Implementation Notes

### Creating a New MCP Tool

```python
# weaver_ai/tools/builtin/my_tool.py
from weaver_ai.tools import Tool, ToolCapability, ToolExecutionContext, ToolResult
import time

class MyTool(Tool):
    """Custom MCP tool."""

    name: str = "my_tool"
    description: str = "Does something useful"
    version: str = "1.0.0"
    capabilities: list[ToolCapability] = [ToolCapability.COMPUTATION]
    required_scopes: list[str] = ["tool:my_tool"]

    input_schema: dict = {
        "type": "object",
        "properties": {
            "input": {"type": "string"}
        },
        "required": ["input"]
    }

    output_schema: dict = {
        "type": "object",
        "properties": {
            "output": {"type": "string"}
        }
    }

    async def execute(
        self,
        context: ToolExecutionContext,
        input: str
    ) -> ToolResult:
        """Execute the tool."""
        start = time.time()

        try:
            # Your tool logic here
            result = {"output": f"Processed: {input}"}

            return ToolResult(
                success=True,
                data=result,
                execution_time=time.time() - start,
                tool_name=self.name
            )
        except Exception as e:
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                execution_time=time.time() - start,
                tool_name=self.name
            )
```

### Registering Tool

```python
# weaver_ai/tools/__init__.py
from .builtin.my_tool import MyTool

tool_registry = ToolRegistry()
tool_registry.register(MyTool())
```

### External MCP Server Integration

```python
# Connect to external MCP server
from weaver_ai.mcp import MCPClient

external_client = MCPClient(
    server_url="https://external-mcp.example.com",
    api_key="your-api-key"
)

# Use external tool
result = await external_client.call("external_tool", {"param": "value"})
```

### Security: JWT Signing

```python
# weaver_ai/mcp.py:60-80
def _sign_call(self, tool_name: str, params: dict, nonce: str) -> str:
    """Sign MCP call with HMAC-SHA256."""
    payload = {
        "tool": tool_name,
        "params": params,
        "nonce": nonce,
        "timestamp": time.time()
    }

    message = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        self.signing_key.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return signature
```

### Nonce Replay Protection

```python
# weaver_ai/mcp.py:90-110
def _validate_nonce(self, nonce: str) -> None:
    """Ensure nonce hasn't been used before."""
    if nonce in self.nonce_cache:
        raise ValueError("Nonce already used (replay attack)")

    self.nonce_cache.add(nonce)

    # Expire nonces after 5 minutes
    if len(self.nonce_cache) > 10000:
        self.nonce_cache.clear()
```

## Testing

### Unit Tests

```python
# tests/test_mcp.py
@pytest.mark.asyncio
async def test_mcp_tool_execution():
    server = MCPServer("test", "secret-key")
    client = MCPClient(server, "secret-key")

    result = await client.call("web_search", {"query": "test"})

    assert result.success
    assert result.tool_name == "web_search"
```

### Integration Tests

```python
# tests/test_mcp_integration.py
@pytest.mark.asyncio
async def test_external_mcp_server():
    client = MCPClient(
        server_url="https://sailpoint-mcp.example.com",
        api_key=os.getenv("SAILPOINT_API_KEY")
    )

    result = await client.call("get_user", {"user_id": "jdoe"})
    assert result.success
```

## Migration Path

If MCP standard evolves or we need to migrate:

1. **Abstraction Layer**: `Tool` base class hides MCP details
2. **Adapter Pattern**: New protocols wrapped in `Tool` interface
3. **Versioning**: Support multiple MCP versions simultaneously
4. **Graceful Deprecation**: Announce changes, provide migration guide

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP GitHub Organization](https://github.com/modelcontextprotocol)
- [Anthropic MCP Announcement](https://www.anthropic.com/news/model-context-protocol)
- Internal: `weaver_ai/tools/` implementation
- Internal: `weaver_ai/mcp.py` MCP server/client
