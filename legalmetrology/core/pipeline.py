"""Scan pipeline: image/listing -> OCR (multi-pass) -> extraction -> validation -> persistence."""
import os, json, re
from . import ocr as ocr_mod, extract as ex, validate as val, fontsize, image_analysis, db

# ------------------------------------------------------------------ extractors
def _best_common_name(passes, product_name, category):
    """Pick the pass whose text matches the product/category tokens best."""
    base = ex.extract_common_name(product_name, passes[0]["text"], category)
    best = base
    for p in passes[1:]:
        cand = ex.extract_common_name(product_name, p["text"], category)
        if cand["found"] and (not best["found"] or len(cand["hits"]) + len(cand["cat_hits"]) >
                              len(best["hits"]) + len(best["cat_hits"])):
            best = cand
    return best

def _best_text_field(passes, fn, prefer_tax=False):
    """Run a list-returning extractor over every OCR pass and pick the best result.
    prefer_tax: for MRP, prefer candidates carrying the 'incl. of all taxes' wording."""
    results = []
    for p in passes:
        try:
            items = fn(p["text"])
            if items:
                results.append((items, p))
        except Exception:
            continue
    if not results:
        return [], None
    if prefer_tax:
        with_tax = [r for r in results if any(x.get("incl_taxes") for x in r[0])]
        if with_tax:
            results = with_tax
        merged = [x for r in results for x in r[0]]
        seen, uniq = set(), []
        for x in merged:
            k = (x.get("value"), x.get("matched", ""))
            if k not in seen:
                seen.add(k); uniq.append(x)
        return uniq, results[0][1]
    def score(items):
        s = 0
        for it in items:
            if it.get("month") and it.get("year"):
                s += 5
            if it.get("phones") or it.get("emails"):
                s += 4
            s += 1
        return s
    best = max(results, key=lambda r: score(r[0]))
    return best[0], best[1]

def _best_dict_field(passes, fn):
    """Run a dict-returning extractor over every pass; pick the richest result."""
    def richness(d):
        s = 0
        if d.get("found"):
            s += 4
        if d.get("origin"):
            s += 4
        s += len(d.get("phones") or []) * 2 + len(d.get("emails") or []) * 2
        s += len(d.get("snippet") or "")
        return s
    best, best_r = fn(passes[0]["text"]), None
    for p in passes[1:]:
        cand = fn(p["text"])
        r = richness(cand)
        if best_r is None or r > best_r:
            best, best_r = cand, r
    return best

