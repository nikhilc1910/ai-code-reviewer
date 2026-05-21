"""Unit tests for the orchestrator pipeline module."""

from __future__ import annotations

import shutil
from unittest.mock import MagicMock, patch

import pytest

import ingestion
import parser
import reviewer
from pipeline import Pipeline, pipeline, run_pipeline
from utils.chunker import make_chunks


class TestSortBySeverity:
    @patch("ingestion.clone_repo")
    @patch("parser.parse_file")
    @patch("utils.chunker.make_chunks")
    @patch("reviewer.review_code")
    def test_severity_sorting(self, mock_review, mock_make_chunks, mock_parse, mock_clone):
        # 1. Verify sorting order: critical -> major -> minor -> info
        mock_clone.return_value = ([{"path": "test.py", "content": "pass"}], "/tmp/dummy")
        mock_parse.return_value = {}
        mock_make_chunks.return_value = ["chunk1"]
        mock_review.return_value = [
            {"severity": "minor", "message": "minor msg", "confidence": 80},
            {"severity": "critical", "message": "critical msg", "confidence": 90},
            {"severity": "info", "message": "info msg", "confidence": 70},
            {"severity": "major", "message": "major msg", "confidence": 85},
        ]

        comments = run_pipeline("https://github.com/owner/repo")
        severities = [c["severity"] for c in comments]
        assert severities == ["critical", "major", "minor", "info"]

    @patch("ingestion.clone_repo")
    @patch("parser.parse_file")
    @patch("utils.chunker.make_chunks")
    @patch("reviewer.review_code")
    def test_confidence_tie_breaking(self, mock_review, mock_make_chunks, mock_parse, mock_clone):
        # 2. Verify tie-breaking by confidence descending (highest first)
        mock_clone.return_value = ([{"path": "test.py", "content": "pass"}], "/tmp/dummy")
        mock_parse.return_value = {}
        mock_make_chunks.return_value = ["chunk1"]
        mock_review.return_value = [
            {"severity": "major", "message": "major low", "confidence": 50},
            {"severity": "major", "message": "major high", "confidence": 95},
            {"severity": "major", "message": "major med", "confidence": 75},
        ]

        comments = run_pipeline("https://github.com/owner/repo")
        confidences = [c["confidence"] for c in comments]
        assert confidences == [95, 75, 50]

    @patch("ingestion.clone_repo")
    @patch("parser.parse_file")
    @patch("utils.chunker.make_chunks")
    @patch("reviewer.review_code")
    def test_case_insensitivity(self, mock_review, mock_make_chunks, mock_parse, mock_clone):
        # 3. Verify case-insensitivity in severity sorting
        mock_clone.return_value = ([{"path": "test.py", "content": "pass"}], "/tmp/dummy")
        mock_parse.return_value = {}
        mock_make_chunks.return_value = ["chunk1"]
        mock_review.return_value = [
            {"severity": "MiNoR", "message": "msg1", "confidence": 50},
            {"severity": "CRITICAL", "message": "msg2", "confidence": 50},
            {"severity": "major", "message": "msg3", "confidence": 50},
        ]

        comments = run_pipeline("https://github.com/owner/repo")
        severities = [c["severity"].lower() for c in comments]
        assert severities == ["critical", "major", "minor"]

    @patch("ingestion.clone_repo")
    @patch("parser.parse_file")
    @patch("utils.chunker.make_chunks")
    @patch("reviewer.review_code")
    def test_invalid_missing_values(self, mock_review, mock_make_chunks, mock_parse, mock_clone):
        # 4. Verify handling of invalid/missing severity or confidence defaults
        mock_clone.return_value = ([{"path": "test.py", "content": "pass"}], "/tmp/dummy")
        mock_parse.return_value = {}
        mock_make_chunks.return_value = ["chunk1"]
        mock_review.return_value = [
            {"message": "missing severity"},  # defaults to info, confidence 50
            {"severity": "critical", "message": "missing confidence"},  # defaults to confidence 50
            {"severity": "major", "confidence": "invalid_conf", "message": "bad confidence"},  # defaults to 50
        ]

        comments = run_pipeline("https://github.com/owner/repo")
        # Critical should come first, then major, then info (defaulted)
        assert comments[0]["severity"] == "critical"
        assert comments[1]["severity"] == "major"
        assert comments[2].get("severity", "info") == "info"

    @patch("ingestion.clone_repo")
    @patch("parser.parse_file")
    @patch("utils.chunker.make_chunks")
    @patch("reviewer.review_code")
    def test_all_matching_sorts(self, mock_review, mock_make_chunks, mock_parse, mock_clone):
        # 5. Verify order is stable when severities and confidences match
        mock_clone.return_value = ([{"path": "test.py", "content": "pass"}], "/tmp/dummy")
        mock_parse.return_value = {}
        mock_make_chunks.return_value = ["chunk1"]
        mock_review.return_value = [
            {"severity": "minor", "message": "first", "confidence": 80},
            {"severity": "minor", "message": "second", "confidence": 80},
        ]

        comments = run_pipeline("https://github.com/owner/repo")
        assert len(comments) == 2
        assert comments[0]["message"] == "first"
        assert comments[1]["message"] == "second"


