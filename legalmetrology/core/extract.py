"""Field extraction from OCR text — Legal Metrology (Packaged Commodities) Rules, 2011."""
import re
from datetime import datetime

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
MONTH_ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
              "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}

COUNTRIES = ["india", "china", "usa", "united states", "america", "japan", "germany", "france",
             "united kingdom", "uk", "italy", "spain", "uae", "united arab emirates", "korea",
             "south korea", "vietnam", "thailand", "malaysia", "indonesia", "bangladesh", "sri lanka",
             "nepal", "bhutan", "pakistan", "singapore", "australia", "canada", "brazil", "mexico",
             "taiwan", "hong kong", "turkey", "poland", "netherlands", "holland", "switzerland",
             "belgium", "austria", "israel", "south africa", "new zealand", "russia", "philippines",
             "myanmar", "iran", "egypt", "saudi arabia", "qatar", "kuwait", "oman"]

UNIT_MAP = [
    (r"kg", "kg", "weight"), (r"kilograms?", "kg", "weight"),
    (r"\bg\b|grams?|gm\b|gr\b", "g", "weight"),
    (r"ml\b|millilit(re|er)s?", "ml", "volume"), (r"lit(re|er)s?|\bl\b", "l", "volume"),
    (r"cm\b|centimet(re|er)s?", "cm", "length"), (r"\bm\b|met(re|er)s?", "m", "length"),
    (r"mm\b|millimet(re|er)s?", "mm", "length"),
    (r"\bn\b|\bu\b|pcs\b|pc\b|nos?\b|no\.?s?\b|pieces?|count|sheets?|units?", "N", "number"),
]

NON_SI = {"gm": "g", "gr": "g", "kgs": "kg", "gms": "g", "ltr": "l", "lts": "l",
          "mls": "ml", "cms": "cm", "mtr": "m", "mts": "m", "k.g": "kg", "kgs.": "kg"}

MFG_KEY = re.compile(r"\b(?:mfg|mfd|mfr|manufactur(?:ed|ing|e)?|pack(?:ed|ing)?|pkg|pre-?pack(?:ed|ing)?|import(?:ed|ing)?|bottl(?:ed|ing)?)\b", re.I)
BB_KEY = re.compile(r"\b(?:best\s*before|use\s*by|use\s*before|expiry|exp(?:iration)?|exp\.?\s*date|best\s*before\s*end|bb)\b", re.I)

def norm(t: str) -> str:
    t = t.replace("₹", "Rs.").replace("\u00d7", "x")
    t = re.sub(r"[\u2013\u2014\u2212\u2018\u2019\u201c\u201d]", "-", t)
    return t

def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", norm(t)).strip()

def parse_month_year(s: str):
    """Parse 'MM/YYYY', 'MM/YY', 'Month YYYY', 'MMM YYYY' → (month, year) or None."""
    s = s.strip(" .:/-")
    m = re.match(r"^(\d{1,2})[/\-.](\d{2,4})$", s)
    if m:
        mo, yr = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12:
            return mo, (2000 + yr if yr < 100 else yr)
        return None
    m = re.match(r"^([A-Za-z]{3,9})\.?\s+(\d{4})$", s)
    if m:
        mo = MONTH_ABBR.get(m.group(1).lower()[:3]) or MONTHS.get(m.group(1).lower())
        if mo:
            return mo, int(m.group(2))
    m = re.match(r"^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})$", s)
    if m:  # DD/MM/YYYY full date
        d, mo, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return mo, (2000 + yr if yr < 100 else yr)
    return None

_TAX_RE = re.compile(r"incl(?:usive)?\.?\s*of\s*all\s*taxes?|incl\.?\s*of\s*taxes?", re.I)

