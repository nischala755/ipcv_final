from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field


class FactorScore(BaseModel):
    name: str
    score: float = Field(ge=0.0, le=1.0)
    evidence: str


class ExplainabilityLayers(BaseModel):
    beginner: str
    technical: str


class DetectionResponse(BaseModel):
    media_type: Literal["image", "video"]
    confidence_fake: float = Field(ge=0.0, le=1.0)
    trust_score: float = Field(ge=0.0, le=1.0)
    factors: List[FactorScore]
    reality_drift_score: float = Field(ge=0.0, le=1.0)
    visual_authenticity_fingerprint: Dict[str, float]
    merkle_root: str
    source_trace: Dict
    policy_decision: Dict
    report_id: str
    report_signature: str
    explanation: ExplainabilityLayers
    heatmap_path: str | None = None
    concept_maps: Dict[str, str] = Field(default_factory=dict)


class VerificationCreateRequest(BaseModel):
    report_id: str
    media_hint: str = "unknown"


class VerificationVoteRequest(BaseModel):
    reviewer: str
    verdict: Literal["real", "fake", "uncertain"]
    note: str = ""
