"""Post review comments to a GitHub pull request (bonus feature)."""

from __future__ import annotations

import os
import re
from typing import Optional

from src.models.schemas import ReviewBatch, ReviewComment


class GitHubPRError(Exception):
    pass


def parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """
    Parse https://github.com/owner/repo/pull/123
    Returns (owner, repo, pr_number).
    """
    pattern = r"github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.search(pattern, pr_url.strip())
    if not match:
        raise GitHubPRError(f"Invalid PR URL: {pr_url}")
    return match.group(1), match.group(2), int(match.group(3))


def format_inline_comment(c: ReviewComment) -> str:
    verify = " **[VERIFY THIS]**" if c.needs_verification else ""
    body = (
        f"**[{c.severity.value.upper()}]** ({c.category.value}) "
        f"— Confidence: {c.confidence}%{verify}\n\n"
        f"{c.message}"
    )
    if c.suggestion:
        body += f"\n\n**Suggestion:** {c.suggestion}"
    return body


def post_pr_review(
    batch: ReviewBatch,
    pr_url: str,
    max_comments: int = 10,
    token: Optional[str] = None,
) -> list[str]:
    """
    Post inline review comments to a GitHub PR.
    Returns list of posted comment URLs or IDs.
    """
    try:
        from github import Github
    except ImportError as e:
        raise GitHubPRError("PyGithub not installed") from e

    token = token or os.getenv("GITHUB_TOKEN")
    if not token:
        raise GitHubPRError("GITHUB_TOKEN not set")

    owner, repo_name, pr_number = parse_pr_url(pr_url)
    gh = Github(token)
    repo = gh.get_repo(f"{owner}/{repo_name}")
    pr = repo.get_pull(pr_number)

    head_sha = pr.head.sha
    posted: list[str] = []

    comments = sorted(batch.comments, key=lambda c: -c.confidence)[:max_comments]

    for c in comments:
        try:
            review_comment = pr.create_review_comment(
                body=format_inline_comment(c),
                commit_id=head_sha,
                path=c.file_path,
                line=c.line_start,
            )
            posted.append(review_comment.html_url)
        except Exception as e:
            posted.append(f"FAILED {c.file_path}:{c.line_start} — {e}")

    return posted
