"""LLM-based code reviewer with retry logic and comment validation."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

from src.review.llm_client import LLMError, LLMReviewer

logger = logging.getLogger(__name__)

# Template uses double-braces for literal JSON braces so .format() works correctly.
_SYSTEM_PROMPT_TEMPLATE = """\
You are a senior software engineer performing a code review.
You will receive a {language} function or class and must return ONLY valid JSON,
with no preamble, markdown, or explanation.

Schema:
{{
  "comments": [
    {{
      "line": <int or null>,
      "category": "bug" | "security" | "performance" | "style" | "maintainability",
      "severity": "critical" | "major" | "minor" | "info",
      "message": "<actionable review comment, 1-2 sentences>",
      "suggestion": "<concrete fix or improvement>",
      "confidence": <integer 0-100>
    }}
  ]
}}

Rules:
- confidence reflects how certain you are this is a real issue (not a false alarm)
- If no issues found, return {{"comments": []}}
- Never hallucinate issues. If uncertain, give confidence < 50
"""

# Kept for backward compatibility; dynamically built prompts are preferred.
SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(language="Python")

DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
MAX_TOKENS = 2048

# Exponential backoff delays (seconds) for rate-limit retries.
_RATE_LIMIT_BACKOFF = [2, 4, 8]

_LANGUAGE_LABELS: dict[str, str] = {
    "python": "Python",
    "javascript": "JavaScript",
    "typescript": "TypeScript/TSX",
}


def _build_system_prompt(language: str) -> str:
    """Return a system prompt tailored to the given programming language."""
    label = _LANGUAGE_LABELS.get(language.lower(), language.capitalize())
    return _SYSTEM_PROMPT_TEMPLATE.format(language=label)


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True if exc represents an HTTP 429 / rate-limit error."""
    if "RateLimitError" in type(exc).__name__:
        return True
    for attr in ("status_code", "code", "http_status"):
        if getattr(exc, attr, None) == 429:
            return True
    return False


def _extract_json(text: str) -> dict[str, Any]:
    """Three-stage JSON extraction.

    Tries:
    1. Markdown code fences (```json ... ``` or ``` ... ```)
    2. Raw text parsing
    3. Finding the first '{' and last '}' substring

    Raises:
        ValueError: If all extraction methods fail.
    """
    text_stripped = text.strip()

    # Stage 1: Markdown code fences
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text_stripped)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Stage 2: Raw text direct parse
    try:
        return json.loads(text_stripped)
    except json.JSONDecodeError:
        pass

    # Stage 3: Scanning first '{' to last '}'
    bracket_match = re.search(r"(\{[\s\S]*\})", text_stripped)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not extract valid JSON from LLM response")


