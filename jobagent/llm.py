"""Forbindelse til AI-modellen.

Bruger openai-biblioteket, som både virker med:
  - Ollama (gratis, kører lokalt på din computer)
  - OpenAI (kræver API-nøgle og koster lidt pr. kald)
Indstillingerne hentes fra .env-filen.
"""

import os
from typing import Protocol


class LLM(Protocol):
    """Alt, der har en chat()-metode, kan bruges som AI-model (gør test nemt)."""

    def chat(self, system: str, user: str) -> str: ...


class OpenAICompatibleLLM:
    def __init__(self, model: str | None = None, base_url: str | None = None, api_key: str | None = None):
        from openai import OpenAI  # importeres her, så tests kan køre uden openai

        self.model = model or os.getenv("AI_MODEL", "llama3.2")
        self.client = OpenAI(
            base_url=base_url or os.getenv("AI_BASE_URL", "http://localhost:11434/v1"),
            api_key=api_key or os.getenv("AI_API_KEY", "ollama"),
        )

    def chat(self, system: str, user: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.4,
        )
        return response.choices[0].message.content or ""
