# Market Scout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working two-stage market research agent (Claude Code project) with `/scan` ranking top 25 B2B ICPs against Hormozi's four criteria and `/deep-dive` producing analyst-quality reports with verified customer quotes.

**Architecture:** Hybrid harness — Claude Code slash commands orchestrate; a Python package (`scout/`) handles deterministic work (config loading, scoring math, source fetches that need libraries, markdown I/O, quote verification). Perplexity + Firecrawl are reached via existing MCPs; Reddit + Google Trends via Python (PRAW, pytrends). Data flows as JSON between subcommands; final outputs are dated markdown files under `runs/`.

**Tech Stack:** Python 3.11+, uv (package manager), PyYAML, PRAW, pytrends, pytest. Claude Code slash commands. Markdown + YAML for outputs/config.

**Spec:** `docs/superpowers/specs/2026-05-23-market-scout-design.md`

---

## File Structure (locks in decomposition)

```
Market Scout/
├── .claude/
│   ├── commands/
│   │   ├── scan.md                 # /scan orchestrator (Task 10)
│   │   └── deep-dive.md            # /deep-dive orchestrator (Task 11)
│   └── settings.local.json         # Task 1
├── scout/
│   ├── __init__.py                 # Task 1
│   ├── __main__.py                 # Task 9 — dispatches to cli.main()
│   ├── cli.py                      # Task 9 — argparse subcommands
│   ├── io.py                       # Task 4 — frontmatter, fetch log, verify
│   ├── filters.py                  # Task 5 — exclusion checks
│   ├── scoring.py                  # Task 6 — rubric, composite, floors
│   └── sources/
│       ├── __init__.py             # Task 1
│       ├── reddit.py               # Task 7 — PRAW adapter
│       └── trends.py               # Task 8 — pytrends adapter
├── tests/
│   ├── __init__.py                 # Task 1
│   ├── test_io.py                  # Task 4
│   ├── test_filters.py             # Task 5
│   ├── test_scoring.py             # Task 6
│   ├── test_reddit.py              # Task 7
│   ├── test_trends.py              # Task 8
│   └── test_cli.py                 # Task 9
├── config/
│   ├── rubric.yaml                 # Task 3
│   ├── exclusions.yaml             # Task 3
│   └── seeds.yaml                  # Task 3
├── runs/
│   ├── scans/.gitkeep              # Task 2
│   └── deep-dives/.gitkeep         # Task 2
├── docs/superpowers/               # already exists
├── .env.example                    # Task 2
├── .gitignore                      # already exists
├── pyproject.toml                  # Task 1
└── README.md                       # Task 12
```

**One responsibility per file:**
- `io.py`: read/write markdown + frontmatter, manage fetch log, verify quotes
- `filters.py`: load exclusions, check whether an ICP is excluded
- `scoring.py`: load rubric, score sub-signals from evidence, compute composite, apply floors
- `sources/reddit.py`: PRAW calls only — no scoring logic
- `sources/trends.py`: pytrends calls only — no scoring logic
- `cli.py`: argparse dispatch; thin glue between subcommands and modules
- `.claude/commands/*.md`: orchestration prompts; chain bash + MCP calls

---

## Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `scout/__init__.py`, `scout/sources/__init__.py`, `tests/__init__.py`
- Create: `.claude/settings.local.json`

- [ ] **Step 1: Write `pyproject.toml`**

Create `pyproject.toml`:

```toml
[project]
name = "market-scout"
version = "0.1.0"
description = "Personal market research agent — Hormozi four-criteria scan + deep-dive"
requires-python = ">=3.11"
dependencies = [
    "praw>=7.7.1",
    "pytrends>=4.9.2",
    "PyYAML>=6.0.1",
    "python-dotenv>=1.0.1",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["scout"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 2: Create package init files**

Create three empty files:
- `scout/__init__.py` — empty
- `scout/sources/__init__.py` — empty
- `tests/__init__.py` — empty

- [ ] **Step 3: Create `.claude/settings.local.json` permissions**

Create `.claude/settings.local.json`:

```json
{
  "permissions": {
    "allow": [
      "Bash(uv run python -m scout *)",
      "Bash(uv run pytest *)",
      "Bash(uv sync)",
      "Bash(uv add *)"
    ]
  }
}
```

- [ ] **Step 4: Install dependencies with uv**

Run from project root:
```powershell
uv sync --all-extras
```

Expected: creates `.venv/`, installs praw, pytrends, PyYAML, python-dotenv, pytest, pytest-mock.

- [ ] **Step 5: Verify install**

Run:
```powershell
uv run python -c "import praw, pytrends, yaml, dotenv; import pytest; print('ok')"
```

Expected output: `ok`

- [ ] **Step 6: Commit**

```powershell
git add pyproject.toml scout/ tests/ .claude/settings.local.json
git commit -m "Add project skeleton (pyproject, package init, permissions)"
```

---

## Task 2: Directory Scaffolding + .env.example

**Files:**
- Create: `runs/scans/.gitkeep`, `runs/deep-dives/.gitkeep`
- Create: `.env.example`

- [ ] **Step 1: Create runtime output dirs with .gitkeep**

Create empty files:
- `runs/scans/.gitkeep`
- `runs/deep-dives/.gitkeep`

(These ensure git tracks the empty dirs.)

- [ ] **Step 2: Create `.env.example`**

Create `.env.example`:

```
# Reddit API — register a "script" app at https://www.reddit.com/prefs/apps
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=market-scout/0.1 by u/your-handle

# Perplexity and Firecrawl run via existing Claude Code MCPs — no keys needed here.
```

- [ ] **Step 3: Commit**

```powershell
git add runs/ .env.example
git commit -m "Add runtime output dirs and .env.example"
```

---

## Task 3: YAML Configs

**Files:**
- Create: `config/rubric.yaml`, `config/exclusions.yaml`, `config/seeds.yaml`

- [ ] **Step 1: Write `config/rubric.yaml`**

Create `config/rubric.yaml`:

```yaml
# Sub-signals are scored 1, 2, 3, 4, or 5.
# Anchors shown below describe what 1, 3, and 5 look like.
# 2 and 4 are "between" cases. Sub-signals lacking evidence are capped at 2.

pain:
  signals:
    complaint_volume:
      1: "<5 threads in last 90 days"
      3: "20-50 threads"
      5: "100+ threads"
    emotional_intensity:
      1: "mild annoyance"
      3: "frustrated, repeated"
      5: "'I hate this', 'killing me', 'desperate'"
    willingness_signals:
      1: "none found"
      3: "2-3 instances of 'I would pay' / 'shut up and take my money' / 'we hired X'"
      5: "6+ instances across sources"
    recency:
      1: "complaints peaked >2y ago"
      3: "steady over 12mo"
      5: "accelerating in last 6mo"

purchasing_power:
  signals:
    avg_deal_size:
      1: "<$5K/yr typical spend in adjacent services"
      3: "$25-100K/yr"
      5: "$250K+/yr"
    budget_authority:
      1: "needs 3+ approvals"
      3: "department head decides"
      5: "ICP holds the budget directly"
    funded_or_profitable:
      1: "mostly struggling / pre-revenue"
      3: "mixed cohort"
      5: "well-funded or profitable cohort"

easy_to_target:
  signals:
    concentrated_channels:
      1: "diffuse, no clear watering holes"
      3: "2-3 channels reach most of ICP"
      5: "1-2 channels reach 70%+ of ICP"
    identifiable_titles:
      1: "fuzzy / many title variants"
      3: "moderately clean"
      5: "single canonical title (e.g., 'Head of RevOps')"
    community_density:
      1: "no active communities"
      3: "a few"
      5: "vibrant, frequent posts, active Slack/Discord"

