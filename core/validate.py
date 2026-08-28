"""Rule-based compliance engine — Legal Metrology (Packaged Commodities) Rules, 2011 (as amended)."""
import re
from datetime import datetime
from . import extract as ex
from .fontsize import required_height_mm

TODAY = datetime.now().date()

def _ck(cid, rule, title, status, severity, message, evidence="", suggestion=""):
    return {"id": cid, "rule": rule, "title": title, "status": status, "severity": severity,
            "message": message, "evidence": evidence[:400], "suggestion": suggestion}

def _fail(cid, rule, title, sev, message, ev="", sug="", suggestion=""):
    return _ck(cid, rule, title, "FAIL", sev, message, ev, sug or suggestion)

def _warn(cid, rule, title, message, ev="", sug="", suggestion=""):
    return _ck(cid, rule, title, "WARN", "MINOR", message, ev, sug or suggestion)

def _pass(cid, rule, title, message, ev=""):
    return _ck(cid, rule, title, "PASS", "OK", message, ev)

def _info(cid, rule, title, message, ev="", suggestion=""):
    return _ck(cid, rule, title, "INFO", "INFO", message, ev, suggestion)

SECOND_SCHEDULE = {  # subset of the Second Schedule (standard pack sizes)
    "tea": ["50 g", "100 g", "200 g", "250 g", "500 g", "1 kg", "2 kg"],
    "biscuit": ["25 g", "50 g", "100 g", "200 g", "250 g", "400 g", "500 g", "750 g", "1 kg"],
    "milk powder": ["50 g", "100 g", "200 g", "250 g", "500 g", "1 kg"],
    "salt": ["100 g", "200 g", "500 g", "1 kg", "2 kg"],
    "sugar": ["500 g", "1 kg", "2 kg", "5 kg"],
    "detergent": ["50 g", "100 g", "200 g", "500 g", "700 g", "1 kg", "1.5 kg", "2 kg"],
    "edible oil": ["100 ml", "200 ml", "500 ml", "1 l", "2 l", "5 l"],
}

