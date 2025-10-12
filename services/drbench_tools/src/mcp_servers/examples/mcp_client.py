"""
An MCP client for interacting with MCP servers directly for testing.
This tool can be used to test any MCP server from the command line or in a script.
"""

import asyncio
import argparse
import json
import logging
import sys
from typing import List, Any, Dict, Optional, Tuple

try:
    from mcp.client import Client
except ImportError:
    print("Error: MCP client library not found. Install with 'pip install mcp[cli]'")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("mcp-client")


class MCPTestClient:
    """Client for interacting with MCP servers for testing and debugging."""
    
    def __init__(self, server_url: str):
        """Initialize with server URL."""
        self.server_url = server_url
        self.client = None
    
    async def __aenter__(self):
        """Connect to the MCP server."""
        logger.info(f"Connecting to {self.server_url}...")
        self.client = Client(self.server_url)
        await self.client.__aenter__()
        logger.info("Connected successfully")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Disconnect from the MCP server."""
        if self.client:
            await self.client.__aexit__(exc_type, exc_val, exc_tb)
            logger.info("Disconnected from server")
    
    async def list_tools(self) -> List[Tuple[str, str]]:
        """List available tools with descriptions."""
        tools = await self.client.list_tools()
        return [(t.name, t.description) for t in tools]
    
    async def list_resources(self) -> List[Tuple[str, str]]:
        """List available resources with descriptions."""
        resources = await self.client.list_resources()
        return [(r.uri, r.description) for r in resources]
    
    async def call_tool(self, tool_name: str, params: Dict[str, Any]) -> Any:
        """Call a tool with parameters."""
        return await self.client.call_tool(tool_name, params)
    
    async def get_resource(self, resource_uri: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Get a resource with optional parameters."""
        return await self.client.get_resource(resource_uri, params)


async def run_interactive_mode(server_url: str):
    """Run an interactive mode for exploring and testing the MCP server."""
    print(f"\n=== MCP Client Interactive Mode ===")
    print(f"Server: {server_url}")
    print("Type 'help' for a list of commands\n")
    
    async with MCPTestClient(server_url) as client:
        while True:
            try:
                command = input("\nMCP> ").strip()
                
                if command.lower() in ("exit", "quit", "q"):
                    print("Exiting interactive mode")
                    break
                
                elif command.lower() in ("help", "?", "h"):
                    print("\nCommands:")
                    print("  tools           - List available tools")
                    print("  resources       - List available resources")
                    print("  call TOOL ARGS  - Call a tool with arguments (JSON format)")
                    print("  get URI [ARGS]  - Get a resource with optional arguments (JSON format)")
                    print("  help            - Show this help message")
                    print("  exit            - Exit interactive mode")
                
                elif command.lower() == "tools":
                    tools = await client.list_tools()
                    print("\nAvailable Tools:")
                    for name, desc in tools:
                        print(f"  {name}: {desc}")
                
                elif command.lower() == "resources":
                    resources = await client.list_resources()
                    print("\nAvailable Resources:")
                    for uri, desc in resources:
                        print(f"  {uri}: {desc}")
                
                elif command.lower().startswith("call "):
                    parts = command.split(" ", 2)
                    if len(parts) < 3:
                        print("Error: Missing tool name or arguments")
                        print("Usage: call TOOL_NAME JSON_ARGS")
                        continue
                    
                    tool_name = parts[1]
                    try:
                        args = json.loads(parts[2])
                        result = await client.call_tool(tool_name, args)
                        print(f"\nResult from {tool_name}:")
                        print(json.dumps(result, indent=2))
                    except json.JSONDecodeError:
                        print("Error: Invalid JSON arguments")
                    except Exception as e:
                        print(f"Error calling tool: {str(e)}")
                
                elif command.lower().startswith("get "):
                    parts = command.split(" ", 2)
                    resource_uri = parts[1]
                    args = None
                    
                    if len(parts) > 2:
                        try:
                            args = json.loads(parts[2])
                        except json.JSONDecodeError:
                            print("Error: Invalid JSON arguments")
                            continue
                    
                    try:
                        result = await client.get_resource(resource_uri, args)
                        print(f"\nResult from {resource_uri}:")
                        print(json.dumps(result, indent=2))
                    except Exception as e:
                        print(f"Error getting resource: {str(e)}")
                
                else:
                    print(f"Unknown command: {command}")
                    print("Type 'help' for a list of commands")
            
            except KeyboardInterrupt:
                print("\nExiting interactive mode")
                break
            except EOFError:
                print("\nExiting interactive mode")
                break
            except Exception as e:
                print(f"Error: {str(e)}")


async def main():
    """Main entry point for the MCP test client."""
    parser = argparse.ArgumentParser(description="MCP Test Client")
    parser.add_argument("--url", default="http://localhost:9090/sse", help="MCP server URL")
    parser.add_argument("--tool", help="Call a specific tool")
    parser.add_argument("--args", help="JSON string of tool arguments")
    parser.add_argument("--resource", help="Get a specific resource")
    parser.add_argument("--list-tools", action="store_true", help="List available tools")
    parser.add_argument("--list-resources", action="store_true", help="List available resources")
    parser.add_argument("--interactive", "-i", action="store_true", help="Start interactive mode")
    
    args = parser.parse_args()
    
    if args.interactive:
        await run_interactive_mode(args.url)
        return
    
    async with MCPTestClient(args.url) as client:
        if args.list_tools:
            tools = await client.list_tools()
            print("\nAvailable Tools:")
            for name, desc in tools:
                print(f"  {name}: {desc}")
        
        elif args.list_resources:
            resources = await client.list_resources()
            print("\nAvailable Resources:")
            for uri, desc in resources:
                print(f"  {uri}: {desc}")
        
        elif args.tool:
            if args.args:
                try:
                    tool_args = json.loads(args.args)
                except json.JSONDecodeError:
                    logger.error("Invalid JSON arguments")
                    return
            else:
                tool_args = {}
            
            try:
                result = await client.call_tool(args.tool, tool_args)
                print(json.dumps(result, indent=2))
            except Exception as e:
                logger.error(f"Error calling tool {args.tool}: {str(e)}")
        
        elif args.resource:
            try:
                result = await client.get_resource(args.resource)
                print(json.dumps(result, indent=2))
            except Exception as e:
                logger.error(f"Error getting resource {args.resource}: {str(e)}")
        
        else:
            # If no specific action, try to connect and show info
            try:
                tools = await client.list_tools()
                resources = await client.list_resources()
                
                print(f"\nSuccessfully connected to {args.url}")
                print(f"Available tools: {len(tools)}")
                print(f"Available resources: {len(resources)}")
                print("\nUse --list-tools or --list-resources to see details")
                print("Use --interactive for interactive mode")
            except Exception as e:
                logger.error(f"Failed to connect to {args.url}: {str(e)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled")
