# ⚖️ LM Compliance System

**Automated compliance checking of packaged commodities under the Legal Metrology
(Packaged Commodities) Rules, 2011**

A web application for enforcement officials that scans package label photographs and
e-commerce product listings, extracts the mandatory legal declarations, validates them
against the Rules (as amended up to GSR 629(E)/2017), measures font sizes against
Rule 7 Table-I, and generates compliance reports (PDF / DOCX / CSV) with a full
repository, dashboard, inspections module, role-based access and audit trail.

## Quick start

```bash
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin fonts-dejavu
pip install -r requirements.txt
python seed.py      # demo database: users, 4 labels, 2 listings, inspection, PDF
python app.py       # → http://localhost:5000
```

| Role | Credentials | Access |
|---|---|---|
| Admin | admin / admin123 | everything incl. user management, audit log |
| Inspector | inspector / inspector123 | scan, review, inspections |
| Viewer | viewer / viewer123 | read-only |

## Deploy from GitHub

The repo is deployment-ready: Dockerfile (includes Tesseract OCR), Procfile,
render.yaml, and first-boot auto-seeding (schema + demo data in a background thread —
the server starts listening immediately, `/health` is the health check).

### 1. Push the project to GitHub

```bash
cd legalmetrology
git init
git add .
git commit -m "LM Compliance System — Legal Metrology packaged commodities checker"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

### 2. Deploy

**Render (free)** — create a free account, then open:

`https://render.com/deploy?repo=https://github.com/YOUR_USERNAME/YOUR_REPO`

(or: New → Blueprint → connect your repo — `render.yaml` is picked up automatically).
First boot seeds demo data in the background (~1–2 min); refresh the dashboard once
seeding finishes.

**Railway / Heroku** — connect the repo; `Procfile` + `Dockerfile` are detected
automatically (Railway uses the Dockerfile; Heroku uses the Procfile).

**Any Docker host** — `docker build -t lm-compliance . && docker run -p 5000:5000 lm-compliance`

Notes:
- The app stores state in **SQLite** (`data/lmcs.db`) plus `uploads/` and `generated/`.
  Free plans use an ephemeral disk (data resets on redeploy). For persistence, mount a
  volume/disk at `/app` (Docker) or use Render's "Persistent Disk" (mount `/app/data`).
- Port is read from the `PORT` environment variable (default 5000).
- Demo accounts after boot: `admin/admin123`, `inspector/inspector123`, `viewer/viewer123`.

# Running with VS Code + a virtual environment

A venv solves the two-Python problem permanently: it pins the exact interpreter and
keeps every package inside the project folder.

## One-time setup (do this in the terminal at the project root)

```powershell
# 1. create the venv with the REAL Python (never bare `python` on this machine)
py -3 -m venv .venv

# 2. activate it (PowerShell)
.\.venv\Scripts\Activate.ps1
#    (if that errors with "running scripts is disabled":  Set-ExecutionPolicy -Scope Process Bypass)

# 3. install packages INTO the venv
python -m pip install -r requirements.txt
#    (the prompt now shows (.venv) — so `python` here IS the venv's python)

# 4. seed + run
python seed.py
python app.py
```

## Using it in VS Code

1. **File → Open Folder…** → select the `legalmetrology` folder.
2. Install the **Python** extension (ms-python.python) if you haven't.
3. **Ctrl+Shift+P** → **Python: Select Interpreter** → choose the one that shows
   `.venv` (it is listed as "…\legalmetrology\.venv\Scripts\python.exe").
   The project already ships a `.vscode/settings.json` that points at this venv,
   so VS Code usually picks it automatically.
