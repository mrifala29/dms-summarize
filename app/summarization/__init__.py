"""Summarization module: LangChain chains, language detection, and prompt management."""

from app.summarization.chains import (
    summarize_document,
    detect_language,
    get_language_name,
    build_language_instruction,
)
from app.summarization.prompts import load_final_prompt, load_map_prompt

__all__ = [
    "summarize_document",
    "detect_language",
    "get_language_name",
    "build_language_instruction",
    "load_final_prompt",
    "load_map_prompt",
]
