# LM Compliance System — Technical Documentation

**Automated compliance checking of packaged commodities under the Legal Metrology
(Packaged Commodities) Rules, 2011**

Version 1.0 · August 2026

---

## 1. Overview

LM Compliance System is a web application that scans photographs of packaged-commodity
labels and e-commerce product listings, extracts the mandatory declarations prescribed
under the **Legal Metrology (Packaged Commodities) Rules, 2011** (as amended), and
validates them against a rule engine implementing the current law. It produces
compliance verdicts, violation summaries, font-size/readability analysis, and digital
reports (PDF / DOCX / CSV), and maintains a searchable repository of scanned products,
inspections and audit trails for enforcement officials.

### 1.1 Problem addressed

| Problem | Solution in this system |
|---|---|
| Manual label inspection is slow and resource-intensive | Automated OCR + extraction + rule-based validation in seconds |
| Missing/incorrect declarations frequently missed | 20+ rule checks with legal references (Rules 6–10, penalties) |
| Font-size violations hard to judge by eye | Physical measurement from OCR geometry vs. Rule 7 Table-I |
| No central record of scans | SQLite repository with full compliance history |
| Reports are ad-hoc | One-click PDF / DOCX / CSV generation per scan |
| No oversight for enforcement | Dashboard, inspections module, audit log, role-based access |

### 1.2 Legal basis

- **Legal Metrology Act, 2009** (1 of 2010) — Sections 18, 35, 36, 39.
- **Legal Metrology (Packaged Commodities) Rules, 2011** — GSR 202(E) dt. 07-03-2011,
  as amended by GSR 784(E)/2011, 832(E)/2011, 318(E)/2011, 427(E)/2012, 137(E)/2014,
  385(E)/2015, 838(E)/2016, 858(E)/2016 and **629(E) dt. 23-06-2017 (effective 01-01-2018)**.

See `docs/COMPLIANCE_RULES.md` for the full rule-reference of every implemented check.

---

