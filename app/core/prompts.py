from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_final_prompt() -> str:
    """Load the final prompt for document summarization (used in both STUFF and REDUCE phases)."""
    return (PROMPTS_DIR / "final_prompt.txt").read_text(encoding="utf-8").strip()


def load_map_prompt() -> str:
    """Load the MAP phase prompt for analyzing individual document chunks."""
    return (PROMPTS_DIR / "map_prompt.txt").read_text(encoding="utf-8").strip()
