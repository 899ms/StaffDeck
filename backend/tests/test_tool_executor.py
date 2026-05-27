from app.tools.tool_executor import ToolExecutor


def test_resolve_secret_header(monkeypatch):
    monkeypatch.setenv("ORDER_API_TOKEN", "token-123")
    executor = object.__new__(ToolExecutor)

    headers = executor._resolve_headers(
        {"Authorization": "Bearer ${secret.ORDER_API_TOKEN}"},
        {},
    )

    assert headers["Authorization"] == "Bearer token-123"

