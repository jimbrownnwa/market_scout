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

Pick a scan-id (today's date, e.g. `2026-05-23`). Write the 60 candidates to `runs/.tmp/<scan-id>/candidates.json`. Each candidate object:
```json
{"icp": "...", "category": "...", "keywords": ["...", "..."], "subreddits": ["...", "..."]}
```

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

For each candidate, assemble the signal bundle into a scoring input with sub-signal scores 1-5 and a one-line evidence citation per sub-signal. Use the rubric anchors in `config/rubric.yaml` to decide 1, 3, or 5 (and 2/4 between).

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
    "purchasing_power": { },
    "easy_to_target": { },
    "growing": { }
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
  "ranked": [ ],
  "suggested_next": [
    "#1 — <ICP>",
    "#4 — <different category>",
    "#11 — <different category>"
  ],
  "sources": [
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
  "easy_to_target": "...",
  "growing": "..."
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
