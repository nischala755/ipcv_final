from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class PolicyProfile:
    name: str
    review_threshold: float
    block_threshold: float


POLICIES = {
    "newsroom": PolicyProfile(name="newsroom", review_threshold=0.45, block_threshold=0.75),
    "legal": PolicyProfile(name="legal", review_threshold=0.35, block_threshold=0.65),
    "social": PolicyProfile(name="social", review_threshold=0.55, block_threshold=0.82),
}


def evaluate_policy(profile_name: str, confidence_fake: float, reality_drift: float) -> Dict[str, str | float]:
    profile = POLICIES.get(profile_name, POLICIES["social"])
    composite = (confidence_fake * 0.8) + (reality_drift * 0.2)

    if composite >= profile.block_threshold:
        action = "block"
    elif composite >= profile.review_threshold:
        action = "manual_review"
    else:
        action = "allow"

    return {
        "profile": profile.name,
        "composite_score": round(composite, 4),
        "review_threshold": profile.review_threshold,
        "block_threshold": profile.block_threshold,
        "action": action,
    }
