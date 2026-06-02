"""Orchestrator pipeline for repository code review."""

from __future__ import annotations

import concurrent.futures
import logging
import shutil
from pathlib import Path
from typing import Any, Union

import ingestion
import parser
import utils.chunker as chunker
import reviewer

logger = logging.getLogger(__name__)


class CommentsList(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.files = []


def _process_file(file_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse, chunk, and review a single file. Returns a list of review comments.

    Designed to run inside a thread — all steps have independent error handling
    so one failing file does not crash the pool.
    """
    content = file_info.get("content", "")
    file_path = file_info.get("path", "<unknown>")
    language = file_info.get("language", "python")
    comments_for_file: list[dict[str, Any]] = []

    # Parse step
    try:
        ast_data = parser.parse_source(content)
    except Exception as e:
        logger.error("Error parsing '%s': %s. Falling back to empty AST.", file_path, e)
        ast_data = {"functions": [], "classes": [], "imports": []}

    # Chunk step
    try:
        chunks = chunker.make_chunks(ast_data, content)
    except Exception as e:
        logger.error("Error chunking '%s': %s. Falling back to raw content.", file_path, e)
        if content.strip():
            try:
                chunks = chunker.chunk_nodes([{"name": "<unknown>", "source": content}])
            except Exception:
                chunks = [content]
        else:
            chunks = []

    # Review each chunk
    for chunk in chunks:
        try:
            comments = reviewer.review_code(chunk, file_path=file_path, language=language)
        except Exception as e:
            logger.error("Error reviewing chunk in '%s': %s. Skipping chunk.", file_path, e)
            continue

        for comment in comments:
            comment["file"] = file_path
            comment["file_path"] = file_path
            comment["chunk_info"] = chunk
            comment["chunk"] = chunk
            comments_for_file.append(comment)

    return comments_for_file


def run_pipeline(repo_url: str, max_workers: int = 4) -> list[dict[str, Any]]:
    """Clone, parse, chunk, and review a repository, returning all comments.

    Files are reviewed concurrently using a ThreadPoolExecutor (safe for
    I/O-bound LLM calls). A configurable max_workers cap keeps API rate limits
    manageable.

    Args:
        repo_url: GitHub repository URL (repo root or /tree/... subdirectory URL).
        max_workers: Maximum concurrent review threads (default 4).

    Returns:
        Sorted list of review comment dicts (critical → info, then by confidence desc).
    """
    tmp_dir_to_clean: str | None = None
    all_comments: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []

    try:
        # 1. Clone repository
        clone_result = ingestion.clone_repo(repo_url, max_files=20)

        if isinstance(clone_result, tuple):
            files, tmp_dir = clone_result
            tmp_dir_to_clean = tmp_dir
        else:
            files = clone_result

        # 2. Review files concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_file = {executor.submit(_process_file, f): f for f in files}
            for future in concurrent.futures.as_completed(future_to_file):
                file_info = future_to_file[future]
                try:
                    all_comments.extend(future.result())
                except Exception as e:
                    logger.error(
                        "Failed to process '%s': %s.",
                        file_info.get("path", "<unknown>"), e,
                    )

    finally:
        # Guarantee tmp_dir cleanup to avoid resource leaks
        if tmp_dir_to_clean:
            try:
                from ingestion import remove_readonly
                shutil.rmtree(tmp_dir_to_clean, onerror=remove_readonly)
            except Exception:
                try:
                    shutil.rmtree(tmp_dir_to_clean, ignore_errors=True)
                except Exception:
                    pass

    # 3. Sort comments by severity then confidence descending
    severity_order = {"critical": 0, "major": 1, "minor": 2, "info": 3}

    def sort_key(comment: dict[str, Any]) -> tuple[int, int]:
        sev = str(comment.get("severity", "info")).lower()
        sev_val = severity_order.get(sev, 4)
        try:
            conf_val = int(comment.get("confidence", 50))
        except (ValueError, TypeError):
            conf_val = 50
        return (sev_val, -conf_val)

    all_comments.sort(key=sort_key)
    result = CommentsList(all_comments)
    result.files = [
        {"path": f.get("path"), "content": f.get("content"), "language": f.get("language")}
        for f in files
    ]
    return result


# Expose alias
pipeline = run_pipeline


class Pipeline:
    def run(self, repo_url: str, max_workers: int = 4) -> list[dict[str, Any]]:
        return run_pipeline(repo_url, max_workers=max_workers)
