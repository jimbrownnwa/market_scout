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
{
  "icp": "...",
  "category": "...",
  "query": "lead routing chaos",
  "reddit_subs": ["revops", "saas"],
  "g2_categories": ["sales-engagement"],
  "quora_topics": ["sales-operations"]
}
```
`query` is the free-text search phrase used across all pain sources. The per-source `*_scope` lists tell each adapter where to look (Reddit subs, G2 categories, Quora topics). HN ignores scope.

**Category assignment:** Assign each candidate one category from this fixed taxonomy:
- `Trades / Field Services` — HVAC, plumbing, electrical, construction contractors; use for *technician/worker/field-service company* ICPs
- `B2B SaaS Ops` — RevOps, CS Ops, Marketing Ops, DevEx, demand gen at SaaS companies
- `Professional Services` — accounting firms, legal ops, marketing agencies, consulting shops
- `Verticalized SMB` — dental groups, MSPs, freight brokers, landscaping business owners; use for *owner/operator* ICPs in small verticals not covered by other categories
- `Mid-Market Functions` — fleet mgmt, finance ops, supply chain, procurement at mid-market cos
- `Regulated Industries` — cybersecurity, compliance, legal ops at regulated enterprises
- `Infrastructure & IT` — IT ops, DevOps, platform engineering at tech-heavy companies

Write the category into each candidate JSON object's `"category"` field. After scoring is complete, note in the output if any category accounts for more than 50% of the top 25 — the `write-scan` command will flag it automatically, but you should be aware.

### Step 2 — Apply exclusions

```bash
uv run python -m scout filter --input runs/.tmp/<scan-id>/candidates.json > runs/.tmp/<scan-id>/filtered.json
```

The `kept` array becomes the working set. Each kept candidate now has `soft_penalty: 0 or 1`.

### Step 3 — Fetch signals per candidate (batched)

For each candidate in `kept`, gather four signal bundles. Batch 5 candidates at a time to manage cost.

**Citation rule (applies to all signals, all steps):** Every specific numeric claim — dollar amounts, deal counts, CAGRs, market sizes, funding amounts, subscriber counts — must include an inline source URL. Format: `"$240B market (Gartner, https://...)"`.

If you cannot produce a URL for a statistic:
- Mark it `(unverified)` rather than presenting it as fact
- Do not cite "per Perplexity data" — surface the underlying source Perplexity used
- If Perplexity provides a claim without a traceable URL, mark it `(unverified — no source URL)`

This citation rule applies to all rationale fields, evidence strings, and the Why Each section of the scan output.

**PAIN signal** — four pain sources, each toggleable in `config/sources.yaml`. Load that file first and skip any source marked `enabled: false`.

All four sources share the same CLI shape: `--query "<phrase>" --scope "<comma-list>" --limit N`. Each returns the same `SourceSignal` JSON: `{source, query, item_count, items, summary}` where each item has `{id, title, text, url, score, date, author, ...}`.

```bash
# Reddit (Apify-backed; needs APIFY_TOKEN)
uv run python -m scout reddit --query "<phrase>" --scope "<reddit_subs>" --limit 15

# Hacker News (Algolia public API; no auth)
uv run python -m scout hackernews --query "<phrase>" --limit 15

# G2/Capterra (Apify; only pulls 1-3 star reviews by default)
uv run python -m scout g2 --query "<phrase>" --scope "<g2_categories>" --limit 15

