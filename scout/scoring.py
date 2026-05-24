"""Rubric loading, sub-signal scoring, and composite computation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_rubric(path: Path | str) -> dict[str, Any]:
    """Load rubric YAML and return a structured dict."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {
        "criteria": {
            name: raw.get(name, {}).get("signals", {})
            for name in ("pain", "purchasing_power", "easy_to_target", "growing")
        },
        "weights": raw.get("weights", {"pain": 1.0, "purchasing_power": 1.0, "easy_to_target": 1.0, "growing": 1.0}),
        "hard_floors": raw.get("hard_floors", {}),
        "saturation_penalties": raw.get("saturation_penalties", {"High": -2.0, "Medium": -1.0, "Low": 0.0}),
    }


def score_signal(declared: int, evidence: str) -> int:
    """Cap at 2 if no evidence; clamp to [1, 5]."""
    score = max(1, min(5, int(declared)))
    if not evidence or not evidence.strip():
        score = min(score, 2)
    return score


def score_criterion(name: str, sub_signals: dict[str, dict[str, Any]], rubric: dict[str, Any]) -> float:
    """Average all sub-signal scores for a criterion."""
    expected_signals = rubric["criteria"].get(name, {})
    scores: list[int] = []
    for sig_name in expected_signals:
        sig = sub_signals.get(sig_name, {})
        scores.append(score_signal(sig.get("score", 0), sig.get("evidence", "")))
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def score_candidate(candidate: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
    """Compute criterion scores, composite, hard floor cuts, soft penalty, and saturation penalty.

    Input candidate dict: {icp, soft_penalty (0 or 1), saturation_risk ("Low"|"Medium"|"High"), criteria: {...}}
    Returns: {icp, criterion_scores, composite, cut, cut_reason, saturation_risk, saturation_penalty}
    """
    criterion_scores: dict[str, float] = {}
    for crit_name in ("pain", "purchasing_power", "easy_to_target", "growing"):
        sub = candidate.get("criteria", {}).get(crit_name, {})
        criterion_scores[crit_name] = score_criterion(crit_name, sub, rubric)

    # Apply soft penalty: -1 on easy_to_target, floor 1
    penalty = int(candidate.get("soft_penalty", 0) or 0)
    if penalty:
        criterion_scores["easy_to_target"] = max(1.0, criterion_scores["easy_to_target"] - 1)

    # Hard floors — evaluated before saturation penalty
    cut = False
    cut_reason = ""
    for crit_name, floor in rubric.get("hard_floors", {}).items():
        if criterion_scores.get(crit_name, 0) <= floor:
            cut = True
            cut_reason = f"{crit_name} score {criterion_scores[crit_name]:.1f} <= floor {floor}"
            break

    # Composite (weighted sum)
    weights = rubric.get("weights", {})
    composite = sum(criterion_scores[c] * weights.get(c, 1.0) for c in criterion_scores)

    # Saturation penalty — applied to composite after hard-floor check
    sat_risk = candidate.get("saturation_risk", "Low") or "Low"
    sat_penalties = rubric.get("saturation_penalties", {"High": -2.0, "Medium": -1.0, "Low": 0.0})
    sat_penalty = float(sat_penalties.get(sat_risk, 0.0))
    composite += sat_penalty

    return {
        "icp": candidate.get("icp", ""),
        "criterion_scores": criterion_scores,
        "composite": round(composite, 2),
        "cut": cut,
        "cut_reason": cut_reason,
        "saturation_risk": sat_risk,
        "saturation_penalty": sat_penalty,
    }