def extract_mrp(text: str):
    """All MRP-like declarations. Tax wording ('incl. of all taxes') is detected in the
    surrounding text window, so it works whether it appears before or after the amount."""
    t = norm(text)
    kw = (r"(?P<kw>m\.?r\.?[dp]\.?|mrd|mrr|mrf|max(?:imum)?\.?\s*(?:retail\s*)?price|max\.?\s*retail|"
          r"retail\s*sale\s*price|retail\s*price)")
    cur = r"[^0-9]{0,45}?(?P<cur>rs\.?|inr|rupees?)?\s*(?P<amt>\d{1,5}(?:[.,]\d{1,2})?)\s*(?:/-)?"
    pat = re.compile(kw + cur, re.I)

    def to_val(s):
        s = s.strip()
        if "," in s and "." in s:
            s = s.replace(",", "")
        elif "," in s and len(s.split(",")[0]) >= 4:
            s = s.replace(",", "")
        elif "," in s:
            s = s.replace(",", ".")
        return round(float(s), 2)

    results = []
    for m in pat.finditer(t):
        amt = to_val(m.group("amt"))
        if amt <= 0 or amt > 999999:
            continue
        win = t[max(0, m.start() - 110):m.end() + 110]
        results.append({
            "value": amt,
            "has_mrp_keyword": "mrp" in m.group("kw").lower().replace(" ", "").replace(".", ""),
            "incl_taxes": bool(_TAX_RE.search(win)),
            "matched": _clean(m.group(0))[:120],
            "pos": m.start(),
        })
    seen, out = set(), []
    for r in results:
        key = (r["value"], r["pos"])
        if key not in seen:
            seen.add(key); out.append(r)
    return out

_UNIT_ALT = (r"kilograms?|millilit(re|er)s?|centimet(re|er)s?|millimet(re|er)s?|met(re|er)s?|"
             r"lit(re|er)s?|grams?|pieces?|count|sheets?|mg|kg|gm|gr|ml|l|cm|mm|pcs|pc|nos?|no\.?s?|m|g|u|n")

def extract_net_qty(text: str):
    """Net quantity candidates with unit and type. Handles attached units ('500g', '500 ml')."""
    t = norm(text)
    out = []
    pat = re.compile(r"(\d+(?:[.,]\d+)?)\s*(" + _UNIT_ALT + r")\b", re.I)
    for m in pat.finditer(t):
        val = float(m.group(1).replace(",", "."))
        unit_raw = m.group(2).lower()
        unit, utype = unit_raw, "weight"
        for rx, u, tp in UNIT_MAP:
            if re.fullmatch(rx, unit_raw):
                unit, utype = u, tp
                break
        if unit_raw == "mg":
            unit, utype = "mg", "weight"
        ctx = t[max(0, m.start() - 30):m.end() + 10]
        score = 0
        if re.search(r"net|qty|quantity|weight|contents|wt\.?", ctx, re.I):
            score += 10
        if re.search(r"gross|pack\s*size|mrp|rs\.?", ctx, re.I):
            score -= 5
        if 0 < val < 100000:
            out.append({"value": val, "unit": unit, "unit_raw": unit_raw, "type": utype,
                        "matched": _clean(m.group(0)), "ctx": _clean(ctx)[-60:],
                        "pos": m.start(), "score": score})
    out.sort(key=lambda r: (-r["score"], -r["pos"]))
    return out

def _date_in_window(window):
    """Find a parseable date (MM/YYYY, Month YYYY or DD/MM/YYYY) in a text window."""
    dm = re.search(r"(?:(?:\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})|(?:\d{1,2}[/\-.]\d{2,4})|(?:[A-Za-z]{3,9}\.?\s+\d{4}))",
                   window)
    if dm:
        parsed = parse_month_year(dm.group(0))
        if parsed:
            return dm.group(0), parsed[0], parsed[1]
    return None, None, None

DURATION_RE = re.compile(r"(\d{1,3})\s*(months?|days?|weeks?|years?)(?:\s*from\s*(?:the\s*)?(?:date\s*of\s*)?(?:manufacture|packing|mfg|pack))?", re.I)