def run_checks(extracted, ocr, image_analysis, context):
    """context: dict(category, ecommerce, dims_str, product_name, pdp_area, pdp_method, fields, user_notes)"""
    cat = (context.get("category") or "").lower()
    ecom = bool(context.get("ecommerce"))
    pdp = context.get("pdp_area") or 0.0
    req = required_height_mm(pdp)
    is_photo = context.get("is_photo", False)
    photo_hint = " (the declaration may be on another panel — re-photograph the principal display panel)" if is_photo else ""
    checks = []

    # ---------------- Rule 6(1)(a) + Rule 10 : manufacturer / packer / importer ----------------
    addr = extracted["address"]
    if addr["found"]:
        checks.append(_pass("MANUF_ADDR", "R6(1)(a), R10",
                            "Name & address of manufacturer/packer/importer",
                            f"Qualifier detected: '{addr['snippet'][:80]}'", addr["snippet"]))
    else:
        checks.append(_fail("MANUF_ADDR", "R6(1)(a), R10", "Name & address of manufacturer/packer/importer",
                            "CRITICAL",
                            "No declaration of name and address of manufacturer/packer/importer found "
                            "(e.g. 'Manufactured by: ...', 'Packed by: ...').",
                            extracted["address"].get("snippet", ""),
                            "Print name and complete address (with PIN code) of manufacturer; if packer is "
                            "different, give both; importer's name/address for imported packages."))
    if addr["snippet"] and not addr["pincode"] and len(addr["snippet"]) > 5:
        checks.append(_warn("MANUF_ADDR_PIN", "R10", "Address completeness",
                            "Address found but no 6-digit PIN code detected — Rule 10 requires the complete address.",
                            addr["snippet"]))

    # ---------------- Rule 6(1)(aa) : country of origin ----------------
    co = extracted["country"]
    if co["imported"]:
        if co["origin"]:
            checks.append(_pass("COUNTRY_ORIGIN", "R6(1)(aa)",
                                "Country of origin (imported product)",
                                f"Country of origin declared: {co['origin']}", co["matched"]))
        else:
            checks.append(_fail("COUNTRY_ORIGIN", "R6(1)(aa)", "Country of origin (imported product)",
                                "CRITICAL",
                                "Product appears imported ('imported by' detected) but country of origin is "
                                "not declared on the label.", co["matched"],
                                "Mention country of origin / manufacture / assembly on the package."))
    else:
        checks.append(_info("COUNTRY_ORIGIN", "R6(1)(aa)", "Country of origin",
                            "No import indication detected; country of origin not mandatory for domestic products."))

    # ---------------- Rule 6(1)(b) : common/generic name ----------------
    cn = extracted["common_name"]
    if cn["found"]:
        hits = (cn["hits"] + cn["cat_hits"])[:6]
        checks.append(_pass("COMMON_NAME", "R6(1)(b)", "Common or generic name of commodity",
                            f"Generic name content detected on label: {', '.join(hits) or 'yes'}", " ".join(hits)))
    else:
        checks.append(_fail("COMMON_NAME", "R6(1)(b)", "Common or generic name of commodity",
                            "CRITICAL",
                            "Common/generic name of the commodity could not be detected on the label "
                            "(brand names alone are insufficient).",
                            f"product tokens: {cn['tokens'][:10]}",
                            "Print the common or generic name (e.g. 'Wheat Biscuits', 'Toilet Soap')."))

    # ---------------- Rule 6(1)(c) : net quantity ----------------
    nq = extracted["net_qty"]
    if nq:
        best = nq[0]
        checks.append(_pass("NET_QTY", "R6(1)(c)", "Net quantity in standard unit",
                            f"Net quantity declared: {best['value']:g} {best['unit']} ({best['type']})",
                            best["matched"]))
        if best["unit_raw"] in ex.NON_SI:
            checks.append(_fail("NET_QTY_UNIT", "R6(1)(c), R8(5)", "Standard (S.I.) unit symbol",
                                "MAJOR",
                                f"Non-standard unit symbol '{best['unit_raw']}' used; SI symbol "
                                f"'{ex.NON_SI[best['unit_raw']]}' is prescribed (Rule 8(5)).",
                                best["matched"],
                                f"Replace '{best['unit_raw']}' with the SI symbol '{ex.NON_SI[best['unit_raw']]}'."))
        elif best["unit"] in ("g", "ml") and best["value"] >= 1000:
            checks.append(_warn("NET_QTY_UNIT", "R6(1)(c), R8(5)", "S.I. unit formatting",
                                f"Quantity {best['value']:g} {best['unit']} may be better expressed in "
                                f"{'kg' if best['unit']=='g' else 'l'} (Rule 8(5) — SI system).", best["matched"]))
        else:
            checks.append(_pass("NET_QTY_UNIT", "R6(1)(c), R8(5)", "Standard (S.I.) unit symbol",
                                f"SI unit symbol '{best['unit']}' used correctly.", best["matched"]))
        if re.search(r"\b(dozen|score|gross|great\s*gross)\b", ocr["text"].lower()):
            checks.append(_fail("NET_QTY_WORD", "R8(4)", "Prohibition of 'dozen/score/gross'",
                                "MAJOR", "Words like 'dozen', 'score', 'gross', 'great gross' detected — "
                                "specifying or indicating such numbers on a package is prohibited.",
                                "text contains 'dozen/score/gross'"))
    else:
        checks.append(_fail("NET_QTY", "R6(1)(c)", "Net quantity in standard unit",
                            "CRITICAL", "No net quantity declaration detected (weight/volume/number "
                            "in standard units is mandatory).",
                            suggestion="Declare net quantity e.g. 'NET WT. 500 g' / '500 ml' / '10 N'." + photo_hint))

    # ---------------- Rule 6(1)(d) : month & year of manufacture ----------------
    if ecom:
        checks.append(_info("MFG_DATE", "R6(1)(d), R6(10)", "Month & year of manufacture",
                            "Exempt for e-commerce listings — Rule 6(10) does not require month/year of "
                            "manufacture on digital network listings."))
    else:
        mfg = extracted["mfg_date"]
        if mfg:
            d = mfg[0]
            extra = ""
            if d["month"] and d["year"]:
                if d["year"] > TODAY.year + 1 or (d["year"] == TODAY.year + 1 and d["month"] > TODAY.month):
                    extra = " Future-dated declaration — review."
            checks.append(_pass("MFG_DATE", "R6(1)(d)", "Month & year of manufacture/packing/import",
                                f"Declared: {d['matched']}.{extra}", d["matched"]))
        else:
            checks.append(_fail("MFG_DATE", "R6(1)(d)", "Month & year of manufacture/packing/import",
                                "CRITICAL",
                                "Month and year of manufacture/packing/import not detected "
                                "(e.g. 'Mfg: 06/2026').",
                                suggestion="Declare month & year of manufacture/pre-packing/import "
                                "(numerals or words, e.g. 'Mfg. 06/2026')." + photo_hint))

    # ---------------- Rule 6(1)(da) : best before / use by ----------------
    perishable = ex.is_perishable_category(cat)
    bb = extracted["best_before"]
    if ecom:
        pass  # still checked below via presence (listings need BB where applicable)
    if bb:
        d = bb[0]
        if d["month"] and d["year"]:
            bd = datetime(d["year"], d["month"], 28).date()
            if bd < TODAY:
                checks.append(_fail("BEST_BEFORE", "R6(1)(da)", "Best before / Use by date",
                                    "MAJOR", f"Declared '{d['matched']}' is in the PAST — product expired/"
                                    "past best-before. Not marketable.", d["matched"],
                                    "Recall/replace stock; declare valid best-before/use-by date."))
            else:
                checks.append(_pass("BEST_BEFORE", "R6(1)(da)", "Best before / Use by date",
                                    f"Declared '{d['matched']}' — valid.", d["matched"]))
        else:
            checks.append(_pass("BEST_BEFORE", "R6(1)(da)", "Best before / Use by date",
                                f"Declared (unparseable format): {d['matched']}", d["matched"]))
    elif perishable:
        checks.append(_fail("BEST_BEFORE", "R6(1)(da)", "Best before / Use by date",
                            "MAJOR",
                            "Category appears to be food/perishable ('{}') but no 'Best before' or 'Use by' "
                            "date detected.".format(cat),
                            suggestion="Declare best-before/use-by date (month & year) for commodities that "
                            "may become unfit for human consumption."))
    else:
        checks.append(_info("BEST_BEFORE", "R6(1)(da)", "Best before / Use by date",
                            "Not applicable — category not identified as perishable."))

    # ---------------- cross-field date consistency ----------------
    mfg0 = (extracted["mfg_date"] or [{}])[0]
    bb0 = (extracted["best_before"] or [{}])[0]
    if mfg0.get("month") and mfg0.get("year"):
        if (mfg0["year"], mfg0["month"]) > (TODAY.year, TODAY.month):
            checks.append(_warn("MFG_FUTURE", "R6(1)(d)", "Manufacture date plausibility",
                                f"Declared manufacture date '{mfg0['matched']}' is in the FUTURE — "
                                "verify the month/year declaration."))
    if (mfg0.get("month") and mfg0.get("year") and bb0.get("month") and bb0.get("year")):
        if (bb0["year"], bb0["month"]) < (mfg0["year"], mfg0["month"]):
            checks.append(_fail("BB_BEFORE_MFG", "R6(1)(d), R6(1)(da)", "Date consistency",
                                "MAJOR",
                                f"Best-before/use-by date '{bb0['matched']}' is EARLIER than the declared "
                                f"manufacture date '{mfg0['matched']}' — declarations are inconsistent.",
                                f"BB {bb0['raw']} vs MFG {mfg0['raw']}",
                                "Correct the best-before/use-by or manufacture date declaration."))

    # ---------------- Rule 6(1)(e) + 2(m) : MRP ----------------
    mrps = extracted["mrp"]
    if mrps:
        m = mrps[0]
        paise = round((m["value"] - int(m["value"])) * 100)
        rounded_ok = paise in (0, 50) or m["value"] == int(m["value"])
        tax_note = ("includes tax wording" if m["incl_taxes"]
                    else "does NOT carry the 'incl. of all taxes' wording")
        checks.append(_pass("MRP", "R6(1)(e), R2(m)", "Retail sale price (MRP) declaration",
                            f"MRP declared: Rs. {m['value']:.2f} — {tax_note}.", m["matched"]))
        if not m["incl_taxes"]:
            checks.append(_fail("MRP_TAX", "R6(1)(e), R2(m)", "MRP 'inclusive of all taxes' wording",
                                "MAJOR",
                                "MRP declared without the mandatory 'inclusive of all taxes' / 'incl. of all "
                                "taxes' wording (see illustrations under Rule 2(m)).", m["matched"],
                                "Print e.g. 'MRP Rs. 99.00 (incl. of all taxes)'."))
        if not m["has_mrp_keyword"]:
            checks.append(_fail("MRP_KW", "R6(1)(e)", "Use of 'MRP' / 'Maximum retail price'",
                                "MAJOR", "Retail price found but without 'MRP' / 'Maximum retail price' "
                                "terminology.", m["matched"],
                                "Prefix with 'MRP' or 'Maximum Retail Price'."))
        if not rounded_ok:
            checks.append(_fail("MRP_ROUNDING", "R2(m) (GSR 629(E)/2017)", "MRP rounding to nearest rupee/50 paise",
                                "MAJOR",
                                f"MRP Rs. {m['value']:.2f} is not rounded to the nearest rupee or 50 paise "
                                "(fraction < 50p → preceding rupee; > 50p & ≤ 95p → 50 paise).", m["matched"],
                                f"Round MRP to nearest rupee or 50 paise (e.g. Rs. {round(m['value'])}.00 or "
                                f"{int(m['value'] // 1)}.50)."))
        if len(mrps) > 1 and len({x['value'] for x in mrps}) > 1:
            vals = ", ".join(f"Rs. {x['value']:.2f}" for x in mrps)
            checks.append(_fail("MRP_SINGLE", "R6(1)(e) (GSR 629(E)/2017)", "Single MRP only",
                                "MAJOR", f"Multiple distinct retail prices detected ({vals}) — only one MRP "
                                "may be declared (no overwriting/dual pricing).", vals,
                                "Print a single MRP; use lower-MRP sticker only as permitted by Rule 6(3)."))
    else:
        checks.append(_fail("MRP", "R6(1)(e), R2(m)", "Retail sale price (MRP) declaration",
                            "CRITICAL", "No Maximum Retail Price (MRP) declaration detected on the label.",
                            suggestion="Print 'MRP Rs. ____ (incl. of all taxes)' on the principal display panel." + photo_hint))
    if mrps and nq:
        best = nq[0]
        m = mrps[0]
        if m["value"] <= 0:
            checks.append(_fail("MRP_ZERO", "R6(1)(e)", "MRP value sanity",
                                "MAJOR", "MRP amount appears to be zero/invalid.", m["matched"],
                                "Declare a valid MRP in rupees and paise."))
        # notional check: implausibly low MRP for the declared quantity (very conservative:
        # below ₹50 per kg/litre is suspicious for most packaged goods)
        if best["unit"] in ("g", "ml") and best["value"] >= 100 and m["value"] < 0.05 * best["value"]:
            checks.append(_warn("MRP_QTY_SANE", "R6(1)(c),(e)", "MRP vs net quantity plausibility",
                                f"MRP Rs. {m['value']:.2f} appears very low for net quantity "
                                f"{best['value']:g} {best['unit']} — verify the amount."))

    # ---------------- Rule 6(2) : consumer care ----------------
    cc = extracted["consumer_care"]
    care_ok = bool(cc["phones"] or cc["emails"]) and cc["care_kw"]
    if care_ok:
        detail = (cc["phones"] + cc["emails"])[:3]
        checks.append(_pass("CONSUMER_CARE", "R6(2)", "Consumer care / complaint contact details",
                            f"Contact details found: {', '.join(detail)}", ", ".join(detail)))
    elif cc["phones"] or cc["emails"]:
        checks.append(_warn("CONSUMER_CARE", "R6(2)", "Consumer care / complaint contact details",
                            "Contact number/email found but no 'consumer care / complaints / helpline' "
                            "label context detected — verify the declaration is identifiable as the "
                            "complaint-contact (Rule 6(2)).", ", ".join(cc["phones"] + cc["emails"])))
    else:
        checks.append(_fail("CONSUMER_CARE", "R6(2)", "Consumer care / complaint contact details",
                            "CRITICAL",
                            "No consumer care contact (name/address, telephone or e-mail for complaints) "
                            "detected on the package (Rule 6(2), as per GSR 385(E)/2015).",
                            suggestion="Print the name, address, telephone number and e-mail address of the "
                            "person/office to be contacted in case of complaints." + photo_hint))

    # ---------------- Rule 6(1)(f) : dimensions ----------------
    dims = extracted["dimensions"]
    if dims:
        checks.append(_info("DIMENSIONS", "R6(1)(f)", "Dimensions of commodity",
                            f"Dimensions declared: {dims[0]['dims']} {dims[0]['unit']}".strip()))
    else:
        checks.append(_info("DIMENSIONS", "R6(1)(f)", "Dimensions of commodity",
                            "No size/dimension declaration detected — required only where sizes of the "
                            "commodity are relevant."))

    # ---------------- Rule 7 : font sizes ----------------
    fields = context.get("fields") or {}
    measure_ok = context.get("measure_ok", True)
    is_photo = context.get("is_photo", False)
    if is_photo and fields:
        # A photograph has no print scale: mm heights cannot be trusted. Report an honest advisory.
        sizes = " · ".join(f"{v['label'].split(' (')[0]}: ≈{v['height_mm']:.2f} mm" for v in fields.values())
        checks.append(_info("PHOTO_SCALE", "R7(2)", "Font-size measurement (photo)",
                            "This image is a photograph without print-resolution metadata — physical font "
                            "heights cannot be measured reliably. Reported as estimate only: " + sizes,
                            suggestion="Re-photograph the label flat with a ruler/scale reference, or enter "
                            "package dimensions and re-scan for a Table-I comparison."))
    for key, f in fields.items():
        req_mm = required_height_mm(pdp)
        if not measure_ok:
            continue  # advisory already emitted above
        if f["height_mm"] < req_mm - 0.15:  # tolerance for OCR measurement
            checks.append(_fail("FONT_SIZE", "R7(2) Table-I",
                                f"Font size — {f['label']}",
                                "MAJOR",
                                f"Measured height ≈ {f['height_mm']:.2f} mm vs minimum required "
                                f"{req_mm:.1f} mm for PDP area {pdp:g} cm².",
                                f"'{f['text']}'", "Enlarge the declaration font to at least the Table-I minimum."))
        else:
            checks.append(_pass("FONT_SIZE", "R7(2) Table-I",
                                f"Font size — {f['label']}",
                                f"Measured height ≈ {f['height_mm']:.2f} mm ≥ required {req_mm:.1f} mm "
                                f"(PDP {pdp:g} cm²).", f"'{f['text']}'"))
        if f["width_mm_avg"] and f["height_mm"]:
            ratio = f["width_mm_avg"] / f["height_mm"]
            if ratio < 0.33:
                checks.append(_fail("FONT_WIDTH", "R7(3)", f"Letter width — {f['label']}",
                                    "MAJOR",
                                    f"Average letter/numeral width ({f['width_mm_avg']:.2f} mm) is less than "
                                    f"1/3 of height ({f['height_mm']:.2f} mm).", f"'{f['text']}'",
                                    "Ensure width of letters/numerals ≥ 1/3 of their height."))
        if f["conf"] < 55:
            checks.append(_warn("LEGIBILITY", "R9(1)(a)", f"Legibility — {f['label']}",
                                f"OCR confidence {f['conf']}% is low for '{f['text']}' — declaration may not "
                                "be legible/prominent (Rule 9(1)(a)). Verify physically.", f"'{f['text']}'"))

    # ---------------- back-panel advisory for photos ----------------
    if is_photo and not extracted["mrp"] and re.search(r"ingredients|best before|storage|fssai", ocr["text"], re.I):
        checks.append(_warn("PDP_PANEL", "R8(1)", "Panel photographed",
                            "The photographed side shows back-panel content (ingredients/address). MRP, net "
                            "quantity and other mandatory declarations live on the principal display panel — "
                            "photograph the FRONT of the package and re-scan.",
                            suggestion="Capture the principal display panel (front) with MRP, net quantity and "
                            "month/year declarations."))

    # ---------------- Rule 8 : clear space around quantity ----------------
    qv = image_analysis.get("clear_space", [])
    if qv:
        checks.append(_warn("QTY_CLEAR_SPACE", "R8(1) proviso", "Clear space around net quantity",
                            "Printed information found within the prescribed clear area around the quantity "
                            "declaration: " + "; ".join(qv[:3]) + ".", "; ".join(qv[:3]),
                            "Keep the area around the quantity declaration free of print: height of numeral "
                            "above/below; twice the height left/right."))
    else:
        checks.append(_pass("QTY_CLEAR_SPACE", "R8(1) proviso", "Clear space around net quantity",
                            "No printed text detected within the required clear zone around the quantity declaration."))

    # ---------------- Rule 9 : contrast ----------------
    for key in ("mrp", "net_qty"):
        f = fields.get(key)
        if not f:
            continue
        cr = image_analysis.get("contrast", {}).get(key)
        if cr is None:
            continue
        if cr < 1.25:
            checks.append(_fail("CONTRAST", "R9(1)(b)", f"Contrast — {f['label']}",
                                "MAJOR",
                                f"Measured contrast ratio {cr}:1 — MRP/net-quantity numerals must contrast "
                                "conspicuously with the label background.",
                                f"'{f['text']}'", "Print MRP & net quantity numerals in a colour that contrasts "
                                "conspicuously with the background."))
        elif cr < 1.5:
            checks.append(_warn("CONTRAST", "R9(1)(b)", f"Contrast — {f['label']}",
                                f"Measured contrast ratio {cr}:1 is low — verify numerals contrast "
                                "conspicuously (Rule 9(1)(b)).", f"'{f['text']}'"))

    # ---------------- Rule 9(4) : language ----------------
    if not ex.has_latin_or_devanagari(ocr["text"]):
        checks.append(_warn("LANGUAGE", "R9(4)", "Language of declarations",
                            "Declarations do not appear to be in English or Hindi (Devanagari) — every "
                            "declaration must be in English or Hindi."))
    else:
        checks.append(_pass("LANGUAGE", "R9(4)", "Language of declarations",
                            "Declarations appear in English/Hindi (Latin/Devanagari script detected)."))

    # ---------------- Rule 6(8) : veg/non-veg dot ----------------
    if ex.is_cosmetic_category(cat):
        dot = image_analysis.get("veg_dot", {})
        if dot.get("found"):
            kind = "green (vegetarian)" if dot.get("green") else "red/brown (non-vegetarian)"
            checks.append(_pass("VEG_DOT", "R6(8)", "Vegetarian / non-vegetarian dot",
                                f"Mark detected: {kind} dot near top of principal display panel."))
        else:
            checks.append(_fail("VEG_DOT", "R6(8)", "Vegetarian / non-vegetarian dot",
                                "MAJOR",
                                "Soap/shampoo/toothpaste/cosmetic/toiletry category — no green (veg) or "
                                "red/brown (non-veg) dot detected at top of the principal display panel.",
                                suggestion="Print a green dot (vegetarian origin) or red/brown dot "
                                "(non-vegetarian origin) at the top of the PDP."))
    else:
        checks.append(_info("VEG_DOT", "R6(8)", "Vegetarian / non-vegetarian dot",
                            "Not applicable for this category (applies to soaps, shampoos, toothpastes, "
                            "cosmetics & toiletries)."))

    # ---------------- Rule 6(3) : stickers ----------------
    checks.append(_info("STICKER", "R6(3)", "Sticker on declarations",
                        "Advisory: verify physically that no sticker alters any mandatory declaration "
                        "(only a lower-MRP sticker is permitted, and it must not cover the original MRP)."))

    # ---------------- Rule 6(7) : GM ----------------
    if re.search(r"\bgenetically\s*modified\b|\bGM\b", ocr["text"]):
        top_text = ocr["text"][:200].lower()
        if "gm" in top_text or "genetically" in top_text:
            checks.append(_pass("GM", "R6(7)", "GM food declaration",
                                "'GM' / genetically modified wording found at top of principal display panel."))
        else:
            checks.append(_fail("GM", "R6(7)", "GM food declaration",
                                "MAJOR", "Genetically modified content indicated but 'GM' must appear at the "
                                "TOP of the principal display panel.", suggestion="Print 'GM' at the top of the PDP."))
    else:
        checks.append(_info("GM", "R6(7)", "GM food declaration",
                            "No GM indication detected; check applies only to genetically modified foods."))

    # ---------------- Rule 6(10) : e-commerce ----------------
    if ecom:
        checks.append(_pass("ECOMM", "R6(10)", "E-commerce listing declarations",
                            "Listing checked for all mandatory declarations (month/year of manufacture "
                            "exempt); applicable declarations verified above."))
    else:
        checks.append(_info("ECOMM", "R6(10)", "E-commerce listing declarations",
                            "Image scan — Rule 6(10) e-commerce listing requirements not applicable."))

    # ---------------- Rule 5 + Second Schedule : standard pack sizes ----------------
    if nq:
        best = nq[0]
        for kw, sizes in SECOND_SCHEDULE.items():
            if kw in cat:
                q_str = f"{best['value']:g} {best['unit']}"
                if q_str not in sizes:
                    checks.append(_warn("STD_PACK", "R5 + Second Schedule",
                                        "Standard package size",
                                        f"Net quantity {q_str} is not a standard pack size listed for "
                                        f"'{kw}' in the Second Schedule ({', '.join(sizes[:6])}...).",
                                        best["matched"]))
                else:
                    checks.append(_pass("STD_PACK", "R5 + Second Schedule", "Standard package size",
                                        f"{q_str} matches a Second Schedule standard pack size."))
                break

    return checks

def overall(checks):
    fails = [c for c in checks if c["status"] == "FAIL"]
    warns = [c for c in checks if c["status"] == "WARN"]
    if fails:
        status = "NON-COMPLIANT"
    elif warns:
        status = "PARTIALLY COMPLIANT"
    else:
        status = "COMPLIANT"
    w = {"CRITICAL": 25, "MAJOR": 12, "MINOR": 5, "INFO": 0}
    score = max(0, 100 - sum(w.get(c["severity"], 5) for c in checks if c["status"] != "PASS"))
    return status, score

def summary(checks):
    out = {"FAIL": 0, "WARN": 0, "PASS": 0, "INFO": 0}
    for c in checks:
        out[c["status"]] = out.get(c["status"], 0) + 1
    out["CRITICAL"] = sum(1 for c in checks if c["severity"] == "CRITICAL")
    out["MAJOR"] = sum(1 for c in checks if c["severity"] == "MAJOR")
    return out
