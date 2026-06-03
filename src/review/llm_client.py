"""LLM client for OpenAI and Anthropic with structured JSON output."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from src.models.schemas import Category, CodeChunk, ReviewComment, Severity
from src.review.prompts import SYSTEM_PROMPT, build_review_prompt

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())
        raise


def _parse_comments(raw: dict, chunk: CodeChunk) -> list[ReviewComment]:
    comments: list[ReviewComment] = []
    for item in raw.get("comments", []):
        try:
            line_start = int(item.get("line_start", chunk.line_start))
            line_end = item.get("line_end")
            if line_end is not None:
                line_end = int(line_end)
            if line_start < chunk.line_start:
                line_start = chunk.line_start
            if line_start > chunk.line_end:
                line_start = chunk.line_start

            comments.append(
                ReviewComment(
                    file_path=chunk.file_path,
                    line_start=line_start,
                    line_end=line_end or line_start,
                    symbol_name=item.get("symbol_name") or chunk.symbol_name,
                    severity=Severity(item["severity"].lower()),
                    category=Category(item["category"].lower()),
                    message=item["message"],
                    suggestion=item.get("suggestion"),
                    confidence=max(0, min(100, int(item["confidence"]))),
                )
            )
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Skipping malformed comment: %s — %s", item, e)
    return comments


class LLMReviewer:
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        if self.provider == "openai":
            self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        else:
            self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    def review_chunk(self, chunk: CodeChunk) -> list[ReviewComment]:
        prompt = build_review_prompt(chunk)
        if self.provider == "anthropic":
            text = self._call_anthropic(prompt)
        else:
            text = self._call_openai(prompt)
        data = _extract_json(text)
        return _parse_comments(data, chunk)

    def _call_openai(self, user_prompt: str) -> str:
        try:
            from openai import OpenAI
        except ImportError as e:
            raise LLMError("openai package not installed") from e

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMError("OPENAI_API_KEY not set")

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
            timeout=30.0,
        )
        return response.choices[0].message.content or "{}"

    def _call_anthropic(self, user_prompt: str) -> str:
        try:
            from anthropic import Anthropic
        except ImportError as e:
            raise LLMError("anthropic package not installed") from e

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY not set")

        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=SYSTEM_PROMPT + "\nRespond with JSON only.",
            messages=[{"role": "user", "content": user_prompt}],
            temperature=0.2,
            timeout=30.0,
        )
        parts = [b.text for b in response.content if hasattr(b, "text")]
        return "".join(parts) or "{}"
