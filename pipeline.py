"""Orchestrator pipeline for repository code review."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Union

import ingestion
import parser
import utils.chunker as chunker
import reviewer

# Setup logger
logger = logging.getLogger(__name__)

# Ensure dynamic aliases for compatibility
if not hasattr(ingestion, "clone_repo"):
    ingestion.clone_repo = ingestion.ingest_repository

# reviewer.py is finalized; dynamically link the review_chunk name to review_code
reviewer.review_chunk = reviewer.review_code


def run_pipeline(repo_url: str) -> list[dict[str, Any]]:
    """Clones, parses, chunks, and reviews a repository, returning all comments.
    
    Ensures absolute resource cleanup of temp directories and runs with step-level
    resilience so that one failing file does not crash the entire process.
    """
    tmp_dir_to_clean: str | None = None
    all_comments: list[dict[str, Any]] = []

    try:
        # 1. Clone repository
        clone_result = ingestion.clone_repo(repo_url, max_files=20)
        
        # Handle both shapes: tuple (files, tmp_dir) or plain file list
        if isinstance(clone_result, tuple):
            files, tmp_dir = clone_result
            tmp_dir_to_clean = tmp_dir
        else:
            files = clone_result

        # 2. Process each file
        for file_info in files:
            content = file_info.get("content", "")
            file_path = file_info.get("path", "<unknown>")

            # Parse step with independent try/except resilience
            try:
                ast_data = parser.parse_file(content)
            except Exception as e:
                logger.error("Error parsing file '%s': %s. Falling back to empty AST.", file_path, e)
                ast_data = {"functions": [], "classes": [], "imports": []}

            # Chunk step with independent try/except resilience
            try:
                chunks = chunker.make_chunks(ast_data, content)
            except Exception as e:
                logger.error("Error chunking file '%s': %s. Falling back to raw content.", file_path, e)
                if content.strip():
                    # Format as a single raw chunk using fallback
                    try:
                        chunks = chunker.chunk_nodes([{"name": "<unknown>", "source": content}])
                    except Exception:
                        chunks = [content]
                else:
                    chunks = []

            # 3. Review each chunk
            for chunk in chunks:
                try:
                    comments = reviewer.review_code(chunk, file_path=file_path)
                except Exception as e:
                    logger.error("Error reviewing chunk in file '%s': %s. Skipping chunk.", file_path, e)
                    continue

                # 4. Attach metadata
                for comment in comments:
                    comment["file"] = file_path
                    comment["file_path"] = file_path
                    comment["chunk_info"] = chunk
                    comment["chunk"] = chunk
                    all_comments.append(comment)

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

    # 5. Sort comments by severity then confidence descending
    severity_order = {
        "critical": 0,
        "major": 1,
        "minor": 2,
        "info": 3
    }

    def sort_key(comment: dict[str, Any]) -> tuple[int, int]:
        sev = str(comment.get("severity", "info")).lower()
        sev_val = severity_order.get(sev, 4)
        
        confidence = comment.get("confidence", 50)
        try:
            conf_val = int(confidence)
        except (ValueError, TypeError):
            conf_val = 50
            
        return (sev_val, -conf_val)

    all_comments.sort(key=sort_key)
    return all_comments


# Expose alias functions
pipeline = run_pipeline


# Public surface class interface
class Pipeline:
    def run(self, repo_url: str) -> list[dict[str, Any]]:
        return run_pipeline(repo_url)
