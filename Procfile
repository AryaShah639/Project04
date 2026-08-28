# Heroku / Railway / Render (non-Docker) start command
# 1 worker: the app runs OCR in-process and bootstraps demo data at import time.
web: gunicorn --workers 1 --threads 4 --bind 0.0.0.0:$PORT app:app
