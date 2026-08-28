"""OCR engine wrapper (Tesseract 5) with preprocessing and word-level boxes.

Multiple binarisation passes are run and merged downstream:
  primary — contrast-stretched grayscale (clean labels)
  alt     — adaptive Gaussian threshold (rescues low-contrast text)
  clahe   — CLAHE contrast enhancement (photos with glare / uneven lighting)
  hin     — adaptive threshold with eng+hin, only when hin is installed AND the
            label looks bilingual (Rule 9(4): English or Hindi declarations)

Windows: the tesseract.exe path is auto-discovered (PATH, or Program Files Tesseract-OCR);
if the engine is missing entirely a clear install hint is raised instead of a cryptic error.
"""
import os, re, shutil
import numpy as np
import cv2
import pytesseract
from PIL import Image, ImageOps, ExifTags

TESS_LANG = "eng+hin"   # Devanagari support (Rule 9(4): English or Hindi)

# ---------------------------------------------------------------- tesseract discovery
def _find_tesseract() -> str | None:
    """Locate the Tesseract binary: PATH first, then standard Windows install paths
    (winget / UB-Mannheim installer puts it under Program Files)."""
    exe = shutil.which("tesseract")
    if exe:
        return exe
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        "/usr/bin/tesseract", "/usr/local/bin/tesseract", "/opt/homebrew/bin/tesseract",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

_tess_bin = _find_tesseract()
if _tess_bin:
    pytesseract.pytesseract.tesseract_cmd = _tess_bin

def _available_langs():
    try:
        return set(pytesseract.get_languages(config=""))
    except Exception:
        return set()

def _check_tesseract():
    """Raise a clear, actionable error when Tesseract is not installed at all."""
    if not (_tess_bin or shutil.which("tesseract")):
        raise RuntimeError(
            "Tesseract OCR engine not found. Install it and retry:\n"
            "  • Windows:  winget install UB-Mannheim.TesseractOCR   (tick 'Hindi' language during setup)\n"
            "  • macOS:    brew install tesseract tesseract-lang\n"
            "  • Ubuntu:   sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin\n"
            "Then open a NEW terminal so the PATH picks it up, and restart the app.")

def load_dpi(img: Image.Image):
    """Read DPI from image metadata. Returns (dpi, source) where source is
    'meta' (trustworthy print resolution) or 'default' (no metadata → assumed 300).
    Photos from phones/cropped files carry no meaningful DPI; callers must treat
    mm-based font measurement as unreliable in that case."""
    try:
        dpi = img.info.get("dpi")
        if dpi:
            v = float(dpi[0]) if isinstance(dpi, tuple) else float(dpi)
            if 72 <= v <= 2400:
                return v, "meta"
    except Exception:
        pass
    try:
        exif = img.getexif()
        if exif and ExifTags.XResolution in exif:
            v = float(exif[ExifTags.XResolution])
            if 72 <= v <= 2400:
                return v, "meta"
    except Exception:
        pass
    return 300.0, "default"

def is_photo_like(dpi: float, dpi_source: str) -> bool:
    """True when the image is a photograph / digital capture without a trustworthy
    print scale — physical (mm) font-size measurement is not possible."""
    return dpi_source == "default" or dpi < 150

def deskew(arr: np.ndarray) -> np.ndarray:
    """Rotate slightly skewed photos upright (phone captures). Only acts for |angle| in [0.6, 30] deg.
    Solid dark areas (e.g. a full-width header band) are excluded so they can't dominate the fit."""
    try:
        hgt, wid = arr.shape
        th = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        coords = np.column_stack(np.where(th < 128))
        if coords.shape[0] < 500:
            return arr
        # keep only thin, text-like strokes: drop large connected components (solid blocks)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(th < 128, 8)
        keep = np.zeros_like(th < 128)
        for i in range(1, n):
            area = stats[i, cv2.CC_STAT_AREA]
            w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            if w > 4 and h > 4 and area < 0.05 * (wid * hgt) and (area / (w * h)) < 0.75:
                keep |= (labels == i)
        coords = np.column_stack(np.where(keep))
        if coords.shape[0] < 500:
            return arr
        rect = cv2.minAreaRect(coords)
        ang = rect[-1]
        # normalise into [-45, 45]
        if ang < -45:
            ang = 90 + ang
        elif ang > 45:
            ang -= 90
        if 0.6 < abs(ang) <= 30:
            M = cv2.getRotationMatrix2D((wid / 2, hgt / 2), ang, 1.0)
            arr = cv2.warpAffine(arr, M, (wid, hgt), flags=cv2.INTER_CUBIC,
                                 borderMode=cv2.BORDER_REPLICATE)
    except Exception:
        pass
    return arr

def _to_gray(img: Image.Image, target_min: int):
    """EXIF-correct, grayscale, upscaled, deskewed image as uint8 array. Returns (arr, scale)."""
    img = ImageOps.exif_transpose(img)          # phone photos: honour EXIF orientation
    arr = np.array(img.convert("L"))
    scale = 1.0
    if max(arr.shape) < target_min:
        scale = target_min / max(arr.shape)
        arr = cv2.resize(arr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return deskew(arr), scale

def stretch(arr: np.ndarray) -> np.ndarray:
    """Mild contrast stretch — skip when the percentile range collapses
    (near-uniform backgrounds with sparse dark text give p2 == p98)."""
    p2, p98 = np.percentile(arr, (2, 98))
    if p98 - p2 >= 10:
        arr = np.clip((arr.astype(np.float32) - p2) * (255.0 / (p98 - p2)), 0, 255).astype(np.uint8)
    return arr

def _words_from_tsv(tsv, scale):
    words = []
    n = len(tsv["text"])
    for i in range(n):
        t = (tsv["text"][i] or "").strip()
        conf = float(tsv["conf"][i] if i < len(tsv["conf"]) else -1)
        if not t or conf < 0:
            continue
        x, y, w, h = int(tsv["left"][i]), int(tsv["top"][i]), int(tsv["width"][i]), int(tsv["height"][i])
        if w < 1 or h < 1:
            continue
        words.append({"text": t, "x": int(x / scale), "y": int(y / scale),
                      "w": int(w / scale), "h": int(h / scale), "conf": conf})
    return words

def _run_pass(arr, lang, scale, psm=None):
    cfg = f"--psm {psm}" if psm else ""
    text = pytesseract.image_to_string(arr, lang=lang, config=cfg)
    tsv = pytesseract.image_to_data(arr, lang=lang, config=cfg,
                                    output_type=pytesseract.Output.DICT)
    return {"text": text, "words": _words_from_tsv(tsv, scale)}

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")

def _want_hin(img: Image.Image) -> bool:
    """Cheap heuristic: run a tiny, fast eng-only probe; if the label is bilingual
    (Hindi words like 'शुद्ध', 'शामिल'), the Devanagari pass is worth the extra time.
    Only called when the hin traineddata is installed."""
    try:
        small = np.array(img.convert("L"))
        small = cv2.resize(small, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        t = pytesseract.image_to_string(small, lang="eng")
        return bool(DEVANAGARI_RE.search(t)) or len(t.split()) < 5
    except Exception:
        return False

def run_ocr(image_path: str):
    """Multi-pass OCR for both clean label renders and real-world photographs.
    Returns a dict with per-pass results plus convenience fields:
      text/words       — best merged text (primary unless it underperforms)
      text_alt/words_alt, text_clahe/words_clahe, text_hin/words_hin (optional)
      passes           — full list of pass dicts
      dpi, dpi_source, is_photo, pix_per_mm, img_w, img_h
    """
    _check_tesseract()
    img = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
    dpi, dpi_source = load_dpi(img)
    photo = is_photo_like(dpi, dpi_source)

    langs = _available_langs()
    eng = "eng" if "eng" in langs else next(iter(langs), "eng")
    use_hin = "hin" in langs and _want_hin(img)

    # standard branch (clean labels / scans)
    arr, scale = _to_gray(img, 1000)
    arr_st = stretch(arr)
    th = cv2.adaptiveThreshold(arr_st, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 15)

    passes = []
    passes.append(("primary", _run_pass(arr_st, eng, scale)))
    passes.append(("alt", _run_pass(th, eng, scale)))

    if photo:
        # photo branch: bigger upscale + CLAHE on the RAW grayscale (stretch flattens
        # mid-tones where photo text lives — CLAHE must see the original contrast)
        raw, scale_raw = _to_gray(img, 1400)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(raw)
        passes.append(("clahe", _run_pass(clahe, eng, scale_raw)))
        # soft-focus photos also benefit from mild sharpening on the CLAHE image
        sharp = cv2.addWeighted(clahe, 1.35, cv2.GaussianBlur(clahe, (0, 0), 2.0), -0.35, 0)
        passes.append(("clahe_sharp", _run_pass(sharp, eng, scale_raw)))
    else:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(arr)
        passes.append(("clahe", _run_pass(clahe, eng, scale)))

    if use_hin:
        passes.append(("hin", _run_pass(th, "eng+hin", scale)))

    # best overall text = the pass with the most high-confidence words
    best = max(passes, key=lambda kv: (sum(1 for w in kv[1]["words"] if w["conf"] >= 55),
                                       len(kv[1]["words"])))
    out = {
        "text": best[1]["text"], "words": best[1]["words"],
        "passes": [{"key": k, **p} for k, p in passes],
        "dpi": dpi, "dpi_source": dpi_source, "is_photo": photo,
        "pix_per_mm": dpi / 25.4,
        "img_w": img.width, "img_h": img.height,
        "word_count": len(best[1]["words"]),
    }
    for k, p in passes:
        out[f"text_{k}"] = p["text"]
        out[f"words_{k}"] = p["words"]
    return out
