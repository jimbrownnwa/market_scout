from pathlib import Path

import pytest
import yaml

from scout.filters import (
    load_exclusions,
    is_excluded,
    soft_penalty_score,
)


@pytest.fixture
def exclusions(tmp_path):
    data = {
        "categories": [
            "AI automation agencies / consultancies",
            "Legal services / law firms",
        ],
        "buyer_profiles": [
            "Solopreneurs without recurring revenue",
            "Pre-revenue founders",
        ],
        "soft_penalties": [
            "Crypto/Web3 native businesses",
            "Cannabis",
        ],
    }
    path = tmp_path / "exclusions.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return load_exclusions(path)


def test_load_exclusions_returns_three_lists(exclusions):
    assert len(exclusions["categories"]) == 2
    assert len(exclusions["buyer_profiles"]) == 2
    assert len(exclusions["soft_penalties"]) == 2


def test_is_excluded_blocks_category_match(exclusions):
    excluded, reason = is_excluded("Founders of AI automation agencies serving SMBs", exclusions)
    assert excluded is True
    assert "AI automation" in reason


def test_is_excluded_blocks_buyer_profile_match(exclusions):
    excluded, reason = is_excluded("Solopreneurs without recurring revenue, building courses", exclusions)
    assert excluded is True
    assert "Solopreneur" in reason or "solopreneur" in reason.lower()


def test_is_excluded_allows_unrelated_icp(exclusions):
    excluded, reason = is_excluded("RevOps leaders at 50-300 person B2B SaaS", exclusions)
    assert excluded is False
    assert reason == ""


def test_soft_penalty_score_returns_one_when_match(exclusions):
    assert soft_penalty_score("Crypto/Web3 trading desks at small hedge funds", exclusions) == 1


def test_soft_penalty_score_returns_zero_when_no_match(exclusions):
    assert soft_penalty_score("RevOps leaders at 50-300 person B2B SaaS", exclusions) == 0
