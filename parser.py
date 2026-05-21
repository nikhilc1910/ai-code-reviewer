"""Python code parser using the built-in ast module.

Extracts function definitions, class definitions, and imports from Python files.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Union


def _extract_args(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Extract argument names from a function or method definition node."""
    args: list[str] = []
    
    # Positional-only arguments (Python 3.8+)
    if hasattr(node.args, "posonlyargs"):
        for arg in node.args.posonlyargs:
            args.append(arg.arg)
            
    # Regular positional / keyword arguments
    if hasattr(node.args, "args") and node.args.args:
        for arg in node.args.args:
            args.append(arg.arg)
            
    # *args
    if getattr(node.args, "vararg", None):
        args.append(node.args.vararg.arg)
        
    # Keyword-only arguments
    if hasattr(node.args, "kwonlyargs") and node.args.kwonlyargs:
        for arg in node.args.kwonlyargs:
            args.append(arg.arg)
            
    # **kwargs
    if getattr(node.args, "kwarg", None):
        args.append(node.args.kwarg.arg)
        
    return args


def parse_source(source_code: str) -> dict[str, list[Any]]:
    """Parse Python source code and extract functions, classes, and imports.

    Returns:
        A dict:
        {
          "functions": [{"name": str, "line": int, "args": list, "docstring": str|None}],
          "classes":   [{"name": str, "line": int, "methods": list}],
          "imports":   [str]
        }
    """
    try:
        tree = ast.parse(source_code)
    except (SyntaxError, ValueError):
        # Handle SyntaxError and ValueError (e.g. null bytes in source) gracefully
        return {
            "functions": [],
            "classes": [],
            "imports": [],
        }

    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    imports_set: set[str] = set()
    imports_list: list[str] = []  # Keep insertion order for imports

    def add_import(module_name: str) -> None:
        if module_name not in imports_set:
            imports_set.add(module_name)
            imports_list.append(module_name)

    # 1. Identify all direct class methods first to exclude them from the global functions list.
    class_methods: set[ast.AST] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    class_methods.add(child)

    # 2. Walk AST to collect all functions, classes, and imports.
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip if it is a class method
            if node in class_methods:
                continue
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "args": _extract_args(node),
                "docstring": ast.get_docstring(node),
            })
            
        elif isinstance(node, ast.ClassDef):
            # Extract method names (functions defined directly in the class body)
            methods: list[str] = []
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(child.name)
            classes.append({
                "name": node.name,
                "line": node.lineno,
                "methods": methods,
            })
            
        elif isinstance(node, ast.Import):
            for alias in node.names:
                add_import(alias.name)
                
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            prefix = "." * level
            if node.module is not None:
                add_import(prefix + node.module)
            else:
                # E.g. from . import a, b
                for alias in node.names:
                    add_import(prefix + alias.name)

    # Sort functions and classes by line number to match their physical layout in the file
    functions.sort(key=lambda x: x["line"])
    classes.sort(key=lambda x: x["line"])

    return {
        "functions": functions,
        "classes": classes,
        "imports": imports_list,
    }


def parse_file(file_path: Union[str, Path]) -> dict[str, list[Any]]:
    """Read a Python file and extract functions, classes, and imports.

    If file_path doesn't exist, is invalid, or represents raw content,
    falls back to parsing the string as raw source code.
    """
    try:
        path = Path(file_path)
        if path.is_file():
            source_code = path.read_text(encoding="utf-8", errors="replace")
            return parse_source(source_code)
    except Exception:
        pass

    # If it is not a file or reading failed, treat the input directly as raw source code
    if isinstance(file_path, (str, Path)):
        return parse_source(str(file_path))
    return {
        "functions": [],
        "classes": [],
        "imports": [],
    }
