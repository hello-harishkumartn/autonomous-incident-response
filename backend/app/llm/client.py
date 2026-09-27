"""LLMClient: tries providers in order, tracks which one actually answered.

`llm_provider` config controls this:
- "auto" (default): gemini (if GEMINI_API_KEY set) -> ollama (if reachable) -> offline.
- "gemini" / "ollama" / "offline": pin to exactly one, no fallback (used by tests
  to keep runs hermetic and by anyone who wants a guaranteed-consistent provider).
"""
from __future__ import annotations

import logging

from app.config import settings
from app.llm.base import AgentContext, LLMProvider, LLMStepDecision, ProviderError, TokenUsage
from app.llm.offline_provider import OfflineHeuristicProvider

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self):
        self._providers: list[LLMProvider] = self._build_chain()

    def _build_chain(self) -> list[LLMProvider]:
        mode = settings.llm_provider
        providers: list[LLMProvider] = []

        if mode in ("auto", "gemini") and settings.gemini_api_key:
            try:
                from app.llm.gemini_provider import GeminiProvider

                providers.append(GeminiProvider(settings.gemini_api_key, settings.gemini_model))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Gemini provider unavailable: %s", exc)

        if mode in ("auto", "ollama"):
            from app.llm.ollama_provider import OllamaProvider

            ollama = OllamaProvider(settings.ollama_host, settings.ollama_model)
            if mode == "ollama" or ollama.is_reachable():
                providers.append(ollama)

        if mode in ("auto", "offline") or not providers:
            providers.append(OfflineHeuristicProvider())

        return providers

    def decide(self, ctx: AgentContext) -> tuple[LLMStepDecision, TokenUsage, str]:
        last_error: Exception | None = None
        for provider in self._providers:
            try:
                decision, usage = provider.decide(ctx)
                return decision, usage, provider.name
            except ProviderError as exc:
                logger.warning("Provider %s failed, falling back: %s", provider.name, exc)
                last_error = exc
                continue
        raise ProviderError(f"All LLM providers exhausted: {last_error}")
