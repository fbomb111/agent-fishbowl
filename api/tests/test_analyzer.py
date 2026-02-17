"""Tests for LLM response parsing in the article analyzer."""

import json

import pytest

from api.services.ingestion.analyzer import AnalysisError, _parse_response


def test_parse_response_valid_json():
    data = {
        "insights": [
            {"text": "Use structured logging", "category": "technique"},
            {"text": "Try LangGraph for agents", "category": "tool"},
        ],
        "ai_summary": "This article covers modern observability patterns and agent frameworks.",
        "relevance_score": 8,
    }
    result = _parse_response(json.dumps(data))
    assert len(result.insights) == 2
    assert result.insights[0]["text"] == "Use structured logging"
    assert result.insights[0]["category"] == "technique"
    assert result.insights[1]["category"] == "tool"
    assert "observability" in result.ai_summary
    assert result.relevance_score == 8


def test_parse_response_empty_insights():
    data = {"insights": [], "ai_summary": None}
    result = _parse_response(json.dumps(data))
    assert result.insights == []
    assert result.ai_summary is None
    assert result.relevance_score == 5  # default when missing


def test_parse_response_short_summary_becomes_none():
    data = {"insights": [], "ai_summary": "Short"}
    result = _parse_response(json.dumps(data))
    assert result.ai_summary is None


def test_parse_response_invalid_json_raises():
    with pytest.raises(AnalysisError, match="Invalid JSON"):
        _parse_response("This is not JSON at all")
