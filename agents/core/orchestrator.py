from __future__ import annotations

from datetime import datetime
from typing import Callable

from ..config import DATA_DIR, KNOWLEDGE_DIR, PROMPTS_DIR
from ..tools import Tool
from ..tools.data_query import make_query_bloggers_tool, make_query_posts_tool
from ..tools.knowledge import (
    make_add_formula_tool,
    make_add_topic_tool,
    make_read_formulas_tool,
    make_read_reviews_tool,
    make_read_topics_tool,
    make_save_review_tool,
    make_update_topic_tool,
)
from .agent import Agent
from .client import ClaudeClient
from .storage import KnowledgeStore
from .types import ROLE_DISPLAY_NAMES, ROLE_PROMPT_FILES, AgentRole

MAX_TOOL_ITERATIONS = 15

_DISPATCH_TOOL = Tool(
    name="dispatch_to_agent",
    description=(
        "派遣任务给子Agent。将具体工作分配给数据分析专家、内容产出专家、复盘专家或选题排期专家。"
        "使用任务信封格式描述任务，确保子Agent有足够上下文独立完成工作。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "agent": {
                "type": "string",
                "enum": ["data_analyst", "content_expert", "review_expert", "topic_scheduler"],
                "description": "目标Agent角色",
            },
            "task": {
                "type": "string",
                "description": "任务描述（建议使用任务信封格式，包含目标、背景、具体要求）",
            },
            "context": {
                "type": "string",
                "description": "额外上下文（如其他Agent的分析结果）",
            },
        },
        "required": ["agent", "task"],
    },
    handler=lambda _: "",  # placeholder, handled by orchestrator
)


class Orchestrator:
    """Manages the TeamLeader conversation and dispatches to sub-agents."""

    def __init__(
        self,
        client: ClaudeClient,
        store: KnowledgeStore | None = None,
        on_status: Callable[[str], None] | None = None,
    ):
        self.client = client
        self.store = store or KnowledgeStore(KNOWLEDGE_DIR)
        self.on_status = on_status or (lambda msg: None)
        self.conversation: list[dict] = []
        self._system_prompt = self._build_system_prompt()
        self._role_tools = self._build_role_tools()

    def chat(self, user_message: str) -> str:
        self.conversation.append({"role": "user", "content": user_message})

        tl_tools = [_DISPATCH_TOOL, make_read_formulas_tool(self.store)]
        tool_defs = [t.definition for t in tl_tools]

        for _ in range(MAX_TOOL_ITERATIONS):
            response = self.client.chat(
                system=self._system_prompt,
                messages=self.conversation,
                tools=tool_defs,
            )

            tool_uses = [b for b in response.content if b.type == "tool_use"]

            if not tool_uses:
                text = self._extract_text(response)
                self.conversation.append({"role": "assistant", "content": text})
                return text

            self.conversation.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tu in tool_uses:
                if tu.name == "dispatch_to_agent":
                    result = self._dispatch(tu.input)
                else:
                    result = self._execute_local_tool(tu.name, tu.input, tl_tools)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": result,
                })
            self.conversation.append({"role": "user", "content": tool_results})

        return self._extract_text(response)

    def reset(self) -> None:
        self.conversation.clear()

    def _dispatch(self, params: dict) -> str:
        role = AgentRole(params["agent"])
        task = params["task"]
        context = params.get("context", "")
        display = ROLE_DISPLAY_NAMES[role]
        self.on_status(f"[Team Leader → {display}] 正在处理...")

        tools = self._role_tools.get(role, [])

        def on_sub_tool(name: str, preview: str) -> None:
            self.on_status(f"  [{display}] 调用工具 {name}")

        agent = Agent(role, self.client, tools, on_tool_call=on_sub_tool)
        result = agent.run(task, context)
        self.on_status(f"[{display}] 完成")
        return result

    def _execute_local_tool(self, name: str, params: dict, tools: list[Tool]) -> str:
        for tool in tools:
            if tool.name == name:
                try:
                    return tool.handler(params)
                except Exception as e:
                    return f"工具执行错误: {e}"
        return f"未知工具: {name}"

    def _build_system_prompt(self) -> str:
        base = (PROMPTS_DIR / ROLE_PROMPT_FILES[AgentRole.TEAM_LEADER]).read_text(encoding="utf-8")
        supplement = (
            "\n\n---\n\n## 系统能力\n\n"
            "你正在 Claude API Agent 系统中运行。你有以下能力：\n\n"
            "- **dispatch_to_agent**：派遣任务给子Agent（数据分析/内容产出/复盘/选题排期）\n"
            "- **read_formulas**：查阅爆款公式手册\n"
            "- 数据分析专家可查询本地已采集的 560 条帖子数据和博主数据\n"
            "- 选题排期专家可管理选题库（添加/更新选题卡片）\n"
            "- 复盘专家可保存复盘记录和更新爆款公式\n\n"
            f"今天日期：{datetime.now().strftime('%Y/%m/%d')}\n"
        )
        return base + supplement

    def _build_role_tools(self) -> dict[AgentRole, list[Tool]]:
        return {
            AgentRole.DATA_ANALYST: [
                make_query_posts_tool(DATA_DIR),
                make_query_bloggers_tool(DATA_DIR),
                make_read_formulas_tool(self.store),
            ],
            AgentRole.CONTENT_EXPERT: [
                make_read_formulas_tool(self.store),
            ],
            AgentRole.REVIEW_EXPERT: [
                make_read_formulas_tool(self.store),
                make_add_formula_tool(self.store),
                make_save_review_tool(self.store),
                make_read_reviews_tool(self.store),
            ],
            AgentRole.TOPIC_SCHEDULER: [
                make_read_topics_tool(self.store),
                make_add_topic_tool(self.store),
                make_update_topic_tool(self.store),
                make_read_formulas_tool(self.store),
            ],
        }

    @staticmethod
    def _extract_text(response) -> str:
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "\n".join(parts) if parts else ""
