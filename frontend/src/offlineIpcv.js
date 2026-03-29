function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

function normalize(value, low, high) {
  if (high <= low) return 0;
  const clipped = Math.max(low, Math.min(high, value));
  return (clipped - low) / (high - low);
}

function loadOpenCvJs() {
  return new Promise((resolve, reject) => {
    if (window.cv && window.cv.Mat) {
      resolve(window.cv);
      return;
    }

    const existing = document.getElementById("opencvjs-script");
    if (existing) {
      existing.addEventListener("load", () => resolve(window.cv));
      existing.addEventListener("error", () => reject(new Error("Failed to load OpenCV.js")));
      return;
    }

    const script = document.createElement("script");
    script.id = "opencvjs-script";
    script.async = true;
    script.src = "https://docs.opencv.org/4.10.0/opencv.js";
    script.onload = () => {
      if (window.cv && window.cv.Mat) {
        resolve(window.cv);
        return;
      }
      window.cv.onRuntimeInitialized = () => resolve(window.cv);
    };
    script.onerror = () => reject(new Error("Failed to load OpenCV.js"));
    document.body.appendChild(script);
  });
}

function fileToImage(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Unable to decode image for offline analysis"));
    img.src = URL.createObjectURL(file);
  });
}

function matVariance(cv, mat) {
  const mean = new cv.Mat();
  const std = new cv.Mat();
  cv.meanStdDev(mat, mean, std);
  const variance = std.doubleAt(0, 0) * std.doubleAt(0, 0);
  mean.delete();
  std.delete();
  return variance;
}

function matMean(cv, mat) {
  const m = cv.mean(mat);
  return m[0];
}

function buildHeatmapDataUrl(cv, gray) {
  const lap = new cv.Mat();
  const absLap = new cv.Mat();
  const norm = new cv.Mat();
  const heat = new cv.Mat();
  const canvas = document.createElement("canvas");

  cv.Laplacian(gray, lap, cv.CV_64F);
  cv.convertScaleAbs(lap, absLap);
  cv.normalize(absLap, norm, 0, 255, cv.NORM_MINMAX);
  cv.applyColorMap(norm, heat, cv.COLORMAP_TURBO);
  cv.imshow(canvas, heat);

  const url = canvas.toDataURL("image/png");
  lap.delete();
  absLap.delete();
  norm.delete();
  heat.delete();
  return url;
}

export async function analyzeImageOffline(file) {
  const cv = await loadOpenCvJs();
  const image = await fileToImage(file);
  const canvas = document.createElement("canvas");
  canvas.width = image.width;
  canvas.height = image.height;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(image, 0, 0);

  let src;
  let gray;
  let hsv;
  let ycrcb;
  let canny;
  let sobelx;
  let sobely;
  let mag;
  let blur;
  let residual;
  let lap;

  try {
    src = cv.imread(canvas);
    gray = new cv.Mat();
    hsv = new cv.Mat();
    ycrcb = new cv.Mat();

    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
    cv.cvtColor(src, hsv, cv.COLOR_RGBA2HSV);
    cv.cvtColor(src, ycrcb, cv.COLOR_RGBA2YCrCb);

    canny = new cv.Mat();
    cv.Canny(gray, canny, 80, 160);
    const edgeDensity = cv.countNonZero(canny) / (gray.rows * gray.cols);
    const edgeScore = clamp01(normalize(edgeDensity, 0.05, 0.24));

    const ycrcbChannels = new cv.MatVector();
    cv.split(ycrcb, ycrcbChannels);
    const cr = ycrcbChannels.get(1);
    const cb = ycrcbChannels.get(2);
    const crVar = matVariance(cv, cr);
    const cbVar = matVariance(cv, cb);
    const colorScore = clamp01(normalize(Math.abs(crVar - cbVar), 20, 1200));

    const hsvChannels = new cv.MatVector();
    cv.split(hsv, hsvChannels);
    const sat = hsvChannels.get(1);
    const satVar = matVariance(cv, sat);

    sobelx = new cv.Mat();
    sobely = new cv.Mat();
    mag = new cv.Mat();
    cv.Sobel(gray, sobelx, cv.CV_32F, 1, 0, 3);
    cv.Sobel(gray, sobely, cv.CV_32F, 0, 1, 3);
    cv.magnitude(sobelx, sobely, mag);
    const freqProxyScore = clamp01(normalize(matVariance(cv, mag), 200, 7000));

    blur = new cv.Mat();
    residual = new cv.Mat();
    cv.GaussianBlur(gray, blur, new cv.Size(31, 31), 0, 0, cv.BORDER_DEFAULT);
    cv.absdiff(gray, blur, residual);
    const lightScore = clamp01(normalize(matMean(cv, residual), 6, 30));

    lap = new cv.Mat();
    cv.Laplacian(gray, lap, cv.CV_64F);
    const jpegNoise = clamp01(normalize(matVariance(cv, lap), 100, 1500));

    const flipped = new cv.Mat();
    cv.flip(gray, flipped, 1);
    const diff = new cv.Mat();
    cv.absdiff(gray, flipped, diff);
    const symmetry = clamp01(normalize(matMean(cv, diff), 8, 48));

    const realityDrift = clamp01(
      freqProxyScore * 0.35 +
        colorScore * 0.15 +
        edgeScore * 0.2 +
        lightScore * 0.1 +
        jpegNoise * 0.1 +
        clamp01(normalize(satVar, 40, 3200)) * 0.1
    );

    const factorMap = {
      fft_artifacts: freqProxyScore,
      color_space: colorScore,
      edge_irregularity: edgeScore,
      lighting_shadow: lightScore,
      jpeg_noise: jpegNoise,
      face_symmetry: symmetry,
    };

    const confidence = clamp01(
      factorMap.fft_artifacts * 0.2 +
        factorMap.color_space * 0.16 +
        factorMap.edge_irregularity * 0.16 +
        factorMap.lighting_shadow * 0.14 +
        factorMap.jpeg_noise * 0.14 +
        factorMap.face_symmetry * 0.08 +
        realityDrift * 0.12
    );

    const factors = Object.entries(factorMap).map(([name, score]) => ({
      name,
      score,
      evidence: "Offline OpenCV.js estimate from deterministic visual statistics.",
    }));

    const heatmapDataUrl = buildHeatmapDataUrl(cv, gray);

    const beginner =
      "This image was analyzed locally in your browser using OpenCV.js. A few visual consistency checks look unusual, so authenticity should be reviewed carefully.";
    const technical =
      "Offline mode used deterministic IPCV metrics (frequency proxy, edge density, color variance, lighting residuals, compression/noise, mirror symmetry). Scores are approximate and intended for rapid triage when the backend is unavailable.";

    const fingerprint = {
      fft: Number(factorMap.fft_artifacts.toFixed(4)),
      color: Number(factorMap.color_space.toFixed(4)),
      edge: Number(factorMap.edge_irregularity.toFixed(4)),
      lighting: Number(factorMap.lighting_shadow.toFixed(4)),
      jpeg_noise: Number(factorMap.jpeg_noise.toFixed(4)),
      face_symmetry: Number(factorMap.face_symmetry.toFixed(4)),
      integrity_hash_mod: Number((canvas.width * 131 + canvas.height * 17).toString().slice(-4)) / 10000,
    };

    flipped.delete();
    diff.delete();
    cr.delete();
    cb.delete();
    sat.delete();
    ycrcbChannels.delete();
    hsvChannels.delete();

    return {
      media_type: "image",
      confidence_fake: confidence,
      trust_score: clamp01(1 - confidence * 0.8 - realityDrift * 0.2),
      factors,
      reality_drift_score: realityDrift,
      visual_authenticity_fingerprint: fingerprint,
      explanation: {
        beginner,
        technical,
      },
      heatmap_path: null,
      heatmap_data_url: heatmapDataUrl,
    };
  } finally {
    if (src) src.delete();
    if (gray) gray.delete();
    if (hsv) hsv.delete();
    if (ycrcb) ycrcb.delete();
    if (canny) canny.delete();
    if (sobelx) sobelx.delete();
    if (sobely) sobely.delete();
    if (mag) mag.delete();
    if (blur) blur.delete();
    if (residual) residual.delete();
    if (lap) lap.delete();
  }
}
