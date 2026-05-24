"""CLI dispatch — `python -m scout <subcommand>`. JSON in, JSON out."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
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


def _split_scope(scope_arg: str | None) -> list[str] | None:
    if not scope_arg:
        return None
    parts = [p.strip() for p in scope_arg.split(",") if p.strip()]
    return parts or None


def cmd_reddit(args: argparse.Namespace) -> int:
    from scout.sources.reddit import search
    sig = search(query=args.query, limit=args.limit, scope=_split_scope(args.scope))
    _emit(sig.to_dict())
    return 0


def cmd_hackernews(args: argparse.Namespace) -> int:
    from scout.sources.hackernews import search
    sig = search(query=args.query, limit=args.limit, scope=_split_scope(args.scope))
    _emit(sig.to_dict())
    return 0


def cmd_g2(args: argparse.Namespace) -> int:
    from scout.sources.g2 import search
    sig = search(query=args.query, limit=args.limit, scope=_split_scope(args.scope))
    _emit(sig.to_dict())
    return 0


def cmd_quora(args: argparse.Namespace) -> int:
    from scout.sources.quora import search
    sig = search(query=args.query, limit=args.limit, scope=_split_scope(args.scope))
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


def _render_structured_sources(sources: dict) -> list[str]:
    """Render the structured sources dict into markdown lines."""
    lines: list[str] = []

    reddit = sources.get("reddit", {})
    if reddit:
        subs = reddit.get("subreddits", [])
        threads = reddit.get("threads_inspected", 0)
        q = reddit.get("queries", 0)
        lines.append(f"**Reddit:** {q} queries across {len(subs)} subreddits, {threads} threads inspected")
        if subs:
            lines.append(f"  - {', '.join(subs)}")

    hn = sources.get("hackernews")
    if hn is not None:
        threads = hn.get("threads_inspected", 0)
        q = hn.get("queries", 0)
        note = hn.get("note", "")
        line = f"**Hacker News:** {q} queries, {threads} threads inspected"
        if note:
            line += f" — {note}"
        lines.append(line)

    g2 = sources.get("g2")
    if g2 is not None:
        q = g2.get("queries", 0)
        pages = g2.get("pages_inspected", 0)
        note = g2.get("note", "")
        line = f"**G2/Capterra:** {q} queries, {pages} pages inspected"
        if note:
            line += f" — {note}"
        lines.append(line)

    quora = sources.get("quora")
    if quora is not None:
        q = quora.get("queries", 0)
        pages = quora.get("pages_inspected", 0)
        note = quora.get("note", "")
        line = f"**Quora:** {q} queries, {pages} pages inspected"
        if note:
            line += f" — {note}"
        lines.append(line)

    pplx = sources.get("perplexity")
    if pplx:
        lines.append(f"**Perplexity:** {pplx.get('queries', 0)} queries (power + target + growth signals)")

    gt = sources.get("google_trends")
    if gt:
        lines.append(f"**Google Trends:** {gt.get('keywords_queried', 0)} keywords queried")

    return lines


def cmd_write_scan(args: argparse.Namespace) -> int:
    bundle = _load_input(args.input)
    today = date.today().isoformat()
    out_path = RUNS_DIR / "scans" / f"{today}-scan.md"

    ranked = bundle.get("ranked", [])

    body_lines: list[str] = [
        f"# Market Scan — {today}",
        "",
        "## Top 25 (ranked by composite)",
        "",
        "| # | ICP | Pain | Power | Target | Growth | Composite | Sat | Category |",
        "|---|-----|------|-------|--------|--------|-----------|-----|----------|",
    ]
    for idx, row in enumerate(ranked, 1):
        cs = row.get("criterion_scores", {})
        sat = (row.get("saturation_risk", "Low") or "Low")[0]
        body_lines.append(
            f"| {idx} | {row['icp']} | {cs.get('pain', 0):.1f} | {cs.get('purchasing_power', 0):.1f} | "
            f"{cs.get('easy_to_target', 0):.1f} | {cs.get('growing', 0):.1f} | {row.get('composite', 0):.1f} | "
            f"{sat} | {row.get('category', '')} |"
        )

    cat_counts = Counter(row.get("category", "") for row in ranked if row.get("category", ""))
    total = len(ranked)
    over_rep = [(cat, cnt) for cat, cnt in cat_counts.items() if total > 0 and cnt / total > 0.50]
    if over_rep:
        body_lines.append("")
        flags = "; ".join(f"**{cat}** {cnt} of {total} ({cnt/total:.0%})" for cat, cnt in over_rep)
        body_lines.append(f"> **Category distribution note:** {flags} — over-represented. Consider diversifying in next scan.")

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
        sat_risk = row.get("saturation_risk", "Low")
        sat_reason = row.get("saturation_reason", "")
        sat_penalty = row.get("saturation_penalty", 0.0)
        sat_line = f"- **Saturation Risk ({sat_risk})**"
        if sat_penalty and float(sat_penalty) != 0.0:
            sat_line += f" — {float(sat_penalty):+.1f} composite penalty"
        if sat_reason:
            sat_line += f" — {sat_reason}"
        body_lines.append(sat_line)
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
        if isinstance(sources, dict):
            body_lines += _render_structured_sources(sources)
        else:
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

    # Pain-signal sources — same shape across all four
    def _add_source_parser(name: str, func, scope_help: str) -> None:
        sp = sub.add_parser(name)
        sp.add_argument("--query", required=True, help="free-text search query")
        sp.add_argument("--scope", default=None, help=f"comma-separated {scope_help} (optional)")
        sp.add_argument("--limit", type=int, default=25)
        sp.set_defaults(func=func)

    _add_source_parser("reddit", cmd_reddit, "subreddit names")
    _add_source_parser("hackernews", cmd_hackernews, "(unused — HN has no scope)")
    _add_source_parser("g2", cmd_g2, "software category slugs")
    _add_source_parser("quora", cmd_quora, "Quora topic slugs")

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
