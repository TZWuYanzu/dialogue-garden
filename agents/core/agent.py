from __future__ import annotations

from typing import Callable

from ..config import PROMPTS_DIR
from ..tools import Tool
from .client import ClaudeClient
from .types import ROLE_PROMPT_FILES, AgentRole

MAX_TOOL_ITERATIONS = 15


class Agent:
    """Sub-agent runner: receives a task, runs tool loops, returns text."""

    def __init__(
        self,
        role: AgentRole,
        client: ClaudeClient,
        tools: list[Tool] | None = None,
        on_tool_call: Callable[[str, str], None] | None = None,
    ):
        self.role = role
        self.client = client
        self.tools = tools or []
        self.on_tool_call = on_tool_call or (lambda name, _input: None)
        self.system_prompt = self._load_prompt()

    def run(self, task: str, context: str = "") -> str:
        user_content = f"{context}\n\n{task}" if context else task
        messages: list[dict] = [{"role": "user", "content": user_content}]
        tool_defs = [t.definition for t in self.tools] if self.tools else None

        for _ in range(MAX_TOOL_ITERATIONS):
            response = self.client.chat(
                system=self.system_prompt,
                messages=messages,
                tools=tool_defs,
            )

            if response.stop_reason == "end_turn" or not self._has_tool_use(response):
                return self._extract_text(response)

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    self.on_tool_call(block.name, str(block.input)[:100])
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})

        return self._extract_text(response)

    def _execute_tool(self, name: str, params: dict) -> str:
        for tool in self.tools:
            if tool.name == name:
                try:
                    return tool.handler(params)
                except Exception as e:
                    return f"工具执行错误: {e}"
        return f"未知工具: {name}"

    def _load_prompt(self) -> str:
        filename = ROLE_PROMPT_FILES[self.role]
        return (PROMPTS_DIR / filename).read_text(encoding="utf-8")

    @staticmethod
    def _has_tool_use(response) -> bool:
        return any(block.type == "tool_use" for block in response.content)

    @staticmethod
    def _extract_text(response) -> str:
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else ""
