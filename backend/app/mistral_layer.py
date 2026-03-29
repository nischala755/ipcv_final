from __future__ import annotations

import os
import re
from typing import Dict, List

import requests


class MistralExplainer:
    def __init__(self) -> None:
        self.api_key = os.getenv("MISTRAL_API_KEY", "")
        self.model = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
        self.base_url = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1/chat/completions")

    def explain(self, factors: List[Dict], confidence_fake: float, reality_drift: float, media_type: str) -> Dict[str, str]:
        if not self.api_key:
            return self._fallback(factors, confidence_fake, reality_drift)

        prompt = self._build_prompt(factors, confidence_fake, reality_drift, media_type)
        try:
            response = requests.post(
                self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": 0.2,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an explainability engine for a rule-based IPCV deepfake detector. "
                                "Never claim ML model usage. Always write clean paragraph prose only. "
                                "Do not use headings, markdown symbols, section labels, bullet points, or numbered lists."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                },
                timeout=20,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parts = content.split("\n<<TECHNICAL>>\n")
            if len(parts) >= 2:
                return {
                    "beginner": self._sanitize_paragraphs(parts[0]),
                    "technical": self._sanitize_paragraphs(parts[1]),
                }
            sanitized = self._sanitize_paragraphs(content)
            return {"beginner": sanitized, "technical": sanitized}
        except Exception:
            return self._fallback(factors, confidence_fake, reality_drift)

    def _build_prompt(self, factors: List[Dict], confidence_fake: float, reality_drift: float, media_type: str) -> str:
        lines = [
            f"Media type: {media_type}",
            f"Fake confidence (0-1): {confidence_fake:.3f}",
            f"Reality drift score (0-1): {reality_drift:.3f}",
            "Factors:",
        ]
        for f in factors:
            lines.append(f"- {f['name']}: score={f['score']:.3f}; evidence={f['evidence']}")

        lines.append(
            "Return exactly two plain-text paragraph blocks separated by \n<<TECHNICAL>>\n. "
            "First block is beginner-friendly. Second block is technical with caveats. "
            "No markdown, no headings, no bullets, no numbered lists."
        )
        return "\n".join(lines)

    def _fallback(self, factors: List[Dict], confidence_fake: float, reality_drift: float) -> Dict[str, str]:
        top = sorted(factors, key=lambda x: x["score"], reverse=True)[:3]
        names = ", ".join([f"{item['name']} ({item['score']:.2f})" for item in top])
        beginner = (
            f"The media was flagged because visual consistency checks were unusual, especially in {names}. "
            f"A higher reality drift score ({reality_drift:.2f}) means the image/video statistics differ from natural camera captures."
        )
        technical = (
            f"Rule-based IPCV analysis estimated fake confidence at {confidence_fake:.2f}. "
            "Primary contributors were high-scoring frequency, color, edge, temporal, or compression anomalies. "
            "These checks are deterministic and reproducible; review potential false positives from heavy recompression, low light, or motion blur."
        )
        return {"beginner": beginner, "technical": technical}

    def _sanitize_paragraphs(self, text: str) -> str:
        text = text.replace("\r", "\n").replace("**", "").replace("`", "")
        raw_lines = text.split("\n")
        cleaned_lines: List[str] = []

        for raw in raw_lines:
            line = raw.strip()
            if not line:
                cleaned_lines.append("")
                continue

            if line.lower().startswith("section "):
                continue

            line = line.lstrip("#").strip()
            line = re.sub(r"^[-*•]+\s*", "", line)
            line = re.sub(r"^\d+[.)]\s*", "", line)
            cleaned_lines.append(line)

        paragraphs: List[str] = []
        current: List[str] = []
        for line in cleaned_lines:
            if not line:
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
            else:
                current.append(line)
        if current:
            paragraphs.append(" ".join(current))

        return "\n\n".join(paragraphs).strip()
