# Market Scout — Design Spec

**Date:** 2026-05-23
**Owner:** Jim Brown
**Purpose:** Personal market research agent for NWA Boost offer development. Surfaces "hungry markets" using Alex Hormozi's four-criteria framework (pain, purchasing power, easy to target, growing) and produces analyst-quality deep-dives with real, sourced customer language.

---

## 1. Goal

Build a Claude Code project that helps Jim answer one repeated question: *"Is this a market worth building an offer for?"*

The agent runs in two stages:
- **Stage 1 — Scan:** Returns a ranked top-25 list of B2B, US-focused, small-team-serviceable ICPs scored on the four Hormozi criteria. Generated from scratch each run (no fixed universe), filtered against an exclusion list.
- **Stage 2 — Deep-Dive:** Jim picks one market from the ranked list; the agent produces a single markdown report that supports the build-or-don't decision. Customer language must be real and sourced.

Not in scope for v1: multi-run market tracking, dashboards, scheduling, web UI, headless/cron operation.

---

## 2. Architecture

**Harness:** Claude Code itself. Slash commands are markdown skills under `.claude/commands/`. They orchestrate work; data-fetching lives in a Python package (`scout/`) called via Bash. Configs are YAML so weights, exclusions, and seeds can be tuned without code edits. Outputs are flat, date-stamped markdown files.

### 2.1 Directory Layout

```
Market Scout/
├── .claude/
│   ├── commands/
│   │   ├── scan.md
│   │   └── deep-dive.md
│   └── settings.local.json
├── scout/
│   ├── __init__.py
│   ├── sources/
│   │   ├── perplexity.py
│   │   ├── firecrawl.py
│   │   ├── reddit.py
│   │   └── trends.py
│   ├── scoring.py
│   ├── filters.py
│   └── io.py
├── runs/
│   ├── scans/                    # YYYY-MM-DD-scan.md
│   └── deep-dives/               # YYYY-MM-DD-<icp-slug>.md
├── config/
│   ├── exclusions.yaml
│   ├── rubric.yaml
│   └── seeds.yaml
├── docs/superpowers/specs/       # this file
├── .env.example
├── pyproject.toml
└── README.md
```

### 2.2 Source Modules (swappable adapters)

Each `scout/sources/<name>.py` exposes a small surface so the orchestration in the slash command doesn't care which source is behind the call.

| Module | Functions | Backing service |
|---|---|---|
| `perplexity.py` | `research(query, depth)`, `search(query, recency)` | Perplexity MCP (already configured) |
| `firecrawl.py` | `scrape(url)`, `search(query, site=)`, `extract_quotes(url)` | Firecrawl MCP (already configured) |
| `reddit.py` | `search_subs(keywords, sort, time)`, `top_threads(subreddit, limit)`, `comments(thread_id)` | PRAW + Reddit API |
| `trends.py` | `curve(keyword, timeframe='5y')`, `breakouts(keyword)` | pytrends |

Swappability: replacing a source means editing one file, no skill changes.

### 2.3 Slash Commands (orchestrators)

| Command | Args | Behavior |
|---|---|---|
| `/scan` | `focus=<category>` (opt), `count=<N>` (opt, default 25) | Generates candidates, fetches signal, scores, ranks, writes scan file |
| `/deep-dive` | `<market-id>` or `<fuzzy-name>` | Loads scan context (or fetches fresh if not in latest scan), deep-fetches, synthesizes, writes deep-dive file |

---

## 3. Stage 1 — `/scan` Flow

