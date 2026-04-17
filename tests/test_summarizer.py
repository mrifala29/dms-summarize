import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.summarizer import summarize_document, _parse_result
from app.schemas.summarize import SummaryResult, KeyDetail


def test_parse_result_valid():
    raw = {
        "summary": "This is a non-disclosure agreement between PT ABC and PT XYZ.",
        "key_details": [
            {"label": "Document Type", "value": "Non-Disclosure Agreement"},
            {"label": "Parties", "value": "PT ABC and PT XYZ"},
        ],
    }
    result = _parse_result(raw)
    assert isinstance(result, SummaryResult)
    assert "non-disclosure" in result.summary.lower()
    assert len(result.key_details) == 2
    assert result.key_details[0].label == "Document Type"


def test_parse_result_empty():
    raw = {}
    result = _parse_result(raw)
    assert result.summary == ""
    assert result.key_details == []


def test_parse_result_skips_empty_labels():
    raw = {
        "summary": "test",
        "key_details": [
            {"label": "", "value": "skip me"},
            {"label": "Valid", "value": "keep"},
        ],
    }
    result = _parse_result(raw)
    assert len(result.key_details) == 1
    assert result.key_details[0].label == "Valid"
