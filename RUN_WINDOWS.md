# Running on Windows

## Quick start (recommended)

1. Install **Python 3.10+** from <https://www.python.org/downloads/> — **tick "Add python.exe to PATH"**
   during installation (critical — without it `python` is not recognised).
2. Double-click **`run.bat`** in the `legalmetrology` folder.
   It will: install the Python packages → install Tesseract OCR if missing
   (choose **English + Hindi** language data in the installer dialog) → seed demo
   data on first run → start the server.
3. The installer requires a fresh terminal: if Tesseract was just installed, **close the
   window, reopen `run.bat`** so the PATH refresh is picked up.
4. Open <http://127.0.0.1:5000> — login with **admin / admin123**.

## If you prefer the manual steps

```powershell
cd legalmetrology
python -m pip install -r requirements.txt
winget install UB-Mannheim.TesseractOCR   # tick English + Hindi languages in setup
python seed.py          # first run only (creates data/lmcs.db with demo scans)
python app.py           # http://127.0.0.1:5000
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `pip install` says *"Requirement already satisfied … in C:\Users\…\Python314\Lib\site-packages"* but `python seed.py` still says `No module named 'werkzeug'` | pip and `python` are running **two different interpreters** (an MSYS2/Git Python shadows the real one on PATH). Diagnose with: `py -3 -c "import sys, werkzeug; print(sys.executable)"` vs `python -c "import sys; print(sys.executable)"`. Run the app with `py -3 seed.py` / `py -3 app.py`, or fix the PATH order so `C:\Users\Arya\AppData\Local\Programs\Python\Python314\` and `…\Scripts\` come before `C:\msys64\…` (Settings → Environment Variables). |
| `C:\msys64\ucrt64\bin\python.exe: No module named pip` (or any `msys64`/`mingw64` path) | An **MSYS2 / Git-for-Windows Python** is shadowing your real Python on PATH. `run.bat` now skips those interpreters automatically and uses your python.org Python. Manually, always use `py -3 -m pip install -r requirements.txt`, or the full path — e.g. `C:\Users\Arya\AppData\Local\Programs\Python\Python314\python.exe -m pip install -r requirements.txt`. |
| `ModuleNotFoundError: No module named 'werkzeug'` (or any package) after pip install | pip and `python` are **two different interpreters**. Use exactly `python -m pip install -r requirements.txt` (the `-m pip` form installs into the *same* Python that `python` runs) — or better, `py -3 -m pip install -r requirements.txt`. Then run `python -m pip show werkzeug` to confirm it reports an install location. |
| Render/Railway logs: `ImportError: libGL.so.1: cannot open shared object file` | The container needs **`opencv-python-headless`** (no OpenGL libraries in slim images). Already fixed in the repo: `requirements.txt` uses `opencv-python-headless` and the Dockerfile installs `libgl1 libglib2.0-0`. Pull the latest commit and re-push. |
| Render logs: `ModuleNotFoundError: No module named 'core'` | The **pushed repo is missing the `core/` folder** (incomplete local copy). See the Deploy from GitHub section in README.md. |
| `tesseract is not installed or it's not in your PATH` / `pytesseract.pytesseract.TesseractNotFoundError` | Tesseract binary missing. Install via `winget install UB-Mannheim.TesseractOCR` or from <https://github.com/UB-Mannheim/tesseract/releases>. The app auto-detects `C:\Program Files\Tesseract-OCR\tesseract.exe`, so the default install location works without PATH changes. **Restart the terminal / run.bat afterwards.** |
| `run.bat` closes instantly or shows nothing | Run it from a terminal (`cd` into the folder, then `run.bat`) so you can read the error messages. |
| `No usable Python found` in run.bat | No python.org Python detected — install it from <https://www.python.org/downloads/> with "Add python.exe to PATH" ticked, then re-run. |
| `Failed loading language 'hin'` | Hindi language data was not installed with Tesseract. Re-run the UB-Mannheim installer and tick **Hindi** in the "Additional language data" step. (The app works without it too — it simply skips the Hindi pass.) |
| Port 5000 already in use | Close the other app or change the port at the bottom of `app.py` (`app.run(port=…)`). |

## Notes

- Demo accounts: `admin / admin123` (administrator), `inspector / inspector123`, `viewer / viewer123`.
- The app stores everything locally under `legalmetrology/` — `data/lmcs.db` (SQLite),
  `uploads/` (images), `generated/` (reports).
- Hindi OCR is used only when the `hin` traineddata is available and the label looks
  bilingual — English-only labels stay fast.
