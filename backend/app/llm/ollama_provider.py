"""Ollama provider — free, fully local fallback when Gemini is unavailable."""
from __future__ import annotations

import json

import httpx

from app.llm.base import AgentContext, LLMStepDecision, ProviderError, TokenUsage
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt


class OllamaProvider:
    name = "ollama"

    def __init__(self, host: str, model: str, timeout: float = 30.0):
        self._host = host.rstrip("/")
        self._model = model
        self._timeout = timeout

    def decide(self, ctx: AgentContext) -> tuple[LLMStepDecision, TokenUsage]:
        payload = {
            "model": self._model,
            "system": SYSTEM_PROMPT,
            "prompt": build_user_prompt(ctx),
            "format": "json",
            "stream": False,
        }
        try:
            resp = httpx.post(f"{self._host}/api/generate", json=payload, timeout=self._timeout)
            resp.raise_for_status()
            data = resp.json()
            decision = LLMStepDecision.model_validate(json.loads(data["response"]))
        except Exception as exc:  # noqa: BLE001 - any failure triggers fallback to offline
            raise ProviderError(f"Ollama call failed: {exc}") from exc

        token_usage = TokenUsage(
            prompt_tokens=data.get("prompt_eval_count", 0) or 0,
            completion_tokens=data.get("eval_count", 0) or 0,
        )
        return decision, token_usage

    def is_reachable(self) -> bool:
        try:
            resp = httpx.get(f"{self._host}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False
