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
