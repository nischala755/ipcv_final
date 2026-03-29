from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import cv2
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .analyzer import IPCVAnalyzer
from .collab import CollaborationStore
from .mistral_layer import MistralExplainer
from .policy import evaluate_policy
from .schemas import (
    DetectionResponse,
    ExplainabilityLayers,
    FactorScore,
    VerificationCreateRequest,
    VerificationVoteRequest,
)
from .security import MerkleTree, payload_integrity_checksum, sign_payload
from .source_trace import estimate_source_trace

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / "tmp"
HEATMAP_DIR = TMP_DIR / "heatmaps"
CONCEPT_DIR = TMP_DIR / "concepts"
UPLOAD_DIR = TMP_DIR / "uploads"
REPORT_DIR = TMP_DIR / "reports"
ROOT_DIR = BASE_DIR.parent

load_dotenv(ROOT_DIR / ".env")

for p in [TMP_DIR, HEATMAP_DIR, CONCEPT_DIR, UPLOAD_DIR, REPORT_DIR]:
    p.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="VeriLens Forensics", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=str(TMP_DIR)), name="static")

analyzer = IPCVAnalyzer()
explainer = MistralExplainer()
collab_store = CollaborationStore()
SIGNING_SECRET = os.getenv("SIGNING_SECRET", "authlab-default-secret")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze", response_model=DetectionResponse)
async def analyze(file: UploadFile = File(...), policy_profile: str = Query("social")) -> DetectionResponse:
    suffix = Path(file.filename or "upload.bin").suffix.lower()
    temp_name = f"{uuid.uuid4().hex}{suffix}"
    upload_path = UPLOAD_DIR / temp_name

    with upload_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    try:
        media_type, confidence_fake, factors_raw, reality_drift, fingerprint, heatmap, concept_visuals, analysis_meta = analyzer.analyze(upload_path)

        heatmap_path = None
        if heatmap is not None:
            heatmap_name = f"{uuid.uuid4().hex}.png"
            heatmap_file = HEATMAP_DIR / heatmap_name
            cv2.imwrite(str(heatmap_file), heatmap)
            heatmap_path = f"/static/heatmaps/{heatmap_name}"

        concept_map_paths = {}
        for concept_name, concept_img in concept_visuals.items():
            concept_file_name = f"{uuid.uuid4().hex}.png"
            concept_file = CONCEPT_DIR / concept_file_name
            cv2.imwrite(str(concept_file), concept_img)
            concept_map_paths[concept_name] = f"/static/concepts/{concept_file_name}"

        explanation_raw = explainer.explain(factors_raw, confidence_fake, reality_drift, media_type)
        trust_score = max(0.0, min(1.0, 1.0 - confidence_fake * 0.85 - reality_drift * 0.15))

        policy_decision = evaluate_policy(policy_profile, confidence_fake, reality_drift)
        source_trace = estimate_source_trace(upload_path, media_type, factors_raw)

        merkle_items = [
            f"{f['name']}:{f['score']:.6f}"
            for f in factors_raw
        ] + analysis_meta.get("frame_hashes", [])
        merkle_root = MerkleTree.from_items(merkle_items).root()

        report_id = uuid.uuid4().hex
        report_payload = {
            "report_id": report_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "media_type": media_type,
            "confidence_fake": confidence_fake,
            "trust_score": trust_score,
            "reality_drift_score": reality_drift,
            "factors": factors_raw,
            "fingerprint": fingerprint,
            "source_trace": source_trace,
            "policy_decision": policy_decision,
            "merkle_root": merkle_root,
            "analysis_meta": analysis_meta,
            "concept_maps": concept_map_paths,
            "explanation": explanation_raw,
        }
        report_payload["integrity_checksum"] = payload_integrity_checksum(report_payload)
        report_signature = sign_payload(report_payload, SIGNING_SECRET)
        report_payload["signature"] = report_signature
        report_file = REPORT_DIR / f"{report_id}.json"
        report_file.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

        return DetectionResponse(
            media_type=media_type,
            confidence_fake=confidence_fake,
            trust_score=trust_score,
            factors=[FactorScore(**f) for f in factors_raw],
            reality_drift_score=reality_drift,
            visual_authenticity_fingerprint=fingerprint,
            merkle_root=merkle_root,
            source_trace=source_trace,
            policy_decision=policy_decision,
            report_id=report_id,
            report_signature=report_signature,
            explanation=ExplainabilityLayers(**explanation_raw),
            heatmap_path=heatmap_path,
            concept_maps=concept_map_paths,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Analysis failed: {str(exc)}") from exc
    finally:
        if upload_path.exists():
            upload_path.unlink(missing_ok=True)


@app.get("/reports/{report_id}.json")
def get_report_json(report_id: str):
    report_file = REPORT_DIR / f"{report_id}.json"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(str(report_file), media_type="application/json")


@app.get("/reports/{report_id}.pdf")
def get_report_pdf(report_id: str):
    report_file = REPORT_DIR / f"{report_id}.json"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report not found")

    report = json.loads(report_file.read_text(encoding="utf-8"))
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    y = 760
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, "VeriLens Forensics - Forensic Report")
    y -= 26
    pdf.setFont("Helvetica", 10)
    lines = [
        f"Report ID: {report_id}",
        f"Generated: {report.get('generated_at', '')}",
        f"Media Type: {report.get('media_type', '')}",
        f"Fake Confidence: {report.get('confidence_fake', 0):.3f}",
        f"Trust Score: {report.get('trust_score', 0):.3f}",
        f"Reality Drift: {report.get('reality_drift_score', 0):.3f}",
        f"Merkle Root: {report.get('merkle_root', '')}",
        f"Integrity Checksum: {report.get('integrity_checksum', '')}",
        f"Signature: {report.get('signature', '')}",
    ]
    for line in lines:
        pdf.drawString(40, y, line)
        y -= 16
    if y < 80:
        pdf.showPage()
    pdf.save()
    buffer.seek(0)
    return StreamingResponse(buffer, media_type="application/pdf")


@app.post("/verify/cases")
def create_case(payload: VerificationCreateRequest):
    case = collab_store.create_case(payload.report_id, payload.media_hint)
    return {
        "id": case.id,
        "report_id": case.report_id,
        "media_hint": case.media_hint,
        "status": case.status,
        "votes": case.votes,
    }


@app.post("/verify/cases/{case_id}/vote")
def vote_case(case_id: str, payload: VerificationVoteRequest):
    try:
        case = collab_store.vote(case_id, payload.reviewer, payload.verdict, payload.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc

    return {
        "id": case.id,
        "report_id": case.report_id,
        "media_hint": case.media_hint,
        "status": case.status,
        "votes": case.votes,
    }


@app.get("/verify/cases/{case_id}")
def get_case(case_id: str):
    try:
        case = collab_store.get_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    return {
        "id": case.id,
        "report_id": case.report_id,
        "media_hint": case.media_hint,
        "status": case.status,
        "votes": case.votes,
    }
