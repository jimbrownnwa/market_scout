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

Create the fetch log path: `runs/.tmp/<icp-slug>-fetch.jsonl`. All subsequent fetches MUST append (URL + raw text) to this log for quote verification.

**To append to the fetch log from this skill:** after each MCP call, write the response text to a temp file, then run:

```bash
uv run python -c "
from scout.io import append_fetch_log
from pathlib import Path
import sys, json
text = Path(sys.argv[2]).read_text(encoding='utf-8')
append_fetch_log(Path(sys.argv[1]), {'url': sys.argv[3], 'text': text})
" "runs/.tmp/<icp-slug>-fetch.jsonl" "<temp-response-file>" "<source-url>"
```

(Or write a small inline Python script for batch-appending if many responses arrive at once.)

### Step 2 — Deep fetch

Run these four buckets in order. Append every fetched response (URL + text) to the fetch log via the helper above.

**Bucket A — Customer language harvest**

Pull from four pain sources, each toggleable in `config/sources.yaml`. Skip any source marked `enabled: false`. All four share the same CLI shape: `--query "<phrase>" --scope "<comma-list>" --limit N`.

1. **Reddit** (Apify): `uv run python -m scout reddit --query "<icp pain phrase>" --scope "<relevant subs>" --limit 20`. Append each item's `title + text` to the fetch log. For the 5-10 top-scoring items, also call the Firecrawl scrape MCP on the `url` to pull full comment threads. Append the Firecrawl response text to the fetch log.
2. **Hacker News** (Algolia, no auth): `uv run python -m scout hackernews --query "<icp pain phrase>" --limit 20`. Append each item's `title + text` to the fetch log. HN already returns top comments inline — no extra Firecrawl pass needed.
3. **G2/Capterra** (Apify, 1-3 stars only): `uv run python -m scout g2 --query "<pain phrase>" --scope "<software-category-slugs>" --limit 15`. Append each review's `title + text` (which includes cons + "why I switched" sections) to the fetch log.
4. **Quora** (Apify): `uv run python -m scout quora --query "<pain phrase>" --scope "<topic-slugs>" --limit 15`. Append each answer's `title + text` (HTML stripped) to the fetch log.
5. As a supplement, call `mcp__perplexity__perplexity_search` for "complaints and negative reviews about <pain area> in <ICP> beyond G2 and Reddit". Append the result text + citations to the fetch log.
6. Extract 20-30 candidate quotes (verbatim, in the source's voice). Each must have: `text`, `source` (e.g. `r/revops`, `Hacker News`, `G2: ExampleTool`, `Quora: <topic>`), `date`, `url`. Filter: keep quotes with concrete pain, urgency, dollar mentions, or "I wish someone would..." patterns. Target 8-15 final quotes after verification.

**Bucket B — Market sizing + buyer profile**

Call `mcp__perplexity__perplexity_research`:
> "For <ICP>: estimate TAM and SAM in the US, average deal size for adjacent services, who owns the budget, typical sales cycle, current alternative solutions (named tools and consultancies), and switching costs. Cite sources."

Append response text + citations to the fetch log.

**Bucket C — Growth + funding**

1. Call `mcp__perplexity__perplexity_search`:
> "Funding rounds, M&A, new entrants, and regulatory shifts affecting <ICP> in the last 18 months. Name companies and amounts."
2. Call `uv run python -m scout trends --keywords "<canonical-keyword>"`.

Append both responses to the fetch log.

**Bucket D — Competitor scan**

Call `mcp__perplexity__perplexity_search`:
> "Who serves <ICP> today (consultancies, tools, agencies)? What do they charge? What are common complaints about them? Cite sources."

Append response to fetch log.

### Step 3 — Synthesize

Build the bundle JSON. **Customer quote verification is enforced by the writer — any quote whose text doesn't appear (whitespace+case normalized) in the fetch log will be dropped before the file is written.**

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
    {"text": "Lead routing is killing me, we tried 3 tools and none of them stick", "source": "r/revops", "date": "2026-04-18", "url": "https://reddit.com/r/revops/comments/abc"}
  ],
  "offer_hypothesis": "**RevOps leaders at 50-300 person B2B SaaS** struggle with **lead-routing chaos across multiple tools**; would pay **$4-8K/month** for **an AI agent that owns routing logic + reports anomalies, set up in <14 days**.\n\n- **Why this price:** evidence...\n- **Why this mechanism:** evidence...\n- **What would kill it:** risks...",
  "buyer_profile": "...",
  "competitive_landscape": "...",
  "growth_tailwinds": "...",
  "risks": "...",
  "sources": ["https://..."]
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
