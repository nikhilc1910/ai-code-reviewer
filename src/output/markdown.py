"""Format review results as Markdown."""

from __future__ import annotations

from src.models.schemas import CONFIDENCE_VERIFY_THRESHOLD, ReviewBatch, ReviewComment


def comment_to_markdown(c: ReviewComment, include_verify: bool = True) -> str:
    verify = " ⚠️ **VERIFY THIS**" if include_verify and c.needs_verification else ""
    lines = [
        f"### [{c.severity.value.upper()}] {c.file_path}:{c.line_start}{verify}",
        f"- **Category:** {c.category.value}",
        f"- **Confidence:** {c.confidence}% ({c.confidence_bucket})",
    ]
    if c.symbol_name:
        lines.append(f"- **Symbol:** `{c.symbol_name}`")
    lines.append(f"\n{c.message}\n")
    if c.suggestion:
        lines.append(f"**Suggestion:** {c.suggestion}\n")
    return "\n".join(lines)


def batch_to_markdown(batch: ReviewBatch) -> str:
    sections = [
        f"# Code Review: {batch.repo_url}",
        "",
        f"- Files analyzed: {batch.files_analyzed}",
        f"- Chunks reviewed: {batch.chunks_reviewed}",
        f"- Total comments: {len(batch.comments)}",
        "",
    ]

    if batch.errors:
        sections.append("## Errors\n")
        for err in batch.errors:
            sections.append(f"- {err}")
        sections.append("")

    high = batch.high_confidence
    medium = batch.medium_confidence
    low = batch.low_confidence

    if high:
        sections.append("## High Confidence (≥80%)\n")
        for c in high:
            sections.append(comment_to_markdown(c, include_verify=False))

    if medium:
        sections.append(f"## Medium Confidence ({CONFIDENCE_VERIFY_THRESHOLD}–79%)\n")
        for c in medium:
            sections.append(comment_to_markdown(c, include_verify=False))

    if low:
        sections.append(f"## Low Confidence — Verify This (<{CONFIDENCE_VERIFY_THRESHOLD}%)\n")
        for c in low:
            sections.append(comment_to_markdown(c, include_verify=True))

    if not batch.comments:
        sections.append("_No issues found._\n")

    return "\n".join(sections)
