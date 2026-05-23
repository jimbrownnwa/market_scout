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
   - Copy `client_id` (the string under the app name) and `client_secret`

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

26 tests cover io, filters, scoring, Reddit (mocked), Trends (mocked), and CLI dispatch.

## Architecture

- `.claude/commands/scan.md` + `deep-dive.md` — Claude Code orchestrators
- `scout/` — Python package (CLI, scoring, filters, I/O, sources)
- `scout/sources/reddit.py` + `trends.py` — PRAW + pytrends adapters
- Perplexity + Firecrawl reached via existing MCPs (no Python adapter needed)
- Quote integrity: every quote in a deep-dive must appear in the run's fetch log, or it's dropped

See `docs/superpowers/specs/2026-05-23-market-scout-design.md` for the full design and `docs/superpowers/plans/2026-05-23-market-scout.md` for the implementation plan.

## First scan checklist

Before your first `/scan`:

- [ ] `uv sync --all-extras` ran clean
- [ ] `.env` populated with real Reddit credentials
- [ ] `/mcp` shows perplexity + firecrawl as connected
- [ ] `uv run pytest -v` shows 26 passed

Then run `/scan count=10` for a quick first pass. If output looks right, run a full `/scan`.
