import json
import re
import logging
from typing import Optional

from json_repair import repair_json
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from langdetect import detect, detect_langs, LangDetectException

from app.core.models import get_chat_model
from app.document import load_and_split
from app.summarization.prompts import load_final_prompt, load_map_prompt
from app.schemas.summarize import SummaryResult, KeyDetail

logger = logging.getLogger(__name__)


# Language detection utilities
LANGUAGE_NAMES = {
    "id": "Indonesian", "en": "English", "th": "Thai", "vi": "Vietnamese",
    "zh-cn": "Chinese (Simplified)", "zh-tw": "Chinese (Traditional)",
    "fr": "French", "es": "Spanish", "de": "German", "ja": "Japanese",
    "ko": "Korean", "ru": "Russian", "ar": "Arabic", "pt": "Portuguese",
    "hi": "Hindi", "bn": "Bengali", "pa": "Punjabi",
}


def detect_language(text: str, fallback: str = "en") -> str:
    """Detect language of text. Returns language code (e.g., 'en', 'id', 'th')."""
    if not text or len(text.strip()) < 20:
        logger.debug(f"Text too short for detection, using fallback: {fallback}")
        return fallback
    try:
        lang = detect(text[:500])  # Use first 500 chars for efficiency
        logger.debug(f"Detected language: {lang}")
        return lang
    except LangDetectException:
        logger.debug(f"Detection failed, using fallback: {fallback}")
        return fallback
    except Exception as e:
        logger.error(f"Language detection error: {e}")
        return fallback


def get_language_name(lang_code: str) -> str:
    """Get human-readable language name from code."""
    return LANGUAGE_NAMES.get(lang_code, lang_code.upper())


def build_language_instruction(lang_code: str) -> str:
    """Build instruction for LLM to output in detected language."""
    lang_name = get_language_name(lang_code)
    return (
        f"The document is written in {lang_name} (code: {lang_code}). "
        f"Respond in {lang_name} ONLY. "
        f"All output must be in {lang_name}. Do NOT translate."
    )


def _extract_and_repair(text: str) -> dict:
    """Extract JSON from LLM output and repair any issues using json-repair."""
    if isinstance(text, list):
        text = text[0].get('text', str(text[0])) if text and isinstance(text[0], dict) else str(text)

    text = str(text).strip()

    # Remove markdown code blocks
    text = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', text, flags=re.DOTALL)
    text = text.strip()

    # Find the start of the JSON object
    start_idx = text.find('{')
    if start_idx == -1:
        raise ValueError("No JSON object found in response")
    text = text[start_idx:]

    # Use json-repair to fix all common issues (unquoted keys, trailing commas,
    # missing quotes, truncated JSON, unbalanced braces, etc.)
    repaired = repair_json(text, return_objects=True)

    if not isinstance(repaired, dict):
        raise ValueError(f"Repaired JSON is {type(repaired).__name__}, expected dict")

    return repaired


class RobustJsonParser(BaseOutputParser):
    """JSON parser that repairs common LLM output issues."""

    def parse(self, text: str) -> dict:
        if not isinstance(text, str):
            text = str(text)
        try:
            return _extract_and_repair(text)
        except Exception as e:
            logger.error(f"JSON parse failed. Error: {e}. Raw (first 300 chars): {text[:300]}")
            raise ValueError(f"Failed to parse JSON: {e}")


def _build_summarize_prompt(language_instruction: str = "") -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_final_prompt(language_instruction)),
        ("human", "Analyze this document:\n\n{text}"),
    ])


def _build_map_prompt(language_instruction: str = "") -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_map_prompt(language_instruction)),
        ("human", "{text}"),
    ])


def _build_reduce_prompt(language_instruction: str = "") -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_final_prompt(language_instruction)),
        ("human", "Partial results:\n\n{partial_results}"),
    ])


STUFF_THRESHOLD = 3


