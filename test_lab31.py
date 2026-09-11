"""
tests/test_lab31.py
===================
Black-box test suite for Lab 3.1.

All tests run without making real network calls or spawning the live MCP
server subprocess. LLM and HTTP calls are mocked at the appropriate layer.

Run normally (no live calls):
    pytest

Run with live end-to-end test:
    pytest --run-llm
"""

import asyncio
import pathlib
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

LAB_ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(LAB_ROOT))


# ---------------------------------------------------------------------------
# Helpers: build mock MCP objects
# ---------------------------------------------------------------------------

def _make_tool(name: str, description: str, schema: dict) -> MagicMock:
    t = MagicMock()
    t.name = name
    t.description = description
    t.inputSchema = schema
    return t


def _make_resource(uri: str, name: str, mime: str) -> MagicMock:
    r = MagicMock()
    r.uri = uri
    r.name = name
    r.mimeType = mime
    return r


def _make_text_content(text: str) -> MagicMock:
    c = MagicMock()
    c.text = text
    return c


def _make_call_result(text: str, is_error: bool = False) -> MagicMock:
    result = MagicMock()
    result.isError = is_error
    result.content = [_make_text_content(text)]
    return result


def _make_list_tools_result(tools: list) -> MagicMock:
    r = MagicMock()
    r.tools = tools
    return r


def _make_list_resources_result(resources: list) -> MagicMock:
    r = MagicMock()
    r.resources = resources
    return r


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

