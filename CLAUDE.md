# Market Scout — Project Context for Claude

Personal market research agent. Two slash commands, Python package backing them, markdown outputs.

## What this project does

- `/scan` — generate 60 B2B ICP candidates from scratch, score them on Hormozi's four criteria (pain, purchasing power, easy to target, growing) with rubric-defined sub-signals, rank top 25, write a dated markdown file under `runs/scans/`.
- `/deep-dive <id-or-name>` — pick one ICP from the latest scan, do a deep fetch, write an analyst-quality memo to `runs/deep-dives/` with **verbatim, source-linked customer quotes**.

Output is for Jim (founder of NWA Boost) deciding which markets to build offers against.

## Architecture (hybrid by design)

```
.claude/commands/scan.md         ← Claude (orchestrator)
.claude/commands/deep-dive.md    ← Claude (orchestrator)
        │
        ▼ calls
scout/ Python package            ← deterministic logic
├── cli.py                       ← argparse dispatch (6 subcommands)
├── io.py                        ← frontmatter, fetch log, quote verification
├── filters.py                   ← exclusion checks
├── scoring.py                   ← rubric → composite (out of 20)
└── sources/
    ├── base.py                  ← SourceSignal dataclass (one shape for all 4 sources)
    ├── _apify.py                ← shared Apify run-actor wrapper
    ├── reddit.py                ← Apify-backed (NOT PRAW — Reddit dev API is blocked)
    ├── hackernews.py            ← Algolia HN Search API, no auth
    ├── g2.py                    ← Apify, 1-3 star reviews only
    ├── quora.py                 ← Apify (Quora actively fights scraping; degrades gracefully)
    └── trends.py                ← pytrends (Google Trends)
```

Perplexity + Firecrawl are reached via existing Claude Code MCPs — no Python adapters.

## Pain source contract (all four are identical)

Every pain source module exposes:
```python
search(query: str, limit: int = 25, scope: list[str] | None = None) -> SourceSignal
```
`scope` is interpreted per source: subreddits (Reddit), HN ignores, G2 categories, Quora topics. Each returns `SourceSignal(source, query, item_count, items, summary)` where each item is `{id, title, text, url, score, date, author, ...}`.

CLI mirrors: `uv run python -m scout {reddit|hackernews|g2|quora} --query "X" --scope "A,B" --limit N`.

## Configs (tunable without code changes)

- `config/rubric.yaml` — sub-signals, anchors, weights, hard floors
- `config/exclusions.yaml` — categories + buyer profiles to hard-cut; soft penalties
- `config/sources.yaml` — toggle each pain source on/off; swap Apify actor IDs
- `config/seeds.yaml` — categories pinned to every scan (default: empty)

## Hard rules (do not break)

