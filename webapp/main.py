"""
webapp/main.py - Financial Document Intelligence Platform
=========================================================
Serves the HTML/JS frontend AND the full API.

UPDATED: Every POST /api/upload now runs the complete processing
pipeline (text extraction → classification → metrics → ratios →
summarization → RAG indexing → anomaly detection → insights) and
stores results in SQLite.  All new per-document GET routes read from
the database.  The legacy global routes (/api/analysis, /api/insights,
/api/anomalies) are kept for backward compatibility with NovaTech data.
"""

import os
import sys
import time
import json
import shutil
import tempfile
import uuid

from datetime import datetime, timedelta
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Response, Depends, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


def _safe_json(obj):
    """Recursively convert numpy / non-JSON-serializable types to native Python."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _safe_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_json(i) for i in obj]
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.str_):
        return str(obj)
    return obj

APP_DIR  = os.path.dirname(os.path.abspath(__file__))
CORE_DIR = os.path.join(os.path.dirname(APP_DIR), "app")
sys.path.insert(0, CORE_DIR)

import core
import database as db
import pipeline
import auth

# Uploads directory (persist files for RAG / re-processing)
UPLOAD_DIR = os.path.join(os.path.dirname(APP_DIR), "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Ledger – Financial Document Intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Migrate the CSV catalog into SQLite on first start (idempotent)."""
    try:
        catalog_path = os.path.join(os.path.dirname(APP_DIR), "data", "raw", "dataset_catalog.csv")
        if os.path.exists(catalog_path):
            db.migrate_catalog_from_csv(catalog_path)
    except Exception as exc:
        print(f"[startup] catalog migration skipped: {exc}")
    db.init_db()   # ensure doc_results table exists


@app.middleware("http")
async def monitoring_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    try:
        db.log_request(request.url.path, str(response.status_code), duration_ms)
    except Exception:
        pass
    return response


class QARequest(BaseModel):
    question: str


class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    confirm_password: str


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    confirm_password: str


# =====================================================================
# Authentication Endpoints
# =====================================================================
@app.post("/auth/register")
async def register(req: RegisterRequest, response: Response):
    full_name = req.full_name.strip()
    email = req.email.strip().lower()
    password = req.password
    confirm = req.confirm_password

    if not full_name:
        raise HTTPException(status_code=400, detail="Full name is required.")
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if password != confirm:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    try:
        pw_hash = auth.hash_password(password)
        user = db.create_user(full_name, email, pw_hash)
    except ValueError as val_err:
        raise HTTPException(status_code=400, detail=str(val_err))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An error occurred during registration.")

    token = auth.create_access_token(user["id"], user["email"])
    response.set_cookie(
        key=auth.COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=86400,
        samesite="lax",
        secure=False,
    )
    return {
        "message": "Account created successfully.",
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
        },
        "token": token,
    }


@app.post("/auth/login")
async def login(req: LoginRequest, response: Response):
    email = req.email.strip().lower()
    password = req.password

    if not email or not password:
        raise HTTPException(status_code=400, detail="Please enter your email and password.")

    user = db.get_user_by_email(email)
    if not user or not auth.verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not user.get("is_active", 1):
        raise HTTPException(status_code=401, detail="Account is deactivated.")

    max_age = 7 * 86400 if req.remember_me else 86400
    token = auth.create_access_token(user["id"], user["email"], remember_me=req.remember_me)
    response.set_cookie(
        key=auth.COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=max_age,
        samesite="lax",
        secure=False,
    )
    return {
        "message": "Login successful.",
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
        },
        "token": token,
    }


@app.get("/auth/me")
async def get_me(current_user: dict = Depends(auth.get_current_user)):
    """Returns safe information about the current logged-in user."""
    return {
        "id": current_user["id"],
        "full_name": current_user["full_name"],
        "email": current_user["email"],
    }


@app.post("/auth/logout")
async def logout(response: Response):
    """Invalidate session and clear cookie."""
    response.delete_cookie(auth.COOKIE_NAME)
    return {"message": "Logged out successfully."}


