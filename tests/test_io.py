import json
from pathlib import Path

import pytest

from scout.io import (
    write_markdown_with_frontmatter,
    read_markdown_with_frontmatter,
    append_fetch_log,
    verify_quotes,
)


def test_write_and_read_frontmatter(tmp_path):
    fm = {"icp": "RevOps at 50-300 B2B SaaS", "score": 18.3}
    body = "# Heading\n\nSome content.\n"
    path = tmp_path / "out.md"

    write_markdown_with_frontmatter(path, fm, body)

    read_fm, read_body = read_markdown_with_frontmatter(path)
    assert read_fm == fm
    assert read_body.strip() == body.strip()


def test_append_fetch_log_writes_jsonl(tmp_path):
    log_path = tmp_path / "fetch.jsonl"

    append_fetch_log(log_path, {"url": "https://reddit.com/r/x/1", "text": "hello"})
    append_fetch_log(log_path, {"url": "https://reddit.com/r/x/2", "text": "world"})

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["url"] == "https://reddit.com/r/x/1"
    assert json.loads(lines[1])["text"] == "world"


def test_verify_quotes_passes_when_substring_found(tmp_path):
    log_path = tmp_path / "fetch.jsonl"
    append_fetch_log(log_path, {"url": "https://x.com/1", "text": "Lead routing is killing me, I'd pay anything to fix it."})

    quotes = ["lead routing is killing me", "I'd pay anything"]
    verified, dropped = verify_quotes(log_path, quotes)

    assert verified == ["lead routing is killing me", "I'd pay anything"]
    assert dropped == []


def test_verify_quotes_drops_fabricated(tmp_path):
    log_path = tmp_path / "fetch.jsonl"
    append_fetch_log(log_path, {"url": "https://x.com/1", "text": "Lead routing is killing me."})

    quotes = ["lead routing is killing me", "this quote was never said"]
    verified, dropped = verify_quotes(log_path, quotes)

    assert verified == ["lead routing is killing me"]
    assert dropped == ["this quote was never said"]


def test_verify_quotes_normalizes_whitespace_and_case(tmp_path):
    log_path = tmp_path / "fetch.jsonl"
    append_fetch_log(log_path, {"url": "https://x.com/1", "text": "Lead    routing\nis killing me."})

    quotes = ["lead routing is killing me"]
    verified, dropped = verify_quotes(log_path, quotes)

    assert verified == quotes
    assert dropped == []
