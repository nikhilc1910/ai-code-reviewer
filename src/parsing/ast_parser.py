"""Extract functions, classes, and imports via AST (Python) and tree-sitter (JS)."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import Iterator, Optional

from src.models.schemas import CodeChunk

logger = logging.getLogger(__name__)

SKIP_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".tox",
    ".eggs",
    "site-packages",
}

MAX_CHUNK_LINES = 120
MIN_CHUNK_LINES = 5
SUPPORTED_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx"}


def _should_skip(path: Path) -> bool:
    return any(part in SKIP_DIRS for part in path.parts)


def discover_source_files(repo_path: Path, max_files: int = 50) -> list[Path]:
    files: list[Path] = []
    for ext in SUPPORTED_EXTENSIONS:
        for f in sorted(repo_path.rglob(f"*{ext}")):
            if _should_skip(f):
                continue
            if f.stat().st_size > 500_000:
                continue
            files.append(f)
            if len(files) >= max_files:
                return files
    return files


def _relative_path(repo_path: Path, file_path: Path) -> str:
    try:
        return str(file_path.relative_to(repo_path)).replace("\\", "/")
    except ValueError:
        return str(file_path)


def _extract_imports(tree: ast.AST) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}" if module else alias.name)
    return imports[:30]


def _get_source_segment(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start - 1 : end])


def _chunk_large_block(
    file_path: str,
    language: str,
    lines: list[str],
    start: int,
    end: int,
    symbol_name: Optional[str],
    symbol_type: str,
    imports: list[str],
) -> Iterator[CodeChunk]:
    """Split oversized functions/classes into overlapping windows."""
    total = end - start + 1
    if total <= MAX_CHUNK_LINES:
        yield CodeChunk(
            file_path=file_path,
            language=language,
            symbol_name=symbol_name,
            symbol_type=symbol_type,
            line_start=start,
            line_end=end,
            source=_get_source_segment(lines, start, end),
            imports=imports,
        )
        return

    overlap = 10
    pos = start
    part = 0
    while pos <= end:
        chunk_end = min(pos + MAX_CHUNK_LINES - 1, end)
        name = f"{symbol_name}__part{part}" if symbol_name else f"fragment_{part}"
        yield CodeChunk(
            file_path=file_path,
            language=language,
            symbol_name=name,
            symbol_type=symbol_type,
            line_start=pos,
            line_end=chunk_end,
            source=_get_source_segment(lines, pos, chunk_end),
            imports=imports,
        )
        if chunk_end >= end:
            break
        pos = chunk_end - overlap + 1
        part += 1


def parse_python_file(repo_path: Path, file_path: Path) -> list[CodeChunk]:
    rel = _relative_path(repo_path, file_path)
    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Cannot read %s: %s", rel, e)
        return []

    lines = source.splitlines()
    try:
        tree = ast.parse(source, filename=rel)
    except SyntaxError as e:
        logger.warning("Syntax error in %s: %s", rel, e)
        return [
            CodeChunk(
                file_path=rel,
                language="python",
                symbol_name=None,
                symbol_type="syntax_error",
                line_start=max(1, e.lineno or 1),
                line_end=max(1, e.lineno or 1),
                source=_get_source_segment(lines, max(1, e.lineno or 1), min(len(lines), (e.lineno or 1) + 5)),
                imports=[],
            )
        ]

    imports = _extract_imports(tree)
    chunks: list[CodeChunk] = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not hasattr(node, "end_lineno") or node.end_lineno is None:
                continue
            start, end = node.lineno, node.end_lineno
            if end - start + 1 < MIN_CHUNK_LINES and isinstance(node, ast.FunctionDef):
                continue
            sym_type = "class" if isinstance(node, ast.ClassDef) else "function"
            for chunk in _chunk_large_block(
                rel, "python", lines, start, end, node.name, sym_type, imports
            ):
                chunks.append(chunk)

    if not chunks and len(lines) >= MIN_CHUNK_LINES:
        for chunk in _chunk_large_block(
            rel, "python", lines, 1, len(lines), None, "module_fragment", imports
        ):
            chunks.append(chunk)

    return chunks


def parse_javascript_file(repo_path: Path, file_path: Path) -> list[CodeChunk]:
    """Parse JS/TS using tree-sitter when available; fallback to line windows."""
    rel = _relative_path(repo_path, file_path)
    try:
        source = file_path.read_text(encoding="utf-8")
    except OSError:
        return []

    lines = source.splitlines()
    lang = "javascript" if file_path.suffix in (".js", ".jsx") else "typescript"

    try:
        from tree_sitter import Language, Parser
        import tree_sitter_javascript as ts_js

        parser = Parser(Language(ts_js.language()))
        tree = parser.parse(source.encode("utf-8"))
        chunks: list[CodeChunk] = []

        def walk(node, depth=0):
            if depth > 50:
                return
            if node.type in ("function_declaration", "method_definition", "class_declaration", "arrow_function"):
                start_row = node.start_point[0] + 1
                end_row = node.end_point[0] + 1
                name_node = node.child_by_field_name("name")
                name = name_node.text.decode() if name_node else None
                if end_row - start_row + 1 >= MIN_CHUNK_LINES:
                    for c in _chunk_large_block(
                        rel, lang, lines, start_row, end_row, name,
                        "function" if "function" in node.type else "class",
                        [],
                    ):
                        chunks.append(c)
            for child in node.children:
                walk(child, depth + 1)

        walk(tree.root_node)
        if chunks:
            return chunks
    except Exception as e:
        logger.debug("tree-sitter JS parse fallback for %s: %s", rel, e)

    # Line-window fallback
    result: list[CodeChunk] = []
    step = MAX_CHUNK_LINES - 15
    for i in range(0, len(lines), step):
        start = i + 1
        end = min(i + MAX_CHUNK_LINES, len(lines))
        if end - start + 1 < MIN_CHUNK_LINES:
            break
        result.append(
            CodeChunk(
                file_path=rel,
                language=lang,
                symbol_name=f"block_{start}",
                symbol_type="module_fragment",
                line_start=start,
                line_end=end,
                source=_get_source_segment(lines, start, end),
                imports=[],
            )
        )
    return result


def parse_repository(repo_path: Path, max_files: int = 50) -> list[CodeChunk]:
    """Parse all supported source files in a repository."""
    all_chunks: list[CodeChunk] = []
    for file_path in discover_source_files(repo_path, max_files=max_files):
        ext = file_path.suffix.lower()
        if ext == ".py":
            all_chunks.extend(parse_python_file(repo_path, file_path))
        elif ext in (".js", ".ts", ".jsx", ".tsx"):
            all_chunks.extend(parse_javascript_file(repo_path, file_path))
    return all_chunks
