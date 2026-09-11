"""
Lab 3.1 — main.py
=================
Entry point. Runs the MCP client, which spawns the server as a subprocess
and exercises the read_file tool.

Usage
-----
    python main.py
"""

import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from mcp_client import connect_and_run, TEST_FILE


async def main() -> None:
    server_path = str(pathlib.Path(__file__).parent / "mcp_server.py")

    print("Starting MCP client — this will launch the server as a subprocess.")
    print(f"Server: {server_path}\n")

    results = await connect_and_run(server_path)

    print("=== Tools advertised by the server ===")
    for name in results["tools"]:
        print(f"  • {name}")

    print("\n=== Resources advertised by the server ===")
    for uri, name in results["resources"]:
        print(f"  • {name}  ({uri})")

    print(f"\n=== read_file('{TEST_FILE}') ===")
    print(results["file_content"])


if __name__ == "__main__":
    asyncio.run(main())
