"""GitHub repository ingestion module.

Clones a repository using GitPython, parses .py, .js, .ts, and .tsx files, and cleans up.
"""

import os
import re
import stat
import shutil
import tempfile
import logging
from pathlib import Path
from urllib.parse import urlparse

import git
from git.exc import GitCommandError

logger = logging.getLogger(__name__)


def _strip_tree_path(url: str) -> str:
    """Strip a GitHub /tree/<branch>/... path segment, returning the repo root URL.

    Example:
        https://github.com/fastapi/fastapi/tree/master/docs_src
        → https://github.com/fastapi/fastapi
    """
    match = re.search(r"(https?://github\.com/[^/]+/[^/]+)/tree/.*", url, re.IGNORECASE)
    if match:
        return match.group(1)
    return url


def validate_github_url(url: str) -> bool:
    """Validate if the given string is a valid GitHub repository URL.

    Supports HTTPS, HTTP, and SSH formats, with or without .git suffix.
    Also accepts /tree/<branch>/... subdirectory URLs — the tree path is
    stripped automatically before cloning.
    """
    if not isinstance(url, str):
        return False
    url = url.strip()
    if not url:
        return False

    # Check for basic presence of github.com
    if "github.com" not in url.lower():
        return False

    # SSH format: git@github.com:owner/repo.git
    if url.startswith("git@"):
        pattern = r"^git@github\.com:[\w.\-]+/[\w.\-]+(?:\.git)?$"
        return bool(re.match(pattern, url, re.IGNORECASE))

    # HTTP/HTTPS/git protocol formats
    parsed = urlparse(url)
    path = parsed.path
    if not parsed.scheme:
        # e.g., github.com/owner/repo
        path = url

    path = path.strip("/")
    parts = [p for p in path.split("/") if p]

    if "github.com" in parts:
        idx = parts.index("github.com")
        subparts = parts[idx + 1:]
    else:
        subparts = parts

    # We need at least owner and repo parts
    return len(subparts) >= 2


def remove_readonly(func, path, excinfo):
    """OnError handler for shutil.rmtree to clear read-only file flags on Windows."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass


def _walk_repo_files(temp_dir: str, max_files: int) -> list[dict]:
    """Walk a cloned repository and collect .py, .js, .ts, and .tsx files.

    Args:
        temp_dir: Path to the cloned repository root.
        max_files: Maximum number of files to return.

    Returns:
        A list of dicts: {"path": str, "language": str, "content": str}
    """
    results = []
    skip_dirs = {"node_modules", ".venv", "__pycache__", ".git"}
    temp_path = Path(temp_dir)

    for root, dirs, files in os.walk(temp_dir):
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for file in files:
            file_path = Path(root) / file
            ext = file_path.suffix.lower()

            if ext == ".py":
                language = "python"
            elif ext == ".js":
                language = "javascript"
            elif ext in (".ts", ".tsx"):
                language = "typescript"
            else:
                continue

            # Get path relative to repository root, using forward slashes
            rel_path = file_path.relative_to(temp_path).as_posix()

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = ""

            results.append({
                "path": rel_path,
                "language": language,
                "content": content,
            })

    if len(results) > max_files:
        logger.warning("Limiting to 20 files for performance")
        results = results[:max_files]

    return results


def ingest_repository(github_url: str, max_files: int = 20) -> list[dict]:
    """Clones a GitHub repository, walks it for source files, and cleans up.

    Args:
        github_url: The URL of the GitHub repository. Accepts repo root URLs or
            /tree/<branch>/... subdirectory URLs — the tree path is stripped
            automatically so git clone receives a valid repo root URL.
        max_files: Maximum number of files to return.

    Returns:
        A list of dicts: {"path": str, "language": "python"|"javascript"|"typescript", "content": str}

    Raises:
        ValueError: If the URL is invalid or the clone fails.
    """
    if not validate_github_url(github_url):
        raise ValueError(f"Invalid GitHub URL: '{github_url}'")

    github_url = _strip_tree_path(github_url.strip().rstrip("/")).removesuffix(".git")

    temp_dir = tempfile.mkdtemp(prefix="git_ingest_")
    repo = None

    import os
    old_terminal_prompt = os.environ.get("GIT_TERMINAL_PROMPT")
    old_askpass = os.environ.get("GIT_ASKPASS")
    try:
        os.environ["GIT_TERMINAL_PROMPT"] = "0"
        os.environ["GIT_ASKPASS"] = "echo"
        repo = git.Repo.clone_from(github_url, temp_dir, depth=1)
    except Exception as e:
        shutil.rmtree(temp_dir, onerror=remove_readonly)
        raise ValueError(f"Failed to clone repository: {e}") from e
    finally:
        if old_terminal_prompt is not None:
            os.environ["GIT_TERMINAL_PROMPT"] = old_terminal_prompt
        else:
            os.environ.pop("GIT_TERMINAL_PROMPT", None)
        if old_askpass is not None:
            os.environ["GIT_ASKPASS"] = old_askpass
        else:
            os.environ.pop("GIT_ASKPASS", None)

    try:
        return _walk_repo_files(temp_dir, max_files)
    finally:
        if repo is not None:
            try:
                repo.close()
            except Exception:
                pass
        try:
            git.Git().clear_cache()
        except Exception:
            pass
        shutil.rmtree(temp_dir, onerror=remove_readonly)


# Alias to support simpler imports if requested
ingest = ingest_repository


def clone_repo(github_url: str, max_files: int = 20) -> tuple[list[dict], str]:
    """Clones a GitHub repository, walks it for source files, and returns (results, temp_dir).

    The caller is responsible for deleting temp_dir.

    Args:
        github_url: The URL of the GitHub repository. Accepts repo root URLs or
            /tree/<branch>/... subdirectory URLs — the tree path is stripped
            automatically so git clone receives a valid repo root URL.
        max_files: Maximum number of files to return.

    Returns:
        A tuple of (file list, temp_dir path).

    Raises:
        ValueError: If the URL is invalid or the clone fails.
    """
    if not validate_github_url(github_url):
        raise ValueError(f"Invalid GitHub URL: '{github_url}'")

    github_url = _strip_tree_path(github_url.strip().rstrip("/")).removesuffix(".git")

    temp_dir = tempfile.mkdtemp(prefix="git_ingest_")
    repo = None

    try:
        clone_env = os.environ.copy()
        clone_env["GIT_TERMINAL_PROMPT"] = "0"
        clone_env["GIT_ASKPASS"] = "echo"
        repo = git.Repo.clone_from(github_url, temp_dir, depth=1, env=clone_env)
        results = _walk_repo_files(temp_dir, max_files)
        return results, temp_dir

    except Exception as e:
        shutil.rmtree(temp_dir, onerror=remove_readonly)
        raise ValueError(f"Failed to clone repository: {e}") from e
    finally:
        if repo is not None:
            try:
                repo.close()
            except Exception:
                pass
        try:
            git.Git().clear_cache()
        except Exception:
            pass
