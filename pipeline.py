"""Orchestrator pipeline for repository code review."""

from __future__ import annotations

import concurrent.futures
import logging
import shutil
import os
import time
from pathlib import Path
from typing import Any, Union

import ingestion
import parser
import utils.chunker as chunker
import reviewer
from utils.progress import PipelineProgress

logger = logging.getLogger(__name__)


class CommentsList(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.files = []
        self.timing_metrics = {}


def run_with_timeout(func, args=(), kwargs={}, timeout=60.0):
    """Run a callable in a single-thread executor enforcing a timeout."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Stage timed out after {timeout} seconds")


def run_pipeline(repo_url: str, max_workers: int = 4, progress: PipelineProgress | None = None) -> list[dict[str, Any]]:
    """Clone, parse, chunk, and review a repository, returning all comments.

    Enforces 60-second timeouts per stage and tracks live progress.
    """
    if progress is None:
        progress = PipelineProgress()

    tmp_dir_to_clean: str | None = None
    files: list[dict[str, Any]] = []
    all_comments: list[dict[str, Any]] = []

    # Stage 1: Cloning
    progress.start_stage("cloning", "Cloning codebase repository...")
    try:
        # Pass env options inside clone_repo if ingestion.py doesn't set them globally
        clone_result = run_with_timeout(ingestion.clone_repo, args=(repo_url,), kwargs={"max_files": 20}, timeout=60.0)
        if isinstance(clone_result, tuple):
            files, tmp_dir = clone_result
            tmp_dir_to_clean = tmp_dir
        else:
            files = clone_result
        progress.complete_stage("cloning", "Repository cloned successfully")
    except Exception as e:
        progress.fail_stage("cloning", f"Cloning failed: {e}")
        raise e

    # Stage 2: Discovery
    progress.start_stage("discovery", "Discovering reviewable files...")
    try:
        def discover_step():
            progress.update_counts(total_files=len(files), discovered_files=len(files))
            return len(files)
        
        run_with_timeout(discover_step, timeout=60.0)
        progress.complete_stage("discovery", f"Discovered {len(files)} files")
    except Exception as e:
        progress.fail_stage("discovery", f"Discovery failed: {e}")
        _cleanup_tmp(tmp_dir_to_clean)
        raise e

    # Stage 3: Parsing AST
    progress.start_stage("parsing", "Parsing source files and extracting ASTs...")
    parsed_asts = {}
    try:
        def parse_step():
            parsed_count = 0
            for f in files:
                path = f.get("path", "")
                content = f.get("content", "")
                try:
                    ast_data = parser.parse_source(content)
                except Exception as e:
                    logger.error("Error parsing '%s': %s", path, e)
                    ast_data = {"functions": [], "classes": [], "imports": []}
                parsed_asts[path] = ast_data
                parsed_count += 1
                progress.update_counts(parsed_files=parsed_count)
            return len(files)
            
        run_with_timeout(parse_step, timeout=60.0)
        progress.complete_stage("parsing", f"Parsed {len(files)} files successfully")
    except Exception as e:
        progress.fail_stage("parsing", f"Parsing failed: {e}")
        _cleanup_tmp(tmp_dir_to_clean)
        raise e

    # Stage 4: Dependencies
    progress.start_stage("dependencies", "Analyzing dependency graphs...")
    try:
        def dependencies_step():
            for path, ast in parsed_asts.items():
                imports = ast.get("imports", [])
                if imports:
                    progress.log(f"Dependencies in {path}: {', '.join(imports)}")
            return True
            
        run_with_timeout(dependencies_step, timeout=60.0)
        progress.complete_stage("dependencies", "Dependencies analyzed")
    except Exception as e:
        progress.fail_stage("dependencies", f"Dependency analysis failed: {e}")
        _cleanup_tmp(tmp_dir_to_clean)
        raise e

    # Stage 5: Chunking
    progress.start_stage("chunking", "Chunking modules into logical blocks...")
    total_chunks = 0
    try:
        def chunking_step():
            nonlocal total_chunks
            for f in files:
                path = f.get("path", "")
                content = f.get("content", "")
                ast_data = parsed_asts.get(path, {"functions": [], "classes": [], "imports": []})
                try:
                    chunks = chunker.make_chunks(ast_data, content)
                except Exception as e:
                    logger.error("Error chunking '%s': %s", path, e)
                    if content.strip():
                        try:
                            chunks = chunker.chunk_nodes([{"name": "<unknown>", "source": content}])
                        except Exception:
                            chunks = [content]
                    else:
                        chunks = []
                f["chunks"] = chunks
                total_chunks += len(chunks)
                progress.update_counts(total_chunks=total_chunks)
            return total_chunks

        run_with_timeout(chunking_step, timeout=60.0)
        progress.complete_stage("chunking", f"Generated {total_chunks} chunks")
    except Exception as e:
        progress.fail_stage("chunking", f"Chunking failed: {e}")
        _cleanup_tmp(tmp_dir_to_clean)
        raise e

    # Stage 6: Static Analysis
    progress.start_stage("static_analysis", "Running quality checks and static analysis...")
    static_findings = []
    try:
        def static_analysis_step():
            for f in files:
                path = f.get("path", "")
                ast_data = parsed_asts.get(path, {})
                for func in ast_data.get("functions", []):
                    if not func.get("docstring"):
                        static_findings.append({
                            "severity": "info",
                            "confidence": 80,
                            "category": "style",
                            "message": f"Function '{func.get('name')}' is missing a docstring.",
                            "file": path,
                            "file_path": path,
                            "line_start": func.get("line", 1),
                            "line_end": func.get("line", 1),
                            "suggestion": f"Add a descriptive docstring to function '{func.get('name')}'."
                        })
            return len(static_findings)

        run_with_timeout(static_analysis_step, timeout=60.0)
        progress.complete_stage("static_analysis", f"Static analysis completed with {len(static_findings)} style suggestions")
    except Exception as e:
        progress.fail_stage("static_analysis", f"Static analysis failed: {e}")
        _cleanup_tmp(tmp_dir_to_clean)
        raise e

    # Stage 7: LLM Review
    progress.start_stage("review", "Generating review comments via LLM Reviewer...")
    try:
        def review_step():
            review_comments = []
            
            def review_chunk_task(chunk, file_path, language):
                try:
                    if language and language != "python":
                        comments = reviewer.review_code(chunk, file_path=file_path, language=language)
                    else:
                        comments = reviewer.review_code(chunk, file_path=file_path)
                    if progress:
                        progress.increment_reviewed()
                    return comments
                except Exception as e:
                    logger.error("Error reviewing chunk in '%s': %s", file_path, e)
                    if progress:
                        progress.increment_reviewed()
                    return []

            tasks = []
            for f in files:
                path = f.get("path", "")
                language = f.get("language", "python")
                for chunk in f.get("chunks", []):
                    tasks.append((chunk, path, language))

            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(review_chunk_task, t[0], t[1], t[2]): t for t in tasks}
                for future in concurrent.futures.as_completed(futures):
                    try:
                        review_comments.extend(future.result())
                    except Exception as e:
                        logger.error("LLM review execution error: %s", e)
            return review_comments

        llm_findings = run_with_timeout(review_step, timeout=60.0)
        progress.complete_stage("review", f"LLM review completed, generated {len(llm_findings)} code findings")
    except Exception as e:
        progress.fail_stage("review", f"LLM review failed or timed out: {e}")
        _cleanup_tmp(tmp_dir_to_clean)
        raise e

    # Stage 8: Aggregation
    progress.start_stage("aggregation", "Deduplicating and filtering findings...")
    try:
        def aggregation_step():
            raw_findings = static_findings + llm_findings
            mapped = []
            for comment in raw_findings:
                comment["file"] = comment.get("file_path", comment.get("file", ""))
                comment["file_path"] = comment.get("file_path", comment.get("file", ""))
                mapped.append(comment)
            return mapped

        all_comments = run_with_timeout(aggregation_step, timeout=60.0)
        progress.complete_stage("aggregation", "Findings aggregated successfully")
    except Exception as e:
        progress.fail_stage("aggregation", f"Aggregation failed: {e}")
        _cleanup_tmp(tmp_dir_to_clean)
        raise e

    # Stage 9: Assembly
    progress.start_stage("assembly", "Sorting and assembling findings report...")
    try:
        def assembly_step():
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
            
            progress.finalize()
            result.timing_metrics = {
                "Clone Time": f"{progress.stage_durations['cloning']:.2f}s",
                "Discovery Time": f"{progress.stage_durations['discovery']:.2f}s",
                "Parse Time": f"{progress.stage_durations['parsing']:.2f}s",
                "Dependencies Time": f"{progress.stage_durations['dependencies']:.2f}s",
                "Chunking Time": f"{progress.stage_durations['chunking']:.2f}s",
                "Static Analysis Time": f"{progress.stage_durations['static_analysis']:.2f}s",
                "Review Time": f"{progress.stage_durations['review']:.2f}s",
                "Aggregation Time": f"{progress.stage_durations['aggregation']:.2f}s",
                "Assembly Time": f"{progress.stage_durations['assembly']:.2f}s",
                "Total Time": f"{progress.total_time:.2f}s"
            }
            return result

        result_list = run_with_timeout(assembly_step, timeout=60.0)
        progress.complete_stage("assembly", "Report assembly complete")
    except Exception as e:
        progress.fail_stage("assembly", f"Assembly failed: {e}")
        raise e
    finally:
        _cleanup_tmp(tmp_dir_to_clean)

    return result_list


def _cleanup_tmp(tmp_dir: str | None):
    if tmp_dir:
        try:
            from ingestion import remove_readonly
            shutil.rmtree(tmp_dir, onerror=remove_readonly)
        except Exception:
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass


# Expose alias
pipeline = run_pipeline


class Pipeline:
    def run(self, repo_url: str, max_workers: int = 4, progress: PipelineProgress | None = None) -> list[dict[str, Any]]:
        return run_pipeline(repo_url, max_workers=max_workers, progress=progress)