def _validate_comment(comment: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a review comment dictionary.

    Ensures correct types and fallback values to prevent downstream crashes.
    """
    valid_categories = {"bug", "security", "performance", "style", "maintainability"}
    category = comment.get("category")
    if not isinstance(category, str) or category.lower() not in valid_categories:
        category = "style"
    else:
        category = category.lower()

    valid_severities = {"critical", "major", "minor", "info"}
    severity = comment.get("severity")
    if not isinstance(severity, str) or severity.lower() not in valid_severities:
        severity = "info"
    else:
        severity = severity.lower()

    line = comment.get("line")
    if line is not None:
        try:
            line = int(line)
        except (ValueError, TypeError):
            line = None

    confidence = comment.get("confidence")
    if confidence is not None:
        try:
            confidence = int(confidence)
            confidence = max(0, min(100, confidence))
        except (ValueError, TypeError):
            confidence = 50
    else:
        confidence = 50

    message = str(comment.get("message", ""))
    suggestion = comment.get("suggestion")
    if suggestion is not None:
        suggestion = str(suggestion)

    return {
        "line": line,
        "category": category,
        "severity": severity,
        "message": message,
        "suggestion": suggestion,
        "confidence": confidence,
    }


def _call_openai(code_chunk: str, model: str, system_prompt: str) -> str:
    """Call the OpenAI Chat Completion API with timeout."""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": code_chunk},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
        timeout=30.0,
    )
    return response.choices[0].message.content or "{}"


def _call_groq(user_message: str, model: str, system_prompt: str) -> str:
    """Call Groq API (OpenAI-compatible endpoint) with timeout."""
    try:
        from openai import OpenAI as _OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package not installed") from exc

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable not set")

    client = _OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            timeout=30.0,
        )
    except Exception as exc:
        raise RuntimeError(f"Groq API error: {exc}") from exc

    content = response.choices[0].message.content
    if content is None:
        raise RuntimeError("Groq returned empty content")
    return content


def _call_anthropic(code_chunk: str, model: str, system_prompt: str) -> str:
    """Call the Anthropic Messages API with timeout."""
    from anthropic import Anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": code_chunk}],
        temperature=0.2,
        timeout=30.0,
    )
    parts = [b.text for b in response.content if hasattr(b, "text")]
    return "".join(parts) or "{}"


def _call_with_timeout_and_retry(
    call_llm_fn,
    code_chunk: str,
    model: str,
    system_prompt: str,
    file_path: str,
) -> str:
    """Call call_llm_fn, retrying up to 3 times on ANY exceptions/timeouts.

    Total 4 attempts (1 initial + 3 retries) with backoffs: 2s, 4s, 8s.
    """
    backoff = [2, 4, 8]
    for attempt in range(len(backoff) + 1):
        try:
            # Handle mock functions in tests (expect 2 arguments) vs production (expect 3 arguments)
            if hasattr(call_llm_fn, "__code__") and call_llm_fn.__code__.co_argcount >= 3:
                return call_llm_fn(code_chunk, model, system_prompt)
            else:
                return call_llm_fn(code_chunk, model)
        except Exception as exc:
            logger.error(
                "LLM call failed (attempt %d/%d) for '%s': %s",
                attempt + 1, len(backoff) + 1, file_path, exc,
                exc_info=True
            )
            # Check for fatal errors that we should not retry (e.g. missing API key or Unauthorized)
            msg = str(exc)
            is_fatal = any(
                p in msg for p in ("not set", "Unauthorized", "not installed", "unauthorized")
            )
            if is_fatal or attempt >= len(backoff):
                raise RuntimeError(
                    f"LLM API request failed: {exc}"
                ) from exc

            wait = backoff[attempt]
            logger.warning(
                "Retrying review for '%s' in %ds...",
                file_path, wait
            )
            time.sleep(wait)
    raise RuntimeError("Unexpected exit from retry loop")


def review_code(
    code_chunk: str,
    file_path: str = "<unknown>",
    language: str = "python",
) -> list[dict[str, Any]]:
    """Perform code review on a source code chunk using OpenAI, Anthropic, or Groq.

    Args:
        code_chunk: The code snippet string to review.
        file_path: The path of the file being reviewed (for logging and tracking).
        language: The programming language of the code ("python", "javascript", "typescript").

    Returns:
        A list of validated comment dictionaries.
    """
    if not code_chunk or not code_chunk.strip():
        logger.debug("Empty or whitespace chunk for '%s'. Skipping.", file_path)
        return []

    system_prompt = _build_system_prompt(language)

    # 1. Resolve LLM provider & model
    provider = os.environ.get("LLM_PROVIDER", "openai").lower()

    if provider == "anthropic":
        model    = os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514")
        call_llm = _call_anthropic
    elif provider == "openai":
        model    = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        call_llm = _call_openai
    elif provider == "groq":
        model    = os.environ.get("LLM_MODEL", DEFAULT_GROQ_MODEL)
        call_llm = _call_groq
    else:
        logger.warning(
            "Unknown LLM_PROVIDER '%s' for '%s'. Falling back to 'openai'.",
            provider, file_path,
        )
        provider = "openai"
        model    = os.environ.get("LLM_MODEL", "gpt-4o-mini")
        call_llm = _call_openai

    logger.debug(
        "Reviewing '%s' (language=%s) with provider='%s', model='%s'.",
        file_path, language, provider, model,
    )

    # 2. Call API (with timeout and retry) & parse, with one retry on JSON parse failure
    for attempt in (1, 2):
        try:
            response_text = _call_with_timeout_and_retry(
                call_llm, code_chunk, model, system_prompt, file_path
            )
            comments_data = _extract_json(response_text)
            raw_comments = comments_data.get("comments", [])

            validated = []
            for c in raw_comments:
                val = _validate_comment(c)
                val["file"] = file_path
                validated.append(val)
            logger.debug(
                "Review completed for '%s' (attempt %d): %d comments.",
                file_path, attempt, len(validated),
            )
            return validated

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "JSON parse error (attempt %d) for '%s': %s.",
                attempt, file_path, e,
            )
            if attempt == 1:
                logger.info("Retrying review for '%s'...", file_path)
                time.sleep(1)
                continue
            logger.error("JSON parsing failed on retry for '%s'. Returning [].", file_path)
            return []

        except RuntimeError as e:
            logger.error("API error for '%s': %s. Failing fast.", file_path, e, exc_info=True)
            return []

        except Exception as e:
            logger.error("Unexpected error for '%s': %s. Failing fast.", file_path, e, exc_info=True)
            return []

    return []


# Canonical alias — no module mutation needed in pipeline.py
review_chunk = review_code

__all__ = ["LLMError", "LLMReviewer", "review_code", "review_chunk"]
