@echo off
REM LM Compliance System - one-click Windows launcher
REM 1. Finds a REAL Python (skips MSYS2/MinGW/WindowsApps stub interpreters)
REM 2. Installs Python dependencies (if missing)   3. Installs Tesseract (if missing)
REM 4. Seeds demo data (first run)                5. Starts the server

cd /d "%~dp0"
title LM Compliance System

REM =====================================================================
REM  1. Locate a usable Python
REM     Priority: project venv -> Windows "py" launcher -> python.org
REM     install folders -> filtered PATH (rejecting msys/mingw/ucrt stubs).
REM =====================================================================
set "PYEXE="

REM -- (a) project virtual environment (created via `py -3 -m venv .venv`) --
if exist ".venv\Scripts\python.exe" set "PYEXE=%CD%\.venv\Scripts\python.exe"

REM -- (b) py launcher (installed with python.org Python, lives in C:\Windows) --
if not defined PYEXE (
  where py >nul 2>nul
  if not errorlevel 1 (
    for /f "delims=" %%i in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%i"
  )
)
if defined PYEXE (
  "%PYEXE%" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
  if errorlevel 1 set "PYEXE="
)

REM -- (b) standard python.org install folders --
if not defined PYEXE (
  for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python314\python.exe" "C:\Python313\python.exe"
    "C:\Python312\python.exe" "C:\Python311\python.exe"
    "C:\Python310\python.exe"
  ) do (
    if not defined PYEXE if exist %%P set "PYEXE=%%P"
  )
)

REM -- (c) anything else on PATH, EXCEPT msys/mingw/ucrt/git/WindowsApps stubs --
if not defined PYEXE (
  for /f "delims=" %%i in ('where python 2^>nul') do (
    echo %%i | findstr /i "msys mingw ucrt WindowsApps" >nul
    if errorlevel 1 if not defined PYEXE set "PYEXE=%%i"
  )
)

if not defined PYEXE (
  echo [ERROR] No usable Python found.
  echo         Install from https://www.python.org/downloads/ and tick
  echo         "Add python.exe to PATH" (the "py" launcher is installed too).
  pause & exit /b 1
)
echo Using Python: %PYEXE%

REM =====================================================================
REM  2. Dependencies (installed into the SAME python that will run the app)
REM =====================================================================
"%PYEXE%" -c "import flask, pytesseract, PIL, cv2, numpy, reportlab, docx" >nul 2>nul
if errorlevel 1 (
  echo Installing Python packages...
  "%PYEXE%" -m pip --version >nul 2>nul
  if errorlevel 1 (
    echo [SETUP] pip missing - bootstrapping it...
    "%PYEXE%" -m ensurepip --upgrade || (
      echo [ERROR] could not bootstrap pip. Try installing Python again with
      echo         "Add python.exe to PATH" ticked.
      pause & exit /b 1
    )
  )
  "%PYEXE%" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo [ERROR] pip install failed - see messages above.
    pause & exit /b 1
  )
) else (
  echo Dependencies: OK
)

REM =====================================================================
REM  3. Tesseract OCR
REM =====================================================================
set TESS=0
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set TESS=1
if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" set TESS=1
if "%TESS%"=="0" (
  where tesseract >nul 2>nul && set TESS=1
)
if "%TESS%"=="0" (
  echo.
  echo [SETUP] Tesseract OCR not found - installing it now via winget...
  echo         In the installer dialog choose English + Hindi language data
  echo         and keep the default install location.
  echo.
  winget install UB-Mannheim.TesseractOCR
  if errorlevel 1 (
    echo [ERROR] winget install failed. Install manually from:
    echo         https://github.com/UB-Mannheim/tesseract/releases
    pause & exit /b 1
  )
  echo [SETUP] Tesseract installed. Close this window, open a NEW terminal,
  echo         and run run.bat again so the PATH is refreshed.
  pause & exit /b 1
) else (
  echo Tesseract: OK
)

REM =====================================================================
REM  4. Seed demo data on first run
REM =====================================================================
if not exist "data\lmcs.db" (
  echo Seeding demo data...
  "%PYEXE%" seed.py || ( echo [ERROR] seed failed & pause & exit /b 1 )
)

REM =====================================================================
REM  5. Launch
REM =====================================================================
echo.
echo Starting LM Compliance System...
echo Open your browser at:  http://127.0.0.1:5000
echo Demo login: admin / admin123   (also inspector / inspector123, viewer / viewer123)
echo.
"%PYEXE%" app.py
pause
