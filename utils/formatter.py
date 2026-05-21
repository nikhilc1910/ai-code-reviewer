"""Output formatting helpers for review comments."""

import json
from typing import Any


def comments_to_json(comments: list[dict[str, Any]]) -> str:
    """Format a list of review comment dictionaries into a formatted JSON string."""
    return json.dumps(comments, indent=2)


def comments_to_markdown(comments: list[dict[str, Any]]) -> str:
    """Format a list of review comment dictionaries into a beautiful, production-grade Markdown report.
    
    Includes severity, file, line, issue/message, suggestion, and confidence.
    """
    if not comments:
        return "# Code Review Report\n\nNo issues were found. Great job! 🎉"

    # Header and Summary Statistics
    total_comments = len(comments)
    severity_counts: dict[str, int] = {}
    for c in comments:
        sev = str(c.get("severity", "info")).lower()
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

    lines = [
        "# Code Review Report",
        "",
        "## Summary Metrics",
        f"- **Total Findings**: {total_comments}",
    ]
    
    # Sort severities consistently: critical, major, minor, info
    severity_order = ["critical", "major", "minor", "info"]
    severity_emojis = {
        "critical": "🔴 Critical",
        "major": "orange 🟠 Major",
        "minor": "yellow 🟡 Minor",
        "info": "blue 🔵 Info"
    }

    # Normalize emojis for display
    display_emojis = {
        "critical": "🔴 Critical",
        "major": "🟠 Major",
        "minor": "🟡 Minor",
        "info": "🔵 Info"
    }

    for sev in severity_order:
        if sev in severity_counts:
            lines.append(f"- **{display_emojis[sev]}**: {severity_counts[sev]}")

    lines.append("")
    lines.append("## Detailed Findings")
    lines.append("")

    for idx, c in enumerate(comments, 1):
        sev_raw = str(c.get("severity", "info")).lower()
        sev_label = display_emojis.get(sev_raw, f"⚪ {sev_raw.upper()}")
        
        file = c.get("file") or c.get("file_path") or "<unknown_file>"
        line = c.get("line") or c.get("line_start") or "N/A"
        confidence = c.get("confidence")
        if confidence is not None:
            confidence_str = f"{confidence}%"
        else:
            confidence_str = "N/A"

        issue = c.get("message") or c.get("issue") or "No description provided."
        suggestion = c.get("suggestion")

        lines.extend([
            f"### {idx}. [{sev_label}] in `{file}` at line {line}",
            f"- **Confidence**: {confidence_str}",
            f"- **Issue**: {issue}",
        ])

        if suggestion:
            lines.append("- **Recommended Fix**:")
            suggestion_str = str(suggestion).strip()
            # If it's already fenced, indent it nicely or just add it
            if suggestion_str.startswith("```"):
                lines.append(suggestion_str)
            else:
                lines.append(f"  ```python\n  {suggestion_str}\n  ```")

        lines.append("")  # Blank line separator

    return "\n".join(lines)
