from __future__ import annotations

import sys

from .config import ANTHROPIC_API_KEY, KNOWLEDGE_DIR, MODEL
from .core.client import ClaudeClient
from .core.orchestrator import Orchestrator
from .core.storage import KnowledgeStore
from .tools.knowledge import (
    make_read_formulas_tool,
    make_read_reviews_tool,
    make_read_topics_tool,
)

HELP_TEXT = """
可用命令：
  /topics    — 查看选题库
  /formulas  — 查看爆款公式手册
  /reviews   — 查看复盘记录
  /cost      — 查看累计 API 花费
  /reset     — 清空对话历史（重新开始）
  /help      — 显示本帮助
  /quit      — 退出
""".strip()


def _print_status(msg: str) -> None:
    print(f"\033[90m{msg}\033[0m", flush=True)


def main() -> None:
    if not ANTHROPIC_API_KEY:
        print("错误：未设置 ANTHROPIC_API_KEY")
        print("请在项目根目录的 .env 文件中填入你的 API Key：")
        print("  ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    client = ClaudeClient(ANTHROPIC_API_KEY, MODEL)
    store = KnowledgeStore(KNOWLEDGE_DIR)
    orch = Orchestrator(client, store, on_status=_print_status)

    print(f"🏔️  户外博主运营团队 v0.1 (model: {MODEL})")
    print(f"输入 /help 查看可用命令\n")

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input.split()[0].lower()

            if cmd in ("/quit", "/exit", "/q"):
                print("再见！")
                break

            elif cmd == "/help":
                print(HELP_TEXT)

            elif cmd == "/cost":
                print(client.cost_summary())

            elif cmd == "/reset":
                orch.reset()
                print("对话历史已清空。")

            elif cmd == "/topics":
                tool = make_read_topics_tool(store)
                print(tool.handler({}))

            elif cmd == "/formulas":
                tool = make_read_formulas_tool(store)
                print(tool.handler({}))

            elif cmd == "/reviews":
                tool = make_read_reviews_tool(store)
                print(tool.handler({}))

            else:
                print(f"未知命令: {cmd}，输入 /help 查看可用命令")

            print()
            continue

        try:
            response = orch.chat(user_input)
            print(f"\n{response}\n")
            _print_status(client.cost_summary())
            print()
        except KeyboardInterrupt:
            print("\n(已中断)")
        except Exception as e:
            print(f"\n错误: {e}\n")


if __name__ == "__main__":
    main()
