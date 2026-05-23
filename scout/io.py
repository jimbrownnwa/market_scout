"""Markdown I/O, fetch logs, and quote verification for Market Scout."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


def write_markdown_with_frontmatter(path: Path, frontmatter: dict[str, Any], body: str) -> None:
    """Write a markdown file with YAML frontmatter at the top."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_yaml = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True).strip()
    content = f"---\n{fm_yaml}\n---\n\n{body.rstrip()}\n"
    path.write_text(content, encoding="utf-8")


def read_markdown_with_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Read a markdown file with YAML frontmatter; return (frontmatter, body)."""
    text = Path(path).read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    fm_text = text[4:end]
    body = text[end + 5 :]
    frontmatter = yaml.safe_load(fm_text) or {}
    return frontmatter, body


def append_fetch_log(path: Path, entry: dict[str, Any]) -> None:
    """Append one JSON line to a fetch log."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def verify_quotes(log_path: Path, quotes: list[str]) -> tuple[list[str], list[str]]:
    """Return (verified, dropped) — quotes that appear in any logged response vs. those that don't."""
    log_path = Path(log_path)
    if not log_path.exists():
        return [], list(quotes)

    haystack_parts: list[str] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        text = entry.get("text", "")
        if text:
            haystack_parts.append(_normalize(text))
    haystack = " ".join(haystack_parts)

    verified: list[str] = []
    dropped: list[str] = []
    for q in quotes:
        if _normalize(q) in haystack:
            verified.append(q)
        else:
            dropped.append(q)
    return verified, dropped
