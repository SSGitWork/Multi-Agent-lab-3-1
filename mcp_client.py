"""
Lab 3.1 -- mcp_client.py
========================
Implement an MCP client that connects to the server via stdio, discovers
its tool and resource, and calls read_file.

MCP client API quick reference
-------------------------------
    params = StdioServerParameters(command=sys.executable, args=["server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()       # .tools -> list[Tool]
            res   = await session.list_resources()   # .resources -> list[Resource]
            r     = await session.call_tool(name, {"key": value})
                                                     # r.content[0].text

Do NOT change TEST_FILE or _main() at the bottom.
"""

import asyncio
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def list_available_tools(session: ClientSession) -> list[str]:
    """Return tool names from session.list_tools() as a list of strings."""
    result = await session.list_tools()
    return [tool.name for tool in result.tools]


async def list_available_resources(session: ClientSession) -> list[tuple[str, str]]:
    """Return (uri, name) tuples. Cast .uri to str."""
    result = await session.list_resources()
    return [(str(resource.uri), resource.name) for resource in result.resources]


async def call_read_file(session: ClientSession, filename: str) -> str:
    """Call read_file tool and return result.content[0].text."""
    result = await session.call_tool("read_file", {"path": filename})
    return result.content[0].text


async def connect_and_run(server_script_path: str) -> dict[str, Any]:
    """Launch server subprocess, open session, call all three functions.

    Returns dict with keys:
        "tools"        -> list[str]
        "resources"    -> list[tuple]
        "file_content" -> str   (from call_read_file(TEST_FILE))
    """
    import os
    import pathlib

    server_path = pathlib.Path(server_script_path).resolve()

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        cwd=str(server_path.parent),
        env=os.environ.copy(),
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await list_available_tools(session)
            resources = await list_available_resources(session)
            file_content = await call_read_file(session, TEST_FILE)

            return {
                "tools": tools,
                "resources": resources,
                "file_content": file_content,
            }


TEST_FILE = "utils.py"


async def _main() -> None:
    import pathlib
    server_path = str(pathlib.Path(__file__).parent / "mcp_server.py")
    results = await connect_and_run(server_path)
    print("\n=== MCP Client Results ===")
    print(f"Tools:     {results['tools']}")
    print(f"Resources: {results['resources']}")
    print(f"\n--- read_file('{TEST_FILE}') ---")
    print(results["file_content"])

if __name__ == "__main__":
    asyncio.run(_main())