# Quora (Apify)
uv run python -m scout quora --query "<phrase>" --scope "<quora_topics>" --limit 15
```

Concatenate the `items` arrays from all enabled sources into a single pain-signal corpus for this candidate. The corpus is what you scan for verbatim phrases, complaint volume, and willingness signals.

**Pain evidence quality rule:** Before scoring each candidate's pain criterion, extract at least one verbatim quoted snippet (10–30 words) from the fetched corpus with its source URL. Use this as the lead evidence for `emotional_intensity` and `willingness_signals`. Thread volume counts ("47 threads") are supplementary — they must not be the only evidence.

If no direct quotable snippet is found:
- Cap `emotional_intensity` at score 2 (treat as missing evidence)
- Cap `willingness_signals` at score 2 (treat as missing evidence)
- Do not pad evidence fields with "N threads about X" phrasing as if that were a quote

Format for evidence strings that include a quote:
`'"[10-30 word verbatim excerpt]" ([upvote-count] upvotes, r/subreddit) — [url]'`

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

**Saturation Risk assessment:** For each candidate, assess how saturated the market is with AI automation agencies / n8n-Make-Zapier consultancies already targeting this exact ICP.

Query Perplexity:
> "AI automation agencies targeting [ICP role]; Make/n8n/Zapier consultancies serving [ICP industry]; 'AI for [role]' tools or agencies in [ICP space]"

Assign `saturation_risk`:
- `High` — >5 AI automation agencies, consultancies, or "AI for [role]" SaaS products already visibly competing for this buyer; role appears in n8n/Make/Zapier marketing content
- `Medium` — 2–5 agencies visible; some competition but market not saturated
- `Low` — <2 agencies; market relatively uncontested from an AI-automation-agency angle

Write a one-sentence `saturation_reason` string (e.g. "8 AI automation agencies actively target CS Ops via Make/n8n community ads and Pavilion partnerships").

Add both fields to each candidate's scoring JSON:
```json
{
  "icp": "...",
  "saturation_risk": "High",
  "saturation_reason": "8 AI automation agencies target CS Ops...",
  ...
}
```

The scorer applies composite penalties automatically: High = −2.0, Medium = −1.0, Low = 0.0.

**Source logging:** As you run each source, maintain a running `sources_log` dict. Update it after each candidate's sources are queried:

```json
{
  "reddit": {
    "queries": "<count of candidates where Reddit was queried>",
    "subreddits": ["r/hvac", "r/msp"],
    "threads_inspected": "<sum of item_count across all Reddit responses>"
  },
  "hackernews": {
    "queries": "<count>",
    "threads_inspected": "<sum>",
    "note": "<empty string, or 'returned 0 results for most queries' if HN consistently returned 0>"
  },
  "g2": {
    "queries": "<count>",
    "pages_inspected": "<sum>",
    "note": "<empty string, or 'actor epctex/g2-scraper unavailable (HTTP 404)' if broken>"
  },
  "quora": {
    "queries": "<count>",
    "pages_inspected": "<sum>",
    "note": "<empty string, or 'actor epctex/quora-scraper unavailable (HTTP 404)' if broken>"
  },
  "perplexity": {"queries": "<count of mcp__perplexity calls made>"},
  "google_trends": {"keywords_queried": "<count>"}
}
```

If a source returns `item_count: 0` for every query, note that explicitly in its `note` field.

### Step 4 — Score each candidate

For each candidate, assemble the signal bundle into a scoring input with sub-signal scores 1-5 and a one-line evidence citation per sub-signal. Use the rubric anchors in `config/rubric.yaml` to decide 1, 3, or 5 (and 2/4 between).

**Distribution check (run after scoring all candidates):** Count how many surviving candidates scored 5.0 on each criterion. If any criterion has >30% of candidates at 5.0, you have ceiling compression. Re-score that criterion for the affected candidates using the 5-level anchors in `config/rubric.yaml` more strictly — a 5.0 requires genuinely exceptional evidence (e.g. for `concentrated_channels` a 5.0 means a named annual conference + active 10K+ Slack + canonical LinkedIn title + 100K+ community). Most ICPs should land at 2–4; reserve 5.0 for markets that clearly dominate on that dimension.

**Citation reminder:** All numeric claims in rationale fields (dollar amounts, deal counts, CAGRs, market sizes, funding amounts) must include inline source URLs per the citation rule in Step 3. Do not carry forward unverified stats from the fetch phase into rationale strings.

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
  "sources": {
    "reddit": {"queries": 40, "subreddits": ["r/hvac", "r/msp"], "threads_inspected": 312},
    "hackernews": {"queries": 40, "threads_inspected": 0, "note": "returned 0 results for most queries"},
    "g2": {"queries": 0, "pages_inspected": 0, "note": "actor epctex/g2-scraper unavailable (HTTP 404)"},
    "quora": {"queries": 0, "pages_inspected": 0, "note": "actor epctex/quora-scraper unavailable (HTTP 404)"},
    "perplexity": {"queries": 120},
    "google_trends": {"keywords_queried": 40}
  }
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

- Pain sources degrade gracefully — if Apify is unreachable, an actor is broken, or HN times out, the source returns a `SourceSignal` with `item_count: 0` and an `error` entry in `items`. The orchestrator should detect `item_count: 0` and note "no `<source>` signal — adapter unavailable" in the rationale. **Multiple pain sources** mean one outage doesn't kill the scan.
- If ALL four pain sources return zero items, cap complaint_volume and recency at score 2 (evidence: "no pain sources returned results").
- If pytrends rate-limits: retry once with 30s delay; if still fails, score `trends_curve` at 2 with evidence "pytrends rate-limited".
- If Perplexity errors: skip that signal; score the affected sub-signals at 2 with evidence noting the failure.
- Never invent quotes or evidence. Missing evidence → capped at 2.

## Cost expectations

~40 surviving candidates × ~4 queries = ~160 calls. Perplexity ~$0.40-2.00. Total wall time 2-4 minutes.