growing:
  signals:
    trends_curve:
      1: "declining (pytrends)"
      3: "flat"
      5: "up >50% in 24mo"
    funding_momentum:
      1: "no rounds in 18mo"
      3: "occasional"
      5: "multiple rounds, increasing size"
    structural_tailwind:
      1: "none"
      3: "one (regulation / tech shift / demographic)"
      5: "two or more"

weights:
  pain: 1.0
  purchasing_power: 1.0
  easy_to_target: 1.0
  growing: 1.0

hard_floors:
  purchasing_power: 1
  pain: 2
```

- [ ] **Step 2: Write `config/exclusions.yaml`**

Create `config/exclusions.yaml`:

```yaml
categories:
  - "AI automation agencies / consultancies"
  - "Workflow automation tools (n8n, Make, Zapier consulting)"
  - "Legal services / law firms"
  - "Medical practices / clinical care"
  - "Financial advisory / wealth management"
  - "Tax preparation / CPAs"
  - "Insurance brokerage"

buyer_profiles:
  - "Solopreneurs without recurring revenue"
  - "Pre-revenue founders"
  - "Course creators with <$10K MRR"
  - "Personal coaches / freelance creatives without retainers"
  - "Bootstrapped indie hackers pre-product-market-fit"

soft_penalties:
  - "Crypto/Web3 native businesses"
  - "Cannabis"
```

- [ ] **Step 3: Write `config/seeds.yaml`**

Create `config/seeds.yaml`:

```yaml
# Optional. Categories listed here are pinned to be considered every /scan.
# Empty list = pure free-brainstorm each run.
pinned_categories: []
```

- [ ] **Step 4: Commit**

```powershell
git add config/
git commit -m "Add rubric, exclusions, and seeds YAML configs"
```

---

## Task 4: `scout/io.py` — Markdown I/O + Quote Verification

**Files:**
- Create: `scout/io.py`
- Create: `tests/test_io.py`

- [ ] **Step 1: Write failing tests in `tests/test_io.py`**

```python
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
```

- [ ] **Step 2: Run tests, verify failure**

Run:
```powershell
uv run pytest tests/test_io.py -v
```

Expected: ImportError or ModuleNotFoundError — `scout.io` doesn't exist yet.

- [ ] **Step 3: Implement `scout/io.py`**

Create `scout/io.py`:

```python
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
```

- [ ] **Step 4: Run tests, verify pass**

Run:
```powershell
uv run pytest tests/test_io.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```powershell
git add scout/io.py tests/test_io.py
git commit -m "Add scout.io: frontmatter, fetch log, quote verification"
```

---

## Task 5: `scout/filters.py` — Exclusion Checks

**Files:**
- Create: `scout/filters.py`
- Create: `tests/test_filters.py`

- [ ] **Step 1: Write failing tests in `tests/test_filters.py`**

```python
from pathlib import Path

import pytest
import yaml

from scout.filters import (
    load_exclusions,
    is_excluded,
    soft_penalty_score,
)


@pytest.fixture
def exclusions(tmp_path):
    data = {
        "categories": [
            "AI automation agencies / consultancies",
            "Legal services / law firms",
        ],
        "buyer_profiles": [
            "Solopreneurs without recurring revenue",
            "Pre-revenue founders",
        ],
        "soft_penalties": [
            "Crypto/Web3 native businesses",
            "Cannabis",
        ],
    }
    path = tmp_path / "exclusions.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return load_exclusions(path)


def test_load_exclusions_returns_three_lists(exclusions):
    assert len(exclusions["categories"]) == 2
    assert len(exclusions["buyer_profiles"]) == 2
    assert len(exclusions["soft_penalties"]) == 2


def test_is_excluded_blocks_category_match(exclusions):
    excluded, reason = is_excluded("Founders of AI automation agencies serving SMBs", exclusions)
    assert excluded is True
    assert "AI automation" in reason


def test_is_excluded_blocks_buyer_profile_match(exclusions):
    excluded, reason = is_excluded("Solopreneurs without recurring revenue, building courses", exclusions)
    assert excluded is True
    assert "Solopreneur" in reason or "solopreneur" in reason.lower()


def test_is_excluded_allows_unrelated_icp(exclusions):
    excluded, reason = is_excluded("RevOps leaders at 50-300 person B2B SaaS", exclusions)
    assert excluded is False
    assert reason == ""


def test_soft_penalty_score_returns_one_when_match(exclusions):
    assert soft_penalty_score("Crypto/Web3 trading desks at small hedge funds", exclusions) == 1


def test_soft_penalty_score_returns_zero_when_no_match(exclusions):
    assert soft_penalty_score("RevOps leaders at 50-300 person B2B SaaS", exclusions) == 0
```

- [ ] **Step 2: Run tests, verify failure**

```powershell
uv run pytest tests/test_filters.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `scout/filters.py`**

```python
"""Exclusion filtering for ICP candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_exclusions(path: Path | str) -> dict[str, list[str]]:
    """Load exclusions YAML. Returns dict with keys: categories, buyer_profiles, soft_penalties."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {
        "categories": data.get("categories", []) or [],
        "buyer_profiles": data.get("buyer_profiles", []) or [],
        "soft_penalties": data.get("soft_penalties", []) or [],
    }


def _matches_any(text: str, patterns: list[str]) -> str | None:
    text_l = text.lower()
    for pat in patterns:
        # Use the first 2-3 meaningful words of each pattern as the match key
        key = " ".join(pat.lower().replace("/", " ").split()[:2])
        if key and key in text_l:
            return pat
    return None


def is_excluded(icp_description: str, exclusions: dict[str, list[str]]) -> tuple[bool, str]:
    """Return (excluded?, reason). Reason names the matched exclusion."""
    matched = _matches_any(icp_description, exclusions.get("categories", []))
    if matched:
        return True, f"category match: {matched}"
    matched = _matches_any(icp_description, exclusions.get("buyer_profiles", []))
    if matched:
        return True, f"buyer profile match: {matched}"
    return False, ""


def soft_penalty_score(icp_description: str, exclusions: dict[str, list[str]]) -> int:
    """Return the number of soft penalties matched (used as a 1-point reduction on easy_to_target)."""
    matched = _matches_any(icp_description, exclusions.get("soft_penalties", []))
    return 1 if matched else 0
```

- [ ] **Step 4: Run tests, verify pass**

```powershell
uv run pytest tests/test_filters.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```powershell
git add scout/filters.py tests/test_filters.py
git commit -m "Add scout.filters: hard exclusions and soft penalty detection"
```

---

## Task 6: `scout/scoring.py` — Rubric Scoring + Composite

**Files:**
- Create: `scout/scoring.py`
- Create: `tests/test_scoring.py`

- [ ] **Step 1: Write failing tests in `tests/test_scoring.py`**