```
User: /scan
  │
  ▼
[1] CANDIDATE GENERATION (Claude reasoning, no external calls)
    - Brainstorm ~60 raw ICP candidates
    - Anchored on: B2B preferred, US, small-team-serviceable, tight ICP grain
    - Apply exclusions.yaml hard cuts → ~40 survivors
  │
  ▼
[2] SIGNAL FETCH (parallel where possible, per candidate)
    - PAIN:    reddit.search_subs(icp_keywords, time='90d')
    - POWER:   perplexity.research("avg deal size, budget owner, funding profile of <ICP>")
    - TARGET:  perplexity.search("trade publications, conferences, communities serving <ICP>")
    - GROWTH:  trends.curve(keywords) + perplexity.search("funding/M&A in <ICP> last 18mo")
  │
  ▼
[3] SCORE (scout/scoring.py)
    - Per criterion: sub-signals scored 1-5 with required evidence citation
    - Sub-signal lacking evidence → capped at 2
    - Criterion = avg of sub-signals
    - Composite = sum of criterion scores × weights (default 1:1:1:1) → out of 20
    - Apply hard_floors (cut candidates below thresholds)
  │
  ▼
[4] RANK + WRITE
    - Trim to top 25 by composite
    - Write runs/scans/YYYY-MM-DD-scan.md
    - Last section auto-suggests top 3 candidates to deep-dive, diversified by category
```

### 3.1 Market "Grain"

Each candidate is a **tight ICP**: role + company size + industry. Examples:
- "RevOps leaders at 50-300 person B2B SaaS"
- "Plant managers at $20-100M food/bev manufacturers"
- "VP Engineering at 30-150 person DevTool companies"

Broad categories ("HR Tech") are not valid candidates.

### 3.2 "Small-team-serviceable" Filter (with AI extension)

The filter favors ICPs an NWA Boost-sized team can serve, but explicitly assumes AI-leveraged delivery. A market that would be unservable with traditional consulting headcount is acceptable if AI agents can plausibly extend reach (e.g., scaling a 5-person team to serve 200+ accounts via agentic workflows). Concretely:

- ICPs requiring deep in-person presence or licensed humans: cut
- ICPs serviceable by ~5 humans + AI agents: keep
- ICPs requiring 50-person delivery org even with AI: cut

### 3.3 Scan File Format

```markdown
---
scan_date: 2026-05-23
focus: (optional)
candidates_generated: 60
candidates_scored: 38
top_n: 25
---

# Market Scan — 2026-05-23

## Top 25 (ranked by composite)

| # | ICP | Pain | Power | Target | Growth | Composite | Category |
|---|-----|------|-------|--------|--------|-----------|----------|
| 1 | RevOps leaders at 50-300 person B2B SaaS | 5.0 | 4.3 | 4.7 | 4.3 | 18.3 | SaaS Ops |
| 2 | ... | ... | ... | ... | ... | ... | ... |

## Why each was selected

### #1 — RevOps leaders at 50-300 person B2B SaaS
- **Pain (5.0):** 47 distinct complaint threads in r/revops + r/SaaS in last 90d; "lead routing chaos" appears in 12 threads
- **Power (4.3):** Adjacent tools (Clay, Default) at $25-80K ACV; budget held by RevOps lead at this size
- **Target (4.7):** r/revops, RevOps Co-op community, RevOps.fm pod — three concentrated channels reach majority
- **Growth (4.3):** RevOps title growth +180% on LinkedIn 2022-2026; 8 funded RevOps tooling rounds in last 12mo

[... 24 more]

## Suggested next deep-dives (top 3, diversified by category)
1. #1 — RevOps leaders at 50-300 person B2B SaaS
2. #4 — Plant managers at $20-100M food/bev manufacturers
3. #11 — Customer Education leaders at 100-500 person B2B SaaS

## Sources touched this scan
[Numbered list of every URL fetched]
```

### 3.4 Cost / Time

- ~40 candidates × 4 queries = ~160 calls
- Reddit + Trends: free
- Perplexity: ~$0.005/query × ~80 queries ≈ $0.40-2.00
- Estimated wall time: 2-4 minutes
- Acceptable for personal use; no caching needed in v1

---

## 4. Stage 2 — `/deep-dive` Flow