class TestRunErrorResilience:
    @patch("ingestion.clone_repo")
    @patch("parser.parse_file")
    @patch("utils.chunker.make_chunks")
    @patch("reviewer.review_code")
    def test_parse_step_crashing(self, mock_review, mock_make_chunks, mock_parse, mock_clone):
        # 1. Parser crashes -> continues with empty AST -> still chunks and reviews
        mock_clone.return_value = ([{"path": "test.py", "content": "print('hello')"}], "/tmp/dummy")
        mock_parse.side_effect = RuntimeError("Parse failed!")
        
        # When parse fails, empty AST is passed to make_chunks, which falls back to raw_content
        mock_make_chunks.return_value = ["fallback_chunk"]
        mock_review.return_value = [{"severity": "info", "message": "reviewed"}]

        comments = run_pipeline("https://github.com/owner/repo")
        assert len(comments) == 1
        assert comments[0]["message"] == "reviewed"
        mock_make_chunks.assert_called_once_with({"functions": [], "classes": [], "imports": []}, "print('hello')")

    @patch("ingestion.clone_repo")
    @patch("parser.parse_file")
    @patch("utils.chunker.make_chunks")
    @patch("reviewer.review_code")
    def test_chunk_step_crashing(self, mock_review, mock_make_chunks, mock_parse, mock_clone):
        # 2. Chunking crashes -> falls back to raw content as a single chunk
        mock_clone.return_value = ([{"path": "test.py", "content": "print('hello')"}], "/tmp/dummy")
        mock_parse.return_value = {}
        mock_make_chunks.side_effect = RuntimeError("Chunk failed!")
        mock_review.return_value = [{"severity": "info", "message": "reviewed"}]

        comments = run_pipeline("https://github.com/owner/repo")
        assert len(comments) == 1
        # Review should be called on the raw content fallback
        mock_review.assert_called_with("=== <unknown> ===\nprint('hello')", file_path="test.py")

    @patch("ingestion.clone_repo")
    @patch("parser.parse_file")
    @patch("utils.chunker.make_chunks")
    @patch("reviewer.review_code")
    def test_review_step_crashing(self, mock_review, mock_make_chunks, mock_parse, mock_clone):
        # 3. Reviewer crashes on one chunk -> skips it and continues
        mock_clone.return_value = ([{"path": "test.py", "content": "pass"}], "/tmp/dummy")
        mock_parse.return_value = {}
        mock_make_chunks.return_value = ["chunk1", "chunk2"]
        
        # Raise error on chunk1, succeed on chunk2
        mock_review.side_effect = [RuntimeError("Review failed!"), [{"severity": "info", "message": "ok"}]]

        comments = run_pipeline("https://github.com/owner/repo")
        assert len(comments) == 1
        assert comments[0]["message"] == "ok"

    @patch("ingestion.clone_repo")
    @patch("shutil.rmtree")
    @patch("parser.parse_file")
    def test_tmp_dir_cleanup_on_success_and_error(self, mock_parse, mock_rmtree, mock_clone):
        # 4. Assert tmp_dir cleanup occurs under all circumstances
        # Case A: Success Path
        mock_clone.return_value = ([{"path": "test.py", "content": "pass"}], "/tmp/cleanup_success")
        mock_parse.return_value = {}
        run_pipeline("https://github.com/owner/repo")
        mock_rmtree.assert_any_call("/tmp/cleanup_success", onerror=ingestion.remove_readonly)

        # Case B: Error mid-pipeline
        mock_clone.return_value = ([{"path": "test.py", "content": "pass"}], "/tmp/cleanup_error")
        mock_parse.side_effect = ValueError("Fatal crash")
        run_pipeline("https://github.com/owner/repo")
        mock_rmtree.assert_any_call("/tmp/cleanup_error", onerror=ingestion.remove_readonly)