async def summarize_document(file_path: str) -> SummaryResult:
    """
    Summarize document with automatic language detection and OCR fallback.
    
    LangChain Pipeline:
    1. Load & extract text (PyPDFLoader or Gemini Vision OCR) → app.document.loader
    2. Detect document language → app.language.detect
    3. Chunk text → RecursiveCharacterTextSplitter
    4. Summarize with language-aware prompts → LangChain chains
       - STUFF: Single LLM call for small docs (≤3 chunks)
       - MAP-REDUCE: Map-reduce pattern for larger docs
    
    Note: Uses LangChain Chains, not Agents (linear deterministic flow)
    """
    # Step 1: Load and split document
    chunks = await load_and_split(file_path)
    if not chunks:
        raise ValueError("Document is empty or could not be parsed.")
    
    # Step 2: Detect language from first chunk
    first_chunk_text = chunks[0].page_content
    lang_code = detect_language(first_chunk_text, fallback="en")
    language_instruction = build_language_instruction(lang_code)
    logger.info(f"Detected language: {lang_code} ({get_language_name(lang_code)})")
    
    # Step 3: Summarize using LangChain chains
    llm = get_chat_model()
    parser = RobustJsonParser()

    if len(chunks) <= STUFF_THRESHOLD:
        return await _stuff_summarize(chunks, llm, parser, language_instruction)

    return await _map_reduce_summarize(chunks, llm, parser, language_instruction)


async def _stuff_summarize(chunks, llm, parser, language_instruction: str = "") -> SummaryResult:
    """
    STUFF chain: Concatenate all chunks and send to LLM in single call.
    
    Best for: Small documents (typically ≤3 chunks, <6K tokens)
    """
    full_text = "\n\n".join(chunk.page_content for chunk in chunks)
    chain = _build_summarize_prompt(language_instruction) | llm | parser
    try:
        result = await chain.ainvoke({"text": full_text})
    except Exception as e:
        raise ValueError(f"Summarization failed: {e}")
    return _parse_result(result)


async def _map_reduce_summarize(chunks, llm, parser, language_instruction: str = "") -> SummaryResult:
    """
    MAP-REDUCE chain: Map summarization across chunks, then reduce results.
    
    Best for: Large documents (>6K tokens, many chunks)
    
    Flow:
      MAP:    For each chunk → mini-summary
      REDUCE: Combine all mini-summaries → final summary
    """
    map_chain = _build_map_prompt(language_instruction) | llm | parser
    partial_results = []

    for i, chunk in enumerate(chunks):
        try:
            partial = await map_chain.ainvoke({"text": chunk.page_content})
            if not isinstance(partial, dict):
                partial = {"partial_summary": str(partial), "partial_details": []}
            partial_results.append(partial)
        except Exception as e:
            # Skip bad chunk — don't fail the whole document
            logger.warning(f"Skipping chunk {i} due to parse error: {e}")
            partial_results.append({
                "partial_summary": f"[Chunk {i} could not be parsed]",
                "partial_details": []
            })

    combined = "\n\n".join(
        f"Partial summary: {p.get('partial_summary', '')}\n"
        f"Partial details: {p.get('partial_details', [])}"
        for p in partial_results
    )

    reduce_chain = _build_reduce_prompt(language_instruction) | llm | parser
    try:
        result = await reduce_chain.ainvoke({"partial_results": combined})
        if not isinstance(result, dict):
            raise ValueError(f"Reduce phase returned invalid type: {type(result).__name__}")
    except Exception as e:
        raise ValueError(f"Reduce phase failed: {e}")

    return _parse_result(result)


def _parse_result(raw: dict) -> SummaryResult:
    if not isinstance(raw, dict):
        raise ValueError(f"Expected dict from parser but got {type(raw).__name__}")

    def _to_str(v) -> str:
        if isinstance(v, list):
            return ", ".join(str(i) for i in v)
        return str(v) if v is not None else ""

    key_details = [
        KeyDetail(label=d.get("label", ""), value=_to_str(d.get("value", "")))
        for d in raw.get("key_details", [])
        if isinstance(d, dict) and d.get("label")
    ]
    return SummaryResult(
        summary=raw.get("summary", ""),
        key_details=key_details,
    )