```python
from pathlib import Path

import pytest

from scout.scoring import (
    load_rubric,
    score_signal,
    score_criterion,
    score_candidate,
)


RUBRIC_PATH = Path(__file__).parent.parent / "config" / "rubric.yaml"


@pytest.fixture
def rubric():
    return load_rubric(RUBRIC_PATH)


def test_load_rubric_has_all_four_criteria(rubric):
    assert set(rubric["criteria"].keys()) == {"pain", "purchasing_power", "easy_to_target", "growing"}
    assert rubric["weights"]["pain"] == 1.0
    assert rubric["hard_floors"]["purchasing_power"] == 1


def test_score_signal_caps_at_2_when_no_evidence(rubric):
    # No evidence given -> capped at 2 regardless of declared score
    score = score_signal(declared=5, evidence="")
    assert score == 2


def test_score_signal_uses_declared_when_evidence_present(rubric):
    score = score_signal(declared=4, evidence="47 threads on r/revops in last 90d")
    assert score == 4


def test_score_signal_clamps_to_1_5(rubric):
    assert score_signal(declared=0, evidence="any") == 1
    assert score_signal(declared=7, evidence="any") == 5


def test_score_criterion_averages_subsignals(rubric):
    sub_signals = {
        "complaint_volume": {"score": 5, "evidence": "found 100+ threads"},
        "emotional_intensity": {"score": 4, "evidence": "many 'I hate this' posts"},
        "willingness_signals": {"score": 5, "evidence": "8 'I'd pay anything' instances"},
        "recency": {"score": 4, "evidence": "uptrend last 6mo"},
    }
    crit_score = score_criterion("pain", sub_signals, rubric)
    assert crit_score == pytest.approx((5 + 4 + 5 + 4) / 4)


def test_score_candidate_computes_composite_with_default_weights(rubric):
    candidate = {
        "icp": "RevOps leaders at 50-300 person B2B SaaS",
        "criteria": {
            "pain": {
                "complaint_volume": {"score": 5, "evidence": "x"},
                "emotional_intensity": {"score": 5, "evidence": "x"},
                "willingness_signals": {"score": 5, "evidence": "x"},
                "recency": {"score": 5, "evidence": "x"},
            },
            "purchasing_power": {
                "avg_deal_size": {"score": 4, "evidence": "x"},
                "budget_authority": {"score": 4, "evidence": "x"},
                "funded_or_profitable": {"score": 4, "evidence": "x"},
            },
            "easy_to_target": {
                "concentrated_channels": {"score": 5, "evidence": "x"},
                "identifiable_titles": {"score": 5, "evidence": "x"},
                "community_density": {"score": 5, "evidence": "x"},
            },
            "growing": {
                "trends_curve": {"score": 4, "evidence": "x"},
                "funding_momentum": {"score": 4, "evidence": "x"},
                "structural_tailwind": {"score": 4, "evidence": "x"},
            },
        },
    }
    result = score_candidate(candidate, rubric)
    # pain=5, power=4, target=5, growing=4 -> 18 (max 20 with all-1.0 weights)
    assert result["composite"] == pytest.approx(18.0)
    assert result["criterion_scores"]["pain"] == pytest.approx(5.0)
    assert result["cut"] is False


def test_hard_floor_cuts_candidate(rubric):
    # purchasing_power averages to 1.0 -> hits hard floor
    candidate = {
        "icp": "Broke solopreneurs",
        "criteria": {
            "pain": {
                "complaint_volume": {"score": 5, "evidence": "x"},
                "emotional_intensity": {"score": 5, "evidence": "x"},
                "willingness_signals": {"score": 5, "evidence": "x"},
                "recency": {"score": 5, "evidence": "x"},
            },
            "purchasing_power": {
                "avg_deal_size": {"score": 1, "evidence": "x"},
                "budget_authority": {"score": 1, "evidence": "x"},
                "funded_or_profitable": {"score": 1, "evidence": "x"},
            },
            "easy_to_target": {
                "concentrated_channels": {"score": 3, "evidence": "x"},
                "identifiable_titles": {"score": 3, "evidence": "x"},
                "community_density": {"score": 3, "evidence": "x"},
            },
            "growing": {
                "trends_curve": {"score": 3, "evidence": "x"},
                "funding_momentum": {"score": 3, "evidence": "x"},
                "structural_tailwind": {"score": 3, "evidence": "x"},
            },
        },
    }
    result = score_candidate(candidate, rubric)
    assert result["cut"] is True
    assert "purchasing_power" in result["cut_reason"]


def test_soft_penalty_reduces_easy_to_target(rubric):
    candidate = {
        "icp": "Crypto/Web3 trading desks",
        "soft_penalty": 1,
        "criteria": {
            "pain": {k: {"score": 3, "evidence": "x"} for k in ["complaint_volume", "emotional_intensity", "willingness_signals", "recency"]},
            "purchasing_power": {k: {"score": 3, "evidence": "x"} for k in ["avg_deal_size", "budget_authority", "funded_or_profitable"]},
            "easy_to_target": {k: {"score": 4, "evidence": "x"} for k in ["concentrated_channels", "identifiable_titles", "community_density"]},
            "growing": {k: {"score": 3, "evidence": "x"} for k in ["trends_curve", "funding_momentum", "structural_tailwind"]},
        },
    }
    result = score_candidate(candidate, rubric)
    # easy_to_target raw avg = 4, soft penalty -1 = 3
    assert result["criterion_scores"]["easy_to_target"] == pytest.approx(3.0)
```

- [ ] **Step 2: Run tests, verify failure**

```powershell
uv run pytest tests/test_scoring.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `scout/scoring.py`**

```python
"""Rubric loading, sub-signal scoring, and composite computation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_rubric(path: Path | str) -> dict[str, Any]:
    """Load rubric YAML and return a structured dict."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {
        "criteria": {
            name: raw.get(name, {}).get("signals", {})
            for name in ("pain", "purchasing_power", "easy_to_target", "growing")
        },
        "weights": raw.get("weights", {"pain": 1.0, "purchasing_power": 1.0, "easy_to_target": 1.0, "growing": 1.0}),
        "hard_floors": raw.get("hard_floors", {}),
    }


def score_signal(declared: int, evidence: str) -> int:
    """Cap at 2 if no evidence; clamp to [1, 5]."""
    score = max(1, min(5, int(declared)))
    if not evidence or not evidence.strip():
        score = min(score, 2)
    return score