class TestPublicSurface:
    @patch("ingestion.clone_repo")
    @patch("parser.parse_file")
    @patch("utils.chunker.make_chunks")
    @patch("reviewer.review_code")
    def test_pipeline_function_alias(self, mock_review, mock_make_chunks, mock_parse, mock_clone):
        # Verify pipeline() works as an alias
        mock_clone.return_value = ([], None)
        res = pipeline("https://github.com/owner/repo")
        assert res == []

    @patch("ingestion.clone_repo")
    @patch("parser.parse_file")
    @patch("utils.chunker.make_chunks")
    @patch("reviewer.review_code")
    def test_pipeline_class_interface(self, mock_review, mock_make_chunks, mock_parse, mock_clone):
        # Verify Pipeline().run() interface works
        mock_clone.return_value = ([], None)
        runner = Pipeline()
        res = runner.run("https://github.com/owner/repo")
        assert res == []


class TestMakeChunks:
    def test_make_chunks_line_slicing(self):
        # 1. Verify line slicing slices source correct to next start line
        raw_code = (
            "def f1():\n"       # Line 1
            "    pass\n"        # Line 2
            "\n"                # Line 3
            "class C1:\n"       # Line 4
            "    def m(self):\n"# Line 5
            "        pass\n"    # Line 6
        )
        ast_data = {
            "functions": [{"name": "f1", "line": 1}],
            "classes": [{"name": "C1", "line": 4}]
        }
        res = make_chunks(ast_data, raw_code)
        assert len(res) == 1  # Standard packing size allows them to fit in one chunk
        chunk_content = res[0]
        # Should contain formatted headers and sliced bodies
        assert "=== f1 ===\ndef f1():\n    pass\n\n" in chunk_content
        assert "=== C1 ===\nclass C1:\n    def m(self):\n        pass\n" in chunk_content

    def test_make_chunks_empty_ast_fallback(self):
        # 2. Falls back to raw content as a single unknown chunk when AST is empty
        raw_code = "print('hello')\nprint('world')"
        ast_data = {"functions": [], "classes": [], "imports": []}
        res = make_chunks(ast_data, raw_code)
        assert len(res) == 1
        assert res[0] == "=== <unknown> ===\nprint('hello')\nprint('world')"

    def test_make_chunks_whitespace_content(self):
        # 3. Returns [] when AST is empty and raw content is whitespace/empty
        ast_data = {"functions": [], "classes": [], "imports": []}
        assert make_chunks(ast_data, "") == []
        assert make_chunks(ast_data, "   \n   ") == []

    def test_make_chunks_sorting(self):
        # 4. Check that functions and classes are sorted by line number before slicing
        raw_code = (
            "class C1:\n"  # Line 1
            "    pass\n"   # Line 2
            "def f1():\n"  # Line 3
            "    pass\n"   # Line 4
        )
        # Passed out of order in AST dictionary
        ast_data = {
            "functions": [{"name": "f1", "line": 3}],
            "classes": [{"name": "C1", "line": 1}]
        }
        res = make_chunks(ast_data, raw_code)
        chunk = res[0]
        # class C1 snippet should be class C1:\n    pass\n
        # def f1 snippet should be def f1():\n    pass\n
        assert "=== C1 ===\nclass C1:\n    pass\n" in chunk
        assert "=== f1 ===\ndef f1():\n    pass\n" in chunk
