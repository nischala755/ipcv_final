from __future__ import annotations

from pathlib import Path
from typing import Dict, List


def estimate_source_trace(file_path: Path, media_type: str, factors: List[Dict]) -> Dict:
    factor_scores = {f["name"]: float(f["score"]) for f in factors}
    jpeg_noise = factor_scores.get("jpeg_noise", 0.0)
    fft = factor_scores.get("fft_artifacts", 0.0)
    color = factor_scores.get("color_space", 0.0)

    lineage_nodes = [
        {"stage": "capture", "confidence": round(max(0.2, 1 - fft * 0.5), 3)},
        {"stage": "compression_pass_1", "confidence": round(max(0.1, 1 - jpeg_noise * 0.7), 3)},
    ]

    if jpeg_noise > 0.55:
        lineage_nodes.append({"stage": "recompression_detected", "confidence": round(jpeg_noise, 3)})
    if color > 0.6:
        lineage_nodes.append({"stage": "color_grade_or_synthesis", "confidence": round(color, 3)})
    if media_type == "video":
        lineage_nodes.append({"stage": "transcode_chain", "confidence": round((jpeg_noise + fft) / 2, 3)})

    ext = file_path.suffix.lower().lstrip(".")
    return {
        "estimated_format": ext or "unknown",
        "lineage_graph": {
            "nodes": lineage_nodes,
            "edges": [{"from": lineage_nodes[i]["stage"], "to": lineage_nodes[i + 1]["stage"]} for i in range(len(lineage_nodes) - 1)],
        },
        "summary": "IPCV-derived compression lineage estimate generated from frequency and compression artifacts.",
    }
