from __future__ import annotations

import anthropic

# Sonnet pricing (per million tokens)
_PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-sonnet-4-5-20250514": {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0, "cache_read": 0.08, "cache_write": 1.0},
}
_DEFAULT_PRICING = {"input": 3.0, "output": 15.0, "cache_read": 0.30, "cache_write": 3.75}


class ClaudeClient:

    def __init__(self, api_key: str, model: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cache_read_tokens = 0
        self.total_cache_creation_tokens = 0

    def chat(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
    ) -> anthropic.types.Message:
        system_with_cache = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_with_cache,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        response = self.client.messages.create(**kwargs)
        self._track_usage(response.usage)
        return response

    def _track_usage(self, usage) -> None:
        self.total_input_tokens += usage.input_tokens
        self.total_output_tokens += usage.output_tokens
        self.total_cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        self.total_cache_creation_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0

    @property
    def cost(self) -> float:
        p = _PRICING.get(self.model, _DEFAULT_PRICING)
        return (
            self.total_input_tokens * p["input"]
            + self.total_output_tokens * p["output"]
            + self.total_cache_read_tokens * p["cache_read"]
            + self.total_cache_creation_tokens * p["cache_write"]
        ) / 1_000_000

    def cost_summary(self) -> str:
        return (
            f"Tokens: {self.total_input_tokens} in / {self.total_output_tokens} out"
            f" | Cache: {self.total_cache_read_tokens} read / {self.total_cache_creation_tokens} write"
            f" | Cost: ${self.cost:.4f}"
        )
