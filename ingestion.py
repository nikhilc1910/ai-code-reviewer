"""GitHub repository ingestion module.

Clones a repository using GitPython, parses .py and .js files, and cleans up.
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



def validate_github_url(url: str) -> bool:
    """Validate if the given string is a valid GitHub repository URL.

    Supports HTTPS, HTTP, and SSH formats, with or without .git suffix.
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
    # e.g., https://github.com/owner/repo or github.com/owner/repo
    parsed = urlparse(url)
    path = parsed.path
    if not parsed.scheme:
        # e.g., github.com/owner/repo
        path = url

    path = path.strip("/")
    parts = [p for p in path.split("/") if p]

    if "github.com" in parts:
        idx = parts.index("github.com")
        subparts = parts[idx + 1 :]
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


def ingest_repository(github_url: str, max_files: int = 20) -> list[dict]:
    """Clones a GitHub repository, walks it for .py and .js files, and cleans up.

    Args:
        github_url: The URL of the GitHub repository.

    Returns:
        A list of dicts: {"path": str, "language": "python"|"javascript", "content": str}

    Raises:
        ValueError: If the URL is invalid or the clone fails.
    """
    if not validate_github_url(github_url):
        raise ValueError(f"Invalid GitHub URL: '{github_url}'")
    
    github_url = github_url.strip().rstrip("/").removesuffix(".git")
    
    temp_dir = tempfile.mkdtemp(prefix="git_ingest_")
    repo = None

    try:
        # Clone the repository (using depth=1 for shallow clone)
        repo = git.Repo.clone_from(github_url, temp_dir, depth=1)
    except Exception as e:
        # Ensure cleanup on clone failure
        shutil.rmtree(temp_dir, onerror=remove_readonly)
        raise ValueError(f"Failed to clone repository: {e}") from e

    try:
        results = []
        skip_dirs = {"node_modules", ".venv", "__pycache__", ".git"}
        temp_path = Path(temp_dir)

        # Recursively walk the repository
        for root, dirs, files in os.walk(temp_dir):
            # Modify dirs in-place to skip specific folders
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for file in files:
                file_path = Path(root) / file
                ext = file_path.suffix.lower()

                if ext == ".py":
                    language = "python"
                elif ext == ".js":
                    language = "javascript"
                else:
                    continue

                # Get path relative to repository root, using forward slashes
                rel_path = file_path.relative_to(temp_path).as_posix()

                try:
                    # Read the file content with UTF-8, replacing invalid bytes
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    # Fallback if file reading fails
                    content = ""

                results.append({
                    "path": rel_path,
                    "language": language,
                    "content": content
                })

        if len(results) > max_files:
            logger.warning("Limiting to 20 files for performance")
            results = results[:max_files]

        return results

    finally:
        # Always clean up the temp directory, ensuring file handles are closed
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
    """Clones a GitHub repository, walks it for .py and .js files, and returns (results, temp_dir).

    The caller is responsible for deleting temp_dir.
    """
    if not validate_github_url(github_url):
        raise ValueError(f"Invalid GitHub URL: '{github_url}'")
    
    github_url = github_url.strip().rstrip("/").removesuffix(".git")
    
    temp_dir = tempfile.mkdtemp(prefix="git_ingest_")
    repo = None

    try:
        # Clone the repository (using depth=1 for shallow clone)
        repo = git.Repo.clone_from(github_url, temp_dir, depth=1)
        
        results = []
        skip_dirs = {"node_modules", ".venv", "__pycache__", ".git"}
        temp_path = Path(temp_dir)

        # Recursively walk the repository
        for root, dirs, files in os.walk(temp_dir):
            # Modify dirs in-place to skip specific folders
            dirs[:] = [d for d in dirs if d not in skip_dirs]

            for file in files:
                file_path = Path(root) / file
                ext = file_path.suffix.lower()

                if ext == ".py":
                    language = "python"
                elif ext == ".js":
                    language = "javascript"
                else:
                    continue

                # Get path relative to repository root, using forward slashes
                rel_path = file_path.relative_to(temp_path).as_posix()

                try:
                    # Read the file content with UTF-8, replacing invalid bytes
                    content = file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    # Fallback if file reading fails
                    content = ""

                results.append({
                    "path": rel_path,
                    "language": language,
                    "content": content
                })

        if len(results) > max_files:
            logger.warning("Limiting to 20 files for performance")
            results = results[:max_files]

        return results, temp_dir

    except Exception as e:
        # Ensure cleanup on clone failure
        shutil.rmtree(temp_dir, onerror=remove_readonly)
        raise ValueError(f"Failed to clone repository: {e}") from e
    finally:
        # Close the repo reference if open
        if repo is not None:
            try:
                repo.close()
            except Exception:
                pass
        try:
            git.Git().clear_cache()
        except Exception:
            pass

