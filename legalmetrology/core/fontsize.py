"""Font-size & PDP-area analysis per Rule 7 (as amended by GSR 629(E) dt. 23.06.2017)."""
import re

# Table-I (current, w.e.f. 01.01.2018): min height (mm) of numerals AND letters vs PDP area
TABLE_I = [
    (50, 1.0, 1.5),      # A <= 50
    (100, 1.5, 3.0),     # 50 < A <= 100
    (500, 2.5, 4.0),     # 100 < A <= 500
    (2500, 4.0, 6.0),    # 500 < A <= 2500
    (float("inf"), 6.0, 6.0),  # 2500 < A
]

def required_height_mm(area_cm2: float, molded: bool = False) -> float:
    """Minimum height of numerals & letters (Rule 7(2), Table-I)."""
    for limit, normal, blown in TABLE_I:
        if area_cm2 <= limit:
            return blown if molded else normal
    return 6.0

def pdp_area(dims_str: str, img_w: int, img_h: int, dpi: float):
    """Compute Principal Display Panel area (Rule 7(4)).
    dims_str formats: '10x8' rectangular HxW cm | 'cyl:20x25' height x circumference cm |
    'other:120' total surface area cm2 | '' estimate from image."""
    dims = (dims_str or "").strip()
    if not dims:
        # estimate: assume full-frame rectangular label at print DPI
        a = (img_w / dpi * 2.54) * (img_h / dpi * 2.54)
        return round(a, 1), "estimated from image (assumes full-frame label @ {} dpi)".format(int(dpi))
    if dims.lower().startswith("cyl:"):
        try:
            h, c = [float(x) for x in dims[4:].split("x")]
            a = 0.4 * h * c
            return round(a, 1), "cylindrical: 40% of height x circumference (Rule 7(4)(b))"
        except Exception:
            pass
    if dims.lower().startswith("other:"):
        try:
            return float(dims[6:]), "other shape: 40% of total surface area (Rule 7(4)(c))"
        except Exception:
            pass
    m = re.match(r"^(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)$", dims)
    if m:
        a = float(m.group(1)) * float(m.group(2))
        return round(a, 1), "rectangular: height x width of PDP side (Rule 7(4)(a))"
    return None, "unparseable dimensions"

FIELD_PATTERNS = {
    "mrp": re.compile(r"m\.?r\.?p\.?|max(?:imum)?\.?\s*(?:retail\s*)?price|retail\s*sale\s*price", re.I),
    "net_qty": re.compile(r"\d+(?:[.,]\d+)?\s*(?:kg|kilograms?|gm|gr|grams?|ml|millilit(re|er)s?|mg|"
                          r"l|lit(re|er)s?|cm|mm|m|pcs|pc|nos?|no\.?s?|pieces?|count|sheets?|u|n)\b", re.I),
    "mfg": re.compile(r"\b(?:mfg|mfd|manufactur(?:ed|ing)|pack(?:ed|ing)|pre-?pack(?:ed|ing)|import(?:ed|ing)?|bottl(?:ed|ing))\b[^A-Za-z]{0,15}\d", re.I),
    "best_before": re.compile(r"\b(?:best\s*before|use\s*by|use\s*before|expiry|exp\.?\s*date|exp)\b[^A-Za-z]{0,15}\d", re.I),
    "consumer_care": re.compile(r"\b(?:consumer\s*(?:care|service|helpline)|customer\s*(?:care|service)|toll\s*free|help\s*line|complaints?)\b|(?:\+?91[\s\-]?)?[6-9]\d{9}|1800[\s\-]?\d{3}[\s\-]?\d{3,4}", re.I),
    "manufacturer": re.compile(r"\b(?:manufactur(?:ed|er)?\s*[by:]|mfg\s*[by:]|packed\s*[by:]|packer\s*[by:]|imported\s*[by:]|marketed\s*[by:]|distributed\s*[by:])\b", re.I),
    "common_name": re.compile(r".+"),  # handled specially via product tokens
}

def line_boxes(words):
    """Group OCR words into visual lines by vertical proximity (tesseract line ids are unreliable).
    Tolerance is based on word height (never on the growing cluster span)."""
    if not words:
        return []
    ws = sorted(words, key=lambda w: (w["y"], w["x"]))
    clusters = []  # each: {"words": [...], "y0","y1","h_med"}
    for w in ws:
        placed = False
        for cl in clusters:
            tol = 0.35 * min(cl["h_med"], w["h"])
            if w["y"] <= cl["y1"] + tol and w["y"] + w["h"] >= cl["y0"] - tol:
                cl["words"].append(w)
                cl["y0"] = min(cl["y0"], w["y"])
                cl["y1"] = max(cl["y1"], w["y"] + w["h"])
                hs = sorted(w["h"] for w in cl["words"])
                cl["h_med"] = hs[len(hs) // 2]
                placed = True
                break
        if not placed:
            clusters.append({"words": [w], "y0": w["y"], "y1": w["y"] + w["h"], "h_med": w["h"]})
    for cl in clusters:
        cl["words"].sort(key=lambda w: w["x"])
    clusters.sort(key=lambda cl: cl["y0"])
    return [cl["words"] for cl in clusters]

def text_of(line):
    return " ".join(w["text"] for w in line)

def measure_fields(ocr, extracted, product_tokens):
    """Measure font heights (mm) for each declaration field. Returns list of field dicts."""
    pix_per_mm = ocr["pix_per_mm"]
    lines = line_boxes(ocr["words"])
    fields = {}

    def add(name, line, label):
        if not line:
            return
        h_px = max(w["h"] for w in line)
        h_mm = round(h_px / pix_per_mm, 2)
        confs = [w["conf"] for w in line]
        char_widths = [round((w["w"] / max(1, len(w["text"]))) / pix_per_mm, 2) for w in line]
        fields[name] = {
            "label": label, "height_mm": h_mm, "conf": int(sum(confs) / len(confs)),
            "width_mm_avg": (sum(char_widths) / len(char_widths)) if char_widths else 0,
            "text": text_of(line)[:90],
            "x": min(w["x"] for w in line), "y": min(w["y"] for w in line),
            "w": max(w["x"] + w["w"] for w in line) - min(w["x"] for w in line),
            "h": max(w["y"] + w["h"] for w in line) - min(w["y"] for w in line),
        }

    def find_line(pat):
        for ln in lines:
            if pat.search(text_of(ln)):
                return ln
        return None

    add("mrp", find_line(FIELD_PATTERNS["mrp"]), "MRP / Retail sale price (Rule 6(1)(e))")
    add("net_qty", find_line(FIELD_PATTERNS["net_qty"]), "Net quantity (Rule 6(1)(c))")
    add("mfg", find_line(FIELD_PATTERNS["mfg"]), "Month & year of manufacture (Rule 6(1)(d))")
    add("best_before", find_line(FIELD_PATTERNS["best_before"]), "Best before / Use by (Rule 6(1)(da))")
    add("consumer_care", find_line(FIELD_PATTERNS["consumer_care"]), "Consumer care details (Rule 6(2))")
    add("manufacturer", find_line(FIELD_PATTERNS["manufacturer"]), "Name & address of manufacturer/packer/importer (Rule 6(1)(a))")
    if product_tokens:
        toks = [t for t in product_tokens if len(t) >= 3]
        if toks:
            for ln in lines:
                t = text_of(ln).lower()
                if any(tok in t for tok in toks):
                    add("common_name", ln, "Common/generic name (Rule 6(1)(b))")
                    break
    return fields
