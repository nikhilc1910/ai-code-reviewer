"""Unit tests for the repository ingestion module."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from git.exc import GitCommandError

from ingestion import validate_github_url, ingest_repository


def test_validate_github_url():
    # Valid HTTPS URLs
    assert validate_github_url("https://github.com/owner/repo") is True
    assert validate_github_url("http://github.com/owner/repo.git") is True
    assert validate_github_url("https://www.github.com/owner/repo/") is True
    assert validate_github_url("github.com/owner/repo") is True
    
    # Valid SSH URLs
    assert validate_github_url("git@github.com:owner/repo.git") is True
    assert validate_github_url("git@github.com:owner/repo") is True
    
    # Invalid URLs
    assert validate_github_url("https://gitlab.com/owner/repo") is False
    assert validate_github_url("not_a_url") is False
    assert validate_github_url("") is False
    assert validate_github_url(None) is False
    assert validate_github_url("https://github.com/owner") is False


def test_ingest_repository_invalid_url():
    with pytest.raises(ValueError) as excinfo:
        ingest_repository("https://gitlab.com/owner/repo")
    assert "Invalid GitHub URL" in str(excinfo.value)


@patch("git.Repo.clone_from")
@patch("tempfile.mkdtemp")
def test_ingest_repository_success(mock_mkdtemp, mock_clone_from, tmp_path):
    # Set mkdtemp to return a directory inside our pytest tmp_path
    temp_dir = tmp_path / "cloned_repo"
    temp_dir.mkdir()
    mock_mkdtemp.return_value = str(temp_dir)
    
    # Mock clone_from to populate the temp_dir with test files
    def mock_clone(url, to_path, depth=1):
        to_path = Path(to_path)
        # Create directories and files to walk
        (to_path / "src").mkdir()
        (to_path / "src" / "main.py").write_text("print('hello python')", encoding="utf-8")
        (to_path / "src" / "index.js").write_text("console.log('hello js')", encoding="utf-8")
        (to_path / "README.md").write_text("Markdown file, should be skipped", encoding="utf-8")
        
        # Create directories that should be skipped
        (to_path / "node_modules").mkdir()
        (to_path / "node_modules" / "package.js").write_text("console.log('skip node')", encoding="utf-8")
        
        (to_path / ".venv").mkdir()
        (to_path / ".venv" / "lib.py").write_text("print('skip venv')", encoding="utf-8")
        
        (to_path / "__pycache__").mkdir()
        (to_path / "__pycache__" / "main.pyc").write_bytes(b"skip pycache")
        
        (to_path / ".git").mkdir()
        (to_path / ".git" / "config").write_text("git config", encoding="utf-8")
        
        return MagicMock() # Return mock Repo instance
        
    mock_clone_from.side_effect = mock_clone

    results = ingest_repository("https://github.com/owner/repo")
    
    # Verify files found and parsed
    assert len(results) == 2
    
    paths = {r["path"] for r in results}
    assert "src/main.py" in paths
    assert "src/index.js" in paths
    assert "README.md" not in paths
    
    # Verify Python file info
    py_file = next(r for r in results if r["path"] == "src/main.py")
    assert py_file["language"] == "python"
    assert py_file["content"] == "print('hello python')"
    
    # Verify JavaScript file info
    js_file = next(r for r in results if r["path"] == "src/index.js")
    assert js_file["language"] == "javascript"
    assert js_file["content"] == "console.log('hello js')"
    
    # Verify temp dir cleanup
    assert not temp_dir.exists()


@patch("git.Repo.clone_from")
@patch("tempfile.mkdtemp")
def test_ingest_repository_clone_failure(mock_mkdtemp, mock_clone_from, tmp_path):
    temp_dir = tmp_path / "failed_clone_repo"
    temp_dir.mkdir()
    mock_mkdtemp.return_value = str(temp_dir)
    
    # Make clone_from raise a GitCommandError
    mock_clone_from.side_effect = GitCommandError("clone", 128, "fatal: repository not found")
    
    with pytest.raises(ValueError) as excinfo:
        ingest_repository("https://github.com/owner/invalid-repo")
        
    assert "Failed to clone repository" in str(excinfo.value)
    
    # Verify temp dir cleanup
    assert not temp_dir.exists()


@patch("git.Repo.clone_from")
@patch("tempfile.mkdtemp")
def test_ingest_repository_max_files_limit(mock_mkdtemp, mock_clone_from, tmp_path):
    temp_dir = tmp_path / "cloned_repo_limit"
    temp_dir.mkdir()
    mock_mkdtemp.return_value = str(temp_dir)
    
    def mock_clone(url, to_path, depth=1):
        to_path = Path(to_path)
        # Create 5 python files
        for i in range(5):
            (to_path / f"file_{i}.py").write_text(f"print({i})", encoding="utf-8")
        return MagicMock()
        
    mock_clone_from.side_effect = mock_clone

    with patch("ingestion.logger") as mock_logger:
        results = ingest_repository("https://github.com/owner/repo", max_files=3)
        assert len(results) == 3
        mock_logger.warning.assert_called_once_with("Limiting to 20 files for performance")

