"""Unit tests for the new parser.py module."""

from __future__ import annotations

import tempfile
from pathlib import Path

from parser import parse_file, parse_source


def test_parse_source_basic():
    source_code = """
import os
import sys as system
from pathlib import Path
from .import_helper import helper

def hello(name: str) -> str:
    \"\"\"Greet a user by name.\"\"\"
    return f"Hello, {name}"

def no_docstring(x, y=10):
    return x + y

class SimpleClass:
    def method_one(self):
        pass

    async def method_two(self, data):
        \"\"\"Async method.\"\"\"
        return data
"""
    result = parse_source(source_code)

    # Validate high-level keys
    assert set(result.keys()) == {"functions", "classes", "imports"}

    # Validate imports
    expected_imports = ["os", "sys", "pathlib", ".import_helper"]
    assert result["imports"] == expected_imports

    # Validate functions
    functions = result["functions"]
    assert len(functions) == 2
    
    # Check 'hello' function
    assert functions[0]["name"] == "hello"
    assert functions[0]["args"] == ["name"]
    assert functions[0]["docstring"] == "Greet a user by name."
    assert isinstance(functions[0]["line"], int)

    # Check 'no_docstring' function
    assert functions[1]["name"] == "no_docstring"
    assert functions[1]["args"] == ["x", "y"]
    assert functions[1]["docstring"] is None

    # Validate classes
    classes = result["classes"]
    assert len(classes) == 1
    assert classes[0]["name"] == "SimpleClass"
    assert classes[0]["methods"] == ["method_one", "method_two"]
    assert isinstance(classes[0]["line"], int)


def test_parse_source_complex_args():
    # Test arguments: pos-only, kw-only, vararg, kwarg
    source_code = """
def complex_func(a, b, /, c, *args, d, e=1, **kwargs):
    pass
"""
    result = parse_source(source_code)
    funcs = result["functions"]
    assert len(funcs) == 1
    # Arguments order in Python AST: posonly, normal, vararg, kwonly, kwarg
    # For: a, b (pos-only) / c (normal) * d, e (kw-only) *args (vararg) **kwargs (kwarg)
    # Let's verify our extracted list
    assert funcs[0]["args"] == ["a", "b", "c", "args", "d", "e", "kwargs"]


def test_parse_source_relative_imports():
    source_code = """
from . import first
from ..parent import second
from ...grandparent.uncle import third
"""
    result = parse_source(source_code)
    assert result["imports"] == [".first", "..parent", "...grandparent.uncle"]


def test_parse_source_syntax_error():
    # Invalid Python source code
    source_code = """
def bad_function(
    print("missing closing paren"
"""
    result = parse_source(source_code)
    assert result["functions"] == []
    assert result["classes"] == []
    assert result["imports"] == []


def test_parse_file_success():
    with tempfile.TemporaryDirectory() as tmp_dir:
        file_path = Path(tmp_dir) / "test_module.py"
        source_code = """
import json

def process():
    pass
"""
        file_path.write_text(source_code, encoding="utf-8")
        
        result = parse_file(file_path)
        assert result["imports"] == ["json"]
        assert len(result["functions"]) == 1
        assert result["functions"][0]["name"] == "process"


def test_parse_file_not_found():
    # Non-existent file should be handled gracefully by returning empty lists
    result = parse_file("non_existent_file_xyz.py")
    assert result["functions"] == []
    assert result["classes"] == []
    assert result["imports"] == []
