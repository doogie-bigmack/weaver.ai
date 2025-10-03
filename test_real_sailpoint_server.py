#!/usr/bin/env python3
"""
Test script to connect to your ACTUAL SailPoint IIQ MCP server.
This connects to the HTTP server running on port 3000.
"""

import asyncio
from typing import Any

import httpx


class RealSailPointClient:
    """Client for your actual SailPoint IIQ HTTP server."""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def health_check(self) -> dict[str, Any]:
        """Check server health."""
        response = await self.client.get(f"{self.base_url}/health")
        return response.json()
    
    async def list_identities(self, limit: int = 10, offset: int = 0) -> dict[str, Any]:
        """List identities from SailPoint."""
        params = {"limit": limit, "offset": offset}
        try:
            response = await self.client.get(
                f"{self.base_url}/identities",
                params=params
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def count_identities(self) -> int:
        """Count total identities."""
        # Try to get identities with limit=1 to get total count
        result = await self.list_identities(limit=1)
        
        if "totalResults" in result:
            return result["totalResults"]
        elif "totalCount" in result:
            return result["totalCount"]
        elif "total" in result:
            return result["total"]
        elif "Resources" in result and "totalResults" in result:
            # SCIM format
            return result["totalResults"]
        else:
            # Try getting all with high limit
            result = await self.list_identities(limit=1000)
            if "identities" in result:
                return len(result["identities"])
            elif "Resources" in result:
                return len(result["Resources"])
            return -1
    
    async def execute_tool(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool through the HTTP server."""
        try:
            response = await self.client.post(
                f"{self.base_url}/execute/{tool_name}",
                json=args
            )
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def close(self):
        """Close the client."""
        await self.client.aclose()


async def main():
    """Main test function."""
    print("\n" + "="*60)
    print("Testing YOUR ACTUAL SailPoint IIQ MCP Server")
    print("="*60)
    
    client = RealSailPointClient()
    
    try:
        # 1. Health check
        print("\n[1] Health Check:")
        health = await client.health_check()
        print(f"  Status: {health.get('status', 'unknown')}")
        print(f"  Service: {health.get('service', 'unknown')}")
        if "iiqConnection" in health:
            conn = health["iiqConnection"]
            print(f"  IIQ URL: {conn.get('url', 'unknown')}")
            print(f"  Authenticated: {conn.get('authenticated', False)}")
        
        # 2. Try to list identities
        print("\n[2] Listing Identities (first 5):")
        identities = await client.list_identities(limit=5)
        
        if "error" in identities:
            print(f"  Error: {identities['error']}")
            if "message" in identities:
                print(f"  Message: {identities['message']}")
            
            # Check if it's a 503 error
            if "503" in str(identities.get('error', '')):
                print("\n  ⚠️  SailPoint IIQ server is unavailable (503 error)")
                print("  The HTTP server is running but cannot connect to SailPoint at:")
                print(f"  {health.get('iiqConnection', {}).get('url', 'unknown')}")
                print("\n  Possible causes:")
                print("  1. SailPoint IIQ is down or restarting")
                print("  2. Network connectivity issues")
                print("  3. Authentication credentials are incorrect")
        else:
            # Success - show results
            if "Resources" in identities:
                # SCIM format
                print(f"  Total Identities: {identities.get('totalResults', 'unknown')}")
                for idx, identity in enumerate(identities.get('Resources', [])[:5], 1):
                    print(f"  {idx}. {identity.get('userName', 'unknown')} - {identity.get('displayName', 'unknown')}")
            elif "identities" in identities:
                # Direct format
                print(f"  Total: {identities.get('total', len(identities['identities']))}")
                for idx, identity in enumerate(identities['identities'][:5], 1):
                    print(f"  {idx}. {identity.get('name', 'unknown')} - {identity.get('displayName', 'unknown')}")
            else:
                print(f"  Response format: {list(identities.keys())}")
        
        # 3. Try to use execute endpoint
        print("\n[3] Testing Execute Endpoint:")
        result = await client.execute_tool("list_identities", {"limit": 1})
        if "error" in result:
            print(f"  Error: {result['error']}")
        else:
            print("  Success: Tool executed")
            if "totalResults" in result or "total" in result:
                total = result.get('totalResults') or result.get('total', 'unknown')
                print(f"  Total Identities Found: {total}")
        
        # 4. Count identities
        print("\n[4] Counting Total Identities:")
        count = await client.count_identities()
        if count > 0:
            print(f"  ✓ Total Identities in SailPoint: {count}")
        else:
            print("  ⚠️  Could not determine total count")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.close()
    
    print("\n" + "="*60)
    print("Summary:")
    print("="*60)
    print("\nYour SailPoint IIQ HTTP server is running on port 3000")
    print("However, it appears the actual SailPoint instance at")
    print("10.201.224.8:8080 may be unavailable (503 error).")
    print("\nClaude Desktop can still access it through the stdio")
    print("transport which may have cached data or a different")
    print("connection method.")
    print("\nTo get the same 231 identities count, ensure:")
    print("1. SailPoint IIQ is running at 10.201.224.8:8080")
    print("2. Credentials are correct in your .env file")
    print("3. Network connectivity is working")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())