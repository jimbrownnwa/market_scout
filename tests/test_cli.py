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


@pytest.mark.parametrize("source_name", ["reddit", "hackernews", "g2", "quora"])
def test_cli_source_subcommand_accepts_unified_args(source_name):
    """Every source subcommand must accept --query, --scope, --limit identically."""
    proc = run_cli(source_name, "--help")
    assert proc.returncode == 0, proc.stderr
    assert "--query" in proc.stdout
    assert "--scope" in proc.stdout
    assert "--limit" in proc.stdout


def _make_bundle(candidates: list[dict], sources=None) -> dict:
    """Build a minimal final_bundle dict for write-scan tests."""
    ranked = []
    for c in candidates:
        ranked.append({
            "icp": c.get("icp", "Test ICP"),
            "category": c.get("category", "B2B SaaS Ops"),
            "saturation_risk": c.get("saturation_risk", "Low"),
            "saturation_reason": c.get("saturation_reason", ""),
            "saturation_penalty": c.get("saturation_penalty", 0.0),
            "criterion_scores": {"pain": 3.0, "purchasing_power": 3.0, "easy_to_target": 3.0, "growing": 3.0},
            "composite": c.get("composite", 12.0),
            "rationale": {"pain": "evidence", "purchasing_power": "evidence", "easy_to_target": "evidence", "growing": "evidence"},
        })
    return {
        "focus": "",
        "candidates_generated": len(candidates),
        "candidates_scored": len(candidates),
        "ranked": ranked,
        "sources": sources if sources is not None else [],
    }


def _write_scan_content(tmp_path, bundle: dict) -> str:
    """Run write-scan CLI and return the written file content."""
    in_path = tmp_path / "bundle.json"
    in_path.write_text(json.dumps(bundle), encoding="utf-8")
    proc = run_cli("write-scan", "--input", str(in_path))
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    return Path(out["path"]).read_text(encoding="utf-8")


def test_write_scan_flags_over_represented_category(tmp_path):
    candidates = (
        [{"icp": f"SaaS ICP {i}", "category": "B2B SaaS Ops"} for i in range(9)]
        + [{"icp": f"Trades ICP {i}", "category": "Trades / Field Services"} for i in range(3)]
    )
    content = _write_scan_content(tmp_path, _make_bundle(candidates))
    # 9 of 12 = 75% in B2B SaaS Ops — must flag
    assert "B2B SaaS Ops" in content
    assert "over-represented" in content.lower()


def test_write_scan_no_flag_when_no_category_dominates(tmp_path):
    candidates = (
        [{"icp": f"SaaS ICP {i}", "category": "B2B SaaS Ops"} for i in range(3)]
        + [{"icp": f"Trades ICP {i}", "category": "Trades / Field Services"} for i in range(3)]
    )
    content = _write_scan_content(tmp_path, _make_bundle(candidates))
    assert "over-represented" not in content.lower()


def test_write_scan_includes_saturation_column_and_detail(tmp_path):
    candidates = [
        {"icp": "CS Ops leads at 100-500 person B2B SaaS", "saturation_risk": "High", "saturation_reason": "8 AI automation agencies target this role", "saturation_penalty": -2.0},
        {"icp": "HVAC business owners at $2-20M", "saturation_risk": "Low", "saturation_reason": "", "saturation_penalty": 0.0},
    ]
    content = _write_scan_content(tmp_path, _make_bundle(candidates))
    # Table header has Saturation column
    assert "Sat" in content
    # Detail section shows saturation risk and reason for High market
    assert "High" in content
    assert "8 AI automation agencies" in content


def test_write_scan_renders_structured_sources(tmp_path):
    sources = {
        "reddit": {"queries": 10, "subreddits": ["r/msp", "r/hvac"], "threads_inspected": 180},
        "hackernews": {"queries": 10, "threads_inspected": 0, "note": "returned 0 results"},
        "g2": {"queries": 0, "pages_inspected": 0, "note": "actor unavailable (HTTP 404)"},
        "quora": {"queries": 0, "pages_inspected": 0, "note": "actor unavailable (HTTP 404)"},
        "perplexity": {"queries": 30},
        "google_trends": {"keywords_queried": 10},
    }
    content = _write_scan_content(tmp_path, _make_bundle([{"icp": "Test ICP"}], sources=sources))
    assert "Reddit" in content
    assert "180 threads" in content
    assert "returned 0 results" in content
    assert "actor unavailable" in content
    assert "Perplexity" in content
    assert "Google Trends" in content


def test_write_scan_flat_list_sources_still_renders(tmp_path):
    sources = ["https://reddit.com/r/msp", "https://perplexity.ai"]
    content = _write_scan_content(tmp_path, _make_bundle([{"icp": "Test ICP"}], sources=sources))
    assert "reddit.com" in content
    assert "perplexity.ai" in content
