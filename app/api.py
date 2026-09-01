"""
app/api.py - FastAPI backend for the Financial Document Intelligence
Platform (Module 13).

Implements the 7 APIs required by the project brief:
    Upload API | OCR API | Classification API | Metrics API |
    Summary API | Q&A API | Insights API

All business logic lives in core.py (no FastAPI/Streamlit/Plotly
dependency there) - this file is a thin routing layer: each endpoint
validates the request, calls the matching core.py function, and
returns the result as JSON. Every core.py function has already been
tested directly (see Module 13 deliverable, Section 4) and works
correctly; this file adds the HTTP layer on top of already-verified
logic.

TOOLING NOTE:
FastAPI (and uvicorn, its server) are not installed in this sandboxed,
offline development environment, and cannot be installed here (no
internet access to PyPI - the same limitation documented for
XGBoost/spaCy/FAISS/etc. in Modules 5-11). This is different from
those cases in one important way: this file is meant to be RUN BY THE
USER on their own machine (which has internet access), not inside
this sandbox - a normal, expected situation for any coding deliverable
in this project. To run it:

    pip install fastapi uvicorn
    uvicorn api:app --reload --port 8000

Then open http://localhost:8000/docs for the interactive Swagger UI
FastAPI generates automatically.
"""

import os
import time
import shutil
import tempfile

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from pydantic import BaseModel

import core
import database as db

app = FastAPI(
    title="Financial Document Intelligence API",
    description="Upload, extract, classify, analyze, summarize, and "
                 "query financial documents - backed by Modules 3-12.",
    version="1.0.0",
)


@app.middleware("http")
async def monitoring_middleware(request: Request, call_next):
    """Module 14 - Application monitoring: logs every request
    (endpoint, status, latency) to the SQLite request_log table."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    db.log_request(request.url.path, str(response.status_code), duration_ms)
    return response


@app.get("/health", tags=["Monitoring"])
async def health_check():
    """Liveness/readiness probe for deployment platforms (Docker,
    AWS/Azure/GCP load balancers, Streamlit Cloud health checks)."""
    return {"status": "healthy", "service": "financial-document-intelligence-api"}


@app.get("/api/monitoring", tags=["Monitoring"])
async def monitoring_summary():
    """Module 14 - Application monitoring dashboard data: request
    counts, error rate, average latency, recent Q&A activity."""
    return db.get_monitoring_summary()


class QARequest(BaseModel):
    question: str


# =================================================================
# 1. Upload API
# =================================================================
@app.post("/api/upload", tags=["Upload API"])
async def upload_document(file: UploadFile = File(...)):
    """Upload a financial document into the pipeline (data/raw/)."""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    try:
        result = core.upload_document(tmp_path, file.filename)
    finally:
        os.remove(tmp_path)
    return result


@app.get("/api/documents", tags=["Upload API"])
async def list_documents():
    """List every document currently in the dataset catalog (Module 14:
    served from the SQLite database, not the raw CSV)."""
    return db.get_documents()


# =================================================================
# 2. OCR API
# =================================================================
@app.get("/api/ocr/{filename}", tags=["OCR API"])
async def get_extracted_text(filename: str):
    """Return the extracted text for a document (Module 4 output)."""
    result = core.get_extracted_text(filename)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# =================================================================
# 3. Classification API
# =================================================================
@app.get("/api/classify/{filename}", tags=["Classification API"])
async def classify_document(filename: str):
    """Classify a document into its financial statement category."""
    text_result = core.get_extracted_text(filename)
    if "error" in text_result:
        raise HTTPException(status_code=404, detail=text_result["error"])
    text = text_result.get("text") or " ".join(str(v) for v in text_result.get("columns", []))
    return core.classify_document(text)


# =================================================================
# 4. Metrics API
# =================================================================
@app.get("/api/metrics", tags=["Metrics API"])
async def get_metrics(filename: str = Query(None, description="Optional: filter to one document")):
    """Return structured financial metrics (Module 7 output)."""
    return core.get_metrics(filename)


# =================================================================
# 5. Summary API
# =================================================================
@app.get("/api/summary/{filename}", tags=["Summary API"])
async def get_summary(filename: str):
    """Return the 5-category summary for a document (Module 9 output)."""
    result = core.get_summary(filename)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# =================================================================
# 6. Q&A API
# =================================================================
@app.post("/api/qa", tags=["Q&A API"])
async def ask_question(request: QARequest):
    """Ask a natural-language question about the document set (RAG, Module 10)."""
    result = core.answer_question(request.question)
    db.log_qa_interaction(request.question, result.get("answer"), result.get("source_document"))
    return result


# =================================================================
# 7. Insights API
# =================================================================
@app.get("/api/insights", tags=["Insights API"])
async def get_insights():
    """Return the AI-generated financial insights + overall risk (Module 12)."""
    result = core.get_insights()
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# =================================================================
# Supporting endpoints for the dashboard (KPIs, ratios, anomalies)
# =================================================================
@app.get("/api/analysis", tags=["Supporting"])
async def get_financial_analysis():
    """Profitability/liquidity/leverage figures (Module 8 output)."""
    return core.get_financial_analysis()


@app.get("/api/anomalies", tags=["Supporting"])
async def get_anomaly_summary():
    """Anomaly detection summary counts (Module 11 output)."""
    return core.get_anomaly_summary()


@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "Financial Document Intelligence API is running. See /docs for all endpoints."}