def score_criterion(name: str, sub_signals: dict[str, dict[str, Any]], rubric: dict[str, Any]) -> float:
    """Average all sub-signal scores for a criterion."""
    expected_signals = rubric["criteria"].get(name, {})
    scores: list[int] = []
    for sig_name in expected_signals:
        sig = sub_signals.get(sig_name, {})
        scores.append(score_signal(sig.get("score", 0), sig.get("evidence", "")))
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def score_candidate(candidate: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    """Compute criterion scores, composite, hard floor cuts, and soft penalty.

    Input candidate dict: {icp, soft_penalty (0 or 1), criteria: {name: {sub_signal: {score, evidence}}}}
    Returns: {icp, criterion_scores, composite, cut, cut_reason}
    """
    criterion_scores: dict[str, float] = {}
    for crit_name in ("pain", "purchasing_power", "easy_to_target", "growing"):
        sub = candidate.get("criteria", {}).get(crit_name, {})
        criterion_scores[crit_name] = score_criterion(crit_name, sub, rubric)

    # Apply soft penalty: -1 on easy_to_target, floor 1
    penalty = int(candidate.get("soft_penalty", 0) or 0)
    if penalty:
        criterion_scores["easy_to_target"] = max(1.0, criterion_scores["easy_to_target"] - 1)

    # Hard floors
    cut = False
    cut_reason = ""
    for crit_name, floor in rubric.get("hard_floors", {}).items():
        if criterion_scores.get(crit_name, 0) <= floor:
            cut = True
            cut_reason = f"{crit_name} score {criterion_scores[crit_name]:.1f} <= floor {floor}"
            break

    # Composite (weighted sum)
    weights = rubric.get("weights", {})
    composite = sum(criterion_scores[c] * weights.get(c, 1.0) for c in criterion_scores)

    return {
        "icp": candidate.get("icp", ""),
        "criterion_scores": criterion_scores,
        "composite": round(composite, 2),
        "cut": cut,
        "cut_reason": cut_reason,
    }
```

- [ ] **Step 4: Run tests, verify pass**

```powershell
uv run pytest tests/test_scoring.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```powershell
git add scout/scoring.py tests/test_scoring.py
git commit -m "Add scout.scoring: sub-signals, criterion averages, composite, hard floors"
```

---

## Task 7: `scout/sources/reddit.py` — PRAW Adapter

**Files:**
- Create: `scout/sources/reddit.py`
- Create: `tests/test_reddit.py`

- [ ] **Step 1: Write failing tests with mocks in `tests/test_reddit.py`**

```python
from unittest.mock import MagicMock, patch

import pytest

from scout.sources.reddit import search_complaints, RedditSignal


def _fake_submission(title, selftext, score, url, subreddit, created_utc):
    sub = MagicMock()
    sub.title = title
    sub.selftext = selftext
    sub.score = score
    sub.url = url
    sub.subreddit = MagicMock()
    sub.subreddit.display_name = subreddit
    sub.created_utc = created_utc
    sub.id = url.split("/")[-1]
    return sub


@patch("scout.sources.reddit._get_reddit_client")
def test_search_complaints_returns_signal_summary(mock_client):
    fake_reddit = MagicMock()
    fake_reddit.subreddit.return_value.search.return_value = [
        _fake_submission("Lead routing is killing me", "We tried 3 tools...", 142, "https://reddit.com/r/revops/1", "revops", 1716_000_000),
        _fake_submission("I'd pay anything to fix attribution", "...", 89, "https://reddit.com/r/revops/2", "revops", 1716_100_000),
    ]
    mock_client.return_value = fake_reddit

    signal: RedditSignal = search_complaints(["revops"], keywords=["routing", "attribution"], limit=5)

    assert signal.thread_count == 2
    assert len(signal.threads) == 2
    assert signal.threads[0]["title"] == "Lead routing is killing me"
    assert "killing" in signal.summary.lower() or signal.thread_count == 2


@patch("scout.sources.reddit._get_reddit_client")
def test_search_complaints_handles_empty_results(mock_client):
    fake_reddit = MagicMock()
    fake_reddit.subreddit.return_value.search.return_value = []
    mock_client.return_value = fake_reddit

    signal = search_complaints(["nonexistent"], keywords=["xyz"], limit=5)
    assert signal.thread_count == 0
    assert signal.threads == []
```

- [ ] **Step 2: Run tests, verify failure**

```powershell
uv run pytest tests/test_reddit.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `scout/sources/reddit.py`**

```python
"""Reddit search adapter via PRAW. Reads credentials from env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from typing import Any

import praw
from dotenv import load_dotenv

load_dotenv()


@dataclass
class RedditSignal:
    thread_count: int
    threads: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get_reddit_client() -> praw.Reddit:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "market-scout/0.1")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET. "
            "Register a script app at https://www.reddit.com/prefs/apps and set values in .env."
        )
    return praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)


def search_complaints(
    subreddits: list[str],
    keywords: list[str],
    limit: int = 25,
    time_filter: str = "year",
) -> RedditSignal:
    """Search target subreddits for keyword-bearing posts. Returns RedditSignal."""
    reddit = _get_reddit_client()
    query = " OR ".join(keywords) if keywords else ""
    threads: list[dict[str, Any]] = []
    for sub_name in subreddits:
        try:
            for submission in reddit.subreddit(sub_name).search(
                query, sort="top", time_filter=time_filter, limit=limit
            ):
                threads.append({
                    "id": submission.id,
                    "title": submission.title,
                    "selftext": (submission.selftext or "")[:2000],
                    "score": submission.score,
                    "url": submission.url,
                    "subreddit": submission.subreddit.display_name,
                    "created_utc": submission.created_utc,
                })
        except Exception as exc:  # noqa: BLE001
            # Subreddit may be private/banned; record but don't crash
            threads.append({"error": f"{sub_name}: {exc}"})

    summary = _summarize(threads)
    return RedditSignal(thread_count=len([t for t in threads if "error" not in t]), threads=threads, summary=summary)


def _summarize(threads: list[dict[str, Any]]) -> str:
    if not threads:
        return "No complaint threads found."
    titles = [t["title"] for t in threads if "title" in t][:5]
    return "Top thread titles: " + " | ".join(titles)
```

- [ ] **Step 4: Run tests, verify pass**

```powershell
uv run pytest tests/test_reddit.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Live smoke test (only if Reddit creds are configured)**

If `.env` has real Reddit creds, run:

```powershell
uv run python -c "from scout.sources.reddit import search_complaints; s = search_complaints(['python'], ['help'], limit=3); print(s.thread_count, s.summary[:120])"
```

Expected: prints a thread count > 0 and a summary string.

If no creds yet, skip — that's expected; Jim sets these up before running `/scan`.

- [ ] **Step 6: Commit**

```powershell
git add scout/sources/reddit.py tests/test_reddit.py
git commit -m "Add Reddit source adapter (PRAW)"
```

---

## Task 8: `scout/sources/trends.py` — pytrends Adapter

**Files:**
- Create: `scout/sources/trends.py`
- Create: `tests/test_trends.py`

- [ ] **Step 1: Write failing tests in `tests/test_trends.py`**

```python
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from scout.sources.trends import curve, TrendsSignal


def _fake_df(values, dates):
    return pd.DataFrame({"revops": values}, index=pd.to_datetime(dates))


@patch("scout.sources.trends._get_pytrends")
def test_curve_returns_direction_up(mock_pytrends):
    pt = MagicMock()
    pt.interest_over_time.return_value = _fake_df(
        values=[10, 20, 40, 60, 80],
        dates=["2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01"],
    )
    mock_pytrends.return_value = pt

    sig: TrendsSignal = curve(["revops"], timeframe="today 5-y")
    assert sig.direction == "up"
    assert sig.delta_pct > 0
    assert len(sig.points) == 5


@patch("scout.sources.trends._get_pytrends")
def test_curve_returns_direction_down(mock_pytrends):
    pt = MagicMock()
    pt.interest_over_time.return_value = _fake_df(
        values=[80, 60, 40, 20, 10],
        dates=["2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01"],
    )
    mock_pytrends.return_value = pt

    sig = curve(["revops"], timeframe="today 5-y")
    assert sig.direction == "down"
    assert sig.delta_pct < 0


@patch("scout.sources.trends._get_pytrends")
def test_curve_handles_flat(mock_pytrends):
    pt = MagicMock()
    pt.interest_over_time.return_value = _fake_df(
        values=[50, 51, 50, 49, 50],
        dates=["2022-01-01", "2022-07-01", "2023-01-01", "2023-07-01", "2024-01-01"],
    )
    mock_pytrends.return_value = pt

    sig = curve(["revops"], timeframe="today 5-y")
    assert sig.direction == "flat"
```

- [ ] **Step 2: Run tests, verify failure**

```powershell
uv run pytest tests/test_trends.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `scout/sources/trends.py`**

```python
"""Google Trends adapter via pytrends."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

import pandas as pd
from pytrends.request import TrendReq


@dataclass
class TrendsSignal:
    keyword: str
    direction: str  # "up" | "flat" | "down"
    delta_pct: float
    points: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _get_pytrends() -> TrendReq:
    return TrendReq(hl="en-US", tz=360)


def curve(keywords: list[str], timeframe: str = "today 5-y", geo: str = "US") -> TrendsSignal:
    """Fetch interest-over-time and classify direction as up/flat/down."""
    pt = _get_pytrends()
    pt.build_payload(keywords, timeframe=timeframe, geo=geo)
    df: pd.DataFrame = pt.interest_over_time()

    keyword = keywords[0]
    if df.empty or keyword not in df.columns:
        return TrendsSignal(keyword=keyword, direction="flat", delta_pct=0.0, points=[])

    series = df[keyword].astype(float)
    points = [{"date": idx.strftime("%Y-%m-%d"), "value": float(v)} for idx, v in series.items()]

    first_third = series.iloc[: max(1, len(series) // 3)].mean()
    last_third = series.iloc[-max(1, len(series) // 3) :].mean()
    if first_third == 0:
        delta_pct = 0.0
    else:
        delta_pct = round((last_third - first_third) / first_third * 100, 1)

    if delta_pct > 15:
        direction = "up"
    elif delta_pct < -15:
        direction = "down"
    else:
        direction = "flat"

    return TrendsSignal(keyword=keyword, direction=direction, delta_pct=delta_pct, points=points)
```

- [ ] **Step 4: Run tests, verify pass**

```powershell
uv run pytest tests/test_trends.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```powershell
git add scout/sources/trends.py tests/test_trends.py
git commit -m "Add Google Trends source adapter (pytrends)"
```

---

## Task 9: `scout/cli.py` — Subcommand Dispatch

**Files:**
- Create: `scout/cli.py`, `scout/__main__.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests in `tests/test_cli.py`**

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


def run_cli(*args, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "scout", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        input=input_text,
    )


def test_cli_filter_blocks_excluded(tmp_path):
    candidates = [
        {"icp": "RevOps leaders at 50-300 person B2B SaaS"},
        {"icp": "AI automation agencies serving SMBs"},
    ]
    in_path = tmp_path / "candidates.json"
    in_path.write_text(json.dumps(candidates), encoding="utf-8")

    proc = run_cli("filter", "--input", str(in_path))
    assert proc.returncode == 0
    result = json.loads(proc.stdout)
    assert len(result["kept"]) == 1
    assert len(result["excluded"]) == 1
    assert result["kept"][0]["icp"].startswith("RevOps")


def test_cli_score_emits_composite(tmp_path):
    candidate = {
        "icp": "RevOps leaders at 50-300 person B2B SaaS",
        "criteria": {
            "pain": {
                "complaint_volume": {"score": 5, "evidence": "47 threads"},
                "emotional_intensity": {"score": 4, "evidence": "many"},
                "willingness_signals": {"score": 5, "evidence": "8 instances"},
                "recency": {"score": 4, "evidence": "rising"},
            },
            "purchasing_power": {
                "avg_deal_size": {"score": 4, "evidence": "$50K ACV"},
                "budget_authority": {"score": 4, "evidence": "RevOps lead owns"},
                "funded_or_profitable": {"score": 4, "evidence": "well-funded"},
            },
            "easy_to_target": {
                "concentrated_channels": {"score": 5, "evidence": "r/revops"},
                "identifiable_titles": {"score": 5, "evidence": "clean"},
                "community_density": {"score": 5, "evidence": "active"},
            },
            "growing": {
                "trends_curve": {"score": 4, "evidence": "+180%"},
                "funding_momentum": {"score": 4, "evidence": "8 rounds"},
                "structural_tailwind": {"score": 3, "evidence": "AI shift"},
            },
        },
    }
    in_path = tmp_path / "candidate.json"
    in_path.write_text(json.dumps(candidate), encoding="utf-8")

    proc = run_cli("score", "--input", str(in_path))
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout)
    assert result["composite"] > 15
    assert result["cut"] is False
```

- [ ] **Step 2: Run tests, verify failure**

```powershell
uv run pytest tests/test_cli.py -v
```

Expected: ImportError / module not found.

- [ ] **Step 3: Implement `scout/cli.py`**

```python
"""CLI dispatch — `python -m scout <subcommand>`. JSON in, JSON out."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from scout import filters as filters_mod
from scout import io as io_mod
from scout import scoring as scoring_mod

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
RUNS_DIR = PROJECT_ROOT / "runs"


def _load_input(path_or_dash: str) -> Any:
    if path_or_dash == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path_or_dash).read_text(encoding="utf-8"))


def _emit(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def cmd_filter(args: argparse.Namespace) -> int:
    candidates = _load_input(args.input)
    exclusions = filters_mod.load_exclusions(CONFIG_DIR / "exclusions.yaml")
    kept: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for c in candidates:
        ex, reason = filters_mod.is_excluded(c.get("icp", ""), exclusions)
        if ex:
            excluded.append({**c, "exclusion_reason": reason})
        else:
            c["soft_penalty"] = filters_mod.soft_penalty_score(c.get("icp", ""), exclusions)
            kept.append(c)
    _emit({"kept": kept, "excluded": excluded})
    return 0


def cmd_reddit(args: argparse.Namespace) -> int:
    from scout.sources.reddit import search_complaints
    subreddits = args.subreddits.split(",")
    keywords = args.keywords.split(",")
    sig = search_complaints(subreddits, keywords, limit=args.limit)
    _emit(sig.to_dict())
    return 0


def cmd_trends(args: argparse.Namespace) -> int:
    from scout.sources.trends import curve
    keywords = args.keywords.split(",")
    sig = curve(keywords, timeframe=args.timeframe)
    _emit(sig.to_dict())
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    candidate = _load_input(args.input)
    rubric = scoring_mod.load_rubric(CONFIG_DIR / "rubric.yaml")
    result = scoring_mod.score_candidate(candidate, rubric)
    _emit(result)
    return 0


def cmd_write_scan(args: argparse.Namespace) -> int:
    bundle = _load_input(args.input)
    today = date.today().isoformat()
    out_path = RUNS_DIR / "scans" / f"{today}-scan.md"

    body_lines: list[str] = [
        f"# Market Scan — {today}",
        "",
        "## Top 25 (ranked by composite)",
        "",
        "| # | ICP | Pain | Power | Target | Growth | Composite | Category |",
        "|---|-----|------|-------|--------|--------|-----------|----------|",
    ]
    ranked = bundle.get("ranked", [])
    for idx, row in enumerate(ranked, 1):
        cs = row.get("criterion_scores", {})
        body_lines.append(
            f"| {idx} | {row['icp']} | {cs.get('pain', 0):.1f} | {cs.get('purchasing_power', 0):.1f} | "
            f"{cs.get('easy_to_target', 0):.1f} | {cs.get('growing', 0):.1f} | {row.get('composite', 0):.1f} | {row.get('category', '')} |"
        )

    body_lines += ["", "## Why each was selected", ""]
    for idx, row in enumerate(ranked, 1):
        body_lines.append(f"### #{idx} — {row['icp']}")
        for crit_name, label in [
            ("pain", "Pain"),
            ("purchasing_power", "Power"),
            ("easy_to_target", "Target"),
            ("growing", "Growth"),
        ]:
            score = row.get("criterion_scores", {}).get(crit_name, 0)
            evidence = row.get("rationale", {}).get(crit_name, "")
            body_lines.append(f"- **{label} ({score:.1f}):** {evidence}")
        body_lines.append("")

    suggested = bundle.get("suggested_next", [])
    if suggested:
        body_lines += ["## Suggested next deep-dives (top 3, diversified by category)", ""]
        for i, s in enumerate(suggested, 1):
            body_lines.append(f"{i}. {s}")
        body_lines.append("")

    sources = bundle.get("sources", [])
    if sources:
        body_lines += ["## Sources touched this scan", ""]
        for i, url in enumerate(sources, 1):
            body_lines.append(f"{i}. {url}")

    fm = {
        "scan_date": today,
        "focus": bundle.get("focus", ""),
        "candidates_generated": bundle.get("candidates_generated", 0),
        "candidates_scored": bundle.get("candidates_scored", 0),
        "top_n": len(ranked),
    }
    io_mod.write_markdown_with_frontmatter(out_path, fm, "\n".join(body_lines))
    _emit({"path": str(out_path)})
    return 0


def cmd_write_deepdive(args: argparse.Namespace) -> int:
    bundle = _load_input(args.input)
    today = date.today().isoformat()
    icp_slug = bundle.get("icp_slug", "unknown")
    out_path = RUNS_DIR / "deep-dives" / f"{today}-{icp_slug}.md"

    # Verify quotes against the fetch log
    log_path = RUNS_DIR / ".tmp" / f"{icp_slug}-fetch.jsonl"
    raw_quotes = bundle.get("quotes", [])
    quote_texts = [q.get("text", "") for q in raw_quotes]
    verified_texts, dropped = io_mod.verify_quotes(log_path, quote_texts)
    verified_quotes = [q for q in raw_quotes if q.get("text", "") in verified_texts]

    fm = {
        "icp": bundle.get("icp", ""),
        "icp_slug": icp_slug,
        "scan_date": bundle.get("scan_date", ""),
        "deep_dive_date": today,
        "composite_score": bundle.get("composite_score", ""),
        "sources_touched": len(bundle.get("sources", [])),
        "quotes_verified": len(verified_quotes),
        "quotes_dropped": len(dropped),
    }

    body_lines = [
        f"# {bundle.get('icp', '')}",
        "",
        "## Verdict",
        bundle.get("verdict", "_(not provided)_"),
        "",
        "## Why this market scored where it did",
        bundle.get("why_scored", "_(not provided)_"),
        "",
        "## Customer language (verbatim, sourced)",
    ]
    for q in verified_quotes:
        body_lines.append(f'> "{q["text"]}" — {q.get("source", "")}, {q.get("date", "")}, [link]({q.get("url", "")})')
    body_lines += ["", "## Offer hypothesis", bundle.get("offer_hypothesis", "_(not provided)_"), ""]
    body_lines += ["## Buyer profile", bundle.get("buyer_profile", "_(not provided)_"), ""]
    body_lines += ["## Competitive landscape", bundle.get("competitive_landscape", "_(not provided)_"), ""]
    body_lines += ["## Growth + tailwinds", bundle.get("growth_tailwinds", "_(not provided)_"), ""]
    body_lines += ["## Risks / why this could be wrong", bundle.get("risks", "_(not provided)_"), ""]

    body_lines += ["## Sources", ""]
    for i, url in enumerate(bundle.get("sources", []), 1):
        body_lines.append(f"{i}. {url}")

    if dropped:
        body_lines += ["", "## Quotes dropped (failed verification)", ""]
        for d in dropped:
            body_lines.append(f"- {d}")

    io_mod.write_markdown_with_frontmatter(out_path, fm, "\n".join(body_lines))
    _emit({"path": str(out_path), "quotes_verified": len(verified_quotes), "quotes_dropped": len(dropped)})
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="scout")
    sub = p.add_subparsers(dest="command", required=True)

    pf = sub.add_parser("filter")
    pf.add_argument("--input", required=True, help="Path to JSON list of candidates (or '-' for stdin)")
    pf.set_defaults(func=cmd_filter)

    pr = sub.add_parser("reddit")
    pr.add_argument("--subreddits", required=True, help="comma-separated subreddit names")
    pr.add_argument("--keywords", required=True, help="comma-separated keywords")
    pr.add_argument("--limit", type=int, default=25)
    pr.set_defaults(func=cmd_reddit)

    pt = sub.add_parser("trends")
    pt.add_argument("--keywords", required=True, help="comma-separated keywords")
    pt.add_argument("--timeframe", default="today 5-y")
    pt.set_defaults(func=cmd_trends)

    ps = sub.add_parser("score")
    ps.add_argument("--input", required=True)
    ps.set_defaults(func=cmd_score)

    pws = sub.add_parser("write-scan")
    pws.add_argument("--input", required=True)
    pws.set_defaults(func=cmd_write_scan)

    pwd = sub.add_parser("write-deepdive")
    pwd.add_argument("--input", required=True)
    pwd.set_defaults(func=cmd_write_deepdive)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Implement `scout/__main__.py`**

```python
import sys

from scout.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run tests, verify pass**

```powershell
uv run pytest tests/test_cli.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Run the full test suite**

```powershell
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add scout/cli.py scout/__main__.py tests/test_cli.py
git commit -m "Add scout CLI with filter, reddit, trends, score, write-scan, write-deepdive subcommands"
```

---

## Task 10: `.claude/commands/scan.md` — `/scan` Orchestrator

**Files:**
- Create: `.claude/commands/scan.md`

- [ ] **Step 1: Write the slash command**

Create `.claude/commands/scan.md`:

````markdown
---
description: Run a market scan — produce a ranked top-25 list of B2B ICPs scored against Hormozi's four criteria.
argument-hint: "[focus=<category>] [count=<N>]"
---

# /scan

You are running the Market Scout scan. Produce a ranked list of B2B ICPs scored on Hormozi's four criteria (pain, purchasing_power, easy_to_target, growing). Output is one markdown file under `runs/scans/`.

**Arguments parsing:** Read `$ARGUMENTS`. Honor `focus=<category>` (narrows brainstorm) and `count=<N>` (default 25). If empty, default to full free brainstorm and N=25.

## Workflow

### Step 1 — Brainstorm ~60 ICP candidates (reasoning only, no tools)

Generate ~60 tight ICP candidates. Each must be: **role + company size + industry**. Anchor on:

- **B2B preferred, US-focused**
- **Small-team-serviceable with AI-leveraged delivery** — a 5-person team + agents can serve them; not a market needing licensed humans or in-person delivery
- **Tight grain** — "RevOps leaders at 50-300 person B2B SaaS", NOT "HR Tech"

Read `config/seeds.yaml` and include any `pinned_categories` in the brainstorm.

Write the 60 candidates to `runs/.tmp/<scan-id>/candidates.json` where `<scan-id>` is today's date. Each candidate object: `{"icp": "...", "category": "...", "keywords": ["...", "..."], "subreddits": ["...", "..."]}`.

### Step 2 — Apply exclusions

```bash
uv run python -m scout filter --input runs/.tmp/<scan-id>/candidates.json > runs/.tmp/<scan-id>/filtered.json
```

The `kept` array becomes the working set. Each kept candidate now has `soft_penalty: 0 or 1`.

### Step 3 — Fetch signals per candidate (batched)

For each candidate in `kept`, gather four signal bundles. Batch 5 candidates at a time to manage cost.

**PAIN signal** — Reddit:
```bash
uv run python -m scout reddit --subreddits "<comma-separated>" --keywords "<keywords>" --limit 15
```
Capture the returned JSON (thread_count, threads, summary).

**POWER signal** — Perplexity research:
Call `mcp__perplexity__perplexity_research` with query:
> "What is the typical budget, average deal size for adjacent services, and buyer authority profile for <ICP>? Cite sources."
Save the response + citations.

**TARGET signal** — Perplexity search:
Call `mcp__perplexity__perplexity_search` with query:
> "Top trade publications, conferences, Slack/Discord communities, and newsletters serving <ICP>."

**GROWTH signal** — Trends + Perplexity:
```bash
uv run python -m scout trends --keywords "<single-keyword>"
```
Plus `mcp__perplexity__perplexity_search`:
> "Funding rounds, M&A, new entrants, regulatory shifts affecting <ICP> in the last 18 months."

### Step 4 — Score each candidate

For each candidate, assemble the signal bundle into a scoring input with sub-signal scores 1-5 and a one-line evidence citation per sub-signal. Use the rubric anchors in `config/rubric.yaml` (referenced in the design spec) to decide 1, 3, or 5 (and 2/4 between).

**Rule: any sub-signal without a concrete evidence string is capped at 2 by the scorer. Do not invent evidence.**

Build per candidate JSON like:
```json
{
  "icp": "RevOps leaders at 50-300 person B2B SaaS",
  "soft_penalty": 0,
  "criteria": {
    "pain": {
      "complaint_volume": {"score": 5, "evidence": "47 threads on r/revops in 90d"},
      "emotional_intensity": {"score": 4, "evidence": "'killing me' appears 11x in top 20 threads"},
      "willingness_signals": {"score": 5, "evidence": "8 instances of 'I'd pay anything' or 'we hired X'"},
      "recency": {"score": 4, "evidence": "thread volume +60% in last 6mo vs prior 6mo"}
    },
    "purchasing_power": { ... },
    "easy_to_target": { ... },
    "growing": { ... }
  }
}
```

Then:
```bash
uv run python -m scout score --input runs/.tmp/<scan-id>/scored/<icp-slug>.json
```

Collect all scored results into `runs/.tmp/<scan-id>/scored_all.json`.

### Step 5 — Rank, trim, write

Filter out any candidate where `cut: true`. Sort remaining by `composite` descending. Trim to N (default 25).

Build a final bundle:
```json
{
  "focus": "<focus arg or empty>",
  "candidates_generated": 60,
  "candidates_scored": <count>,
  "ranked": [ ... ],          // ordered list of scored results with `rationale` map per criterion
  "suggested_next": [          // top 3, diversified by category
    "#1 — <ICP>",
    "#4 — <different category>",
    "#11 — <different category>"
  ],
  "sources": [                  // all unique URLs touched this run
    "https://...",
    "..."
  ]
}
```

For each ranked entry, add a `rationale` field mapping each criterion to a 1-2 sentence "why this score, citing real signal":
```json
"rationale": {
  "pain": "47 distinct complaint threads on r/revops in last 90d; phrase 'lead routing chaos' appeared in 12.",
  "purchasing_power": "Adjacent tools (Clay, Default) at $25-80K ACV; budget held by RevOps lead.",
  ...
}
```

Then:
```bash
uv run python -m scout write-scan --input runs/.tmp/<scan-id>/final_bundle.json
```

This writes `runs/scans/YYYY-MM-DD-scan.md`. Report the path back to the user.

### Step 6 — Summarize to user

Show:
- Path to the scan file
- Top 5 ICPs by composite (one line each)
- The 3 suggested next deep-dives
- Total time + approximate Perplexity cost (estimated from query count)

## Failure handling

- If Reddit creds aren't configured: skip the pain Reddit call for that candidate; note "no reddit signal — credentials not configured" in the rationale; cap complaint_volume + recency at score 2.
- If pytrends rate-limits: retry once with 30s delay; if still fails, score `trends_curve` at 2 with evidence "pytrends rate-limited".
- If Perplexity errors: skip that signal; score the affected sub-signals at 2 with evidence noting the failure.
- Never invent quotes or evidence. Missing evidence → capped at 2.

## Cost expectations

~40 surviving candidates × ~4 queries = ~160 calls. Perplexity ~$0.40-2.00. Total wall time 2-4 minutes.
````

- [ ] **Step 2: Commit**

```powershell
git add .claude/commands/scan.md
git commit -m "Add /scan slash command orchestrator"
```

---

## Task 11: `.claude/commands/deep-dive.md` — `/deep-dive` Orchestrator

**Files:**
- Create: `.claude/commands/deep-dive.md`

- [ ] **Step 1: Write the slash command**

Create `.claude/commands/deep-dive.md`:

````markdown
---
description: Produce an analyst-quality deep-dive report on one chosen market from the latest scan (or a fresh ICP).
argument-hint: "<market-id-or-name>"
---

# /deep-dive

You are producing a deep-dive market report. Output is one markdown file under `runs/deep-dives/`.

**Argument:** `$ARGUMENTS` is either a numeric ID (matches "# N" in the latest scan), or fuzzy text matching an ICP slug (case-insensitive substring). If empty, ask the user which market.

## Workflow

### Step 1 — Resolve the market

- Find the latest file in `runs/scans/*.md` by date in filename.
- Parse the table to locate the row matching `$ARGUMENTS` (numeric ID or fuzzy text on ICP).
- Pull: ICP, criterion scores, composite, category, rationale.
- If `$ARGUMENTS` doesn't match anything in the latest scan: treat it as a fresh ICP. Ask the user to confirm exact ICP wording, then proceed without scan context.

Compute an `icp_slug`: lowercase, hyphenated, max 40 chars (e.g. `revops-saas-50-300`).

Create the fetch log path: `runs/.tmp/<icp-slug>-fetch.jsonl`. All subsequent fetches MUST be appended to it (URL + raw text) for quote verification.

### Step 2 — Deep fetch

Run these four buckets in order. Append every fetched response (URL + text) to the fetch log via `runs/.tmp/<icp-slug>-fetch.jsonl` using `uv run python -m scout` is not yet implemented for fetch-log writes from the skill side — instead, write each MCP response to a temp file and append manually using a small shell snippet OR call the Python helper directly:

```bash
uv run python -c "from scout.io import append_fetch_log; from pathlib import Path; append_fetch_log(Path('runs/.tmp/<icp-slug>-fetch.jsonl'), {'url': '<url>', 'text': '''<text>'''})"
```

(In practice: stash the MCP response text in a temp file, then call append_fetch_log with file content via a python -c that reads the file.)

**Bucket A — Customer language harvest**

1. Call `uv run python -m scout reddit --subreddits "<relevant>" --keywords "<icp keywords>" --limit 20`. Append each thread's `selftext + title` to the fetch log.
2. For the 5-10 top-scoring threads, call `mcp__plugin_firecrawl__firecrawl-scrape` (or the Firecrawl MCP available) on the thread URL to get full comments. Append response text to fetch log.
3. Call `mcp__perplexity__perplexity_search` for "G2 / Capterra / TrustRadius reviews complaining about <pain area> in <ICP>". Append text + citations to fetch log.
4. Extract 20-30 candidate quotes (verbatim, in the source's voice). Each must have: `text`, `source` (site/sub), `date`, `url`. Filter: keep quotes with concrete pain, urgency, dollar mentions, or "I wish someone would..." patterns. Target 8-15 final quotes after verification.

**Bucket B — Market sizing + buyer profile**

Call `mcp__perplexity__perplexity_research`:
> "For <ICP>: estimate TAM and SAM in the US, average deal size for adjacent services, who owns the budget, typical sales cycle, current alternative solutions (named tools and consultancies), and switching costs. Cite sources."

Append response to fetch log.

**Bucket C — Growth + funding**

1. Call `mcp__perplexity__perplexity_search`:
> "Funding rounds, M&A, new entrants, and regulatory shifts affecting <ICP> in the last 18 months. Name companies and amounts."
2. Call `uv run python -m scout trends --keywords "<canonical-keyword>"`.

Append both responses to fetch log.

**Bucket D — Competitor scan**

Call `mcp__perplexity__perplexity_search`:
> "Who serves <ICP> today (consultancies, tools, agencies)? What do they charge? What are common complaints about them? Cite sources."

Append response to fetch log.

### Step 3 — Synthesize

Build the bundle JSON. **Customer quotes verification is enforced by the writer — any quote whose text doesn't appear (whitespace+case normalized) in the fetch log will be dropped before the file is written.**

The synthesis bundle:

```json
{
  "icp": "RevOps leaders at 50-300 person B2B SaaS",
  "icp_slug": "revops-saas-50-300",
  "scan_date": "2026-05-23",
  "composite_score": "18.3/20",
  "verdict": "Build. The combination of acute, current pain + concentrated channels + funded buyers makes this the strongest market in the scan...",
  "why_scored": "Pain (5.0) reflects 47 active complaint threads in last 90d; Power (4.3) backed by Clay/Default at $25-80K ACV...",
  "quotes": [
    {"text": "Lead routing is killing me, we tried 3 tools and none of them stick", "source": "r/revops", "date": "2026-04-18", "url": "https://reddit.com/r/revops/comments/abc"},
    ...  // 8-15 quotes total
  ],
  "offer_hypothesis": "**RevOps leaders at 50-300 person B2B SaaS** struggle with **lead-routing chaos across multiple tools**; would pay **$4-8K/month** for **an AI agent that owns routing logic + reports anomalies, set up in <14 days**.\n\n- **Why this price:** evidence...\n- **Why this mechanism:** evidence...\n- **What would kill it:** risks...",
  "buyer_profile": "...",
  "competitive_landscape": "...",
  "growth_tailwinds": "...",
  "risks": "...",
  "sources": ["https://...", "..."]
}
```

**Offer hypothesis rules:**

- Must follow the template: `[ICP] struggles with [specific pain]; would pay $[range] for [delivered outcome via mechanism] within [timeline].`
- If a slot can't be filled from harvested evidence, write `Could not determine [slot] from sources — manual research needed.` Never fabricate.

Save the bundle to `runs/.tmp/<icp-slug>-bundle.json`.

### Step 4 — Write the report

```bash
uv run python -m scout write-deepdive --input runs/.tmp/<icp-slug>-bundle.json
```

This:
1. Loads the bundle
2. Calls `verify_quotes` against the fetch log
3. Drops unverified quotes
4. Writes `runs/deep-dives/YYYY-MM-DD-<icp-slug>.md` with full frontmatter
5. Lists dropped quotes in a "Quotes dropped (failed verification)" section at the end (for your inspection)

### Step 5 — Summarize to user

Report:
- Path to the deep-dive file
- Verdict (one line)
- Quote count: verified vs dropped
- Offer hypothesis (one line)
- Top 3 risks named

## Cleanup

Delete `runs/.tmp/<icp-slug>-fetch.jsonl` and `runs/.tmp/<icp-slug>-bundle.json` on success. Keep them on failure for inspection.

## Cost expectations

~50-80 fetch calls. Perplexity ~$2-5. Wall time 10-15 min.
````

- [ ] **Step 2: Commit**

```powershell
git add .claude/commands/deep-dive.md
git commit -m "Add /deep-dive slash command orchestrator"
```

---

## Task 12: End-to-End Smoke Run + README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# Market Scout

Personal market research agent for surfacing hungry B2B markets via Alex Hormozi's four-criteria framework (pain, purchasing power, easy to target, growing).

Two stages:
- `/scan` — produces a ranked top-25 list of B2B ICP candidates
- `/deep-dive <id-or-name>` — produces an analyst-quality report on one chosen market

## Setup (one-time, ~5 min)

1. Install Python deps:
   ```powershell
   uv sync --all-extras
   ```

2. Register a Reddit app:
   - Go to https://www.reddit.com/prefs/apps
   - Create app, type: **script**
   - Copy `client_id` (under app name) and `client_secret`

3. Copy `.env.example` to `.env` and fill in:
   ```
   REDDIT_CLIENT_ID=...
   REDDIT_CLIENT_SECRET=...
   REDDIT_USER_AGENT=market-scout/0.1 by u/your-handle
   ```

4. Confirm Perplexity + Firecrawl MCPs are configured in Claude Code:
   ```
   /mcp
   ```
   Both should show as connected.

## Usage

In Claude Code, in this project directory:

```
/scan
```

Optionally with arguments:
```
/scan focus=B2B-ops
/scan count=15
```

Output: `runs/scans/YYYY-MM-DD-scan.md`

After reviewing the scan, pick a market and run:

```
/deep-dive 4
/deep-dive revops
/deep-dive "RevOps leaders"
```

Output: `runs/deep-dives/YYYY-MM-DD-<icp-slug>.md`

## Configuration

Tunable without code changes:

- `config/rubric.yaml` — sub-signals, anchors, weights, hard floors
- `config/exclusions.yaml` — categories and buyer profiles to skip; soft penalties
- `config/seeds.yaml` — categories pinned to every scan

## Running tests

```powershell
uv run pytest -v
```

## Architecture

- `.claude/commands/scan.md` + `deep-dive.md` — Claude Code orchestrators
- `scout/` — Python package (CLI, scoring, filters, I/O, sources)
- `scout/sources/reddit.py` + `trends.py` — PRAW + pytrends adapters
- Perplexity + Firecrawl reached via existing MCPs (no Python adapter)
- Quote integrity: every quote in a deep-dive must appear in the run's fetch log, or it's dropped

See `docs/superpowers/specs/2026-05-23-market-scout-design.md` for the full design.
```

- [ ] **Step 2: Run the full test suite one more time**

```powershell
uv run pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Smoke run `/scan` end-to-end**

In Claude Code, with `.env` configured:
```
/scan count=10
```

Verify:
- `runs/scans/<today>-scan.md` exists
- File has YAML frontmatter
- Table has ~10 rows
- Each "Why selected" section cites specific signals (numbers, thread counts, dollar amounts), not framework restatement
- "Suggested next deep-dives" section has 3 entries diversified by category

If any of these fail, treat as a bug — investigate, fix, commit, re-run.

- [ ] **Step 4: Smoke run `/deep-dive`**

Pick #1 from the scan and run:
```
/deep-dive 1
```

Verify:
- `runs/deep-dives/<today>-<slug>.md` exists
- 8-15 verbatim quotes, each with a working source link
- Frontmatter `quotes_verified` > 0; if `quotes_dropped` > 0, those appear in the "Quotes dropped" section
- Offer hypothesis fills the template; no `_(not provided)_` markers in critical sections
- Verdict is a clear build/don't with a named reason

- [ ] **Step 5: Commit**

```powershell
git add README.md
git commit -m "Add README with setup, usage, and architecture overview"
```

- [ ] **Step 6: Push to GitHub**

```powershell
git push
```

---

## Self-Review

**Spec coverage check** (run after writing the plan):

| Spec section | Task |
|---|---|
| §1 Goal — two stages, B2B/US/small-team-serviceable | Tasks 10, 11 |
| §2.1 Directory layout | Tasks 1, 2 |
| §2.2 Source modules (Perplexity/Firecrawl via MCP; Reddit/Trends as Python) | Tasks 7, 8, 10, 11 |
| §2.3 Slash commands | Tasks 10, 11 |
| §3.1 Tight ICP grain | Task 10 (Step 1) |
| §3.2 Small-team-serviceable with AI extension | Task 10 (Step 1) |
| §3.3 Scan file format | Task 9 (cmd_write_scan) |
| §3.4 Cost/time | Task 10 (footer) |
| §4.1 Quote integrity / fetch log | Task 4 (verify_quotes), Task 9 (cmd_write_deepdive), Task 11 |
| §4.2 Offer hypothesis template | Task 11 (Step 3) |
| §4.3 Deep-dive file format | Task 9 (cmd_write_deepdive) |
| §5 Scoring rubric | Tasks 3, 6 |
| §6 Exclusions | Tasks 3, 5 |
| §7 Setup | Tasks 1, 2, 12 |
| §8 Operational decisions | Tasks 10, 11 (failure handling sections) |
| §9 Quality bar | Task 12 (Steps 3-4 smoke verification) |
| §10 Out of scope (no tracking, no web UI, etc.) | Plan respects — none added |

Coverage looks complete. No placeholders. Type/method names consistent (`search_complaints`, `curve`, `score_candidate`, `verify_quotes`, `write_markdown_with_frontmatter` used identically across tasks). Plan ready.
