"""Unit tests for the reviewer.py module."""

from __future__ import annotations

import json
import os
import time
from unittest.mock import patch, MagicMock

import pytest

import reviewer
from reviewer import review_code, _extract_json, _validate_comment


class TestOpenAISuccess:
    @patch("reviewer._call_openai")
    def test_happy_path(self, mock_call):
        # 1. Happy path test
        mock_response = {
            "comments": [
                {
                    "line": 12,
                    "category": "bug",
                    "severity": "critical",
                    "message": "Potential division by zero here.",
                    "suggestion": "Check if denominator is 0.",
                    "confidence": 95,
                }
            ]
        }
        mock_call.return_value = json.dumps(mock_response)
        
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            comments = review_code("def div(a, b): return a / b", "math.py")
            
        assert len(comments) == 1
        assert comments[0]["line"] == 12
        assert comments[0]["category"] == "bug"
        assert comments[0]["severity"] == "critical"
        assert comments[0]["message"] == "Potential division by zero here."
        assert comments[0]["suggestion"] == "Check if denominator is 0."
        assert comments[0]["confidence"] == 95
        mock_call.assert_called_once()

    @patch("reviewer._call_openai")
    def test_empty_response(self, mock_call):
        # 2. Empty response handling
        mock_call.return_value = json.dumps({"comments": []})
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            comments = review_code("def good_code(): pass")
        assert comments == []
        mock_call.assert_called_once()

    @patch("reviewer._call_openai")
    def test_json_markdown_fence_json(self, mock_call):
        # 3. Fenced code block with json identifier
        mock_call.return_value = "```json\n{\"comments\": [{\"category\": \"bug\"}]}\n```"
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            comments = review_code("def dummy(): pass")
        assert len(comments) == 1
        assert comments[0]["category"] == "bug"

    @patch("reviewer._call_openai")
    def test_json_markdown_fence_no_json(self, mock_call):
        # 4. Fenced code block without json identifier
        mock_call.return_value = "```\n{\"comments\": [{\"category\": \"security\"}]}\n```"
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            comments = review_code("def dummy(): pass")
        assert len(comments) == 1
        assert comments[0]["category"] == "security"

    @patch("reviewer._call_openai")
    def test_json_buried_in_prose(self, mock_call):
        # 5. JSON buried in explanation text
        mock_call.return_value = "Sure, here is the review:\n {\"comments\": [{\"category\": \"performance\"}]} \nHope this helps!"
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            comments = review_code("def dummy(): pass")
        assert len(comments) == 1
        assert comments[0]["category"] == "performance"

    @patch("reviewer._call_openai")
    def test_raw_json(self, mock_call):
        # 6. Raw JSON directly
        mock_call.return_value = "{\"comments\": [{\"category\": \"style\"}]}"
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            comments = review_code("def dummy(): pass")
        assert len(comments) == 1
        assert comments[0]["category"] == "style"


class TestAnthropicSuccess:
    @patch("reviewer._call_anthropic")
    def test_anthropic_happy_path(self, mock_call):
        # 7. Anthropic happy path
        mock_response = {"comments": [{"category": "security", "severity": "major", "message": "API key leak"}]}
        mock_call.return_value = json.dumps(mock_response)
        
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}):
            comments = review_code("api_key = '123'", "config.py")
            
        assert len(comments) == 1
        assert comments[0]["category"] == "security"
        mock_call.assert_called_once()

    @patch("reviewer._call_anthropic")
    def test_llm_model_env_override(self, mock_call):
        # 8. Model env override verification
        mock_call.return_value = "{\"comments\": []}"
        with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic", "LLM_MODEL": "claude-custom-1"}):
            review_code("def f(): pass")
        mock_call.assert_called_once_with("def f(): pass", "claude-custom-1")


