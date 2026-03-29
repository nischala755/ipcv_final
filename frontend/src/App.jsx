import { useMemo, useState } from "react";
import { analyzeImageOffline } from "./offlineIpcv";
import UploadPanel from "./components/UploadPanel";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

function scoreLabel(score) {
  if (score >= 0.75) return "High Suspicion";
  if (score >= 0.45) return "Moderate Suspicion";
  return "Likely Authentic";
}

function pct(score) {
  return `${(score * 100).toFixed(1)}%`;
}

export default function App() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [technical, setTechnical] = useState(false);
  const [analysisMode, setAnalysisMode] = useState("server");

  const sortedFactors = useMemo(() => {
    if (!result?.factors) return [];
    return [...result.factors].sort((a, b) => b.score - a.score);
  }, [result]);

  const explainText = technical ? result?.explanation?.technical || "" : result?.explanation?.beginner || "";
  const explainParagraphs = useMemo(
    () => explainText.split(/\n{2,}/).map((p) => p.trim()).filter(Boolean),
    [explainText]
  );

  async function analyze(file) {
    setLoading(true);
    setError("");
    setResult(null);
    setAnalysisMode("server");

    try {
      const form = new FormData();
      form.append("file", file);

      const res = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const payload = await res.json();
        throw new Error(payload.detail || "Analysis failed");
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      const isImage = file.type.startsWith("image/");
      if (isImage) {
        try {
          const offline = await analyzeImageOffline(file);
          setResult(offline);
          setAnalysisMode("offline-opencvjs");
        } catch (offlineErr) {
          setError(offlineErr.message || err.message || "Unexpected error");
        }
      } else {
        setError(err.message || "Unexpected error");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <p className="eyebrow">VeriLens Forensics Platform</p>
        <h1>VeriLens Forensics</h1>
        <p className="subtitle">
          Deterministic deepfake detection using frequency, color, temporal, compression, and optical-flow signatures.
        </p>
      </header>

      <UploadPanel onFileSelected={analyze} loading={loading} />

      {error && <section className="error-box">{error}</section>}

      {loading && (
        <section className="pulse-card">
          <div className="pulse-bar" />
          <p>Running multi-factor IPCV checks and generating explainability narrative...</p>
        </section>
      )}

      {result && (
        <section className="results-grid">
          <article className="score-card">
            <p className="metric-title">Fake Confidence</p>
            <p className="metric-value">{pct(result.confidence_fake)}</p>
            <p className="metric-caption">{scoreLabel(result.confidence_fake)}</p>
            <p className="mode-chip">Mode: {analysisMode === "server" ? "Cloud IPCV" : "Offline OpenCV.js"}</p>
            <div className="meter">
              <span style={{ width: `${(result.confidence_fake * 100).toFixed(2)}%` }} />
            </div>
            <p className="small">Trust Score: {pct(result.trust_score)}</p>
            <p className="small">Reality Drift: {pct(result.reality_drift_score)}</p>
          </article>

          <article className="explain-card">
            <div className="toggle-row">
              <h3>Explainability</h3>
              <button className="ghost" onClick={() => setTechnical((v) => !v)}>
                {technical ? "Beginner View" : "Technical View"}
              </button>
            </div>
            <div className="explanation-text">
              {explainParagraphs.map((paragraph, idx) => (
                <p key={idx}>{paragraph}</p>
              ))}
            </div>
          </article>

          <article className="factor-card">
            <h3>Anomaly Breakdown</h3>
            <ul>
              {sortedFactors.map((factor) => (
                <li key={factor.name}>
                  <div className="factor-head">
                    <span>{factor.name}</span>
                    <span>{pct(factor.score)}</span>
                  </div>
                  <div className="meter mini">
                    <span style={{ width: `${(factor.score * 100).toFixed(2)}%` }} />
                  </div>
                  <p>{factor.evidence}</p>
                </li>
              ))}
            </ul>
          </article>

          <article className="heatmap-card">
            <h3>Artifact Heatmap</h3>
            {result.heatmap_path ? (
              <img src={`${API_BASE}${result.heatmap_path}`} alt="Artifact heatmap" />
            ) : result.heatmap_data_url ? (
              <img src={result.heatmap_data_url} alt="Artifact heatmap" />
            ) : (
              <p>Heatmap unavailable for this media.</p>
            )}
          </article>

          {result.concept_maps && Object.keys(result.concept_maps).length > 0 && (
            <article className="concept-card">
              <h3>IPCV Concept Visualizations</h3>
              <div className="concept-grid">
                {Object.entries(result.concept_maps).map(([name, path]) => (
                  <div className="concept-item" key={name}>
                    <h4>{name.replaceAll("_", " ")}</h4>
                    <img src={`${API_BASE}${path}`} alt={name} />
                  </div>
                ))}
              </div>
            </article>
          )}

          <article className="fingerprint-card">
            <h3>Visual Authenticity Fingerprint</h3>
            <div className="fingerprint-grid">
              {Object.entries(result.visual_authenticity_fingerprint).map(([key, value]) => (
                <div key={key}>
                  <label>{key}</label>
                  <strong>{Number(value).toFixed(4)}</strong>
                </div>
              ))}
            </div>

            {result.policy_decision && (
              <div className="policy-box">
                <h4>Policy Decision</h4>
                <p>
                  Profile: <strong>{result.policy_decision.profile}</strong>
                </p>
                <p>
                  Action: <strong>{result.policy_decision.action}</strong>
                </p>
                <p>Composite Score: {pct(result.policy_decision.composite_score)}</p>
              </div>
            )}

            {result.merkle_root && (
              <div className="attest-box">
                <h4>Integrity Attestation</h4>
                <p className="mono">Merkle Root: {result.merkle_root}</p>
                <p className="mono">Signature: {result.report_signature}</p>
              </div>
            )}

            {result.report_id && (
              <div className="report-links">
                <a href={`${API_BASE}/reports/${result.report_id}.json`} target="_blank" rel="noreferrer">
                  Download JSON Report
                </a>
                <a href={`${API_BASE}/reports/${result.report_id}.pdf`} target="_blank" rel="noreferrer">
                  Download PDF Report
                </a>
              </div>
            )}
          </article>
        </section>
      )}
    </main>
  );
}