def run_image_scan(image_path, product_name, category, dims_str, user_id=None):
    """Full pipeline for a package image. Returns dict with scan row + checks."""
    o = ocr_mod.run_ocr(image_path)
    passes = o["passes"]

    # ---- extraction across passes ----
    ext = {}
    ext["mrp"], _ = _best_text_field(passes, ex.extract_mrp, prefer_tax=True)
    ext["net_qty"], _ = _best_text_field(passes, ex.extract_net_qty)
    ext["mfg_date"], _ = _best_text_field(passes, ex.extract_mfg_date)
    ext["best_before"], _ = _best_text_field(passes, ex.extract_best_before)
    ext["consumer_care"] = _best_dict_field(passes, ex.extract_consumer_care)
    ext["dimensions"], _ = _best_text_field(passes, ex.extract_dimensions)
    ext["address"] = _best_dict_field(passes, ex.extract_address)
    ext["country"] = _best_dict_field(passes, ex.extract_country)
    ext["barcode"] = _best_dict_field(passes, ex.extract_barcode)
    ext["common_name"] = _best_common_name(passes, product_name, category)

    # ---- geometry (mm measurement only valid when the image has a print scale) ----
    measure_ok = not o["is_photo"]
    area, method = fontsize.pdp_area(dims_str, o["img_w"], o["img_h"], o["dpi"])
    if o["is_photo"] and not dims_str:
        area, method = None, "photo without print resolution — PDP area not computed"
    if area is None and dims_str:
        area, method = fontsize.pdp_area("", o["img_w"], o["img_h"], o["dpi"])

    product_tokens = ext["common_name"]["tokens"]
    fields = fontsize.measure_fields(o, ext, product_tokens)
    if measure_ok and "mrp" not in fields:
        for p in passes[1:]:
            alt_ocr = dict(o); alt_ocr["words"] = p["words"]
            alt_fields = fontsize.measure_fields(alt_ocr, ext, product_tokens)
            for k in ("mrp", "net_qty", "consumer_care", "manufacturer", "mfg", "best_before"):
                if k not in fields and k in alt_fields:
                    fields[k] = alt_fields[k]

    from PIL import Image
    img = Image.open(image_path)
    qty_line = None
    for ln in fontsize.line_boxes(o["words"]):
        if fontsize.FIELD_PATTERNS["net_qty"].search(fontsize.text_of(ln)):
            qty_line = ln
            break
    img_an = {
        "clear_space": image_analysis.clear_space_violations(o["words"], qty_line),
        "contrast": {},
        "veg_dot": image_analysis.detect_veg_dot(img),
    }
    for key, f in fields.items():
        if key in ("mrp", "net_qty"):
            pat = re.compile(r"\d+[.,]\d{2}") if key == "mrp" else re.compile(r"\d+")
            cands = [w for w in o["words"] + o.get("words_alt", [])
                     if pat.search(w["text"]) and w["x"] >= f["x"] - 5 and w["x"] + w["w"] <= f["x"] + f["w"] + 5
                     and w["y"] >= f["y"] - 5 and w["y"] + w["h"] <= f["y"] + f["h"] + 5]
            if cands:
                tight = {"x": min(w["x"] for w in cands), "y": min(w["y"] for w in cands),
                         "w": max(w["x"] + w["w"] for w in cands) - min(w["x"] for w in cands),
                         "h": max(w["y"] + w["h"] for w in cands) - min(w["y"] for w in cands)}
                img_an["contrast"][key] = image_analysis.box_contrast(img, tight)
            else:
                img_an["contrast"][key] = image_analysis.box_contrast(img, f)

    checks = val.run_checks(ext, o, img_an, {
        "category": category, "ecommerce": False, "dims_str": dims_str,
        "product_name": product_name, "pdp_area": area, "pdp_method": method,
        "fields": fields, "measure_ok": measure_ok, "is_photo": o["is_photo"]})
    status, score = val.overall(checks)

    conn = db.get_conn()
    scan_code = db.new_scan_code()
    cur = conn.execute("""INSERT INTO scans
        (scan_code, product_name, category, source, file_path, pkg_dims_cm, pdp_area_cm2, dpi,
         raw_text, extracted_json, checks_json, font_json, overall_status, score, created_by,
         is_photo, dpi_source)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (scan_code, product_name, category, "image", image_path, dims_str, area, o["dpi"],
         o["text"], json.dumps(ext, ensure_ascii=False), json.dumps(checks, ensure_ascii=False),
         json.dumps(fields, ensure_ascii=False), status, score, user_id,
         1 if o["is_photo"] else 0, o["dpi_source"]))
    scan_id = cur.lastrowid
    conn.commit(); conn.close()
    db.audit(None if not user_id else {"id": user_id, "username": "inspector"}, "SCAN_IMAGE",
             scan_code, f"{product_name} -> {status} ({score})")
    return {"id": scan_id, "scan_code": scan_code, "status": status, "score": score,
            "checks": checks, "fields": fields, "pdp_area": area, "pdp_method": method,
            "ocr_word_count": o["word_count"], "dpi": o["dpi"], "is_photo": o["is_photo"]}

def run_listing_scan(listing_text, product_name, category, user_id=None):
    """Compliance check of an e-commerce listing (Rule 6(10)) — text-only pipeline."""
    ext = {
        "mrp": ex.extract_mrp(listing_text),
        "net_qty": ex.extract_net_qty(listing_text),
        "mfg_date": ex.extract_mfg_date(listing_text),
        "best_before": ex.extract_best_before(listing_text),
        "consumer_care": ex.extract_consumer_care(listing_text),
        "address": ex.extract_address(listing_text),
        "country": ex.extract_country(listing_text),
        "common_name": ex.extract_common_name(product_name, listing_text, category),
        "dimensions": ex.extract_dimensions(listing_text),
        "barcode": ex.extract_barcode(listing_text),
    }
    o = {"text": listing_text, "words": [], "pix_per_mm": 300 / 25.4, "dpi": 300,
         "img_w": 0, "img_h": 0, "is_photo": False}
    img_an = {"clear_space": [], "contrast": {}, "veg_dot": {"green": False, "red_brown": False, "found": False}}
    checks = val.run_checks(ext, o, img_an, {
        "category": category, "ecommerce": True, "dims_str": "",
        "product_name": product_name, "pdp_area": 0, "pdp_method": "n/a (listing)",
        "fields": {}, "measure_ok": False, "is_photo": False})
    checks = [c for c in checks if c["id"] not in ("QTY_CLEAR_SPACE", "FONT_SIZE", "FONT_WIDTH",
                                                   "CONTRAST", "VEG_DOT", "LEGIBILITY", "STICKER",
                                                   "PHOTO_SCALE", "PDP_PANEL")]
    status, score = val.overall(checks)
    conn = db.get_conn()
    scan_code = db.new_scan_code()
    cur = conn.execute("""INSERT INTO scans
        (scan_code, product_name, category, source, listing_text, raw_text, extracted_json, checks_json,
         overall_status, score, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (scan_code, product_name, category, "listing", listing_text, listing_text,
         json.dumps(ext, ensure_ascii=False), json.dumps(checks, ensure_ascii=False), status, score, user_id))
    scan_id = cur.lastrowid
    conn.commit(); conn.close()
    db.audit(None if not user_id else {"id": user_id, "username": "inspector"}, "SCAN_LISTING",
             scan_code, f"{product_name} -> {status} ({score})")
    return {"id": scan_id, "scan_code": scan_code, "status": status, "score": score, "checks": checks}

def overlay_for(scan_row, image_path):
    """Generate annotated overlay image path for a scan."""
    from PIL import Image
    try:
        fields = json.loads(scan_row["font_json"] or "{}")
        o = ocr_mod.run_ocr(image_path)
        out = os.path.join(db.GEN_DIR, f"overlay_{scan_row['id']}.jpg")
        return image_analysis.make_overlay(Image.open(image_path), o["words"], fields, out)
    except Exception:
        return None