4. Open the integrated terminal (**Ctrl+`**) — VS Code auto-activates the venv
   (prompt shows `(.venv)`), so `python app.py` just works.
5. Debugging: press **F5** (Python debugger) or run `python app.py` in the terminal.

Notes:
- The venv is only for VS Code / terminal use. `run.bat` also detects `.venv`
  automatically and uses it if present.
- Never delete `.venv` and run `python` directly — the MSYS2 shadowing will bite
  again. If something breaks: delete `.venv`, re-run steps 1–4.
- `data/*.db`, `uploads/`, `generated/`, `.venv/` are git-ignored (see `.gitignore`).

## Windows

Run **`run.bat`** (double-click) — it installs Python deps + Tesseract OCR automatically
and starts the server. Manual steps and troubleshooting: **`RUN_WINDOWS.md`**.
Quick manual version:

```powershell
python -m pip install -r requirements.txt   # -m pip matters: same interpreter as python
winget install UB-Mannheim.TesseractOCR     # tick English + Hindi in the installer
python seed.py && python app.py             # http://127.0.0.1:5000  (admin/admin123)
```

## UI & core notes (v1.1)

- **UI**: Tailwind CSS 3.4 (self-hosted, 40 KB) + locally served Inter font — no CDN
  dependencies, so the app works offline and inside sandboxed preview iframes. Refined
  palette, heroicon-style inline SVG icons, score ring, status pills, clean tables.
- **Auth**: session cookies for normal browsers, plus a bearer-token fallback
  (`/api/login`, `?token=…`, `X-Auth-Token`) so login works inside preview iframes that
  block cookies.
- **OCR core**: multi-pass OCR tuned for **real-world photographs** — EXIF orientation,
  text-aware deskew, adaptive-threshold pass, CLAHE + sharpening pass on raw grayscale for
  phone photos (glare/uneven light), fuzzy qualifier matching ("Ma By" → "Mfd By"), and
  photo detection: photos without print-resolution metadata get advisory font-size
  findings instead of bogus mm verdicts, plus a "photograph the front panel" advisory
  when only back-panel content is in frame. Window-based MRP tax-wording detection,
  cross-field checks (future mfg date, best-before before manufacture, implausible MRP).

## What it checks (summary)

- Name & address of manufacturer/packer/importer (R6(1)(a), R10) · Country of origin for
  imports (R6(1)(aa)) · Common/generic name (R6(1)(b)) · Net quantity in SI units
  (R6(1)(c), R8(5)) · Month & year of manufacture (R6(1)(d)) · Best-before/use-by &
  expiry (R6(1)(da)) · MRP incl. of all taxes, single MRP, rounding (R6(1)(e), R2(m)) ·
  Consumer care details (R6(2)) · Font sizes vs. PDP-area Table-I (R7) · Clear space
  around quantity (R8) · Contrast & legibility (R9) · Language (R9(4)) · Veg/non-veg
  dot (R6(8)) · GM marking (R6(7)) · Sticker rule (R6(3)) · E-commerce display
  (R6(10)) · Second Schedule pack sizes (R5).

## Documentation

- `docs/TECHNICAL_DOCUMENTATION.md` — architecture, pipeline, data model, deployment.
- `docs/COMPLIANCE_RULES.md` — every check with its legal provision, severities, Table-I.
- `docs/LM_Packaged_Commodities_Rules_2011_consolidated.pdf` — the Rules (consolidated).

## Repository layout

```
legalmetrology/
├── app.py                  # Flask application (routes, auth, roles, auto-bootstrap)
├── seed.py                 # demo data + first scans through the real pipeline
├── requirements.txt
├── Dockerfile              # self-contained image (Tesseract OCR included)
├── Procfile                # gunicorn start command (Render/Railway/Heroku)
├── render.yaml             # Render Blueprint (one-click deploy)
├── run.bat                 # Windows one-click launcher
├── core/
│   ├── ocr.py              # Tesseract 5 wrapper (two-pass binarisation)
│   ├── extract.py          # declaration extractors
│   ├── fontsize.py         # line clustering, PDP area, Table-I measurement
│   ├── image_analysis.py   # contrast, veg dot, clear space, overlay
│   ├── validate.py         # rules engine (20+ checks)
│   ├── pipeline.py         # scan orchestration (image & listing)
│   ├── reports.py          # PDF / DOCX / CSV reports
│   ├── db.py               # SQLite schema + audit
│   └── sample_data.py      # demo label renderer (300 DPI, controlled font sizes)
├── templates/  static/     # UI (custom CSS, no CDN dependencies)
└── data/  uploads/  generated/   # runtime state (created on first run)
```

## Disclaimer

This system is an automated **screening aid**. Findings — especially font-size
estimates and low-contrast determinations — must be verified physically by an
authorised Legal Metrology Inspector before any enforcement action. The penalty
reference is informative and subject to the orders of the competent authority.
