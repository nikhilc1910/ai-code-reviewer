"""GitPython clone logic.

This module keeps the simple `agent.*` project layout while reusing the
implementation in `src.ingestion`.
"""

from src.ingestion.clone_repo import (
    CloneError,
    clone_repository,
    get_repo_stats,
    normalize_repo_url,
    repo_slug_from_url,
    validate_github_url,
)

__all__ = [
    "CloneError",
    "clone_repository",
    "get_repo_stats",
    "normalize_repo_url",
    "repo_slug_from_url",
    "validate_github_url",
]

