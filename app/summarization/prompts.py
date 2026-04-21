from pathlib import Path
from typing import Optional

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def load_final_prompt(language_instruction: str = "") -> str:
    """
    Load the final prompt for document summarization.
    
    Used in both STUFF and REDUCE phases.
    Optionally appends multilingual instruction.
    
    Args:
        language_instruction: Optional instruction for multilingual output
                              (e.g., "The document is in Indonesian (id). Respond in Indonesian only.")
    """
    prompt = (PROMPTS_DIR / "final_prompt.txt").read_text(encoding="utf-8").strip()
    
    if language_instruction:
        prompt = f"{prompt}\n\nLANGUAGE REQUIREMENT:\n{language_instruction}"
    
    return prompt


def load_map_prompt(language_instruction: str = "") -> str:
    """
    Load the MAP phase prompt for analyzing individual document chunks.
    
    Optionally appends multilingual instruction.
    
    Args:
        language_instruction: Optional instruction for multilingual output
    """
    prompt = (PROMPTS_DIR / "map_prompt.txt").read_text(encoding="utf-8").strip()
    
    if language_instruction:
        prompt = f"{prompt}\n\nLANGUAGE REQUIREMENT:\n{language_instruction}"
    
    return prompt
