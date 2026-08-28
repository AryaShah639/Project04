"""Image-level analysis: contrast (Rule 9), veg/non-veg dot (Rule 6(8)), clear-space (Rule 8)."""
import re
import numpy as np
import cv2
from PIL import Image

def _luminance(arr):
    return 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2] if arr.ndim == 3 else arr

def contrast_ratio(fg, bg):
    """WCAG-style ratio for two luminance values."""
    l1, l2 = (fg + 5.0) / (255.0 + 5.0), (bg + 5.0) / (255.0 + 5.0)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)

def box_contrast(img: Image.Image, box) -> float:
    """Contrast ratio between text and background inside an OCR box region (Otsu split)."""
    x, y, w, h = int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])
    pad = max(2, int(0.3 * h))
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(img.width, x + w + pad), min(img.height, y + h + pad)
    crop = np.array(img.convert("RGB"))[y0:y1, x0:x1]
    if crop.size == 0:
        return 21.0
    lum = _luminance(crop.astype(np.float32))
    _, th = cv2.threshold(lum.astype(np.uint8), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    fg = lum[th == 0]
    bg = lum[th == 255]
    if fg.size == 0 or bg.size == 0:
        return 21.0
    return round(contrast_ratio(float(fg.mean()), float(bg.mean())), 2)

def detect_veg_dot(img: Image.Image):
    """Detect green (veg) / red-brown (non-veg) dot near the top of the label (Rule 6(8)).
    Uses RGB-dominant colour masks + compact-blob check. Returns dict."""
    arr = np.array(img.convert("RGB")).astype(np.int16)
    top = arr[: max(1, int(arr.shape[0] * 0.25))]
    R, G, B = top[:, :, 0], top[:, :, 1], top[:, :, 2]
    green = ((G > R + 25) & (G > B + 25) & (G > 70)).astype(np.uint8) * 255
    red_brown = ((R > G + 30) & (R > B + 25) & (R > 70)).astype(np.uint8) * 255
    def has_blob(mask):
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        for i in range(1, n):
            area = stats[i, cv2.CC_STAT_AREA]
            w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            if 30 <= area <= 40000 and w >= 4 and h >= 4 and 0.2 <= (area / (w * h)) <= 1.0:
                return True
        return False
    g = has_blob(green)
    rb = has_blob(red_brown)
    return {"green": g, "red_brown": rb, "found": g or rb}

def clear_space_violations(words, qty_line):
    """Rule 8(1) proviso: area around quantity declaration free from printed info.
    Returns list of violation descriptions."""
    if not qty_line:
        return []
    # the declaration proper = the digit word(s) of the quantity line and its row-mates
    qty_digit = next((w for w in qty_line if re.search(r"\d", w["text"])), None)
    row_y = qty_digit["y"] if qty_digit else qty_line[0]["y"]
    row_h = qty_digit["h"] if qty_digit else 20
    same_row = [w for w in qty_line if abs(w["y"] - row_y) <= 0.6 * row_h]
    x0 = min(w["x"] for w in same_row); y0 = min(w["y"] for w in same_row)
    x1 = max(w["x"] + w["w"] for w in same_row); y1 = max(w["y"] + w["h"] for w in same_row)
    hgt = max(w["h"] for w in same_row)
    viol = []
    for w in words:
        if w in same_row:
            continue
        cx = (w["x"] + w["x"] + w["w"]) / 2
        cy = (w["y"] + w["y"] + w["h"]) / 2
        inside_h = x0 - 2 * hgt <= w["x"] + w["w"] and x1 + 2 * hgt >= w["x"] and \
                   y0 - hgt <= w["y"] + w["h"] and y1 + hgt >= w["y"]
        if not inside_h:
            continue
        overlap_x = w["x"] < x1 and w["x"] + w["w"] > x0
        overlap_y = w["y"] < y1 and w["y"] + w["h"] > y0
        if overlap_x and overlap_y:
            continue
        if (x0 - 2 * hgt <= w["x"] + w["w"] <= x0) or (x1 <= w["x"] <= x1 + 2 * hgt):
            if overlap_y:
                viol.append(f"'{w['text']}' printed beside quantity declaration within 2x height zone")
        elif (y0 - hgt <= w["y"] + w["h"] <= y0) or (y1 <= w["y"] <= y1 + hgt):
            if overlap_x:
                viol.append(f"'{w['text']}' printed above/below quantity declaration within height zone")
    return viol[:6]

def make_overlay(img: Image.Image, words, fields, path):
    """Draw green/red boxes on a copy: green = matched declaration fields, red = other words."""
    from PIL import ImageDraw
    ov = img.convert("RGB").copy()
    d = ImageDraw.Draw(ov)
    field_boxes = []
    for f in fields.values():
        if "x" in f:
            field_boxes.append((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"]))
    for (x, y, x2, y2) in field_boxes:
        d.rectangle([x, y, x2, y2], outline=(0, 160, 60), width=4)
    for w in words:
        if not any(fb[0] <= w["x"] <= fb[2] and fb[1] <= w["y"] <= fb[3] for fb in field_boxes):
            if w["conf"] < 50:
                d.rectangle([w["x"], w["y"], w["x"] + w["w"], w["y"] + w["h"]], outline=(220, 120, 0), width=2)
    ov.save(path, quality=90)
    return path
