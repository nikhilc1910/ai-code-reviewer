from __future__ import annotations

from typing import Any


def _format_snippet(node: Any) -> str:
    """Format an AST-extracted function or class node.
    
    Rules:
    - If node is a dict with "name"/"label" and "source" keys:
      returns "=== {name} ===\\n{source}"
    - If node dict has no name: uses "<unknown>" as the label
    - If source is blank/whitespace: returns ""
    - If node is not a dict: returns str(node)
    """
    if isinstance(node, dict):
        name = node.get("name")
        if name is None:
            name = node.get("label")
        if name is None:
            name = "<unknown>"
            
        source = node.get("source")
        if not source or not str(source).strip():
            return ""
            
        return f"=== {name} ===\n{source}"
        
    # Non-dict node fallback
    node_str = str(node)
    if not node_str.strip():
        return ""
    return node_str


def chunk_nodes(nodes: list[Any], max_chars: int = 3000, max_items: int = 3) -> list[str]:
    """Split a list of nodes into text chunks.
    
    Each chunk contains 1 to max_items snippets and is kept under max_chars length.
    Oversized snippets exceeding max_chars are emitted in their own chunk.
    """
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0
    
    for node in nodes:
        snippet = _format_snippet(node)
        if not snippet:
            continue
            
        snippet_len = len(snippet)
        
        if not current_chunk:
            current_chunk.append(snippet)
            current_len = snippet_len
        else:
            potential_len = current_len + 2 + snippet_len
            if potential_len > max_chars or len(current_chunk) >= max_items:
                # Flush current chunk
                chunks.append("\n\n".join(current_chunk))
                # Start new chunk with current snippet
                current_chunk = [snippet]
                current_len = snippet_len
            else:
                current_chunk.append(snippet)
                current_len = potential_len
                
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
        
    return chunks


def make_chunks(ast_data: dict[str, Any], raw_content: str) -> list[str]:
    """Convert AST-parsed function/class metadata and raw source code into formatted text chunks.
    
    Merges functions and classes, sorts by line_start, slices raw_content by line number,
    and feeds the resulting nodes to chunk_nodes(). Falls back to raw content when AST is empty.
    """
    functions = ast_data.get("functions", [])
    classes = ast_data.get("classes", [])

    items = []
    for f in functions:
        items.append({"name": f.get("name"), "line": f.get("line", 1)})
    for c in classes:
        items.append({"name": c.get("name"), "line": c.get("line", 1)})

    items.sort(key=lambda x: x["line"])

    if not items:
        if not raw_content or not raw_content.strip():
            return []
        return chunk_nodes([{"name": "<unknown>", "source": raw_content}])

    lines = raw_content.splitlines(keepends=True)
    total_lines = len(lines)

    nodes_for_chunking = []
    for idx, item in enumerate(items):
        start_line = max(1, item["line"])
        start_idx = start_line - 1
        
        if idx < len(items) - 1:
            end_line = max(1, items[idx + 1]["line"])
            end_idx = end_line - 1
        else:
            end_idx = total_lines

        snippet = "".join(lines[start_idx:end_idx])
        nodes_for_chunking.append({
            "name": item["name"],
            "source": snippet
        })

    return chunk_nodes(nodes_for_chunking)
