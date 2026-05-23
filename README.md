# Market Scout

Personal market research agent for surfacing hungry B2B markets via Alex Hormozi's four-criteria framework (pain, purchasing power, easy to target, growing).

Two stages:
- `/scan` — produces a ranked top-25 list of B2B ICP candidates
- `/deep-dive <id-or-name>` — produces an analyst-quality report on one chosen market

## Setup (one-time, ~3 min)

1. Install Python deps:
   ```powershell
   uv sync --all-extras
   ```

2. Get an Apify token:
   - Sign in at https://console.apify.com
   - Account → Integrations → copy your API token
   - Apify backs three of the four pain sources (Reddit, G2/Capterra, Quora). Hacker News uses the public Algolia API and needs no auth.

3. Copy `.env.example` to `.env` and fill in:
   ```
   APIFY_TOKEN=apify_api_...
   ```

4. Confirm Perplexity + Firecrawl MCPs are configured in Claude Code:
   ```
   /mcp
   ```
   Both should show as connected.

5. Optional: edit `config/sources.yaml` to toggle individual pain sources or swap Apify actor IDs.

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

Tests cover io, filters, scoring, all four pain-source adapters (mocked), the shared Apify helper, Google Trends (mocked), and CLI dispatch.

## Architecture

- `.claude/commands/scan.md` + `deep-dive.md` — Claude Code orchestrators
- `scout/` — Python package (CLI, scoring, filters, I/O, sources)
- `scout/sources/base.py` — shared `SourceSignal` dataclass (one shape for all four pain sources)
- `scout/sources/_apify.py` — thin Apify wrapper used by reddit/g2/quora
- `scout/sources/reddit.py` — Apify-backed Reddit search (replaces PRAW)
- `scout/sources/hackernews.py` — Algolia HN Search API (no auth)
- `scout/sources/g2.py` — Apify-backed G2/Capterra review scrape (1-3 star filter)
- `scout/sources/quora.py` — Apify-backed Quora answers
- `scout/sources/trends.py` — pytrends (Google Trends)
- Perplexity + Firecrawl reached via existing MCPs (no Python adapter needed)
- Quote integrity: every quote in a deep-dive must appear in the run's fetch log, or it's dropped

### Pain-source interface

All four pain sources expose the same function signature:

```python
search(query: str, limit: int = 25, scope: list[str] | None = None) -> SourceSignal
```

`scope` is interpreted per source: subreddits (Reddit), software categories (G2), topics (Quora), or ignored (HN). Each returns the same shape, so the orchestrator calls them identically.

See `docs/superpowers/specs/2026-05-23-market-scout-design.md` for the full design and `docs/superpowers/plans/2026-05-23-market-scout.md` for the implementation plan.

## First scan checklist

Before your first `/scan`:

- [ ] `uv sync --all-extras` ran clean
- [ ] `.env` populated with a real `APIFY_TOKEN`
- [ ] `/mcp` shows perplexity + firecrawl as connected
- [ ] `uv run pytest -v` is green

Then run `/scan count=10` for a quick first pass. If output looks right, run a full `/scan`.
