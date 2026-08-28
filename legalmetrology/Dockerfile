# LM Compliance System — self-contained image (includes Tesseract OCR)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# OCR engine: English + Hindi traineddata, plus DejaVu fonts (needed by reportlab PDFs)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# runtime dirs (SQLite db, uploads, generated reports)
RUN mkdir -p data uploads generated

EXPOSE 5000
CMD ["sh", "-c", "gunicorn --workers 1 --threads 4 --bind 0.0.0.0:${PORT:-5000} app:app"]
