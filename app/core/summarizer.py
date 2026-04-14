from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.core.models import get_chat_model
from app.core.document_loader import load_and_split
from app.core.prompts import load_system_prompt
from app.schemas.summarize import SummaryResult, KeyDetail


def _build_summarize_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", load_system_prompt()),
            ("human", "Analyze this document:\n\n{text}"),
        ]
    )

MAP_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a document analyst. Summarize the following chunk of a document "
                "in 2-3 sentences and list any key details (label: value) you find. "
                "Return ONLY valid JSON with keys: \"partial_summary\" and \"partial_details\" (list of objects with label/value)."
            ),
        ),
        ("human", "{text}"),
    ]
)

REDUCE_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            (
                "You are a senior document analyst specializing in HR and legal documents. "
                "You are given partial summaries and key details extracted from chunks of a single document. "
                "Combine them into a final JSON object with exactly two keys:\n"
                '  "summary": a concise paragraph (3-5 sentences) describing what the document is about.\n'
                '  "key_details": a deduplicated list of objects with "label" and "value" keys.\n\n'
                "Merge duplicates, keep the most complete value, and ensure the output is coherent. "
                "Return ONLY valid JSON, no markdown fences, no explanation."
            ),
        ),
        ("human", "Partial results:\n\n{partial_results}"),
    ]
)

STUFF_THRESHOLD = 3


async def summarize_document(file_path: str) -> SummaryResult:
    chunks = load_and_split(file_path)
    if not chunks:
        raise ValueError("Document is empty or could not be parsed.")

    llm = get_chat_model()
    parser = JsonOutputParser()

    if len(chunks) <= STUFF_THRESHOLD:
        return await _stuff_summarize(chunks, llm, parser)

    return await _map_reduce_summarize(chunks, llm, parser)


async def _stuff_summarize(chunks, llm, parser) -> SummaryResult:
    full_text = "\n\n".join(chunk.page_content for chunk in chunks)
    chain = _build_summarize_prompt() | llm | parser
    result = await chain.ainvoke({"text": full_text})
    return _parse_result(result)


async def _map_reduce_summarize(chunks, llm, parser) -> SummaryResult:
    map_chain = MAP_PROMPT | llm | parser
    partial_results = []
    for chunk in chunks:
        partial = await map_chain.ainvoke({"text": chunk.page_content})
        partial_results.append(partial)

    combined = "\n\n".join(
        f"Partial summary: {p.get('partial_summary', '')}\n"
        f"Partial details: {p.get('partial_details', [])}"
        for p in partial_results
    )

    reduce_chain = REDUCE_PROMPT | llm | parser
    result = await reduce_chain.ainvoke({"partial_results": combined})
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