```
User: /deep-dive 4    (or /deep-dive revops)
  │
  ▼
[1] LOAD CONTEXT
    - Find latest runs/scans/*.md
    - Locate row by ID or fuzzy match on ICP slug
    - Pull row scores, rationale, source URLs
    - If not in latest scan: proceed anyway with fresh fetch (no scan dependency)
  │
  ▼
[2] DEEP FETCH
    a) Customer language harvest
       - reddit.top_threads(icp_subs, limit=20, sort='top', time='year')
       - firecrawl.scrape each thread → extract_quotes
       - firecrawl.search G2/Capterra/TrustRadius reviews for ICP-relevant tools
       - Filter quotes: keep those with concrete pain, urgency, dollar mentions, or "I wish someone would..."
       - Tag each: source URL, date, subreddit/site, original handle (anonymized if not public-by-default)

    b) Market sizing + buyer profile
       - perplexity.research("<ICP> TAM, SAM, avg deal size, budget owner, sales cycle, current alternatives, switching costs")

    c) Growth + funding evidence
       - perplexity.search("<ICP> funding M&A new entrants regulatory shifts last 18mo")
       - trends.curve(keywords, 5y)

    d) Competitor scan
       - perplexity.search("who serves <ICP>, pricing, gaps in delivery")
  │
  ▼
[3] SYNTHESIZE → runs/deep-dives/YYYY-MM-DD-<icp-slug>.md
```

### 4.1 Quote Integrity (enforced)

Every customer quote in the deep-dive must carry an inline source link.

**Fetch log:** during a deep-dive run, `scout/io.py` writes a transient `runs/.tmp/<icp-slug>-fetch.jsonl` log capturing each external call's URL + raw response text. Before the deep-dive markdown is written, every quote string is verified to appear (case-insensitive, whitespace-normalized) within at least one logged response. Unverified quotes are dropped. The log is deleted after a successful write; kept for inspection on failure.

Trade-off accepted: fewer quotes that are real beats many that are plausible.

### 4.2 Offer Hypothesis (enforced template)

Required format:
> **[ICP] struggles with [specific pain]; would pay $[range] for [delivered outcome via mechanism] within [timeline].**

If any slot can't be filled from harvested evidence, the section explicitly says so:
> "Could not size deal value from sources — manual research needed."

Better to flag a gap than guess.

### 4.3 Deep-Dive File Format

```markdown
---
icp: RevOps leaders at 50-300 person B2B SaaS
icp_slug: revops-saas-50-300
scan_date: 2026-05-23
deep_dive_date: 2026-05-23
composite_score: 18.3/20
sources_touched: 47
quotes_verified: 12
---

# RevOps at 50-300 person B2B SaaS

## Verdict
[1 paragraph: build or don't, with the key reason]

## Why this market scored where it did
[Cites actual signals from scan + deep fetch, not framework restatement]

## Customer language (verbatim, sourced)
> "exact quote" — r/revops, 2026-04-18, [link]
> "exact quote" — G2 review of Clay, 2026-03-02, [link]
[8-15 quotes, grouped by pain theme]

## Offer hypothesis
**RevOps leaders at 50-300 person B2B SaaS struggle with lead-routing chaos across multiple tools; would pay $4-8K/month for an AI agent that owns routing logic + reports anomalies, set up in <14 days.**

- **Why this price:** evidence
- **Why this mechanism:** evidence
- **What would kill it:** risks

## Buyer profile
- Title / seniority
- Budget owner
- Avg deal size in adjacent services
- Current alternatives + gaps

## Competitive landscape
[Who serves them, pricing, exploitable gaps]

## Growth + tailwinds
[Trends curve summary, funding, M&A, regulation]

## Risks / why this could be wrong
[Honest counter-case — what would make this a bad bet?]

## Sources
[Numbered list of every URL touched, deduplicated]
```

### 4.4 Cost / Time

- ~50-80 fetch calls per deep-dive
- Perplexity heavier here: ~$2-5 per dive
- Estimated wall time: 10-15 min
- Acceptable for a personal decision-support tool

---

## 5. Scoring Rubric (`config/rubric.yaml`)

