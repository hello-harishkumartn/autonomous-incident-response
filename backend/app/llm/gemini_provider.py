"""Gemini provider — primary hosted LLM per the project's stack requirements."""
from __future__ import annotations

import json

from app.llm.base import AgentContext, LLMStepDecision, ProviderError, TokenUsage
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
            raise ProviderError("google-genai package not installed") from exc
        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def decide(self, ctx: AgentContext) -> tuple[LLMStepDecision, TokenUsage]:
        from google.genai import types

        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=build_user_prompt(ctx),
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=LLMStepDecision,
                    temperature=0.2,
                ),
            )
        except Exception as exc:  # noqa: BLE001 - any SDK/network failure triggers fallback
            raise ProviderError(f"Gemini call failed: {exc}") from exc

        decision = getattr(response, "parsed", None)
        if decision is None:
            try:
                decision = LLMStepDecision.model_validate(json.loads(response.text))
            except Exception as exc:  # noqa: BLE001
                raise ProviderError(f"Gemini returned unparseable output: {exc}") from exc

        usage = response.usage_metadata
        token_usage = TokenUsage(
            prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            completion_tokens=getattr(usage, "candidates_token_count", 0) or 0,
        )
        return decision, token_usage