def extract_mfg_date(text: str):
    t = norm(text)
    out = []
    for m in re.finditer(MFG_KEY, t):
        window = t[m.end():m.end() + 50]
        raw, mo, yr = _date_in_window(window)
        if raw:
            out.append({"matched": _clean(m.group(0) + " " + raw)[:80], "month": mo, "year": yr, "raw": raw})
    seen = set(); uniq = []
    for o in out:
        if o["matched"] not in seen:
            seen.add(o["matched"]); uniq.append(o)
    return uniq

def extract_best_before(text: str):
    t = norm(text)
    out = []
    for m in re.finditer(BB_KEY, t):
        window = t[m.end():m.end() + 60]
        raw, mo, yr = _date_in_window(window)
        if raw:
            out.append({"matched": _clean(m.group(0) + " " + raw)[:90], "month": mo, "year": yr,
                        "raw": raw, "keyword": m.group(0).lower(), "duration": None})
            continue
        dm = DURATION_RE.search(window)
        if dm:
            out.append({"matched": _clean(m.group(0) + " " + dm.group(0))[:90], "month": None,
                        "year": None, "raw": dm.group(0), "keyword": m.group(0).lower(),
                        "duration": f"{dm.group(1)} {dm.group(2)}"})
    seen = set(); uniq = []
    for o in out:
        if o["matched"] not in seen:
            seen.add(o["matched"]); uniq.append(o)
    return uniq

def extract_consumer_care(text: str):
    t = norm(text)
    phones = []
    for m in re.finditer(r"(?:\+?91[\s\-]?)?(?:1800[\s\-]?\d{3}[\s\-]?\d{3,4}|[6-9]\d{9}|\b0\d{2,4}[\s\-]?\d{6,8}\b)", t):
        phones.append(m.group(0))
    emails = re.findall(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}", t)
    care_kw = re.search(r"consumer\s*(care|service|helpline|complaint)|customer\s*(care|service|helpline)|toll\s*free|complaints?\s*(?:contact|please|at)?|help\s*line", t, re.I)
    return {"phones": phones[:5], "emails": emails[:3], "care_kw": bool(care_kw)}

_BAD_SNIPPETS = re.compile(r"^(on|in|at|date|the|for|from|by|of|with|and|upto|up\s*to)\b", re.I)
# strict corporate suffix, plus a fuzzy variant for OCR-garbled suffixes (PVT.LD, WOM SOLON LL…)
_COMPANY_RE = re.compile(r"([A-Z][A-Za-z0-9&\.\-\s]{2,60}?"
                         r"(?:PVT\.?\s*LTD|PVT\.?\s*LIMITED|PRIVATE\s+LIMITED|LIMITED|LLP|\bHOLDINGS\b|"
                         r"\bPVT\b|\bLTD\b|\bLL\b))")
# fuzzy qualifiers: OCR commonly mangles "Mfd By" into "Ma By", "Mid By", "Md By"…
# The fuzzy branch REQUIRES the word 'by' so it cannot match inside ordinary prose.
_QUAL_RE = re.compile(
    r"(?:manufactur(?:ed|er)?|mfg|mfd|pack(?:ed|er)?|import(?:ed|er)?|market(?:ed|er)?|"
    r"distribut(?:ed|or)?|bottl(?:ed|er)?)\s*(?:by|at)?\s*[:.]?\s*([^\n]{3,100})"
    r"|m[a-z]{0,2}d?[a-z]{0,2}\s+[Bb]y\s+([^\n]{3,100})",
    re.I)

