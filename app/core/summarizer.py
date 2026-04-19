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


def _repair_json(text: str) -> str:
    """Extract and repair JSON from LLM output (handles markdown blocks, trailing commas, extra text)."""
    # Handle cases where response is list-like
    if isinstance(text, list):
        if len(text) > 0 and isinstance(text[0], dict) and 'text' in text[0]:
            text = text[0]['text']
        else:
            text = str(text)
    
    text = str(text).strip()
    
    # Remove markdown code blocks (```json ... ``` or ``` ... ```)
    text = re.sub(r'```(?:json)?\s*(.*?)\s*```', r'\1', text, flags=re.DOTALL)
    text = text.strip()
    
    # Find first { and extract until balanced }
    start_idx = text.find('{')
    if start_idx == -1:
        raise ValueError(f"No JSON object found in response")
    
    # Extract from { to balanced }
    brace_count = 0
    end_idx = -1
    for i in range(start_idx, len(text)):
        if text[i] == '{':
            brace_count += 1
        elif text[i] == '}':
            brace_count -= 1
            if brace_count == 0:
                end_idx = i + 1
                break
    
    if end_idx == -1:
        raise ValueError("Unbalanced JSON braces in response")
    
    json_str = text[start_idx:end_idx]
    
    # Repair trailing commas
    json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
    
    return json_str.strip()


class RobustJsonParser(BaseOutputParser):
    """Json parser that repairs common issues like trailing commas."""

    def parse(self, text: str) -> dict:
        try:
            text = _repair_json(text)
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON after repair: {str(e)}")


def _build_summarize_prompt() -> ChatPromptTemplate:
    """Build prompt for STUFF phase (document with ≤3 chunks)."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", load_final_prompt()),
            ("human", "Analyze this document:\n\n{text}"),
        ]
    )


def _build_map_prompt() -> ChatPromptTemplate:
    """Build prompt for MAP phase (chunk-by-chunk analysis in map-reduce)."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", load_map_prompt()),
            ("human", "{text}"),
        ]
    )


def _build_reduce_prompt() -> ChatPromptTemplate:
    """Build prompt for REDUCE phase (combining partial results in map-reduce)."""
    return ChatPromptTemplate.from_messages(
        [
            ("system", load_final_prompt()),
            ("human", "Partial results:\n\n{partial_results}"),
        ]
    )


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
        raise ValueError(f"Summarization failed (stuff): {str(e)}")
    return _parse_result(result)


async def _map_reduce_summarize(chunks, llm, parser) -> SummaryResult:
    map_chain = _build_map_prompt() | llm | parser
    partial_results = []
    for i, chunk in enumerate(chunks):
        try:
            partial = await map_chain.ainvoke({"text": chunk.page_content})
            partial_results.append(partial)
        except Exception as e:
            raise ValueError(f"Map phase failed on chunk {i}: {str(e)}")

    combined = "\n\n".join(
        f"Partial summary: {p.get('partial_summary', '')}\n"
        f"Partial details: {p.get('partial_details', [])}"
        for p in partial_results
    )

    reduce_chain = _build_reduce_prompt() | llm | parser
    try:
        result = await reduce_chain.ainvoke({"partial_results": combined})
    except Exception as e:
        raise ValueError(f"Reduce phase failed: {str(e)}")
    return _parse_result(result)


def _parse_result(raw: dict) -> SummaryResult:
    key_details = [
        KeyDetail(label=d.get("label", ""), value=d.get("value", ""))
        for d in raw.get("key_details", [])
        if d.get("label")
    ]
    return SummaryResult(
        summary=raw.get("summary", ""),
        key_details=key_details,
    )
