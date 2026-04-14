from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_system_prompt() -> str:
    return (PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8").strip()
