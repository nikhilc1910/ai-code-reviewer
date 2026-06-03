"""Clone and validate GitHub repositories using GitPython."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError

GITHUB_URL_PATTERN = re.compile(
    r"^(https?://)?(www\.)?github\.com/[\w.\-]+/[\w.\-]+/?(\.git)?$",
    re.IGNORECASE,
)


class CloneError(Exception):
    pass


def normalize_repo_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        return url
    if "github.com" in url.lower():
        return url if url.endswith(".git") else f"{url}.git"
    return url


def validate_github_url(url: str) -> bool:
    normalized = url.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return bool(GITHUB_URL_PATTERN.match(normalized))


def repo_slug_from_url(url: str) -> str:
    path = urlparse(normalize_repo_url(url)).path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = path.split("/")
    if len(parts) >= 2:
        return f"{parts[-2]}_{parts[-1]}"
    return path.replace("/", "_") or "repo"


def clone_repository(
    repo_url: str,
    target_dir: Path,
    branch: Optional[str] = None,
    depth: int = 1,
) -> Path:
    """
    Clone a GitHub repository into target_dir.
    Returns the path to the cloned working tree.
    """
    if not validate_github_url(repo_url):
        raise CloneError(
            f"Invalid GitHub URL: {repo_url}. "
            "Expected format: https://github.com/owner/repo"
        )

    normalized = normalize_repo_url(repo_url)
    slug = repo_slug_from_url(repo_url)
    clone_path = target_dir / slug

    if clone_path.exists():
        shutil.rmtree(clone_path, ignore_errors=True)

    target_dir.mkdir(parents=True, exist_ok=True)

    import os
    old_terminal_prompt = os.environ.get("GIT_TERMINAL_PROMPT")
    old_askpass = os.environ.get("GIT_ASKPASS")
    try:
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
        os.environ["GIT_ASKPASS"] = "echo"
        
        kwargs: dict = {"depth": depth}
        if branch:
            kwargs["branch"] = branch
        Repo.clone_from(normalized, str(clone_path), **kwargs)
    except GitCommandError as e:
        raise CloneError(f"Failed to clone repository: {e}") from e
    finally:
        if old_terminal_prompt is not None:
            os.environ["GIT_TERMINAL_PROMPT"] = old_terminal_prompt
        else:
            os.environ.pop("GIT_TERMINAL_PROMPT", None)
        if old_askpass is not None:
            os.environ["GIT_ASKPASS"] = old_askpass
        else:
            os.environ.pop("GIT_ASKPASS", None)

    if not (clone_path / ".git").exists():
        raise CloneError(f"Clone succeeded but .git not found at {clone_path}")

    return clone_path


def get_repo_stats(repo_path: Path) -> dict:
    """Collect basic statistics about a cloned repository."""
    py_files = list(repo_path.rglob("*.py"))
    js_files = list(repo_path.rglob("*.js")) + list(repo_path.rglob("*.ts"))
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}

    def count_lines(files: list[Path]) -> int:
        total = 0
        for f in files:
            if any(part in skip_dirs for part in f.parts):
                continue
            try:
                total += len(f.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                pass
        return total

    return {
        "python_files": len([f for f in py_files if not any(d in f.parts for d in skip_dirs)]),
        "javascript_files": len([f for f in js_files if not any(d in f.parts for d in skip_dirs)]),
        "total_lines_python": count_lines(py_files),
    }
