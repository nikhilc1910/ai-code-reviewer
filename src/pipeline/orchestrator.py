"""Orchestrate ingestion → parse → review pipeline."""

from __future__ import annotations

import logging
import tempfile
import concurrent.futures
from pathlib import Path
from typing import Callable, Optional

from src.ingestion.clone_repo import CloneError, clone_repository, get_repo_stats
from src.models.schemas import CodeChunk, ReviewBatch, ReviewComment
from src.parsing.ast_parser import discover_source_files, parse_repository
from src.review.llm_client import LLMError, LLMReviewer
from utils.progress import PipelineProgress

logger = logging.getLogger(__name__)


def run_with_timeout(func, args=(), kwargs={}, timeout=60.0):
    """Run a callable in a single-thread executor enforcing a timeout."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Stage timed out after {timeout} seconds")


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
        progress: Optional[PipelineProgress] = None,
    ) -> ReviewBatch:
        batch = ReviewBatch(repo_url=repo_url)
        if progress is None:
            progress = PipelineProgress()

        def report(msg: str, pct: float):
            if progress_callback:
                progress_callback(msg, pct)

        # Stage 1: Cloning
        progress.start_stage("cloning", "Cloning codebase repository...")
        report("Cloning repository...", 0.05)
        
        with tempfile.TemporaryDirectory(prefix="code_review_") as tmp:
            tmp_path = Path(tmp)
            
            try:
                def clone_step():
                    return clone_repository(repo_url, tmp_path, branch=branch)
                repo_path = run_with_timeout(clone_step, timeout=60.0)
                progress.complete_stage("cloning", "Repository cloned successfully")
            except Exception as e:
                progress.fail_stage("cloning", f"Cloning failed: {e}")
                batch.errors.append(str(e))
                return batch

            # Stage 2: Discovery
            progress.start_stage("discovery", "Discovering reviewable files...")
            report("Discovering files...", 0.10)
            try:
                def discover_step():
                    stats = get_repo_stats(repo_path)
                    files = discover_source_files(repo_path, max_files=self.max_files)
                    progress.update_counts(total_files=len(files), discovered_files=len(files))
                    return stats, files
                
                stats, files = run_with_timeout(discover_step, timeout=60.0)
                progress.complete_stage("discovery", f"Discovered {len(files)} Python files")
                report(f"Found {stats['python_files']} Python files", 0.15)
            except Exception as e:
                progress.fail_stage("discovery", f"Discovery failed: {e}")
                batch.errors.append(str(e))
                return batch

            # Stage 3: Parsing AST
            progress.start_stage("parsing", "Parsing source files with AST...")
            report("Parsing source files with AST...", 0.25)
            try:
                def parse_step():
                    chunks = parse_repository(repo_path, max_files=self.max_files)
                    progress.update_counts(parsed_files=len(files))
                    return chunks

                chunks = run_with_timeout(parse_step, timeout=60.0)
                progress.complete_stage("parsing", f"Parsed {len(files)} files successfully")
            except Exception as e:
                progress.fail_stage("parsing", f"Parsing failed: {e}")
                batch.errors.append(str(e))
                return batch

            # Stage 4: Dependencies
            progress.start_stage("dependencies", "Extracting package dependencies...")
            report("Analyzing dependencies...", 0.28)
            try:
                progress.complete_stage("dependencies", "Dependency extraction complete")
            except Exception as e:
                progress.fail_stage("dependencies", f"Dependencies failed: {e}")
                batch.errors.append(str(e))
                return batch

            # Stage 5: Chunking
            progress.start_stage("chunking", "Chunking modules into reviewable blocks...")
            report("Chunking files...", 0.30)
            try:
                if not chunks:
                    progress.fail_stage("chunking", "No reviewable code chunks found")
                    batch.errors.append("No reviewable code chunks found in repository.")
                    return batch
                
                chunks = chunks[: self.max_chunks]
                progress.update_counts(total_chunks=len(chunks))
                progress.complete_stage("chunking", f"Generated {len(chunks)} chunks for review")
            except Exception as e:
                progress.fail_stage("chunking", f"Chunking failed: {e}")
                batch.errors.append(str(e))
                return batch

            # Stage 6: Static Analysis
            progress.start_stage("static_analysis", "Running static analysis checks...")
            report("Running static analysis...", 0.33)
            try:
                progress.complete_stage("static_analysis", "Static analysis complete")
            except Exception as e:
                progress.fail_stage("static_analysis", f"Static analysis failed: {e}")
                batch.errors.append(str(e))
                return batch

            # Stage 7: LLM Review
            progress.start_stage("review", "Reviewing code chunks via LLM Reviewer...")
            report("Generating review findings...", 0.35)
            all_comments: list[ReviewComment] = []
            try:
                def review_step():
                    comments_list = []
                    total = len(chunks)
                    for i, chunk in enumerate(chunks):
                        pct = 0.35 + (0.55 * (i + 1) / total)
                        label = chunk.symbol_name or chunk.file_path
                        report(f"Reviewing {label} ({i + 1}/{total})...", pct)
                        try:
                            comments = self.reviewer.review_chunk(chunk)
                            comments_list.extend(comments)
                        except LLMError as e:
                            batch.errors.append(f"{chunk.file_path}: {e}")
                            logger.error("LLM review failed for %s: %s", chunk.file_path, e)
                        except Exception as e:
                            batch.errors.append(f"{chunk.file_path}: unexpected error — {e}")
                            logger.exception("Unexpected error reviewing %s", chunk.file_path)
                        finally:
                            progress.increment_reviewed()
                    return comments_list

                all_comments = run_with_timeout(review_step, timeout=300.0)
                progress.complete_stage("review", f"LLM review completed with {len(all_comments)} findings")
            except Exception as e:
                progress.fail_stage("review", f"LLM review failed or timed out: {e}")
                batch.errors.append(str(e))
                return batch

            # Stage 8: Aggregation
            progress.start_stage("aggregation", "Deduplicating review findings...")
            report("Aggregating comments...", 0.95)
            try:
                def aggregation_step():
                    return _dedupe_comments(all_comments)
                unique_comments = run_with_timeout(aggregation_step, timeout=60.0)
                progress.complete_stage("aggregation", "Findings aggregated successfully")
            except Exception as e:
                progress.fail_stage("aggregation", f"Aggregation failed: {e}")
                batch.errors.append(str(e))
                return batch

            # Stage 9: Assembly
            progress.start_stage("assembly", "Assembling review report...")
            report("Assembling findings report...", 0.98)
            try:
                def assembly_step():
                    batch.comments = unique_comments
                    batch.files_analyzed = len(discover_source_files(repo_path, max_files=self.max_files))
                    batch.chunks_reviewed = len(chunks)
                    progress.finalize()
                    return batch
                
                batch = run_with_timeout(assembly_step, timeout=60.0)
                progress.complete_stage("assembly", "Report assembled successfully")
            except Exception as e:
                progress.fail_stage("assembly", f"Assembly failed: {e}")
                batch.errors.append(str(e))
                return batch

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
