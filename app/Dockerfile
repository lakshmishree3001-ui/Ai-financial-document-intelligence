# Financial Document Intelligence Platform - Module 14
# Containerizes the FastAPI backend. Build and run with Docker
# (see Module 14 deliverable for full instructions).

FROM python:3.11-slim

WORKDIR /app

# System dependency needed by the pdf/OCR-related packages used
# elsewhere in this project (pytesseract, pdf2image) if the full
# pipeline is containerized alongside the API.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The SQLite database and processed data folders are mounted as a
# volume in docker-compose.yml so data persists across container
# restarts/rebuilds rather than living only inside the image layer.

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
