"""Orchestrate ingestion → parse → review pipeline."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Callable, Optional

from src.ingestion.clone_repo import CloneError, clone_repository, get_repo_stats
from src.models.schemas import CodeChunk, ReviewBatch, ReviewComment
from src.parsing.ast_parser import discover_source_files, parse_repository
from src.review.llm_client import LLMError, LLMReviewer

logger = logging.getLogger(__name__)


class ReviewPipeline:
    def __init__(
        self,
        max_files: int = 30,
        max_chunks: int = 25,
        reviewer: Optional[LLMReviewer] = None,
    ):
        self.max_files = max_files
        self.max_chunks = max_chunks
        self.reviewer = reviewer or LLMReviewer()

    def run(
        self,
        repo_url: str,
        branch: Optional[str] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> ReviewBatch:
        batch = ReviewBatch(repo_url=repo_url)

        def report(msg: str, pct: float):
            if progress_callback:
                progress_callback(msg, pct)

        report("Cloning repository…", 0.05)
        with tempfile.TemporaryDirectory(prefix="code_review_") as tmp:
            tmp_path = Path(tmp)
            try:
                repo_path = clone_repository(repo_url, tmp_path, branch=branch)
            except CloneError as e:
                batch.errors.append(str(e))
                return batch

            stats = get_repo_stats(repo_path)
            report(f"Found {stats['python_files']} Python files", 0.15)

            report("Parsing source files with AST…", 0.25)
            chunks = parse_repository(repo_path, max_files=self.max_files)
            if not chunks:
                batch.errors.append("No reviewable code chunks found in repository.")
                return batch

            chunks = chunks[: self.max_chunks]
            batch.files_analyzed = len(discover_source_files(repo_path, max_files=self.max_files))
            batch.chunks_reviewed = len(chunks)

            all_comments: list[ReviewComment] = []
            total = len(chunks)

            for i, chunk in enumerate(chunks):
                pct = 0.3 + (0.65 * (i + 1) / total)
                label = chunk.symbol_name or chunk.file_path
                report(f"Reviewing {label} ({i + 1}/{total})…", pct)
                try:
                    comments = self.reviewer.review_chunk(chunk)
                    all_comments.extend(comments)
                except LLMError as e:
                    batch.errors.append(f"{chunk.file_path}: {e}")
                    logger.error("LLM review failed for %s: %s", chunk.file_path, e)
                except Exception as e:
                    batch.errors.append(f"{chunk.file_path}: unexpected error — {e}")
                    logger.exception("Unexpected error reviewing %s", chunk.file_path)

            batch.comments = _dedupe_comments(all_comments)
            report("Review complete.", 1.0)

        return batch


def _dedupe_comments(comments: list[ReviewComment]) -> list[ReviewComment]:
    seen: set[tuple] = set()
    unique: list[ReviewComment] = []
    for c in sorted(comments, key=lambda x: (-x.confidence, x.file_path, x.line_start)):
        key = (c.file_path, c.line_start, c.message[:80])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique
