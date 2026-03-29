# VeriLens Forensics - IPCV Deepfake Detection Platform

Production-minded deepfake detection platform where the **core detector is strictly IPCV (no ML/DL inference)** and Mistral is used only for explanation.

## What Is Implemented Now

### Core Detection (IPCV-only)
- Frequency-domain artifact analysis (FFT proxy + spectral irregularity)
- Color-space anomaly checks (YCbCr/HSV relationships)
- Edge inconsistency detection (Canny + Sobel energy)
- Lighting and shadow mismatch checks
- JPEG blockiness + noise variance checks
- Classical face symmetry proxy (Haar + mirror comparison)
- Temporal inconsistency and optical flow inconsistency for video

### Explainability Layer (Mistral optional)
- Beginner and technical narratives
- Fallback deterministic explanation if Mistral is unavailable
- Trust score + reasoned factor mapping

### Security and Forensic Features
- **Simulated Merkle Tree** over factor stream + frame hashes
- Signed forensic report export (`.json` and `.pdf`)
- Integrity checksum and HMAC signature
- Visual Authenticity Fingerprint
- Source Trace Estimation (compression lineage graph)

### Governance and Collaboration
- Policy engine profiles:
  - `newsroom`
  - `legal`
  - `social`
- Collaborative verification queue (create case, vote, consensus status)

### Frontend + PWA
- Premium responsive UI (upload, anomaly breakdown, explainability panel, heatmap)
- Offline-ready PWA shell
- **OpenCV.js browser fallback for image analysis** when backend is unavailable

### Chrome Extension
- Right-click image/video -> Analyze for Deepfake
- Overlay authenticity summary directly on pages

### Deployment Assets
- Docker Compose with reverse proxy + static hosting
- Nginx API gateway (`/api` -> backend)
- Render backend deployment file (`render.yaml`)
- Vercel frontend config (`frontend/vercel.json`)

---

## Architecture (Textual)

```text
Browser/PWA + Chrome Extension
        |
        |  /api/analyze
        v
Nginx Gateway (docker or cloud edge)
        |
        v
FastAPI Backend
  |- IPCV Analyzer (OpenCV + NumPy)
  |    |- Image path
  |    |- Video path with parallel frame workers
  |
  |- Source Trace Estimator
  |- Policy Engine
  |- Merkle + Integrity + Signature
  |- Forensic Report Export (JSON/PDF)
  |- Collaboration Verification API
  |
  |- Mistral Explainer (secondary, explanation only)
```

---

## Novel and Practical Security Features

## 1) Reality Drift Score
Deterministic scalar measuring deviation from natural image statistics.

## 2) Simulated Merkle Tree (Implemented)
Merkle root is built from deterministic factor entries and frame hashes.
- Gives tamper-evident analysis attestations
- Supports chain-of-custody style verification

## 3) Source Trace Estimation (Implemented)
Heuristic compression lineage graph inferred from IPCV signals.
- Capture -> compression pass -> recompression/color synthesis stages

---

## API Summary

### `GET /health`
Health check.

### `POST /analyze?policy_profile={newsroom|legal|social}`
Upload media (`multipart/form-data`, key: `file`).
Returns:
- IPCV scores
- Reality drift
- Fingerprint
- Merkle root
- Policy decision
- Source trace graph
- Report id + signature
- Explainability text

### `GET /reports/{report_id}.json`
Download signed forensic JSON report.

### `GET /reports/{report_id}.pdf`
Download PDF forensic summary.

### `POST /verify/cases`
Create collaboration review case.

Body:
```json
{
  "report_id": "<id>",
  "media_hint": "optional-name"
}
```

### `POST /verify/cases/{case_id}/vote`
Cast vote.

Body:
```json
{
  "reviewer": "analyst-a",
  "verdict": "fake",
  "note": "edge seam"
}
```

### `GET /verify/cases/{case_id}`
Get status and vote history.

---

## Local Setup

## 1) Environment
A local `.env` has been created already. It includes your Mistral key and signing secret.

Important: since the key was shared in chat, rotate it in Mistral dashboard after testing.

Template:
- `.env.example`

## 2) Backend
```powershell
cd backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 3) Frontend
```powershell
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` and proxies `/api` to backend.

## 4) Chrome Extension
1. Open `chrome://extensions`
2. Enable Developer Mode
3. Load unpacked from `extension/`
4. Right-click image/video -> `Analyze for Deepfake`

---

## Smoke Tests (Already Performed)

Validated in this workspace:
- Backend compile check passed (`python -m compileall`)
- Frontend production build passed (`npm run build`)
- `GET /health` returned `{"status":"ok"}`
- `POST /analyze` succeeded with sample image
- JSON report export succeeded
- PDF report export succeeded
- Collaboration case creation + voting reached `consensus_fake`
- Docker Compose config validated (`docker compose config`)

---

## Docker Production Run

```powershell
docker compose up --build
```

- App gateway: `http://localhost:8080`
- Backend internal service: `backend:8000`

---

## Deploy Plan: Vercel + Render

## Backend on Render
- Config file: `render.yaml`
- Create a new Render Web Service from repo
- Ensure environment vars are set:
  - `MISTRAL_API_KEY`
  - `MISTRAL_MODEL`
  - `MISTRAL_BASE_URL`
  - `SIGNING_SECRET`

## Frontend on Vercel
- Root project: `frontend`
- Build command: `npm run build`
- Output: `dist`
- Update `frontend/vercel.json`:
  - Replace `https://YOUR_RENDER_BACKEND_URL` with actual Render backend URL

---

## Roadmap Status Against Requested Items

1. Move IPCV hot-path to WebAssembly/OpenCV.js for browser-side edge analysis.
- Implemented for image fallback in frontend (`frontend/src/offlineIpcv.js`).

2. Add distributed frame processing workers for long video uploads.
- Implemented as parallel frame worker execution in backend analyzer.

3. Add source trace estimation module (compression lineage graph).
- Implemented (`backend/app/source_trace.py`).

4. Add signed forensic report export (PDF/JSON with integrity checksum).
- Implemented (`/reports/{report_id}.json`, `/reports/{report_id}.pdf`).

5. Add policy engine (newsroom, legal, social moderation profiles).
- Implemented (`backend/app/policy.py` + `policy_profile` query parameter).

6. Add collaborative verification queues and analyst consensus flow.
- Implemented (`backend/app/collab.py` + `/verify/cases*` endpoints).

7. Deploy with CDN edge cache + object storage + async task queue for global scale.
- Partially implemented now:
  - Edge-like gateway via Nginx reverse proxy
  - PWA cache layer
  - Deployment-ready infra files
- Full cloud object storage and external async queue are documented as next production step.

---

## Key Files

- Backend API: `backend/app/main.py`
- IPCV engine: `backend/app/analyzer.py`
- Merkle/signing: `backend/app/security.py`
- Policy engine: `backend/app/policy.py`
- Source trace: `backend/app/source_trace.py`
- Collaboration queue: `backend/app/collab.py`
- PWA app: `frontend/src/App.jsx`
- Offline OpenCV.js: `frontend/src/offlineIpcv.js`
- Extension: `extension/background.js`, `extension/content.js`
- Docker compose: `docker-compose.yml`
- Nginx config: `deploy/nginx.conf`
- Render deployment: `render.yaml`
- Vercel deployment: `frontend/vercel.json`

---

## Security Notes

- `.env` is gitignored.
- Rotate leaked API keys before public deployment.
- Set a strong random `SIGNING_SECRET` in production.
- Restrict CORS and upload limits in production.
