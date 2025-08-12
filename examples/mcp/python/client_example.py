#!/usr/bin/env python3
"""
Example Python MCP client for Open Host Factory Plugin.

This example demonstrates how to connect to the MCP server and perform
common infrastructure provisioning tasks.
"""
import asyncio
import json
import logging
from typing import Dict, Any

# Note: Install mcp package: pip install mcp
from mcp import ClientSession, StdioServerParameters

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class HostFactoryMCPClient:
    """MCP client for Open Host Factory Plugin."""

    def __init__(self):
        """Initialize the MCP client."""
        self.session = None
        self.server_params = StdioServerParameters(command="ohfp", args=["mcp", "serve", "--stdio"])

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = ClientSession(self.server_params)
        await self.session.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.__aexit__(exc_type, exc_val, exc_tb)

    async def initialize(self) -> Dict[str, Any]:
        """Initialize the MCP session."""
        logger.info("Initializing MCP session...")
        result = await self.session.initialize()
        logger.info(f"Session initialized: {result}")
        return result

    async def list_tools(self) -> Dict[str, Any]:
        """List available tools."""
        logger.info("Listing available tools...")
        tools = await self.session.list_tools()
        logger.info(f"Found {len(tools)} tools")
        return tools

    async def list_resources(self) -> Dict[str, Any]:
        """List available resources."""
        logger.info("Listing available resources...")
        resources = await self.session.list_resources()
        logger.info(f"Found {len(resources)} resources")
        return resources

    async def list_prompts(self) -> Dict[str, Any]:
        """List available prompts."""
        logger.info("Listing available prompts...")
        prompts = await self.session.list_prompts()
        logger.info(f"Found {len(prompts)} prompts")
        return prompts

    async def call_tool(self, name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call a specific tool."""
        if arguments is None:
            arguments = {}

        logger.info(f"Calling tool: {name} with arguments: {arguments}")
        result = await self.session.call_tool(name, arguments)
        logger.info(f"Tool result: {result}")
        return result

    async def read_resource(self, uri: str) -> Dict[str, Any]:
        """Read a specific resource."""
        logger.info(f"Reading resource: {uri}")
        result = await self.session.read_resource(uri)
        logger.info(f"Resource content: {result}")
        return result

    async def get_prompt(self, name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get a specific prompt."""
        if arguments is None:
            arguments = {}

        logger.info(f"Getting prompt: {name} with arguments: {arguments}")
        result = await self.session.get_prompt(name, arguments)
        logger.info(f"Prompt result: {result}")
        return result


async def example_basic_operations():
    """Example: Basic MCP operations."""
    print("=== Basic MCP Operations Example ===")

    async with HostFactoryMCPClient() as client:
        # Initialize session
        await client.initialize()

        # List capabilities
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()

        print(f"Available tools: {[t.name for t in tools]}")
        print(f"Available resources: {[r.uri for r in resources]}")
        print(f"Available prompts: {[p.name for p in prompts]}")


async def example_infrastructure_provisioning():
    """Example: Infrastructure provisioning workflow."""
    print("=== Infrastructure Provisioning Example ===")

    async with HostFactoryMCPClient() as client:
        await client.initialize()

        # List available providers
        providers = await client.call_tool("list_providers")
        print(f"Available providers: {providers}")

        # Check provider health
        health = await client.call_tool("check_provider_health")
        print(f"Provider health: {health}")

        # List available templates
        templates = await client.call_tool("list_templates")
        print(f"Available templates: {templates}")

        # Request infrastructure (example)
        # Note: This would actually provision resources
        # request_result = await client.call_tool("request_machines", {
        #     "template_id": "EC2FleetInstant",
        #     "count": 2
        # })
        # print(f"Request result: {request_result}")


async def example_resource_access():
    """Example: Resource access."""
    print("=== Resource Access Example ===")

    async with HostFactoryMCPClient() as client:
        await client.initialize()

        # Read templates resource
        templates = await client.read_resource("templates://")
        print(f"Templates resource: {templates}")

        # Read providers resource
        providers = await client.read_resource("providers://")
        print(f"Providers resource: {providers}")


async def example_ai_prompts():
    """Example: AI prompt usage."""
    print("=== AI Prompts Example ===")

    async with HostFactoryMCPClient() as client:
        await client.initialize()

        # Get provision infrastructure prompt
        provision_prompt = await client.get_prompt(
            "provision_infrastructure", {"template_type": "ec2", "instance_count": 3}
        )
        print(f"Provision prompt: {provision_prompt}")

        # Get troubleshooting prompt
        troubleshoot_prompt = await client.get_prompt(
            "troubleshoot_deployment", {"request_id": "req-12345"}
        )
        print(f"Troubleshoot prompt: {troubleshoot_prompt}")


async def example_error_handling():
    """Example: Error handling."""
    print("=== Error Handling Example ===")

    async with HostFactoryMCPClient() as client:
        await client.initialize()

        try:
            # Try to call non-existent tool
            await client.call_tool("non_existent_tool")
        except Exception as e:
            print(f"Expected error for non-existent tool: {e}")

        try:
            # Try to read non-existent resource
            await client.read_resource("invalid://")
        except Exception as e:
            print(f"Expected error for invalid resource: {e}")


async def main():
    """Run all examples."""
    examples = [
        example_basic_operations,
        example_infrastructure_provisioning,
        example_resource_access,
        example_ai_prompts,
        example_error_handling,
    ]

    for example in examples:
        try:
            await example()
            print()
        except Exception as e:
            logger.error(f"Error in {example.__name__}: {e}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