1. **Quote integrity is enforced.** Every quote in a deep-dive must appear (whitespace+case normalized) in the run's fetch log (`runs/.tmp/<icp-slug>-fetch.jsonl`). Unverified quotes are dropped before the markdown is written. **Never fabricate quotes.**
2. **Evidence-cap on scoring.** A sub-signal with empty `evidence` is capped at 2 by the scorer regardless of declared score. The slash commands instruct: if a fetch failed or returned nothing, leave evidence blank — don't invent it. Capping is the anti-fabrication mechanism.
3. **Markets to avoid** (hard-cut at `is_excluded`):
   - AI automation consultancies / n8n/Make/Zapier shops (Jim's competitive backyard)
   - Regulated: legal, medical, financial advisory, tax/CPA, insurance brokerage
   - Broke buyers: solopreneurs without recurring revenue, pre-revenue founders, course creators under $10K MRR, freelancers without retainers, indie hackers pre-PMF
4. **Soft penalties** (allowed but `easy_to_target -1`): Crypto/Web3, Cannabis.
5. **Tight ICP grain.** Each candidate is "role + company size + industry" — e.g. "RevOps leaders at 50-300 person B2B SaaS". Broad categories ("HR Tech") are not valid candidates.
6. **Small-team-serviceable with AI extension.** A market is OK if a 5-person team + AI agents can serve it. Markets needing in-person delivery or licensed humans are cut.

## Where things live

- `docs/superpowers/specs/2026-05-23-market-scout-design.md` — design spec (frozen reference)
- `docs/superpowers/plans/2026-05-23-market-scout.md` — original implementation plan
- `runs/scans/` — dated scan output, one file per scan
- `runs/deep-dives/` — dated deep-dive output, one file per market
- `runs/.tmp/` — fetch logs and intermediate JSON, gitignored

## Development conventions

- **Python 3.11+, uv-managed.** `uv sync --all-extras` installs deps including pytest.
- **TDD when modifying Python.** Tests live in `tests/test_*.py`. Mock external APIs (`scout.sources.*.run_actor`, `requests.get`); never hit live services in unit tests.
- **`uv run pytest -v`** is the test command. All tests should pass before commit.
- **Per-file responsibility.** `io.py` doesn't score; `scoring.py` doesn't fetch; sources don't write markdown. Keep boundaries clean.
- **Commits are atomic.** One logical change per commit, descriptive message, push immediately on `main`.
- **Windows/PowerShell.** Bash tool uses Git Bash, forward-slash paths work. `uv` is on PATH.

## Known broken pain sources (as of 2026-05-23)

- **G2 actor `epctex/g2-scraper` returns HTTP 404** — actor no longer exists on Apify. Swap in `config/sources.yaml` when a replacement is found, or disable the source (`enabled: false`).
- **Quora actor `epctex/quora-scraper` returns HTTP 404** — same issue. Quora actively fights scraping; treat this source as unreliable until a working actor is confirmed.
- **HN (Algolia) returns 0 items** for most B2B niche queries — the API works but topic coverage is too sparse to be useful. HN pain signals only materialize for developer-adjacent ICPs.
- **Practical effect:** Reddit is currently the only reliable pain source. All G2/Quora/HN sub-signals are evidence-capped at 2 automatically. Score rankings still hold — Reddit alone provides enough signal.

## Scorer output shape

The `scout score` CLI strips the full `criteria` object and returns only:
```json
{"icp": "...", "criterion_scores": {"pain": 4.0, ...}, "composite": 17.3, "cut": false, "cut_reason": ""}
```
When building `final_bundle.json`, you must separately inject `rationale` (evidence strings from the original per-candidate scored files) into each ranked entry — the scorer does not preserve evidence. The `write-scan` command reads both `criterion_scores` and `rationale` from each ranked entry.

## Common pitfalls (specific to this project)

- **`str.lstrip("r/")` strips a character set, not a literal string.** Use `s.removeprefix("r/")` or `s[2:] if s.startswith("r/") else s`. (We hit this on Reddit subreddit URL building.)
- **Apify actor IDs in `config/sources.yaml` are best-effort defaults.** If an actor returns errors, swap to a working one and update the YAML — no code change needed.
- **`pytrends` rate-limits aggressively.** Don't hammer it in a tight loop; one keyword per candidate is enough.
- **HN Algolia URL** is `hn.algolia.com/api/v1` (not `angolia`, not `vi`).
- **The fetch log is the source of truth for quotes.** If you change how the orchestrator stores fetch responses, update `scout.io.verify_quotes` too — they're a contract.
- **Windows console UnicodeEncodeError** — evidence strings can contain non-ASCII characters (arrows, smart quotes). Always use `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` in any ad-hoc Python scripts that print evidence.

## Secrets

- `.env` is gitignored; `.env.example` is the committed template.
- Only `APIFY_TOKEN` is needed for the Python code. Perplexity + Firecrawl auth lives in Claude Code's MCP config, not in this repo.
- **Never write a real token into `.env.example`.** If a real value appears there during editing, treat it as compromised and rotate at the issuer.
