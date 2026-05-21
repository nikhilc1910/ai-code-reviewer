"""Unit tests for AST parsing (no API keys required)."""

import tempfile
from pathlib import Path

from src.parsing.ast_parser import parse_python_file, parse_repository


def test_parse_simple_python():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        f = repo / "sample.py"
        f.write_text(
            '''
import os

def hello(name: str) -> str:
    """Greet by name with basic validation."""
    if not name:
        raise ValueError("name required")
    cleaned = name.strip()
    return f"Hello, {cleaned}"

class Greeter:
    def greet(self, target: str) -> str:
        if not target:
            return "Hello, world"
        return hello(target)
'''
        )
        chunks = parse_python_file(repo, f)
        assert len(chunks) >= 2
        names = {c.symbol_name for c in chunks}
        assert "hello" in names
        assert "Greeter" in names


def test_parse_repository_skips_venv():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        (repo / "main.py").write_text("def main():\n    x = 1\n    return x\n")
        venv = repo / ".venv" / "lib.py"
        venv.parent.mkdir(parents=True)
        venv.write_text("def hidden(): pass\n" * 10)
        chunks = parse_repository(repo, max_files=10)
        paths = {c.file_path for c in chunks}
        assert not any(".venv" in p for p in paths)