def extract_address(text: str):
    t = norm(text)
    qual = None
    for m in _QUAL_RE.finditer(t):
        cand = (m.group(1) or m.group(2) or "").strip()
        if _BAD_SNIPPETS.match(cand):
            continue
        if re.match(r"^\d{1,2}[/\-.]\d{2,4}", cand):
            continue
        qual = cand
        break
    # fallback: OCR often garbles the qualifier word but keeps the company name readable —
    # a corporate-suffix name adjacent to address content is strong evidence of the declaration
    if not qual:
        m = _COMPANY_RE.search(t)
        if m:
            qual = m.group(1).strip()
    snippet = (qual or "")[:100]
    pincode = re.search(r"\b\d{6}\b", t) or re.search(r"pin\s*[:\-]?\s*\d{6}", t, re.I)
    street = re.search(r"\b(road|rd\.?|street|st\.?|nagar|lane|colony|complex|industrial\s*estate|phase\s*\d|district|dist\.?|mandal|tehsil|taluk|post|p\.?o\.?|h\.?o\.?|works|regd\.?\s*office|office)\b", t, re.I)
    return {"found": bool(qual and (pincode or street or len(snippet) > 8)), "snippet": snippet,
            "pincode": bool(pincode), "street_kw": bool(street), "qualifier": bool(qual)}

def extract_country(text: str):
    t = norm(text).lower()
    imported = bool(re.search(r"\bimport(?:ed|er|ation)?\b", t))
    found = None
    m = re.search(r"(?:country\s*of\s*origin|origin\s*[:.]?|made\s*in|produced\s*in|manufactur(?:ed|ing)\s*in|imported\s*from|product\s*of|assembled\s*in|grown\s*in)\s*[:.]?\s*([A-Za-z .]{2,40})", t)
    if m:
        cand = m.group(1).strip().strip(".:")
        for c in COUNTRIES:
            if c in cand:
                found = c.title(); break
        if not found and len(cand) > 2 and not re.search(r"\d", cand):
            found = cand.title()[:40]
    return {"imported": imported, "origin": found, "matched": m.group(0).strip()[:80] if m else ""}

def extract_common_name(product_name: str, text: str, category: str = ""):
    t = norm(text).lower()
    stop = {"the", "and", "with", "for", "of", "in", "on", "plus", "new", "rich", "pure", "100", "25",
            "50", "extra", "super", "premium", "value", "pack", "free", "x", "special", "gold", "silver"}
    tokens = [w for w in re.findall(r"[a-z0-9]{3,}", product_name.lower()) if w not in stop]
    hits = [w for w in tokens if w in t]
    cat_words = [w for w in re.findall(r"[a-z]{4,}", category.lower()) if w not in stop]
    cat_hits = [w for w in cat_words if w in t]
    ratio = len(hits) / max(1, len(tokens))
    return {"found": bool(hits or cat_hits), "tokens": tokens, "hits": hits, "cat_hits": cat_hits,
            "ratio": ratio}

def extract_dimensions(text: str):
    t = norm(text)
    out = re.findall(r"\b(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)(?:\s*[xX]\s*(\d+(?:\.\d+)?))?\s*(cm|mm|m)?\b", t)
    return [{"dims": [v for v in d if v], "unit": u or ""} for d in out[:5]]

def extract_barcode(text: str):
    t = norm(text)
    found = bool(re.search(r"\b\d{8,14}\b", t))
    return {"found": found}

def has_latin_or_devanagari(text: str) -> bool:
    latin = len(re.findall(r"[A-Za-z]", text))
    dev = len(re.findall(r"[\u0900-\u097F]", text))
    return latin > 10 or dev > 5

def is_perishable_category(category: str) -> bool:
    c = (category or "").lower()
    perish = ["food", "dairy", "beverage", "bakery", "snack", "chocolate", "confectionery", "sauce",
              "oil", "spice", "tea", "coffee", "rice", "atta", "flour", "juice", "drink", "frozen",
              "pickle", "jam", "honey", "noodle", "pasta", "cereal", "baby food", "pet food"]
    return any(re.search(r"\b" + re.escape(p) + r"\b", c) for p in perish)

def is_cosmetic_category(category: str) -> bool:
    c = (category or "").lower()
    return any(k in c for k in ["soap", "shampoo", "toothpaste", "cosmetic", "toilet", "cream", "lotion",
                                "deodorant", "sanitizer", "hair", "skin", "perfume", "beauty", "body"])
