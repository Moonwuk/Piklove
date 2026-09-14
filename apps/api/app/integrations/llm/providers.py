import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from app.config import Settings
from app.integrations.llm.errors import LLMError, LLMInvalidResponse, LLMTimeout
from app.services.schemas import (
    AIConversationContext,
    ConversationAnalysis,
    ReplySuggestions,
)

PROMPTS = Path(__file__).parents[2] / "prompts"


class JSONChatProvider:
    provider_name: str
    base_url: str

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.analysis_model = settings.effective_analysis_model
        self.reply_model = settings.effective_reply_model
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {settings.effective_llm_api_key}"},
            timeout=settings.effective_llm_timeout_seconds,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        attempts = self.settings.effective_llm_max_retries + 1
        for attempt in range(attempts):
            try:
                response = await self.client.post(path, json=payload)
            except httpx.TimeoutException as exc:
                if attempt + 1 == attempts:
                    raise LLMTimeout from exc
            except httpx.RequestError as exc:
                if attempt + 1 == attempts:
                    raise LLMError from exc
            else:
                if response.status_code < 400:
                    try:
                        return response.json()
                    except ValueError as exc:
                        raise LLMInvalidResponse from exc
                if response.status_code not in (429, 500, 502, 503, 504) or attempt + 1 == attempts:
                    raise LLMError
            await asyncio.sleep(min(0.1 * (2**attempt), 1.0))
        raise AssertionError("retry loop exhausted")

    @staticmethod
    def _validate(content: Any, schema: type[BaseModel]) -> BaseModel:
        if not isinstance(content, str) or not content.strip():
            raise LLMInvalidResponse
        try:
            return schema.model_validate_json(content)
        except (ValidationError, ValueError, TypeError) as exc:
            raise LLMInvalidResponse from exc

    @staticmethod
    def _system_prompt(filename: str, schema: type[BaseModel]) -> str:
        prompt = (PROMPTS / filename).read_text()
        return (
            f"{prompt}\n\nReturn exactly one JSON object matching this JSON schema; "
            f"do not use markdown fences:\n{json.dumps(schema.model_json_schema())}"
        )

    async def analyze_conversation(self, context: AIConversationContext) -> ConversationAnalysis:
        content = await self._chat(
            self.analysis_model,
            self._system_prompt("conversation_analyzer.md", ConversationAnalysis),
            context.model_dump_json(),
        )
        return self._validate(content, ConversationAnalysis)

    async def generate_replies(
        self, context: AIConversationContext, analysis: ConversationAnalysis
    ) -> ReplySuggestions:
        prompt = self._system_prompt("reply_generator.md", ReplySuggestions)
        user = f"{context.model_dump_json()}\nAnalysis:\n{analysis.model_dump_json()}"
        content = await self._chat(self.reply_model, prompt, user)
        return self._validate(content, ReplySuggestions)

    async def summarize_conversation(self, context: AIConversationContext) -> str:
        return ""

    async def _chat(self, model: str, system: str, user: str) -> str:
        raise NotImplementedError


class DeepSeekProvider(JSONChatProvider):
    provider_name = "deepseek"
    base_url = "https://api.deepseek.com"

    async def _chat(self, model: str, system: str, user: str) -> str:
        body = await self._post(
            "/chat/completions",
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
                "stream": False,
            },
        )
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMInvalidResponse from exc


class OllamaCloudProvider(JSONChatProvider):
    provider_name = "ollama_cloud"
    base_url = "https://ollama.com"

    async def _chat(self, model: str, system: str, user: str) -> str:
        body = await self._post(
            "/api/chat",
            {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
            },
        )
        try:
            return body["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise LLMInvalidResponse from exc
