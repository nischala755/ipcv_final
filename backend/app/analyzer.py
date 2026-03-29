from __future__ import annotations

import os
import hashlib
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np


class IPCVAnalyzer:
    """Pure IPCV deepfake detector with reproducible, rule-based scoring."""

    IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

    def detect_media_type(self, file_path: Path) -> str:
        ext = file_path.suffix.lower()
        if ext in self.IMAGE_EXT:
            return "image"
        if ext in self.VIDEO_EXT:
            return "video"
        return "image"

    def analyze(self, file_path: Path) -> Tuple[str, float, List[Dict], float, Dict[str, float], np.ndarray | None, Dict[str, np.ndarray], Dict]:
        media_type = self.detect_media_type(file_path)
        if media_type == "video":
            return self._analyze_video(file_path)
        return self._analyze_image(file_path)

    def _normalize(self, value: float, low: float, high: float) -> float:
        if high <= low:
            return 0.0
        clipped = max(low, min(value, high))
        return (clipped - low) / (high - low)

    def _quality_profile(self, gray: np.ndarray, bgr: np.ndarray) -> Dict[str, float]:
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        sharpness = float(np.var(cv2.Laplacian(gray, cv2.CV_64F)))
        compression = float(self._blockiness_score(gray))
        noise_proxy = float(np.var(gray.astype(np.float32) - cv2.GaussianBlur(gray, (5, 5), 0).astype(np.float32)))
        saturation = float(np.mean(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 1]))
        return {
            "brightness": brightness,
            "contrast": contrast,
            "sharpness": sharpness,
            "compression": compression,
            "noise_proxy": noise_proxy,
            "saturation": saturation,
        }

    def _adaptive_bounds(self, factor: str, low: float, high: float, q: Dict[str, float] | None) -> Tuple[float, float]:
        if not q:
            return low, high

        b, c, s = q["brightness"], q["contrast"], q["sharpness"]
        comp, noise, sat = q["compression"], q["noise_proxy"], q["saturation"]

        if factor == "fft_artifacts":
            if s < 300:
                low *= 0.82
                high *= 0.9
            if noise < 50:
                low *= 0.9
        elif factor == "edge_irregularity":
            if c < 35:
                low *= 0.75
                high *= 0.9
            if s < 260:
                low *= 0.88
        elif factor == "lighting_shadow":
            if b < 75:
                low *= 0.55
                high *= 0.8
            elif b > 185:
                low *= 0.78
                high *= 0.9
        elif factor == "jpeg_noise":
            if comp > 0.55:
                low *= 0.72
                high *= 0.88
            if noise < 40:
                low *= 0.82
        elif factor == "color_space":
            if sat < 40:
                low *= 0.75
                high *= 0.9

        if high <= low:
            high = low + 1e-6
        return low, high

    def _adaptive_normalize(self, value: float, factor: str, low: float, high: float, q: Dict[str, float] | None) -> float:
        a_low, a_high = self._adaptive_bounds(factor, low, high, q)
        return self._normalize(value, a_low, a_high)

    def _fft_artifact_score(self, gray: np.ndarray, quality: Dict[str, float] | None = None) -> float:
        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        magnitude = np.log1p(np.abs(fshift))
        h, w = magnitude.shape
        yy, xx = np.indices((h, w))
        cy, cx = h / 2.0, w / 2.0
        rr = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
        rmax = min(h, w) / 2.0

        mid_mask = (rr >= rmax * 0.08) & (rr < rmax * 0.28)
        high_mask = rr >= rmax * 0.28

        mid_mean = float(np.mean(magnitude[mid_mask]) + 1e-6)
        high_mean = float(np.mean(magnitude[high_mask]))
        ratio = high_mean / mid_mean
        anisotropy = float(np.std(magnitude[high_mask]) / (high_mean + 1e-6))

        raw = self._adaptive_normalize(ratio, "fft_artifacts", 0.55, 1.25, quality) * 0.7 + self._adaptive_normalize(anisotropy, "fft_artifacts", 0.18, 1.1, quality) * 0.3
        return max(0.0, min(float(raw), 1.0))

    def _color_anomaly_score(self, bgr: np.ndarray, quality: Dict[str, float] | None = None) -> float:
        ycbcr = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        _, cb, cr = cv2.split(ycbcr)
        h, s, _ = cv2.split(hsv)
        cbcr_corr = np.corrcoef(cb.flatten(), cr.flatten())[0, 1]
        if not np.isfinite(cbcr_corr):
            cbcr_corr = 0.0
        sat_skew = float(np.mean(np.abs(s.astype(np.float32) - np.median(s))))
        hue_var = float(np.var(h.astype(np.float32)))
        raw = (
            abs(cbcr_corr) * 0.4
            + self._adaptive_normalize(sat_skew, "color_space", 12, 65, quality) * 0.3
            + self._adaptive_normalize(hue_var, "color_space", 180, 1400, quality) * 0.3
        )
        return max(0.0, min(float(raw), 1.0))

    def _edge_irregularity_score(self, gray: np.ndarray, quality: Dict[str, float] | None = None) -> float:
        canny = cv2.Canny(gray, 80, 160)
        sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(sobelx.astype(np.float32), sobely.astype(np.float32))
        edge_density = np.count_nonzero(canny) / (gray.shape[0] * gray.shape[1])
        edge_energy_var = float(np.var(magnitude))
        raw = self._adaptive_normalize(edge_density, "edge_irregularity", 0.015, 0.22, quality) * 0.4 + self._adaptive_normalize(edge_energy_var, "edge_irregularity", 250, 8000, quality) * 0.6
        return max(0.0, min(float(raw), 1.0))

    def _lighting_shadow_mismatch(self, bgr: np.ndarray, quality: Dict[str, float] | None = None) -> float:
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l, _, _ = cv2.split(lab)
        blur = cv2.GaussianBlur(l, (31, 31), 0)
        residual = cv2.absdiff(l, blur)
        mismatch = float(np.mean(residual))
        return self._adaptive_normalize(mismatch, "lighting_shadow", 2.0, 22.0, quality)

    def _jpeg_noise_score(self, gray: np.ndarray, quality: Dict[str, float] | None = None) -> float:
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        noise_var = float(np.var(lap))
        blockiness = self._blockiness_score(gray)
        return max(0.0, min(self._adaptive_normalize(noise_var, "jpeg_noise", 25, 900, quality) * 0.6 + blockiness * 0.4, 1.0))

    def _blockiness_score(self, gray: np.ndarray) -> float:
        h, w = gray.shape
        h8 = (h // 8) * 8
        w8 = (w // 8) * 8
        if h8 <= 8 or w8 <= 8:
            return 0.0
        crop = gray[:h8, :w8].astype(np.float32)
        v_a = crop[:, 7::8]
        v_b = crop[:, 8::8]
        v_cols = min(v_a.shape[1], v_b.shape[1])
        if v_cols == 0:
            v_diff = 0.0
        else:
            v_diff = float(np.abs(v_a[:, :v_cols] - v_b[:, :v_cols]).mean())

        h_a = crop[7::8, :]
        h_b = crop[8::8, :]
        h_rows = min(h_a.shape[0], h_b.shape[0])
        if h_rows == 0:
            h_diff = 0.0
        else:
            h_diff = float(np.abs(h_a[:h_rows, :] - h_b[:h_rows, :]).mean())
        return self._normalize(float(v_diff + h_diff), 4, 26)

    def _face_symmetry_score(self, gray: np.ndarray) -> float:
        cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(64, 64))
        if len(faces) == 0:
            return 0.35
        x, y, w, h = faces[0]
        roi = gray[y : y + h, x : x + w]
        mid = w // 2
        left = roi[:, :mid]
        right = roi[:, w - mid :]
        right_flipped = cv2.flip(right, 1)
        min_h = min(left.shape[0], right_flipped.shape[0])
        min_w = min(left.shape[1], right_flipped.shape[1])
        left = left[:min_h, :min_w]
        right_flipped = right_flipped[:min_h, :min_w]
        diff = float(np.mean(np.abs(left.astype(np.float32) - right_flipped.astype(np.float32))))
        return self._normalize(diff, 4, 38)

    def _reality_drift_score(self, gray: np.ndarray, bgr: np.ndarray) -> float:
        # Novel feature: measures deviation from expected natural image statistics.
        grad = cv2.Laplacian(gray, cv2.CV_64F)
        kurtosis_like = float(np.mean((grad - grad.mean()) ** 4) / (np.var(grad) ** 2 + 1e-6))
        nat_stat_deviation = abs(kurtosis_like - 3.0)
        saturation = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[:, :, 1].astype(np.float32)
        sat_entropy = self._entropy(saturation)
        noise_band = float(np.var(cv2.GaussianBlur(gray, (3, 3), 0) - cv2.medianBlur(gray, 3)))
        score = (
            self._normalize(nat_stat_deviation, 0.2, 4.0) * 0.45
            + self._normalize(sat_entropy, 3.0, 6.5) * 0.3
            + self._normalize(noise_band, 8, 220) * 0.25
        )
        return max(0.0, min(score, 1.0))

    def _entropy(self, arr: np.ndarray) -> float:
        hist = cv2.calcHist([arr.astype(np.uint8)], [0], None, [256], [0, 256]).flatten()
        p = hist / (np.sum(hist) + 1e-8)
        p = p[p > 0]
        return float(-np.sum(p * np.log2(p)))

    def _fingerprint(self, factor_values: Dict[str, float], gray: np.ndarray) -> Dict[str, float]:
        # Reproducible IPCV signature used for lineage comparison and auditing.
        h = hashlib.sha256(gray.tobytes()).hexdigest()
        return {
            "fft": round(factor_values["fft_artifacts"], 4),
            "color": round(factor_values["color_space"], 4),
            "edge": round(factor_values["edge_irregularity"], 4),
            "lighting": round(factor_values["lighting_shadow"], 4),
            "jpeg_noise": round(factor_values["jpeg_noise"], 4),
            "face_symmetry": round(factor_values["face_symmetry"], 4),
            "integrity_hash_mod": int(h[:8], 16) / float(0xFFFFFFFF),
        }

    def _heatmap(self, gray: np.ndarray) -> np.ndarray:
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        abs_lap = cv2.convertScaleAbs(lap)
        norm = cv2.normalize(abs_lap, None, 0, 255, cv2.NORM_MINMAX)
        return cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)

    def _concept_visuals(self, bgr: np.ndarray, gray: np.ndarray) -> Dict[str, np.ndarray]:
        visuals: Dict[str, np.ndarray] = {}

        f = np.fft.fft2(gray)
        fshift = np.fft.fftshift(f)
        spectrum = 20 * np.log(np.abs(fshift) + 1)
        spec_norm = cv2.normalize(spectrum, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        visuals["frequency_spectrum"] = cv2.applyColorMap(spec_norm, cv2.COLORMAP_INFERNO)

        canny = cv2.Canny(gray, 80, 160)
        visuals["edge_consistency"] = cv2.applyColorMap(canny, cv2.COLORMAP_OCEAN)

        ycbcr = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        _, cr, cb = cv2.split(ycbcr)
        chroma_diff = cv2.absdiff(cr, cb)
        chroma_norm = cv2.normalize(chroma_diff, None, 0, 255, cv2.NORM_MINMAX)
        visuals["color_inconsistency"] = cv2.applyColorMap(chroma_norm, cv2.COLORMAP_PLASMA)

        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l, _, _ = cv2.split(lab)
        blur = cv2.GaussianBlur(l, (31, 31), 0)
        residual = cv2.absdiff(l, blur)
        light_norm = cv2.normalize(residual, None, 0, 255, cv2.NORM_MINMAX)
        visuals["lighting_shadow_mismatch"] = cv2.applyColorMap(light_norm, cv2.COLORMAP_BONE)

        lap = cv2.Laplacian(gray, cv2.CV_64F)
        noise_map = cv2.convertScaleAbs(lap)
        noise_norm = cv2.normalize(noise_map, None, 0, 255, cv2.NORM_MINMAX)
        visuals["jpeg_noise_pattern"] = cv2.applyColorMap(noise_norm, cv2.COLORMAP_TWILIGHT)

        mirror = cv2.flip(gray, 1)
        symm = cv2.absdiff(gray, mirror)
        symm_norm = cv2.normalize(symm, None, 0, 255, cv2.NORM_MINMAX)
        visuals["facial_symmetry_diff"] = cv2.applyColorMap(symm_norm, cv2.COLORMAP_SPRING)

        return visuals

    def _aggregate(self, scores: Dict[str, float], reality_drift: float, temporal: float | None = None, optical: float | None = None) -> float:
        weighted = (
            scores["fft_artifacts"] * 0.18
            + scores["color_space"] * 0.14
            + scores["edge_irregularity"] * 0.14
            + scores["lighting_shadow"] * 0.12
            + scores["jpeg_noise"] * 0.12
            + scores["face_symmetry"] * 0.1
            + reality_drift * 0.2
        )
        if temporal is not None:
            weighted = weighted * 0.8 + temporal * 0.12 + (optical or 0.0) * 0.08
        return max(0.0, min(float(weighted), 1.0))

    def _factor_payload(self, factor_values: Dict[str, float], temporal: float | None = None, optical: float | None = None) -> List[Dict]:
        evidence_map = {
            "fft_artifacts": "Abnormal high-frequency to low-frequency energy ratio.",
            "color_space": "YCbCr/HSV channel relationships deviate from natural capture patterns.",
            "edge_irregularity": "Edge density and gradient energy indicate synthetic blending seams.",
            "lighting_shadow": "Local illumination residuals suggest inconsistent lighting composition.",
            "jpeg_noise": "Block boundaries and noise variance mismatch expected compression behavior.",
            "face_symmetry": "Facial mirror consistency differs from organic asymmetry profile.",
        }
        factors = [
            {"name": k, "score": float(v), "evidence": evidence_map[k]}
            for k, v in factor_values.items()
        ]
        if temporal is not None:
            factors.append(
                {
                    "name": "temporal_inconsistency",
                    "score": float(temporal),
                    "evidence": "Frame-to-frame luminance transitions are unstable for natural motion.",
                }
            )
        if optical is not None:
            factors.append(
                {
                    "name": "optical_flow_inconsistency",
                    "score": float(optical),
                    "evidence": "Motion vectors show abrupt local incoherence around manipulated regions.",
                }
            )
        return factors

    def _analyze_image(self, file_path: Path):
        bgr = cv2.imread(str(file_path), cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError("Unable to read image file")
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        gray_hash = hashlib.sha256(gray.tobytes()).hexdigest()
        quality = self._quality_profile(gray, bgr)

        factor_values = {
            "fft_artifacts": self._fft_artifact_score(gray, quality),
            "color_space": self._color_anomaly_score(bgr, quality),
            "edge_irregularity": self._edge_irregularity_score(gray, quality),
            "lighting_shadow": self._lighting_shadow_mismatch(bgr, quality),
            "jpeg_noise": self._jpeg_noise_score(gray, quality),
            "face_symmetry": self._face_symmetry_score(gray),
        }
        reality_drift = self._reality_drift_score(gray, bgr)
        confidence_fake = self._aggregate(factor_values, reality_drift)
        fingerprint = self._fingerprint(factor_values, gray)
        heatmap = self._heatmap(gray)
        concept_visuals = self._concept_visuals(bgr, gray)

        return (
            "image",
            confidence_fake,
            self._factor_payload(factor_values),
            reality_drift,
            fingerprint,
            heatmap,
            concept_visuals,
            {"worker_count": 1, "frame_count": 1, "frame_hashes": [gray_hash], "quality_profile": quality},
        )

    def _analyze_frame(self, frame: np.ndarray) -> Dict:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        quality = self._quality_profile(gray, frame)
        fv = {
            "fft_artifacts": self._fft_artifact_score(gray, quality),
            "color_space": self._color_anomaly_score(frame, quality),
            "edge_irregularity": self._edge_irregularity_score(gray, quality),
            "lighting_shadow": self._lighting_shadow_mismatch(frame, quality),
            "jpeg_noise": self._jpeg_noise_score(gray, quality),
            "face_symmetry": self._face_symmetry_score(gray),
        }
        return {
            "factor_values": fv,
            "gray": gray,
            "fingerprint": self._fingerprint(fv, gray),
            "frame_hash": hashlib.sha256(gray.tobytes()).hexdigest(),
            "quality": quality,
        }

    def _sample_frames(self, cap: cv2.VideoCapture, max_frames: int = 24) -> List[np.ndarray]:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            frames = []
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frames.append(frame)
                if len(frames) >= max_frames:
                    break
            return frames

        step = max(1, total // max_frames)
        frames = []
        idx = 0
        while True:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
            idx += step
            if len(frames) >= max_frames:
                break
        return frames

    def _temporal_inconsistency(self, grays: List[np.ndarray]) -> float:
        if len(grays) < 3:
            return 0.3
        diffs = []
        for i in range(1, len(grays)):
            d = cv2.absdiff(grays[i], grays[i - 1])
            diffs.append(np.mean(d))
        return self._normalize(float(np.var(diffs)), 2, 45)

    def _optical_flow_inconsistency(self, grays: List[np.ndarray]) -> float:
        if len(grays) < 2:
            return 0.3
        coherence = []
        for i in range(1, len(grays)):
            flow = cv2.calcOpticalFlowFarneback(
                grays[i - 1],
                grays[i],
                None,
                pyr_scale=0.5,
                levels=3,
                winsize=15,
                iterations=3,
                poly_n=5,
                poly_sigma=1.2,
                flags=0,
            )
            mag, ang = cv2.cartToPolar(flow[..., 0], flow[..., 1])
            coherence.append(float(np.std(mag) / (np.mean(mag) + 1e-6) + np.std(ang) / (np.mean(ang) + 1e-6)))
        return self._normalize(float(np.mean(coherence)), 0.8, 6.0)

    def _analyze_video(self, file_path: Path):
        cap = cv2.VideoCapture(str(file_path))
        if not cap.isOpened():
            raise ValueError("Unable to read video file")
        frames = self._sample_frames(cap)
        cap.release()
        if not frames:
            raise ValueError("Video had no readable frames")

        per_frame_scores = []
        grays = []
        first_heatmap = None
        fingerprints = []
        frame_hashes = []
        qualities = []
        worker_count = max(2, min((os.cpu_count() or 2), 8))
        ordered_results = [None] * len(frames)
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            futures = {pool.submit(self._analyze_frame, frame): idx for idx, frame in enumerate(frames)}
            for fut in as_completed(futures):
                idx = futures[fut]
                ordered_results[idx] = fut.result()

        for result in ordered_results:
            fv = result["factor_values"]
            gray = result["gray"]
            per_frame_scores.append(fv)
            grays.append(gray)
            fingerprints.append(result["fingerprint"])
            frame_hashes.append(result["frame_hash"])
            qualities.append(result["quality"])
            if first_heatmap is None:
                first_heatmap = self._heatmap(gray)

        mean_factors = {
            k: float(np.mean([frame_scores[k] for frame_scores in per_frame_scores]))
            for k in per_frame_scores[0].keys()
        }
        reality_drift = float(np.mean([self._reality_drift_score(g, f) for g, f in zip(grays, frames)]))
        temporal = self._temporal_inconsistency(grays)
        optical = self._optical_flow_inconsistency(grays)
        confidence_fake = self._aggregate(mean_factors, reality_drift, temporal, optical)
        concept_visuals = self._concept_visuals(frames[0], grays[0])

        avg_fingerprint = {
            key: float(np.mean([fp[key] for fp in fingerprints]))
            for key in fingerprints[0].keys()
        }

        return (
            "video",
            confidence_fake,
            self._factor_payload(mean_factors, temporal, optical),
            reality_drift,
            avg_fingerprint,
            first_heatmap,
            concept_visuals,
            {
                "worker_count": worker_count,
                "frame_count": len(frames),
                "frame_hashes": frame_hashes,
                "quality_profile": {
                    key: float(np.mean([q[key] for q in qualities])) for key in qualities[0].keys()
                },
            },
        )
