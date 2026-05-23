from pathlib import Path

import pytest

from scout.scoring import (
    load_rubric,
    score_signal,
    score_criterion,
    score_candidate,
)


RUBRIC_PATH = Path(__file__).parent.parent / "config" / "rubric.yaml"


@pytest.fixture
def rubric():
    return load_rubric(RUBRIC_PATH)


def test_load_rubric_has_all_four_criteria(rubric):
    assert set(rubric["criteria"].keys()) == {"pain", "purchasing_power", "easy_to_target", "growing"}
    assert rubric["weights"]["pain"] == 1.0
    assert rubric["hard_floors"]["purchasing_power"] == 1


def test_score_signal_caps_at_2_when_no_evidence(rubric):
    score = score_signal(declared=5, evidence="")
    assert score == 2


def test_score_signal_uses_declared_when_evidence_present(rubric):
    score = score_signal(declared=4, evidence="47 threads on r/revops in last 90d")
    assert score == 4


def test_score_signal_clamps_to_1_5(rubric):
    assert score_signal(declared=0, evidence="any") == 1
    assert score_signal(declared=7, evidence="any") == 5


def test_score_criterion_averages_subsignals(rubric):
    sub_signals = {
        "complaint_volume": {"score": 5, "evidence": "found 100+ threads"},
        "emotional_intensity": {"score": 4, "evidence": "many 'I hate this' posts"},
        "willingness_signals": {"score": 5, "evidence": "8 'I'd pay anything' instances"},
        "recency": {"score": 4, "evidence": "uptrend last 6mo"},
    }
    crit_score = score_criterion("pain", sub_signals, rubric)
    assert crit_score == pytest.approx((5 + 4 + 5 + 4) / 4)


def test_score_candidate_computes_composite_with_default_weights(rubric):
    candidate = {
        "icp": "RevOps leaders at 50-300 person B2B SaaS",
        "criteria": {
            "pain": {
                "complaint_volume": {"score": 5, "evidence": "x"},
                "emotional_intensity": {"score": 5, "evidence": "x"},
                "willingness_signals": {"score": 5, "evidence": "x"},
                "recency": {"score": 5, "evidence": "x"},
            },
            "purchasing_power": {
                "avg_deal_size": {"score": 4, "evidence": "x"},
                "budget_authority": {"score": 4, "evidence": "x"},
                "funded_or_profitable": {"score": 4, "evidence": "x"},
            },
            "easy_to_target": {
                "concentrated_channels": {"score": 5, "evidence": "x"},
                "identifiable_titles": {"score": 5, "evidence": "x"},
                "community_density": {"score": 5, "evidence": "x"},
            },
            "growing": {
                "trends_curve": {"score": 4, "evidence": "x"},
                "funding_momentum": {"score": 4, "evidence": "x"},
                "structural_tailwind": {"score": 4, "evidence": "x"},
            },
        },
    }
    result = score_candidate(candidate, rubric)
    assert result["composite"] == pytest.approx(18.0)
    assert result["criterion_scores"]["pain"] == pytest.approx(5.0)
    assert result["cut"] is False


def test_hard_floor_cuts_candidate(rubric):
    candidate = {
        "icp": "Broke solopreneurs",
        "criteria": {
            "pain": {
                "complaint_volume": {"score": 5, "evidence": "x"},
                "emotional_intensity": {"score": 5, "evidence": "x"},
                "willingness_signals": {"score": 5, "evidence": "x"},
                "recency": {"score": 5, "evidence": "x"},
            },
            "purchasing_power": {
                "avg_deal_size": {"score": 1, "evidence": "x"},
                "budget_authority": {"score": 1, "evidence": "x"},
                "funded_or_profitable": {"score": 1, "evidence": "x"},
            },
            "easy_to_target": {
                "concentrated_channels": {"score": 3, "evidence": "x"},
                "identifiable_titles": {"score": 3, "evidence": "x"},
                "community_density": {"score": 3, "evidence": "x"},
            },
            "growing": {
                "trends_curve": {"score": 3, "evidence": "x"},
                "funding_momentum": {"score": 3, "evidence": "x"},
                "structural_tailwind": {"score": 3, "evidence": "x"},
            },
        },
    }
    result = score_candidate(candidate, rubric)
    assert result["cut"] is True
    assert "purchasing_power" in result["cut_reason"]


def test_soft_penalty_reduces_easy_to_target(rubric):
    candidate = {
        "icp": "Crypto/Web3 trading desks",
        "soft_penalty": 1,
        "criteria": {
            "pain": {k: {"score": 3, "evidence": "x"} for k in ["complaint_volume", "emotional_intensity", "willingness_signals", "recency"]},
            "purchasing_power": {k: {"score": 3, "evidence": "x"} for k in ["avg_deal_size", "budget_authority", "funded_or_profitable"]},
            "easy_to_target": {k: {"score": 4, "evidence": "x"} for k in ["concentrated_channels", "identifiable_titles", "community_density"]},
            "growing": {k: {"score": 3, "evidence": "x"} for k in ["trends_curve", "funding_momentum", "structural_tailwind"]},
        },
    }
    result = score_candidate(candidate, rubric)
    assert result["criterion_scores"]["easy_to_target"] == pytest.approx(3.0)
