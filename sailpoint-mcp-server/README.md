# SailPoint IIQ MCP Server

This is a Model Context Protocol (MCP) server that provides integration with SailPoint IdentityIQ for the Weaver.AI framework.

## Features

- Connects to real SailPoint IdentityIQ instances via REST API
- Falls back to realistic demo data if SailPoint is unavailable
- Provides MCP-compliant endpoints for tool integration
- Supports identity and role management operations

## Setup

1. **Install Dependencies**
```bash
cd sailpoint-mcp-server
npm install
```

2. **Configure SailPoint Connection**
Edit the `.env` file with your SailPoint instance details:
```env
SAILPOINT_URL=http://your-sailpoint-server:8080/identityiq
SAILPOINT_USERNAME=your-username
SAILPOINT_PASSWORD=your-password
```

3. **Start the Server**
```bash
npm start
```

The server will start on port 3000 (or the port specified in MCP_PORT).

## Available Operations

The MCP server exposes the following tools:

### sailpoint_countIdentities
Count users and roles in SailPoint IIQ

### sailpoint_searchIdentities  
Search and list identities with pagination

### sailpoint_searchBundles
Search and list roles/bundles with pagination

### sailpoint_getIdentity
Get detailed information about a specific identity

### sailpoint_getBundle
Get detailed information about a specific role/bundle

## Testing the Server

1. **Health Check**
```bash
curl http://localhost:3000/health
```

2. **Test MCP Call**
```bash
curl -X POST http://localhost:3000/mcp/v1/tools/call \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "sailpoint_countIdentities",
      "arguments": {
        "types": ["Identity", "Bundle"]
      }
    },
    "id": "test-1"
  }'
```

## Data Sources

- **Live Mode**: When connected to a real SailPoint instance, returns actual data
- **Demo Mode**: When SailPoint is unavailable, returns realistic demo data with:
  - 3,847 identities across 8 departments and locations
  - 156 roles (82 business, 74 IT)
  - Realistic entitlements, access history, and risk scores
  - Proper relationships between identities and roles

## Integration with Weaver.AI

The Python `SailPointIIQTool` class in Weaver.AI will automatically connect to this MCP server when it's running. The tool will:

1. Try to connect to the MCP server at `localhost:3000`
2. Make actual API calls to retrieve SailPoint data
3. Fall back to mock data if the server is unavailable

## Troubleshooting

- **Connection Refused**: Make sure the MCP server is running (`npm start`)
- **Authentication Failed**: Check your SailPoint credentials in `.env`
- **Timeout Errors**: Increase `API_TIMEOUT` in `.env` or check network connectivity
- **Port Already in Use**: Change `MCP_PORT` in `.env` to a different port