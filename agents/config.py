import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
MODEL: str = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")

DATA_DIR: Path = PROJECT_ROOT / "xhs" / "data"
KNOWLEDGE_DIR: Path = PROJECT_ROOT / "data" / "knowledge"
PROMPTS_DIR: Path = PROJECT_ROOT / "accio-deploy" / "prompts"
