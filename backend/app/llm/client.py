from __future__ import annotations

from collections.abc import Iterator
import json
from typing import Any

from openai import OpenAI

from app.db.models import ModelConfig
from app.security.encryption import decrypt_secret


class LLMError(Exception):
    """Raised when an LLM provider request or response normalization fails."""


class LLMClient:
    def __init__(self, model_config: ModelConfig):
        api_key = decrypt_secret(model_config.api_key_encrypted)
        if not api_key:
            raise LLMError("Model API key is not configured")
        self.client = OpenAI(api_key=api_key, base_url=model_config.base_url)
        self.model = model_config.model
        self.temperature = model_config.temperature
        self.max_output_tokens = model_config.max_output_tokens

    def generate_text(self, system_prompt: str, user_payload: dict[str, Any]) -> str:
        serialized = json.dumps(user_payload, ensure_ascii=False)
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=system_prompt,
                input=serialized,
                temperature=self.temperature,
                max_output_tokens=self.max_output_tokens,
            )
            return response.output_text
        except Exception as first_exc:
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": serialized},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_output_tokens,
                )
                content = completion.choices[0].message.content
                if not content:
                    raise LLMError("Model returned an empty response")
                return content
            except Exception as second_exc:
                raise LLMError(str(second_exc)) from first_exc

    def generate_text_stream(self, system_prompt: str, user_payload: dict[str, Any]) -> Iterator[str]:
        serialized = json.dumps(user_payload, ensure_ascii=False)
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": serialized},
                ],
                temperature=self.temperature,
                max_tokens=self.max_output_tokens,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except Exception as exc:
            raise LLMError(str(exc)) from exc

    def generate_json(self, system_prompt: str, user_payload: dict[str, Any]) -> dict[str, Any]:
        text = self.generate_text(system_prompt, user_payload)
        try:
            return json.loads(_extract_json(text))
        except json.JSONDecodeError:
            retry_payload = {
                "previous_output": text,
                "instruction": "请将上一次输出修正为合法 JSON，不要输出任何解释。",
            }
            retry_text = self.generate_text(system_prompt, retry_payload)
            try:
                return json.loads(_extract_json(retry_text))
            except json.JSONDecodeError as exc:
                raise LLMError("Model did not return valid JSON") from exc


def _extract_json(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end >= start:
        return stripped[start : end + 1]
    return stripped