@app.post("/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    token = uuid.uuid4().hex
    expires = (datetime.now() + timedelta(hours=1)).isoformat()

    user = db.get_user_by_email(email)
    if user:
        db.create_password_reset(email, token, expires)

    return {
        "message": "If an account exists for this email, password reset instructions have been sent.",
        "dev_token": token if user else None,
    }


@app.post("/auth/reset-password")
async def reset_password(req: ResetPasswordRequest):
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match.")

    reset_rec = db.get_password_reset(req.token)
    if not reset_rec or reset_rec.get("used"):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token.")

    exp_str = reset_rec.get("expires_at")
    try:
        exp_dt = datetime.fromisoformat(exp_str)
        if datetime.now() > exp_dt:
            raise HTTPException(status_code=400, detail="Reset token has expired.")
    except Exception:
        pass

    user = db.get_user_by_email(reset_rec["email"])
    if not user:
        raise HTTPException(status_code=400, detail="User not found.")

    new_hash = auth.hash_password(req.new_password)
    db.update_user_password(user["id"], new_hash)
    db.mark_password_reset_used(req.token)
    return {"message": "Password reset successfully. You can now log in."}


# =====================================================================
# Frontend & Static Files (with Cache-Control prevention)
# =====================================================================
@app.middleware("http")
async def add_cache_control_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


app.mount("/static", StaticFiles(directory=os.path.join(APP_DIR, "static")), name="static")


@app.get("/")
async def root():
    resp = FileResponse(os.path.join(APP_DIR, "index.html"))
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp


@app.get("/health")
async def health():
    return {"status": "healthy", "pipeline": "ready"}


# =====================================================================
# Upload — triggers the full processing pipeline (Associated with User)
# =====================================================================
@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(auth.get_current_user)
):
    """
    Accept a PDF or CSV, run the complete 8-stage pipeline synchronously,
    associated with the authenticated user, and return the full analysis result.
    """
    fname = file.filename or "upload"
    allowed_exts = (".pdf", ".csv", ".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif")
    if not fname.lower().endswith(allowed_exts):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Accepted: PDF, CSV, JPG, PNG, WEBP, TIFF."
        )

    # Generate a unique ID for this upload
    doc_id = "DOC-" + uuid.uuid4().hex[:8].upper()

    # Ensure uploads directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Persist the file permanently (needed for RAG re-queries)
    ext = os.path.splitext(fname)[1] or ".pdf"
    saved_path = os.path.join(UPLOAD_DIR, f"{doc_id}{ext}")
    try:
        with open(saved_path, "wb") as f_out:
            shutil.copyfileobj(file.file, f_out)
    except Exception as write_err:
        return JSONResponse(
            status_code=500,
            content={"document_id": doc_id, "filename": fname,
                     "status": "failed",
                     "error": f"Could not save uploaded file: {write_err}"}
        )

    # Run the full pipeline (synchronous — associated with current_user["id"])
    try:
        result = pipeline.run(doc_id, saved_path, fname, user_id=current_user["id"])
    except Exception as pipe_err:
        return JSONResponse(
            status_code=200,  # 200 so frontend can parse the error body
            content={"document_id": doc_id, "filename": fname,
                     "status": "failed",
                     "error": f"Pipeline error: {pipe_err}"}
        )

    # Ensure the response always includes document_id and filename at the top level
    result.setdefault("document_id", doc_id)
    result.setdefault("filename", fname)
    result.pop("traceback", None)
    safe_result = _safe_json(result)
    return JSONResponse(content=safe_result)


# =====================================================================
# Document listing (Filtered by authenticated user)
# =====================================================================
@app.get("/api/documents")
async def list_documents(current_user: dict = Depends(auth.get_current_user)):
    """Returns pipeline-processed docs belonging to the user and catalog docs."""
    pipeline_docs = db.get_all_doc_results(user_id=current_user["id"])
    catalog_docs  = []
    try:
        catalog_docs = db.get_documents()
    except Exception:
        pass
    return {"pipeline_documents": pipeline_docs, "catalog_documents": catalog_docs}


