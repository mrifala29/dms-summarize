import json
import re
import logging

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import BaseOutputParser

from app.core.models import get_chat_model
from app.core.document_loader import load_and_split
from app.core.prompts import load_final_prompt, load_map_prompt
from app.schemas.summarize import SummaryResult, KeyDetail

logger = logging.getLogger(__name__)


def _force_close_json(text: str) -> str:
    """Force-close an incomplete JSON by tracking unclosed brackets/braces."""
    in_string = False
    escape_next = False
    stack = []
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in '{[':
            stack.append(ch)
        elif ch == '}' and stack and stack[-1] == '{':
            stack.pop()
        elif ch == ']' and stack and stack[-1] == '[':
            stack.pop()

    # Remove trailing comma before closing
    text = re.sub(r',\s*$', '', text.rstrip())

    # Close all unclosed brackets in reverse order
    for ch in reversed(stack):
        text += ']' if ch == '[' else '}'

    return text


def _repair_json(text: str) -> str:
    """Extract and repair JSON from LLM output."""
    if isinstance(text, list):
        text = text[0].get('text', str(text[0])) if text and isinstance(text[0], dict) else str(text)

    text = str(text).strip()

    # Remove markdown code blocks
    text = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', text, flags=re.DOTALL)
    text = text.strip()

    # Find opening brace
    start_idx = text.find('{')
    if start_idx == -1:
        raise ValueError("No JSON object found in response")

    text = text[start_idx:]

    # Try to find balanced end (properly handles strings with braces)
    brace_count = 0
    end_idx = -1
    in_string = False
    escape_next = False
    for i, ch in enumerate(text):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            brace_count += 1
        elif ch == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break

    if end_idx == -1:
        logger.warning("JSON not balanced — attempting force-close")
        text = _force_close_json(text)
    else:
        text = text[:end_idx]

    # Fix trailing commas
    text = re.sub(r',\s*([\]}])', r'\1', text)

    return text.strip()


class RobustJsonParser(BaseOutputParser):
    """JSON parser that repairs common LLM output issues."""

    def parse(self, text: str) -> dict:
        if not isinstance(text, str):
            text = str(text)

        try:
            repaired = _repair_json(text)
            result = json.loads(repaired)
            if not isinstance(result, dict):
                raise ValueError(f"Expected JSON object, got {type(result).__name__}")
            return result
        except Exception as e:
            logger.error(f"JSON parse failed. Error: {e}. Raw (first 300 chars): {text[:300]}")
            raise ValueError(f"Failed to parse JSON: {e}")


def _build_summarize_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_final_prompt()),
        ("human", "Analyze this document:\n\n{text}"),
    ])


def _build_map_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_map_prompt()),
        ("human", "{text}"),
    ])


def _build_reduce_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", load_final_prompt()),
        ("human", "Partial results:\n\n{partial_results}"),
    ])


STUFF_THRESHOLD = 3


async def summarize_document(file_path: str) -> SummaryResult:
    chunks = load_and_split(file_path)
    if not chunks:
        raise ValueError("Document is empty or could not be parsed.")

    llm = get_chat_model()
    parser = RobustJsonParser()

    if len(chunks) <= STUFF_THRESHOLD:
        return await _stuff_summarize(chunks, llm, parser)

    return await _map_reduce_summarize(chunks, llm, parser)


async def _stuff_summarize(chunks, llm, parser) -> SummaryResult:
    full_text = "\n\n".join(chunk.page_content for chunk in chunks)
    chain = _build_summarize_prompt() | llm | parser
    try:
        result = await chain.ainvoke({"text": full_text})
    except Exception as e:
        raise ValueError(f"Summarization failed: {e}")
    return _parse_result(result)


async def _map_reduce_summarize(chunks, llm, parser) -> SummaryResult:
    map_chain = _build_map_prompt() | llm | parser
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

    reduce_chain = _build_reduce_prompt() | llm | parser
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
