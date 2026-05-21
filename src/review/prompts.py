"""Prompt templates for structured LLM code review."""

from __future__ import annotations

import json

from src.models.schemas import CodeChunk

SYSTEM_PROMPT = """You are an expert code reviewer. Analyze the provided source code chunk and return ONLY valid JSON.

Rules:
1. Only flag issues you can point to in the given code — do not invent files, APIs, or behavior not shown.
2. Each comment must reference real line numbers within the chunk (line_start relative to the file).
3. Assign confidence 0-100: how certain you are this is a real issue (not stylistic preference).
   - 80-100: clear bug, security flaw, or definite anti-pattern visible in code
   - 60-79: likely issue but context might change the assessment
   - 0-59: possible issue, needs human verification — use sparingly
4. If the code looks fine, return {"comments": []}.
5. Maximum 5 comments per chunk. Prefer quality over quantity.

Output schema (JSON only, no markdown):
{
  "comments": [
    {
      "line_start": <int>,
      "line_end": <int or null>,
      "symbol_name": "<str or null>",
      "severity": "critical|high|medium|low|info",
      "category": "bug|security|performance|style|maintainability|best_practice",
      "message": "<clear description>",
      "suggestion": "<optional fix>",
      "confidence": <0-100>
    }
  ]
}"""


def build_review_prompt(chunk: CodeChunk) -> str:
    meta = {
        "file_path": chunk.file_path,
        "language": chunk.language,
        "symbol_name": chunk.symbol_name,
        "symbol_type": chunk.symbol_type,
        "line_start": chunk.line_start,
        "line_end": chunk.line_end,
        "imports": chunk.imports[:15],
    }
    return f"""Review this code chunk.

Metadata:
{json.dumps(meta, indent=2)}

Source (lines {chunk.line_start}-{chunk.line_end}):
```
{chunk.source}
```

Return JSON only."""


REVIEW_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "comments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "line_start": {"type": "integer"},
                    "line_end": {"type": ["integer", "null"]},
                    "symbol_name": {"type": ["string", "null"]},
                    "severity": {"type": "string"},
                    "category": {"type": "string"},
                    "message": {"type": "string"},
                    "suggestion": {"type": ["string", "null"]},
                    "confidence": {"type": "integer"},
                },
                "required": ["line_start", "severity", "category", "message", "confidence"],
            },
        }
    },
    "required": ["comments"],
}