@app.get("/api/documents/processed")
async def list_processed_documents(current_user: dict = Depends(auth.get_current_user)):
    """Returns only pipeline-processed documents belonging to the authenticated user."""
    return db.get_all_doc_results(user_id=current_user["id"])


# =====================================================================
# Delete a document (DB + uploaded file + RAG index)
# =====================================================================
@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str, current_user: dict = Depends(auth.get_current_user)):
    """
    Permanently delete a document belonging to the authenticated user:
      1. Remove DB row from doc_results
      2. Delete the uploaded file from data/uploads/
      3. Delete the RAG index directory from data/rag/{doc_id}/
    """
    _get_or_404(doc_id, user_id=current_user["id"])
    deleted_db = db.delete_doc_result(doc_id, user_id=current_user["id"])

    # Delete uploaded file (any extension)
    deleted_file = False
    for fname in os.listdir(UPLOAD_DIR):
        if fname.startswith(doc_id):
            try:
                os.remove(os.path.join(UPLOAD_DIR, fname))
                deleted_file = True
            except Exception:
                pass

    # Delete RAG index directory
    rag_dir = os.path.join(os.path.dirname(APP_DIR), "data", "rag", doc_id)
    deleted_rag = False
    if os.path.isdir(rag_dir):
        try:
            shutil.rmtree(rag_dir)
            deleted_rag = True
        except Exception:
            pass

    if not deleted_db and not deleted_file:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    return {
        "document_id": doc_id,
        "deleted": True,
        "db_row_removed": deleted_db,
        "file_removed": deleted_file,
        "rag_index_removed": deleted_rag,
    }


# =====================================================================
# Per-document routes (pipeline data from DB, with ownership check)
# =====================================================================
def _get_or_404(doc_id: str, user_id: int | None = None) -> dict:
    result = db.get_doc_result(doc_id, user_id=user_id)
    if not result:
        if user_id is not None:
            any_doc = db.get_doc_result(doc_id)
            if any_doc:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied. You do not have permission to view this document."
                )
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")
    return result


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str, current_user: dict = Depends(auth.get_current_user)):
    return _get_or_404(doc_id, user_id=current_user["id"])


@app.get("/api/documents/{doc_id}/classification")
async def get_doc_classification(doc_id: str, current_user: dict = Depends(auth.get_current_user)):
    r = _get_or_404(doc_id, user_id=current_user["id"])
    return {
        "document_id": doc_id,
        "filename": r.get("filename"),
        "category": r.get("doc_category") or "Financial Document",
        "confidence": r.get("clf_confidence"),
        "model_used": r.get("clf_model") or "rule_based_classifier",
        "class_probabilities": r.get("class_probabilities") or {},
        "status": r.get("status"),
    }


@app.get("/api/documents/{doc_id}/metrics")
async def get_doc_metrics(doc_id: str, current_user: dict = Depends(auth.get_current_user)):
    r = _get_or_404(doc_id, user_id=current_user["id"])
    raw_values = {}
    ratios = {}
    try:
        import json
        raw_values = json.loads(r.get("raw_values_json") or "{}")
        ratios = json.loads(r.get("ratios_json") or "{}")
    except Exception:
        pass
    return {
        "document_id": doc_id,
        "filename": r.get("filename"),
        "document_year": r.get("doc_year"),
        "raw_values": raw_values,
        "ratios": ratios,
        "financial_health": r.get("financial_health"),
        "metrics": r.get("metrics") or [],
    }


