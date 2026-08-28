# Legal Metrology Compliance System (LMCS)

Automated compliance checking of packaged commodities under the **Legal Metrology
(Packaged Commodities) Rules, 2011** — scans package label images and e-commerce
listings, extracts mandatory declarations via OCR, validates them against the Rules
(as amended up to GSR 629(E)/2017), measures font sizes vs. Rule 7 Table-I, and
generates PDF/DOCX/CSV compliance reports.

## Run it

```bash
cd legalmetrology
pip install -r requirements.txt        # + tesseract-ocr (eng, hin), fonts-dejavu
python seed.py                          # demo DB: users, 4 labels, 2 listings
python app.py                           # http://localhost:5000
```

Demo logins: **admin/admin123** · **inspector/inspector123** · **viewer/viewer123**

## Deliverables

| Item | Where |
|---|---|
| Web application (live) | `legalmetrology/` — Flask app, dashboard, scans, reports, inspections, users, audit |
| Demo dataset | `seed.py` → 4 rendered labels + 2 listings with known ground truth |
| Rules engine | `core/validate.py` + `docs/COMPLIANCE_RULES.md` (every check, provision, severity) |
| Reports (PDF/DOCX/CSV) | `core/reports.py` — per-scan, downloadable from the UI |
| Technical documentation | `legalmetrology/docs/TECHNICAL_DOCUMENTATION.md` |
| Rules text (consolidated) | `legalmetrology/docs/LM_Packaged_Commodities_Rules_2011_consolidated.pdf` |

The system is an automated screening aid; findings require physical verification by a
Legal Metrology Inspector before enforcement action.
