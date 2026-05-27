from app.llm.client import LLMClient


def test_generate_json_extracts_fenced_json(monkeypatch):
    client = object.__new__(LLMClient)

    def fake_generate_text(_system_prompt, _payload):
        return '```json\n{"decision": "continue_current_skill"}\n```'

    monkeypatch.setattr(client, "generate_text", fake_generate_text)

    assert client.generate_json("prompt", {}) == {"decision": "continue_current_skill"}


def test_generate_json_retries_invalid_json(monkeypatch):
    client = object.__new__(LLMClient)
    calls = iter(["not json", '{"ok": true}'])

    def fake_generate_text(_system_prompt, _payload):
        return next(calls)

    monkeypatch.setattr(client, "generate_text", fake_generate_text)

    assert client.generate_json("prompt", {}) == {"ok": True}

