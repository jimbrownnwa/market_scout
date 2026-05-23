"""Exclusion filtering for ICP candidates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_exclusions(path: Path | str) -> dict[str, list[str]]:
    """Load exclusions YAML. Returns dict with keys: categories, buyer_profiles, soft_penalties."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {
        "categories": data.get("categories", []) or [],
        "buyer_profiles": data.get("buyer_profiles", []) or [],
        "soft_penalties": data.get("soft_penalties", []) or [],
    }


def _matches_any(text: str, patterns: list[str]) -> str | None:
    text_l = text.lower().replace("/", " ")
    for pat in patterns:
        # Use the first 2-3 meaningful words of each pattern as the match key
        key = " ".join(pat.lower().replace("/", " ").split()[:2])
        if key and key in text_l:
            return pat
    return None


def is_excluded(icp_description: str, exclusions: dict[str, list[str]]) -> tuple[bool, str]:
    """Return (excluded?, reason). Reason names the matched exclusion."""
    matched = _matches_any(icp_description, exclusions.get("categories", []))
    if matched:
        return True, f"category match: {matched}"
    matched = _matches_any(icp_description, exclusions.get("buyer_profiles", []))
    if matched:
        return True, f"buyer profile match: {matched}"
    return False, ""


def soft_penalty_score(icp_description: str, exclusions: dict[str, list[str]]) -> int:
    """Return the number of soft penalties matched (used as a 1-point reduction on easy_to_target)."""
    matched = _matches_any(icp_description, exclusions.get("soft_penalties", []))
    return 1 if matched else 0
