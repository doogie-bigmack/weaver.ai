#!/bin/bash

echo "============================================"
echo "SailPoint MCP Server Setup"
echo "============================================"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

echo "✓ Node.js found: $(node --version)"

# Navigate to server directory
cd sailpoint-mcp-server

# Install dependencies
echo ""
echo "Installing dependencies..."
npm install

echo ""
echo "============================================"
echo "Setup Complete!"
echo "============================================"
echo ""
echo "To start the MCP server:"
echo "  cd sailpoint-mcp-server"
echo "  npm start"
echo ""
echo "To test the integration:"
echo "  python test_real_sailpoint_mcp.py"
echo ""
echo "Configuration:"
echo "  Edit sailpoint-mcp-server/.env to configure SailPoint connection"
echo ""
echo "The server will:"
echo "  1. Try to connect to real SailPoint if configured"
echo "  2. Fall back to realistic demo data if unavailable"
echo "============================================"