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
