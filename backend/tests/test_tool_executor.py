import sys
from pathlib import Path

import httpx

from app.tools.tool_executor import ToolExecutor
from app.tools.tool_schema import ToolCall
from app.db.models import Tenant, Tool
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


def test_resolve_secret_header(monkeypatch):
    monkeypatch.setenv("ORDER_API_TOKEN", "token-123")
    executor = object.__new__(ToolExecutor)

    headers = executor._resolve_headers(
        {"Authorization": "Bearer ${secret.ORDER_API_TOKEN}"},
        {},
    )

    assert headers["Authorization"] == "Bearer token-123"


def test_execute_builtin_mcp_tool_success() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        db.add(
            Tool(
                tenant_id="tenant_demo",
                name="mcp.demo_echo",
                display_name="MCP Demo Echo",
                tool_type="mcp",
                method="POST",
                url="mcp://builtin.demo/echo",
                config_json={"server": "builtin.demo", "tool": "echo"},
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                enabled=True,
            )
        )
        db.commit()

        result = ToolExecutor(db).execute(
            tenant_id="tenant_demo",
            tool_call=ToolCall(name="mcp.demo_echo", arguments={"text": "hello mcp"}),
        )

        assert result.success is True
        assert result.data == {"text": "hello mcp", "length": 9}


def test_execute_builtin_mcp_tool_unknown_config_returns_error() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        db.add(
            Tool(
                tenant_id="tenant_demo",
                name="mcp.bad",
                display_name="Bad MCP",
                tool_type="mcp",
                method="POST",
                url="mcp://builtin.demo/missing",
                config_json={"server": "builtin.demo", "tool": "missing"},
                enabled=True,
            )
        )
        db.commit()

        result = ToolExecutor(db).execute(
            tenant_id="tenant_demo",
            tool_call=ToolCall(name="mcp.bad", arguments={}),
        )

        assert result.success is False
        assert result.error is not None
        assert result.error.code == "MCP_ERROR"


def test_execute_stdio_mcp_tool_success() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        db.add(
            Tool(
                tenant_id="tenant_demo",
                name="mcp.real_echo",
                display_name="Real MCP Echo",
                tool_type="mcp",
                method="POST",
                url="mcp://stdio/mock/echo",
                config_json={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [str(_mock_mcp_server_path())],
                    "tool": "echo",
                },
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                enabled=True,
            )
        )
        db.commit()

        result = ToolExecutor(db).execute(
            tenant_id="tenant_demo",
            tool_call=ToolCall(name="mcp.real_echo", arguments={"text": "hello real mcp"}),
        )

        assert result.success is True
        assert result.data == {"text": "hello real mcp", "length": 14}


def test_execute_stdio_mcp_tool_error_is_stable() -> None:
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        db.add(
            Tool(
                tenant_id="tenant_demo",
                name="mcp.real_sum",
                display_name="Real MCP Sum",
                tool_type="mcp",
                method="POST",
                url="mcp://stdio/mock/sum",
                config_json={
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [str(_mock_mcp_server_path())],
                    "tool": "sum",
                },
                enabled=True,
            )
        )
        db.commit()

        result = ToolExecutor(db).execute(
            tenant_id="tenant_demo",
            tool_call=ToolCall(name="mcp.real_sum", arguments={"numbers": ["bad"]}),
        )

        assert result.success is False
        assert result.error is not None
        assert result.error.code == "MCP_ERROR"
        assert "numbers" in result.error.message


def test_execute_get_tool_preserves_query_string_when_arguments_empty(monkeypatch) -> None:
    requested: dict[str, object] = {}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def request(self, method, url, headers=None, json=None, params=None):
            requested.update({"method": method, "url": url, "params": params})
            return httpx.Response(
                200,
                json={"current": {"temperature_2m": 27.4}},
                request=httpx.Request(method, url),
            )

    monkeypatch.setattr(httpx, "Client", FakeClient)
    with _test_session() as db:
        db.add(Tenant(id="tenant_demo", name="Demo"))
        db.add(
            Tool(
                tenant_id="tenant_demo",
                name="weather.forecast",
                display_name="天气查询",
                method="GET",
                url=(
                    "https://api.open-meteo.com/v1/forecast"
                    "?latitude=39.90&longitude=116.40&current=temperature_2m"
                ),
                enabled=True,
            )
        )
        db.commit()

        result = ToolExecutor(db).execute(
            tenant_id="tenant_demo",
            tool_call=ToolCall(name="weather.forecast", arguments={}),
        )

    assert result.success is True
    assert result.data == {"current": {"temperature_2m": 27.4}}
    assert requested == {
        "method": "GET",
        "url": (
            "https://api.open-meteo.com/v1/forecast"
            "?latitude=39.90&longitude=116.40&current=temperature_2m"
        ),
        "params": None,
    }


def _mock_mcp_server_path() -> Path:
    return Path(__file__).resolve().parents[1] / "mock_servers" / "mcp_stdio_server.py"


def _test_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)