class TestRetry:
    @patch("reviewer.time.sleep")
    @patch("reviewer._call_openai")
    def test_retry_on_bad_json_success(self, mock_call, mock_sleep):
        # 9. Failure on first call (bad json), success on retry
        mock_call.side_effect = [
            "invalid json here...",
            "{\"comments\": [{\"category\": \"bug\"}]}"
        ]
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            comments = review_code("def f(): pass")
        assert len(comments) == 1
        assert comments[0]["category"] == "bug"
        assert mock_call.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch("reviewer.time.sleep")
    @patch("reviewer._call_openai")
    def test_both_attempts_fail(self, mock_call, mock_sleep):
        # 10. Both calls return bad JSON
        mock_call.side_effect = [
            "invalid json first...",
            "invalid json second..."
        ]
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            comments = review_code("def f(): pass")
        assert comments == []
        assert mock_call.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch("reviewer._call_openai")
    def test_no_retry_on_api_error(self, mock_call):
        # 11. Mock _call_openai to raise RuntimeError — assert API called exactly once and return value is []
        mock_call.side_effect = RuntimeError("API error: 401 Unauthorized")
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            comments = review_code("def f(): pass")
        assert comments == []
        mock_call.assert_called_once()

    @patch("reviewer.time.sleep")
    @patch("reviewer._call_openai")
    def test_sleep_called_before_retry(self, mock_call, mock_sleep):
        # 12. Direct assertion that time.sleep is called before retrying
        mock_call.side_effect = [
            "invalid json",
            "{\"comments\": []}"
        ]
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            review_code("def f(): pass")
        mock_sleep.assert_called_once_with(1)


class TestEdgeCases:
    def test_empty_input(self):
        # 13. Empty chunk returns immediately
        comments = review_code("")
        assert comments == []

    def test_whitespace_input(self):
        # 14. Whitespace chunk returns immediately
        comments = review_code("   \n   \t  ")
        assert comments == []

    @patch("reviewer._call_openai")
    def test_unknown_provider_fallback(self, mock_call):
        # 15. Unknown provider falls back to openai
        mock_call.return_value = "{\"comments\": []}"
        with patch.dict(os.environ, {"LLM_PROVIDER": "grok"}):
            comments = review_code("def f(): pass")
        assert comments == []
        mock_call.assert_called_once()

    @patch("reviewer._call_openai")
    def test_missing_api_key_error(self, mock_call):
        # 16. Test missing API key (represented as RuntimeError from _call_openai)
        mock_call.side_effect = RuntimeError("OPENAI_API_KEY not set")
        with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}):
            comments = review_code("def f(): pass")
        assert comments == []
        mock_call.assert_called_once()


class TestCommentValidation:
    def test_valid_category(self):
        # 17. Valid category preserved
        validated = _validate_comment({"category": "bug"})
        assert validated["category"] == "bug"

    def test_invalid_category_default(self):
        # 18. Invalid category defaults to "style"
        validated = _validate_comment({"category": "CODE_SMELL"})
        assert validated["category"] == "style"
        
        # Missing category defaults to "style"
        validated_missing = _validate_comment({})
        assert validated_missing["category"] == "style"

    def test_valid_severity(self):
        # 19. Valid severity preserved
        validated = _validate_comment({"severity": "critical"})
        assert validated["severity"] == "critical"

    def test_invalid_severity_default(self):
        # 20. Invalid severity defaults to "info"
        validated = _validate_comment({"severity": "high"})
        assert validated["severity"] == "info"
        
        # Missing severity defaults to "info"
        validated_missing = _validate_comment({})
        assert validated_missing["severity"] == "info"

    def test_line_as_int(self):
        # 21. Line as integer preserved
        validated = _validate_comment({"line": 42})
        assert validated["line"] == 42

    def test_line_as_string_int(self):
        # 22. Line string represented integer parsed
        validated = _validate_comment({"line": "105"})
        assert validated["line"] == 105

    def test_line_invalid_default(self):
        # 23. Invalid line values default to None
        assert _validate_comment({"line": "abc"})["line"] is None
        assert _validate_comment({"line": {}})["line"] is None
        assert _validate_comment({})["line"] is None

    def test_confidence_clamping(self):
        # 24. Clamping confidence to 0-100
        assert _validate_comment({"confidence": 150})["confidence"] == 100
        assert _validate_comment({"confidence": -20})["confidence"] == 0
        assert _validate_comment({"confidence": 85})["confidence"] == 85

    def test_confidence_invalid_default(self):
        # 25. Invalid confidence values default to 50
        assert _validate_comment({"confidence": "high"})["confidence"] == 50
        assert _validate_comment({"confidence": None})["confidence"] == 50
        assert _validate_comment({})["confidence"] == 50


class TestExtractJson:
    def test_extract_valid_raw(self):
        # 26. Valid direct raw JSON extraction
        raw_json = '{"comments": [], "status": "success"}'
        res = _extract_json(raw_json)
        assert res["status"] == "success"

    def test_extract_invalid_throws(self):
        # 27. Invalid JSON throws ValueError
        with pytest.raises(ValueError):
            _extract_json("This is just normal text without any json.")