```yaml
pain:
  signals:
    complaint_volume:
      1: "<5 threads"
      3: "20-50 threads"
      5: "100+ threads"
    emotional_intensity:
      1: "mild annoyance"
      3: "frustrated, repeated"
      5: "'I hate this', 'killing me', 'desperate'"
    willingness_signals:
      1: "none found"
      3: "2-3 instances"
      5: "6+ instances across sources"
    recency:
      1: "complaints peaked >2y ago"
      3: "steady over 12mo"
      5: "accelerating in last 6mo"

purchasing_power:
  signals:
    avg_deal_size:
      1: "<$5K/yr"
      3: "$25-100K/yr"
      5: "$250K+/yr"
    budget_authority:
      1: "needs 3+ approvals"
      3: "department head decides"
      5: "ICP holds the budget"
    funded_or_profitable:
      1: "mostly struggling"
      3: "mixed"
      5: "well-funded or profitable cohort"

easy_to_target:
  signals:
    concentrated_channels:
      1: "diffuse, no clear watering holes"
      3: "2-3 channels reach most of ICP"
      5: "1-2 channels reach 70%+"
    identifiable_titles:
      1: "fuzzy / many title variants"
      3: "moderately clean"
      5: "single canonical title"
    community_density:
      1: "none active"
      3: "a few"
      5: "vibrant, frequent posts"

growing:
  signals:
    trends_curve:
      1: "declining"
      3: "flat"
      5: "up >50% in 24mo"
    funding_momentum:
      1: "no rounds in 18mo"
      3: "occasional"
      5: "multiple rounds, increasing size"
    structural_tailwind:
      1: "none"
      3: "one"
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

**Scoring mechanics:**
- Each sub-signal scored 1-5 with a one-line evidence citation (URL or quoted phrase)
- Sub-signals lacking evidence are capped at 2
- Criterion score = average of sub-signal scores
- Composite = sum of (criterion × weight), out of 20 when weights = 1.0
- Hard floors cut candidates regardless of composite (the broke-buyer guard)

---

## 6. Exclusions (`config/exclusions.yaml`)

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

Applied at two points:
1. **Candidate generation:** Claude does not propose excluded ICPs.
2. **Post-fetch:** If signal reveals an ICP is in fact a hidden match for an excluded buyer profile (e.g., turns out to mostly be broke solopreneurs), it's cut before scoring.

Soft penalties: candidate allowed but `easy_to_target` final score is reduced by 1 point (floor 1) to reflect channel/payment friction.

---

## 7. Setup (one-time, ~5 min)

1. `uv sync` — installs `praw`, `pytrends`, `pyyaml`, `requests`
2. Register Reddit app at `reddit.com/prefs/apps` (type: "script"); drop `client_id` + `client_secret` into `.env`
3. Confirm Perplexity + Firecrawl MCPs respond (`/mcp` in Claude Code)
4. Optional: edit `config/seeds.yaml` to pin specific categories you want covered every scan

`.env.example`:
```
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_USER_AGENT=market-scout/0.1 by <reddit-handle>
```

(Perplexity and Firecrawl run via the existing Claude MCP config — no keys needed in this project.)

---

## 8. Operational Decisions (defaults)

| Question | Default behavior |
|---|---|
| Deep-dive on a market not in the latest scan? | Allowed; fetches fresh, no scan dependency |
| Stale scans? | Files never auto-delete; each `/scan` writes a new dated file |
| Concurrency / rate limits | Reddit ~1 req/sec; Perplexity batched 5 at a time |
| Source failure mid-scan? | Skip that signal, score from what's there, note the gap in "why selected" |
| Multi-run market tracking? | Not in v1 |
| Auto-suggest next deep-dives? | Yes — last section of scan file lists top 3, diversified by category |

---

## 9. Quality Bar (definition of done)

- Scan: top-25 ICPs ranked, each with 4 sub-scores + composite + 2-3 sentence rationale citing real signals (not framework restatement)
- Deep-dive: passes the "would a sharp analyst hand this over?" test
  - 8-15 verbatim customer quotes, each with source link, all verifiable against fetch log
  - Offer hypothesis fills the enforced template with evidence per slot
  - Verdict paragraph is a clear build/don't with the key reason named
  - Honest "why this could be wrong" section
- Source modules can be replaced by editing one file
- Exclusions and rubric tunable via YAML, no code changes
- No fabrication: quotes that don't trace to a fetched URL are dropped

---

## 10. Out of Scope (v1)

- Multi-run comparison / market tracking over time
- Web UI or dashboard
- Scheduling / cron / headless operation
- Other markets beyond US-focused B2B
- Outbound list-building (this informs decisions; it doesn't fill a CRM)
- Automatic offer generation (the hypothesis is the input to *Jim's* offer work, not the offer itself)
