"""
app/core.py - Core business logic for the Financial Document Intelligence
Platform (Module 13).

This module contains NO FastAPI, Streamlit, or Plotly imports - it is
pure Python + pandas/sklearn/joblib, so it can be tested and verified
right now, independently of whether those three frameworks are
installed. api.py (FastAPI) and dashboard.py (Streamlit) both import
from here rather than duplicating logic - a standard "thin
API/UI, thick core" architecture.

Each function wraps the already-built output of Modules 3-12 (reading
the JSON/CSV files those modules produced) rather than re-running
heavy computation on every call - the same design a real production
API would use (serve pre-computed results fast; only compute live
where genuinely necessary, like Q&A).
"""

import os
import sys
import json
import shutil
from datetime import datetime

import joblib
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# =================================================================
# 1. UPLOAD API - accept a new document into the pipeline
# =================================================================
def upload_document(source_path: str, original_filename: str) -> dict:
    """Copy a new file into data/raw/ and append it to the dataset
    catalog. Mirrors what Module 3's collection script does, but for
    a single incoming file rather than a batch."""
    raw_dir = os.path.join(DATA_DIR, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    dest_path = os.path.join(raw_dir, original_filename)
    shutil.copyfile(source_path, dest_path)

    catalog_path = os.path.join(raw_dir, "dataset_catalog.csv")
    catalog = pd.read_csv(catalog_path) if os.path.exists(catalog_path) else pd.DataFrame(
        columns=["document_id", "filename", "document_type", "scanned_copy",
                 "file_type", "pages_or_rows", "size_kb", "source", "collected_on"]
    )
    next_id = f"DOC{len(catalog) + 1:03d}"
    ext = os.path.splitext(original_filename)[1].lstrip(".").upper()
    size_kb = round(os.path.getsize(dest_path) / 1024, 1)
    new_row = {
        "document_id": next_id, "filename": original_filename,
        "document_type": "Unclassified", "scanned_copy": "No",
        "file_type": ext, "pages_or_rows": "N/A", "size_kb": size_kb,
        "source": "Uploaded via API", "collected_on": datetime.now().strftime("%Y-%m-%d"),
    }
    catalog = pd.concat([catalog, pd.DataFrame([new_row])], ignore_index=True)
    catalog.to_csv(catalog_path, index=False)

    return {"document_id": next_id, "filename": original_filename,
            "status": "uploaded", "path": dest_path}


def list_documents() -> list:
    """Backing data for the dashboard's document list / upload panel."""
    catalog_path = os.path.join(DATA_DIR, "raw", "dataset_catalog.csv")
    if not os.path.exists(catalog_path):
        return []
    return pd.read_csv(catalog_path).to_dict(orient="records")


# =================================================================
# 2. OCR API - extracted text for a document (Module 4 output)
# =================================================================
def get_extracted_text(filename: str) -> dict:
    base = os.path.splitext(filename)[0]
    txt_path = os.path.join(DATA_DIR, "processed", base + ".txt")
    if os.path.exists(txt_path):
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return {"filename": filename, "text": text, "char_count": len(text)}

    json_path = os.path.join(DATA_DIR, "processed", base + ".json")
    if os.path.exists(json_path):
        with open(json_path) as f:
            return json.load(f)  # CSV documents: structured summary, not raw text

    return {"filename": filename, "error": "No processed output found. "
            "Run module4_document_processing.py first."}


# =================================================================
# 3. CLASSIFICATION API (Module 6 model)
# =================================================================
_classifier_cache = {}


def _load_classifier():
    if "model" not in _classifier_cache:
        models_dir = os.path.join(DATA_DIR, "models")
        _classifier_cache["vectorizer"] = joblib.load(os.path.join(models_dir, "tfidf_vectorizer.joblib"))
        _classifier_cache["model"] = joblib.load(os.path.join(models_dir, "best_model.joblib"))
        with open(os.path.join(models_dir, "model_type.txt")) as f:
            _classifier_cache["model_type"] = f.read().strip()
    return _classifier_cache


def classify_document(text: str) -> dict:
    cache = _load_classifier()
    X = cache["vectorizer"].transform([text])
    prediction = cache["model"].predict(X)[0]
    proba = None
    if hasattr(cache["model"], "predict_proba"):
        proba = dict(zip(cache["model"].classes_, cache["model"].predict_proba(X)[0].round(3)))
    return {"predicted_category": prediction, "model_used": cache["model_type"],
            "class_probabilities": proba}


# =================================================================
# 4. METRICS API (Module 7 output)
# =================================================================
def get_metrics(filename: str = None) -> list:
    path = os.path.join(DATA_DIR, "metrics_extracted", "financial_metrics_dataset.csv")
    if not os.path.exists(path):
        return []
    df = pd.read_csv(path)
    if filename:
        df = df[df["document"] == filename]
    return df.to_dict(orient="records")


# =================================================================
# 5. SUMMARY API (Module 9 output)
# =================================================================
def get_summary(filename: str) -> dict:
    base = os.path.splitext(filename)[0]
    path = os.path.join(DATA_DIR, "summaries", base + ".json")
    if not os.path.exists(path):
        return {"filename": filename, "error": "No summary found for this document."}
    with open(path) as f:
        return json.load(f)


# =================================================================
# 6. Q&A API (Module 10 RAG pipeline - genuinely live per call)
# =================================================================
_rag_cache = {}


def _load_rag():
    if "retrieve" not in _rag_cache:
        from module10_rag_qa import tfidf_analyzer, simple_stem, ask, SimpleVectorStore
        # The saved vectorizer's custom analyzer was pickled with a
        # reference to "__main__" (since module10_rag_qa.py was run
        # directly when it was created). Register it under whichever
        # module is currently __main__ (api.py, dashboard.py, a test
        # script, ...) so unpickling succeeds regardless of entry point.
        main_module = sys.modules["__main__"]
        main_module.tfidf_analyzer = tfidf_analyzer
        main_module.simple_stem = simple_stem

        rag_dir = os.path.join(DATA_DIR, "rag")
        vectorizer = joblib.load(os.path.join(rag_dir, "tfidf_vectorizer.joblib"))
        chunk_vectors = joblib.load(os.path.join(rag_dir, "chunk_vectors.joblib"))
        with open(os.path.join(rag_dir, "chunks.json")) as f:
            chunks = json.load(f)
        store = SimpleVectorStore(vectorizer, chunk_vectors, chunks)
        _rag_cache["store"] = store
        _rag_cache["ask"] = ask
    return _rag_cache


def answer_question(question: str) -> dict:
    cache = _load_rag()
    return cache["ask"](cache["store"], question)


# =================================================================
# 7. INSIGHTS API (Module 12 output)
# =================================================================
def get_insights() -> dict:
    path = os.path.join(DATA_DIR, "insights", "financial_insights_report.json")
    if not os.path.exists(path):
        return {"error": "No insights report found. Run module12_insights_engine.py first."}
    with open(path) as f:
        return json.load(f)


# =================================================================
# Supporting data for dashboard KPIs / charts (Module 8 + 11 output)
# =================================================================
def get_financial_analysis() -> dict:
    path = os.path.join(DATA_DIR, "analysis", "financial_analysis_report.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)


def get_anomaly_summary() -> dict:
    path = os.path.join(DATA_DIR, "anomalies", "anomaly_detection_report.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)