EXPECTED_TOOL = _make_tool(
    "read_file",
    "Reads a file from the project_files directory",
    {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
)

EXPECTED_RESOURCE = _make_resource(
    "file://project/listing",
    "Project Directory Listing",
    "text/plain",
)

UTILS_PY_CONTENT = (LAB_ROOT / "project_files" / "utils.py").read_text()


@pytest.fixture
def mock_session() -> AsyncMock:
    """A mock ClientSession pre-wired with realistic responses."""
    session = AsyncMock()
    session.initialize = AsyncMock(return_value=None)
    session.list_tools = AsyncMock(return_value=_make_list_tools_result([EXPECTED_TOOL]))
    session.list_resources = AsyncMock(
        return_value=_make_list_resources_result([EXPECTED_RESOURCE])
    )

    async def _call_tool(name: str, args: dict):
        if name == "read_file":
            path = args.get("path", "")
            if ".." in path or path.startswith("/"):
                return _make_call_result("ERROR: path traversal denied", is_error=True)
            target = LAB_ROOT / "project_files" / path
            if not target.exists():
                return _make_call_result(f"ERROR: file not found: {path}", is_error=True)
            return _make_call_result(target.read_text())
        else:
            return _make_call_result(f"ERROR: unknown tool {name}", is_error=True)

    session.call_tool = AsyncMock(side_effect=_call_tool)
    return session


# ---------------------------------------------------------------------------
# Tests: mcp_client functions
# ---------------------------------------------------------------------------

class TestListAvailableTools:
    async def test_returns_list_of_strings(self, mock_session):
        from mcp_client import list_available_tools
        tools = await list_available_tools(mock_session)
        assert isinstance(tools, list)
        assert all(isinstance(t, str) for t in tools)

    async def test_contains_read_file(self, mock_session):
        from mcp_client import list_available_tools
        tools = await list_available_tools(mock_session)
        assert "read_file" in tools, "read_file must be in the tool list"

    async def test_calls_session_list_tools(self, mock_session):
        from mcp_client import list_available_tools
        await list_available_tools(mock_session)
        mock_session.list_tools.assert_called_once()


class TestListAvailableResources:
    async def test_returns_list_of_tuples(self, mock_session):
        from mcp_client import list_available_resources
        resources = await list_available_resources(mock_session)
        assert isinstance(resources, list)
        assert all(isinstance(r, tuple) and len(r) == 2 for r in resources)

    async def test_contains_project_listing_resource(self, mock_session):
        from mcp_client import list_available_resources
        resources = await list_available_resources(mock_session)
        uris = [r[0] for r in resources]
        assert any("project/listing" in u for u in uris)

    async def test_calls_session_list_resources(self, mock_session):
        from mcp_client import list_available_resources
        await list_available_resources(mock_session)
        mock_session.list_resources.assert_called_once()


class TestCallReadFile:
    async def test_returns_string(self, mock_session):
        from mcp_client import call_read_file
        result = await call_read_file(mock_session, "utils.py")
        assert isinstance(result, str)

    async def test_returns_file_contents(self, mock_session):
        from mcp_client import call_read_file
        result = await call_read_file(mock_session, "utils.py")
        assert "def add" in result

    async def test_calls_correct_tool_name(self, mock_session):
        from mcp_client import call_read_file
        await call_read_file(mock_session, "utils.py")
        call_args = mock_session.call_tool.call_args
        assert call_args[0][0] == "read_file"

    async def test_passes_path_argument(self, mock_session):
        from mcp_client import call_read_file
        await call_read_file(mock_session, "utils.py")
        call_args = mock_session.call_tool.call_args
        assert call_args[0][1].get("path") == "utils.py"


# ---------------------------------------------------------------------------
# Tests: mcp_server helpers
# ---------------------------------------------------------------------------

class TestServerReadFile:
    async def test_reads_existing_file(self):
        from mcp_server import _read_file
        result = await _read_file("utils.py")
        assert isinstance(result, list)
        assert len(result) == 1
        assert "def add" in result[0].text

    async def test_rejects_path_traversal_dotdot(self):
        from mcp_server import _read_file
        result = await _read_file("../mcp_server.py")
        assert result[0].text.startswith("ERROR:")

    async def test_rejects_absolute_path(self):
        from mcp_server import _read_file
        result = await _read_file("/etc/passwd")
        assert result[0].text.startswith("ERROR:")

    async def test_missing_file_returns_error(self):
        from mcp_server import _read_file
        result = await _read_file("nonexistent_xyz.py")
        assert result[0].text.startswith("ERROR:")


class TestServerToolRegistration:
    async def test_list_tools_returns_one_tool(self):
        import mcp.types as types
        from mcp_server import server

        handler = server.request_handlers.get(types.ListToolsRequest)
        assert handler is not None, "list_tools handler must be registered"

        req = types.ListToolsRequest(method="tools/list")
        result = await handler(req)
        tool_names = [t.name for t in result.root.tools]
        assert tool_names == ["read_file"], (
            f"Expected exactly ['read_file'], got {tool_names}"
        )

    async def test_read_file_tool_has_valid_json_schema(self):
        import mcp.types as types
        from mcp_server import server

        handler = server.request_handlers.get(types.ListToolsRequest)
        req = types.ListToolsRequest(method="tools/list")
        result = await handler(req)
        tool = result.root.tools[0]

        schema = tool.inputSchema
        assert schema.get("type") == "object"
        assert "properties" in schema
        assert "path" in schema["properties"]
        assert "required" in schema
        assert "path" in schema["required"]

    async def test_unknown_tool_returns_error(self):
        import mcp.types as types
        from mcp_server import server

        handler = server.request_handlers.get(types.CallToolRequest)
        assert handler is not None, "call_tool handler must be registered"

        req = types.CallToolRequest(
            method="tools/call",
            params=types.CallToolRequestParams(name="nonexistent_tool", arguments={}),
        )
        result = await handler(req)
        assert result.root.content[0].text.startswith("ERROR:")


class TestServerResourceRegistration:
    async def test_list_resources_returns_project_listing(self):
        import mcp.types as types
        from mcp_server import server

        handler = server.request_handlers.get(types.ListResourcesRequest)
        assert handler is not None, "list_resources handler must be registered"

        req = types.ListResourcesRequest(method="resources/list")
        result = await handler(req)
        uris = [str(r.uri) for r in result.root.resources]
        assert any("project/listing" in u for u in uris)

    async def test_read_resource_returns_directory_listing(self):
        import warnings
        import mcp.types as types
        from mcp_server import server, PROJECT_DIR

        handler = server.request_handlers.get(types.ReadResourceRequest)
        assert handler is not None, "read_resource handler must be registered"

        req = types.ReadResourceRequest(
            method="resources/read",
            params=types.ReadResourceRequestParams(uri="file://project/listing"),
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = await handler(req)

        content_text = result.root.contents[0].text
        for fname in [f.name for f in PROJECT_DIR.iterdir()]:
            assert fname in content_text


# ---------------------------------------------------------------------------
# Integration smoke test: connect_and_run with mocked stdio transport
# ---------------------------------------------------------------------------

def _make_transport_patches(mock_session):
    from contextlib import asynccontextmanager

    class _FakeStdioClient:
        def __call__(self, params):
            @asynccontextmanager
            async def _cm():
                yield (AsyncMock(), AsyncMock())
            return _cm()

    class _SessionCM:
        def __init__(self_inner, r, w):
            pass
        async def __aenter__(self_inner):
            return mock_session
        async def __aexit__(self_inner, *a):
            pass

    return (
        patch("mcp_client.stdio_client", new=_FakeStdioClient()),
        patch("mcp_client.ClientSession", _SessionCM),
    )


class TestConnectAndRun:
    async def test_returns_all_keys(self, mock_session):
        from mcp_client import connect_and_run
        p1, p2 = _make_transport_patches(mock_session)
        with p1, p2:
            results = await connect_and_run("mcp_server.py")
        assert "tools" in results
        assert "resources" in results
        assert "file_content" in results
        assert "http_content" not in results, (
            "http_content was removed — connect_and_run should not include it"
        )

    async def test_tools_list_contains_read_file(self, mock_session):
        from mcp_client import connect_and_run
        p1, p2 = _make_transport_patches(mock_session)
        with p1, p2:
            results = await connect_and_run("mcp_server.py")
        assert "read_file" in results["tools"]

    async def test_file_content_is_populated(self, mock_session):
        from mcp_client import connect_and_run
        p1, p2 = _make_transport_patches(mock_session)
        with p1, p2:
            results = await connect_and_run("mcp_server.py")
        assert "def add" in results["file_content"]


# ---------------------------------------------------------------------------
# Live end-to-end test (opt-in only)
# ---------------------------------------------------------------------------

@pytest.mark.llm
async def test_live_end_to_end():
    """Spawns the real server subprocess. Run with: pytest --run-llm"""
    from mcp_client import connect_and_run
    server_path = str(LAB_ROOT / "mcp_server.py")
    results = await connect_and_run(server_path)

    assert results["tools"] == ["read_file"]
    assert "def add" in results["file_content"]
    assert any("project/listing" in r[0] for r in results["resources"])