## 2. Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                         Web layer (Flask 3)                        │
│   login/auth · dashboard · scan workflows · repository · reports   │
├────────────────────────────────────────────────────────────────────┤
│                        Application services                        │
│   ┌────────────┐  ┌─────────────┐  ┌──────────────┐  ┌──────────┐  │
│   │ OCR engine │→│ Extraction  │→│ Rules engine │→│ Reports  │  │
│   │ Tesseract5 │ │ regex+heuristic│ validate.py │ │ PDF/DOCX/│  │
│   │ (eng+hin)  │ │ extract.py   │ │ (20 checks) │ │ CSV      │  │
│   └─────┬──────┘ └──────┬──────┘ └──────┬───────┘ └────┬─────┘  │
│         │               │               │               │        │
│   ┌─────▼───────────────▼───────────────▼───────────────▼──────┐ │
│   │           pipeline.py (orchestrator, scan lifecycle)        │ │
│   └──────────────────────────┬──────────────────────────────────┘ │
│   ┌──────────────────────────▼──────────────────────────────────┐ │
│   │  Image analysis: contrast (R9), veg dot (R6(8)), clear-space│ │
│   │  (R8), font-size geometry (R7) — OpenCV + Pillow            │ │
│   └──────────────────────────┬──────────────────────────────────┘ │
├──────────────────────────────┼───────────────────────────────────┤
│              Persistence: SQLite (db.py) — users, products,     │
│   scans, checks (JSON), inspections, reports, audit_log         │
└──────────────────────────────┴───────────────────────────────────┘
```

### 2.1 Module map (`legalmetrology/`)

| Module | Responsibility |
|---|---|
| `app.py` | Flask routes, session auth, role enforcement (`admin`/`inspector`/`viewer`), uploads, downloads |
| `core/ocr.py` | Tesseract 5 wrapper: grayscale preprocessing + adaptive-threshold fallback pass, word boxes + confidence, EXIF DPI |
| `core/extract.py` | Declaration extractors: MRP, net quantity (SI units), mfg month/year, best-before/use-by, consumer care, address/qualifiers, country of origin, common name, dimensions, barcode |
| `core/fontsize.py` | Visual-line clustering of OCR words; PDP area computation (Rule 7(4)); Table-I minimum heights; per-field height/width/confidence measurement |
| `core/image_analysis.py` | MRP/net-qty text–background contrast (Rule 9(1)(b)); veg/non-veg dot detection (Rule 6(8)); quantity clear-space check (Rule 8(1)); annotated overlay rendering |
| `core/validate.py` | Rule engine: 20+ checks with rule references, severities (critical/major/minor/advisory), overall verdict & 0–100 score, Second Schedule pack sizes, penalty reference |
| `core/pipeline.py` | Orchestration: OCR → extract (with primary/fallback merging) → measure → validate → persist; image & listing scans |
| `core/reports.py` | PDF (ReportLab), DOCX (python-docx), CSV generation with meta, declarations, checks, font table, penalty reference, signature block |
| `core/db.py` | SQLite schema, helpers, audit logging |
| `core/sample_data.py` + `seed.py` | Demo labels (PIL, 300 DPI, controlled font sizes), sample listings, demo users, first inspection + PDF |

### 2.2 Scan pipeline (image)

1. **Ingest** — image uploaded (`uploads/`), DPI read from EXIF (default 300).
2. **OCR (two passes)** — grayscale contrast-stretch pass (primary) and adaptive
   Gaussian threshold pass (fallback, rescues low-contrast text). Both return text and
   per-word bounding boxes with confidence.
3. **Extraction** — per-field extractors run on the primary text; fields missed are
   re-attempted on the fallback pass; MRP prefers the variant carrying the
   *"incl. of all taxes"* wording.
4. **Geometry** — OCR words are clustered into visual lines; each declaration line's
   glyph height is converted to mm via `pix_per_mm = dpi / 25.4`; PDP area from user
   dimensions or image estimate; required minimum height from Table-I.
5. **Image analysis** — Otsu-based contrast ratio for MRP/net-qty numeral boxes;
   veg/non-veg dot colour-blob detection in the top band; clear-space scan around the
   quantity declaration.
6. **Validation** — rule engine emits checks (status/severity/evidence/suggestion).
7. **Persist + report** — scan row, checks JSON, overlay image; PDF/DOCX/CSV on demand.

### 2.3 Scan pipeline (e-commerce listing)

Same validation with `ecommerce=True`: month/year of manufacture exempt (Rule 6(10)),
image-only checks (font size, contrast, clear space, veg dot, sticker) skipped.

---

## 3. Rule engine design

Each check is a data row: `{id, rule, title, status, severity, message, evidence, suggestion}`.

**Severity mapping**

| Severity | Examples | Effect on verdict |
|---|---|---|
| CRITICAL | missing manufacturer address, net qty, MRP, consumer care, mfg date, country of origin (imported) | any → NON-COMPLIANT |
| MAJOR | non-SI unit, MRP without tax wording, MRP not rounded, expired best-before, font < Table-I, low contrast, missing veg dot | any → NON-COMPLIANT |
| MINOR | crowded quantity zone, low OCR confidence, non-standard pack size | WARN → PARTIALLY COMPLIANT |
| INFO / OK | advisory notes, passing checks | no effect |

**Score**: `max(0, 100 − Σ weights)` with CRITICAL 25, MAJOR 12, MINOR 5.

**Font-size measurement caveat**: OCR boxes approximate printed cap-height; a ±0.15 mm
tolerance is applied on the Table-I threshold. Measured values are labelled as
"≈ estimated" in reports; physical verification is advised (also required by the
disclaimer on every report).

---

## 4. Deployment

### 4.1 Requirements

- Python 3.10+ (tested 3.13)
- Tesseract OCR 5.x with `eng` and `hin` traineddata
- DejaVu fonts (for demo label generation)
- pip packages — see `requirements.txt` (Flask, pytesseract, Pillow, opencv-python,
  numpy, reportlab, python-docx)

### 4.2 Installation

```bash
# Debian/Ubuntu
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin \
                        fonts-dejavu poppler-utils

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python seed.py          # create DB, demo users, sample scans
python app.py           # http://0.0.0.0:5000
```

Demo accounts: `admin/admin123`, `inspector/inspector123`, `viewer/viewer123`.

### 4.3 Production deployment

- **WSGI**: `gunicorn -w 4 -b 0.0.0.0:8000 app:app` behind Nginx (proxy, TLS, static).
- **State**: SQLite `data/lmcs.db` — mount `data/`, `uploads/`, `generated/` on
  persistent/backed-up storage. For multi-node scale-out, swap `core/db.py` for
  PostgreSQL (same schema) — the JSON columns keep the change isolated.
- **Security**: set a strong `LM_SECRET` env var; change demo passwords; HTTPS only;
  file-upload whitelist is enforced in `app.py`; role checks on every restricted route.
- **OCR throughput**: Tesseract runs synchronously (~2–6 s/scan). For large volumes,
  move `core/pipeline.py` invocation to a worker queue (Celery/RQ) and add a status
  field to the scans table.
- **Backups**: nightly copy of `data/` (SQLite `VACUUM INTO` or `sqlite3 .backup`).

### 4.4 Authentication modes

The app supports two auth paths:

1. **Session cookie (normal browser)** — classic Flask session; POST `/login` redirects to
   the dashboard.
2. **Bearer token (sandboxed/embedded previews)** — some preview iframes block cookies,
   which previously caused "login succeeds but you bounce back to /login". The login page
   now posts JSON to `/api/login` and receives a bearer token; the token travels in the
   URL (`?token=…`) and in the `X-Auth-Token` header on POSTs (`static/js/auth.js`
   rewrites internal links and submits forms via fetch). Tokens persist in the
   `auth_tokens` table and are revoked on logout.

## 4.5 Configuration points

- `core/validate.py` — `SECOND_SCHEDULE` pack sizes, contrast thresholds (1.25/1.5),
  Table-I via `core/fontsize.py::TABLE_I`.
- `core/ocr.py` — `TESS_LANG`, adaptive-threshold block size.
- `app.py` — upload size limit, allowed extensions.

---

## 5. Data model (SQLite)

| Table | Purpose |
|---|---|
| `users` | username, password hash, role (admin/inspector/viewer), designation, state, active flag |
| `products` | product registry (name, category, brand, manufacturer) |
| `scans` | scan code, product ref, source (image/listing), file path, listing text, package dims, PDP area, DPI, raw OCR text, extracted JSON, checks JSON, font JSON, overall status, score, notes, review status, creator, timestamp |
| `inspections` | inspections linked to scans: title, location, inspector, findings, action taken, notice ref, status |
| `reports` | generated report files per scan |
| `audit_log` | immutable trail of logins, scans, reviews, report exports, user administration |

---

## 6. Testing & validation approach

- **Demo corpus** (`seed.py`): four rendered labels (compliant tea @ 100/100;
  imported noodles with 6 violations @ 0/100; soap with MRP-rounding + contrast
  issues; milk with expired *use-by* date) and two listings — the engine's verdicts
  match the ground truth encoded in each sample.
- **Two-pass OCR** was introduced because page-level binarisation dropped
  low-contrast MRP text; the fallback pass recovers it while the primary pass keeps
  high accuracy on normal labels.
- **Extractor unit behaviour** (MRP incl-taxes wording, "500g" attached units,
  `MM/YYYY`/`Month YYYY` dates, "24 months from mfg" best-before durations, qualifier
  regexes) is exercised by the demo corpus; extend `seed.py` or add pytest cases for
  new label styles.

---

## 7. Roadmap

- Mobile capture app / camera feed with live overlay.
- Barcode/QR decoding to auto-fill product metadata and Second Schedule lookup.
- Hindi (Devanagari) extraction scoring with per-line transliteration.
- Batch scanning (multi-page PDFs) and scheduled re-checks of listings.
- PostgreSQL + worker-queue scale-out; REST API for third-party e-commerce feeds.
- ML-based OCR confidence calibration on a labelled corpus of real retail labels.