@app.get("/api/documents/{doc_id}/analysis")
async def get_doc_analysis(doc_id: str, current_user: dict = Depends(auth.get_current_user)):
    r = _get_or_404(doc_id, user_id=current_user["id"])
    import json
    ratios = {}
    raw_values = {}
    try:
        ratios = json.loads(r.get("ratios_json") or "{}")
        raw_values = json.loads(r.get("raw_values_json") or "{}")
    except Exception:
        pass
    return {
        "document_id": doc_id,
        "filename": r.get("filename"),
        "doc_year": r.get("doc_year"),
        "doc_category": r.get("doc_category"),
        "financial_health": r.get("financial_health"),
        "profitability": {
            "revenue": raw_values.get("Revenue"),
            "net_income": raw_values.get("Net Income"),
            "gross_profit": raw_values.get("Gross Profit"),
            "profit_margin_pct": ratios.get("profit_margin_pct"),
            "gross_margin_pct": ratios.get("gross_margin_pct"),
            "operating_margin_pct": ratios.get("operating_margin_pct"),
        },
        "liquidity": {
            "current_assets": raw_values.get("Current Assets"),
            "current_liabilities": raw_values.get("Current Liabilities"),
            "current_ratio": ratios.get("current_ratio"),
        },
        "leverage": {
            "debt": raw_values.get("Debt"),
            "equity": raw_values.get("Equity"),
            "debt_to_equity": ratios.get("debt_to_equity"),
        },
        "all_ratios": ratios,
    }


@app.get("/api/documents/{doc_id}/summary")
async def get_doc_summary(doc_id: str, current_user: dict = Depends(auth.get_current_user)):
    r = _get_or_404(doc_id, user_id=current_user["id"])
    import json
    summary = {}
    try:
        summary = json.loads(r.get("summary_json") or "{}")
    except Exception:
        pass
    return {
        "document_id": doc_id,
        "filename": r.get("filename"),
        "word_count": r.get("word_count"),
        **summary,
    }


@app.get("/api/documents/{doc_id}/insights")
async def get_doc_insights(doc_id: str, current_user: dict = Depends(auth.get_current_user)):
    r = _get_or_404(doc_id, user_id=current_user["id"])
    import json
    insights = {}
    try:
        insights = json.loads(r.get("insights_json") or "{}")
    except Exception:
        pass
    return {"document_id": doc_id, "filename": r.get("filename"), **insights}


@app.get("/api/documents/{doc_id}/anomalies")
async def get_doc_anomalies(doc_id: str, current_user: dict = Depends(auth.get_current_user)):
    r = _get_or_404(doc_id, user_id=current_user["id"])
    import json
    anomalies = []
    try:
        anomalies = json.loads(r.get("anomalies_json") or "[]")
    except Exception:
        pass
    return {"document_id": doc_id, "filename": r.get("filename"), "anomalies": anomalies}


@app.post("/api/documents/{doc_id}/ask")
async def ask_document_question(
    doc_id: str, request: QARequest, current_user: dict = Depends(auth.get_current_user)
):
    """Q&A against a specific uploaded document's RAG index with user ownership check."""
    # Verify document exists and belongs to current_user
    _get_or_404(doc_id, user_id=current_user["id"])
    result = pipeline.ask_question_for_doc(doc_id, request.question)
    try:
        db.log_qa_interaction(request.question, result.get("answer"), doc_id)
    except Exception:
        pass
    return result


# =====================================================================
# Legacy / global routes (NovaTech pre-computed data — backward compat)
# =====================================================================
@app.get("/api/document/{filename}/summary")
async def document_summary_legacy(filename: str):
    result = core.get_summary(filename)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/api/document/{filename}/metrics")
async def document_metrics_legacy(filename: str):
    return core.get_metrics(filename)


@app.get("/api/document/{filename}/classification")
async def document_classification_legacy(filename: str):
    text_result = core.get_extracted_text(filename)
    if "error" in text_result:
        raise HTTPException(status_code=404, detail=text_result["error"])
    text = text_result.get("text") or " ".join(str(c) for c in text_result.get("columns", []))
    return core.classify_document(text)


@app.post("/api/qa")
async def ask_question_global(request: QARequest):
    result = core.answer_question(request.question)
    try:
        db.log_qa_interaction(request.question, result.get("answer"), result.get("source_document"))
    except Exception:
        pass
    return result


@app.get("/api/insights")
async def insights_global():
    result = core.get_insights()
    if "error" in result:
        return {"error": result["error"], "note": "Upload a document to generate insights."}
    return result


@app.get("/api/analysis")
async def analysis_global():
    return core.get_financial_analysis()


@app.get("/api/anomalies")
async def anomalies_global():
    return core.get_anomaly_summary()


@app.get("/api/monitoring")
async def monitoring():
    return db.get_monitoring_summary()
