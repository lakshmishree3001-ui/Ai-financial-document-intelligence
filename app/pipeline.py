"""
app/pipeline.py  —  End-to-end Document Processing Pipeline
=============================================================
Takes a newly uploaded PDF, CSV, or image and runs every stage in order:

  extract_text → preprocess → classify → extract_metrics →
  compute_ratios → summarize → build_rag → detect_anomalies →
  generate_insights → persist_to_db

Supported input types:
  - PDF  (digital text or scanned — with OCR fallback)
  - CSV
  - Images: JPG, JPEG, PNG, WEBP, TIFF (OCR via pytesseract + Pillow)

All logic is borrowed directly from the existing scripts/ modules
(no duplication) and adapted to work on an in-memory text string
rather than a file path sitting in data/processed/.

The DB (app/database.py extended schema) is the only output — nothing
in data/processed/ is required as INPUT for a new document.
processed_data can still be written as a cache if the caller wants,
but it is never READ here.
"""

import os
import re
import sys
import json
import joblib
import shutil
import traceback
import numpy as np
from datetime import datetime
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
DATA_DIR = os.path.join(BASE_DIR, "data")

sys.path.insert(0, SCRIPTS_DIR)

# ── Windows encoding fix: ensure stdout/stderr can handle Unicode ──────
import io as _io
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── Optional imports (OCR may be unavailable) ─────────────────────────
try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False

try:
    from pypdf import PdfReader
    PYPDF_OK = True
except ImportError:
    PYPDF_OK = False

try:
    import pytesseract
    from PIL import Image
    import subprocess, tempfile
    TESSERACT_OK = True
except ImportError:
    TESSERACT_OK = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

STOP_WORDS = set(ENGLISH_STOP_WORDS) if SKLEARN_OK else set()

# Clear model cache on (re)load so any newly-retrained model is always used
_clf_cache = {}

# ═══════════════════════════════════════════════════════════════════════
# STAGE 1 — Text Extraction
# ═══════════════════════════════════════════════════════════════════════
BLANK_PAGE_THRESHOLD = 20


def _clean_text(raw: str) -> str:
    text = raw.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def _ocr_page(pdf_path: str, page_number: int) -> str:
    """OCR a single PDF page. Returns empty string if unavailable."""
    if not TESSERACT_OK:
        return ""
    try:
        tmp_dir = tempfile.mkdtemp()
        prefix = os.path.join(tmp_dir, "page")
        subprocess.run(
            ["pdftoppm", "-jpeg", "-r", "200", "-f", str(page_number),
             "-l", str(page_number), pdf_path, prefix],
            check=True, capture_output=True, timeout=30,
        )
        images = [f for f in os.listdir(tmp_dir) if f.lower().endswith(".jpg")]
        if not images:
            return ""
        return pytesseract.image_to_string(Image.open(os.path.join(tmp_dir, images[0])))
    except Exception:
        return ""
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".tif"}


def extract_text_from_image(file_path: str) -> dict:
    """
    Extract text from an image file (JPG, PNG, WEBP, TIFF) using OCR.
    Returns the same dict shape as extract_text().
    """
    if not TESSERACT_OK:
        return {
            "text": "",
            "word_count": 0,
            "num_pages": 1,
            "extraction_method": "ocr_unavailable",
            "ocr_used": True,
            "source_type": "image",
            "error": "pytesseract / Pillow not installed. Cannot OCR images.",
        }
    try:
        img = Image.open(file_path)
        # Convert to RGB to ensure compatibility with all tesseract modes
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        raw_text = pytesseract.image_to_string(img)
        cleaned = _clean_text(raw_text)
        if not cleaned.strip():
            return {
                "text": "",
                "word_count": 0,
                "num_pages": 1,
                "extraction_method": "ocr_tesseract",
                "ocr_used": True,
                "source_type": "image",
                "error": "OCR produced no text. The image may be too blurry or low resolution.",
            }
        return {
            "text": cleaned,
            "word_count": len(cleaned.split()),
            "num_pages": 1,
            "extraction_method": "ocr_tesseract",
            "ocr_used": True,
            "source_type": "image",
            "error": None,
        }
    except Exception as e:
        return {
            "text": "",
            "word_count": 0,
            "num_pages": 1,
            "extraction_method": "failed",
            "ocr_used": True,
            "source_type": "image",
            "error": f"Image OCR failed: {e}",
        }


def extract_text(file_path: str) -> dict:
    """
    Extract text from a PDF, CSV, or image file.
    Returns:
        {text, word_count, num_pages, extraction_method, ocr_used, source_type, error}
    """
    ext = os.path.splitext(file_path)[1].lower()

    # ── Image extraction ───────────────────────────────────────────
    if ext in IMAGE_EXTENSIONS:
        return extract_text_from_image(file_path)

    if ext == ".csv":
        try:
            import csv as csv_mod
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv_mod.reader(f)
                rows = list(reader)
            header = rows[0] if rows else []
            text = " ".join(header) + "\n" + "\n".join(
                " ".join(cell.strip() for cell in row) for row in rows[1:] if any(r.strip() for r in row)
            )
            cleaned = _clean_text(text)
            return {
                "text": cleaned,
                "word_count": len(cleaned.split()),
                "num_pages": len(rows),
                "extraction_method": "csv_direct",
                "ocr_used": False,
                "source_type": "csv",
                "error": None,
            }
        except Exception as e:
            return {"text": "", "word_count": 0, "num_pages": 0,
                    "extraction_method": "failed", "ocr_used": False,
                    "source_type": "csv",
                    "error": f"CSV read error: {e}"}

    # ── PDF extraction ─────────────────────────────────────────────
    if not PDFPLUMBER_OK and not PYPDF_OK:
        return {"text": "", "word_count": 0, "num_pages": 0,
                "extraction_method": "unavailable", "ocr_used": False,
                "source_type": "digital_pdf",
                "error": "Neither pdfplumber nor pypdf is installed in this environment. "
                         "Please install them: pip install pdfplumber pypdf"}

    try:
        num_pages = 0
        if PYPDF_OK:
            try:
                num_pages = len(PdfReader(file_path).pages)
            except Exception:
                pass

        page_texts = []
        methods_used = set()
        ocr_used = False

        if PDFPLUMBER_OK:
            try:
                with pdfplumber.open(file_path) as pdf:
                    num_pages = num_pages or len(pdf.pages)
                    for i, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text() or ""
                        if len(text.strip()) < BLANK_PAGE_THRESHOLD:
                            ocr_text = _ocr_page(file_path, i)
                            if len(ocr_text.strip()) >= BLANK_PAGE_THRESHOLD:
                                page_texts.append(ocr_text)
                                methods_used.add("ocr_tesseract")
                                ocr_used = True
                            else:
                                page_texts.append("")
                        else:
                            page_texts.append(text)
                            methods_used.add("pdf_text_extraction")
            except Exception as plumber_err:
                # pdfplumber failed — fall back to pypdf
                print(f"[pipeline] pdfplumber error: {plumber_err} — trying pypdf fallback")
                page_texts = []
                methods_used = set()
                if PYPDF_OK:
                    try:
                        reader = PdfReader(file_path)
                        num_pages = len(reader.pages)
                        for i, page in enumerate(reader.pages, start=1):
                            page_text = page.extract_text() or ""
                            page_texts.append(page_text)
                            methods_used.add("pypdf_extraction")
                    except Exception as pypdf_err:
                        return {"text": "", "word_count": 0, "num_pages": 0,
                                "extraction_method": "failed", "ocr_used": False,
                                "source_type": "digital_pdf",
                                "error": f"PDF extraction failed with both pdfplumber ({plumber_err}) and pypdf ({pypdf_err})."}
                else:
                    return {"text": "", "word_count": 0, "num_pages": 0,
                            "extraction_method": "failed", "ocr_used": False,
                            "source_type": "digital_pdf",
                            "error": f"PDF extraction failed: {plumber_err}"}
        else:
            # pypdf fallback
            reader = PdfReader(file_path)
            num_pages = len(reader.pages)
            for i, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                page_texts.append(text)
                methods_used.add("pypdf_extraction")

        combined = "\n".join(page_texts)
        cleaned = _clean_text(combined)

        if not cleaned.strip():
            return {"text": "", "word_count": 0, "num_pages": num_pages,
                    "extraction_method": "none_extracted", "ocr_used": ocr_used,
                    "source_type": "scanned_pdf" if ocr_used else "digital_pdf",
                    "error": "No text could be extracted. The PDF may be a scanned image. "
                             "Enable Tesseract OCR for scanned document support."}

        return {
            "text": cleaned,
            "word_count": len(cleaned.split()),
            "num_pages": num_pages,
            "extraction_method": "+".join(sorted(methods_used)),
            "ocr_used": ocr_used,
            "source_type": "scanned_pdf" if ocr_used else "digital_pdf",
            "error": None,
        }
    except Exception as e:
        return {"text": "", "word_count": 0, "num_pages": 0,
                "extraction_method": "failed", "ocr_used": False,
                "source_type": "digital_pdf",
                "error": f"PDF extraction failed: {e}"}


# ═══════════════════════════════════════════════════════════════════════
# STAGE 2 — Document Classification
# ═══════════════════════════════════════════════════════════════════════
_clf_cache = {}


# ── Keyword-based fallback classifier ──────────────────────────────────
# ── Keyword & rule-based classifier dictionary ──────────────────────────
_KEYWORD_CATEGORIES = [
    (
        "Invoice / Receipt",
        ["receipt", "receipt no", "received with thanks", "fee receipt", "college fee",
         "fee cleared", "payment receipt", "invoice", "invoice no", "invoice number",
         "tax invoice", "bill to", "ship to", "amount due", "total due", "subtotal",
         "payment terms", "remit to", "gstin", "po number", "total amount",
         "cashier", "payer", "payee", "online transaction", "against document",
         "towards fee", "cash/dd/neft", "rupees in words"],
    ),
    (
        "Bank Statement",
        ["bank statement", "account statement", "account number", "account summary",
         "opening balance", "closing balance", "total deposits", "total withdrawals",
         "cleared balance", "statement period", "transaction history", "neft", "rtgs",
         "debit card", "credit card", "bank branch", "ifsc code", "savings account",
         "current account", "value date", "withdrawal amount", "deposit amount"],
    ),
    (
        "Balance Sheet",
        ["balance sheet", "statement of financial position", "total assets",
         "total liabilities", "stockholders equity", "shareholders equity",
         "current assets", "current liabilities", "long-term debt", "retained earnings",
         "non-current assets", "non-current liabilities", "property plant and equipment",
         "accounts payable", "accounts receivable", "total equity and liabilities"],
    ),
    (
        "Income Statement",
        ["income statement", "statement of profit", "profit and loss", "statement of operations",
         "revenue from operations", "total revenue", "gross profit", "operating profit",
         "operating expenses", "net income", "net profit", "earnings per share", "ebitda",
         "ebit", "cost of goods sold", "cogs", "diluted eps", "finance costs"],
    ),
    (
        "Cash Flow Statement",
        ["cash flow", "statement of cash flows", "operating activities",
         "investing activities", "financing activities", "net increase in cash",
         "cash and cash equivalents", "cash flows from operations", "capital expenditures",
         "dividends paid", "proceeds from issuance"],
    ),
    (
        "Annual Report",
        ["annual report", "integrated report", "form 10-k", "board of directors",
         "corporate governance", "chairmans statement", "directors report",
         "management discussion and analysis", "letter to shareholders",
         "auditors report", "notes to consolidated financial statements"],
    ),
    (
        "Earnings Report",
        ["earnings report", "earnings release", "quarterly report", "form 10-q",
         "financial results for the quarter", "quarterly results", "q1", "q2", "q3", "q4",
         "half year results", "investor presentation"],
    ),
    (
        "Tax Document",
        ["tax return", "income tax", "taxable income", "deferred tax",
         "tax liability", "form 16", "w-2", "1099", "withholding tax", "gst return",
         "advance tax", "tax assessment"],
    ),
    (
        "Audit Report",
        ["independent auditor", "audit report", "audit opinion",
         "material misstatement", "audit committee", "internal controls",
         "going concern", "qualified opinion", "unmodified opinion"],
    ),
]


def _classify_by_keywords(text: str) -> dict:
    """Keyword-based classifier scoring each category by keyword hits with phrase weights."""
    text_lower = text.lower()
    scores = {}
    for category, keywords in _KEYWORD_CATEGORIES:
        score = 0
        for kw in keywords:
            if kw in text_lower:
                # Give multi-word phrases higher weight
                weight = 3 if len(kw.split()) > 1 else 1
                score += weight
        scores[category] = score

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_cat, best_score = sorted_scores[0]
    total_hits = sum(scores.values())

    if best_score == 0:
        return {
            "category": "Financial Document",
            "confidence": 0.50,
            "model_used": "keyword_fallback",
            "class_probabilities": {"Financial Document": 1.0},
        }

    # Normalize probabilities for top matching categories
    probs = {}
    for cat, sc in sorted_scores:
        if sc > 0:
            probs[cat] = round(sc / total_hits, 3)

    # Base confidence between 0.65 and 0.95 based on dominance
    confidence = round(min(0.65 + (best_score / max(total_hits, 1)) * 0.30, 0.95), 3)

    return {
        "category": best_cat,
        "confidence": confidence,
        "model_used": "rule_based_classifier",
        "class_probabilities": probs,
    }


def classify_document(text: str) -> dict:
    """
    Classify a financial document using a robust hybrid system:
    1. Evaluates ML model (TF-IDF + Random Forest / SVC).
    2. Evaluates domain financial keyword signatures.
    3. Combines both: uses high-confidence domain classifier when ML confidence is low,
       ensuring documents like receipts, invoices, statements are accurately labeled.
    """
    import warnings

    # 1. Run domain keyword classifier
    kw_result = _classify_by_keywords(text)

    # 2. Try ML model
    ml_result = None
    try:
        if "model" not in _clf_cache:
            models_dir = os.path.join(DATA_DIR, "models")
            vec_path   = os.path.join(models_dir, "tfidf_vectorizer.joblib")
            model_path = os.path.join(models_dir, "best_model.joblib")
            if not (os.path.exists(vec_path) and os.path.exists(model_path)):
                raise FileNotFoundError("ML model files not found.")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _clf_cache["vec"] = joblib.load(vec_path)
                _clf_cache["model"] = joblib.load(model_path)
            with open(os.path.join(models_dir, "model_type.txt")) as f:
                _clf_cache["model_type"] = f.read().strip()

        X = _clf_cache["vec"].transform([text])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            prediction = _clf_cache["model"].predict(X)[0]
            confidence = None
            class_probs = {}
            if hasattr(_clf_cache["model"], "predict_proba"):
                proba = _clf_cache["model"].predict_proba(X)[0]
                confidence = round(float(max(proba)), 3)
                if hasattr(_clf_cache["model"], "classes_"):
                    for c_name, p_val in zip(_clf_cache["model"].classes_, proba):
                        class_probs[str(c_name)] = round(float(p_val), 3)

        ml_result = {
            "category": str(prediction),
            "confidence": float(confidence) if confidence is not None else None,
            "model_used": str(_clf_cache.get("model_type", "ml_model")),
            "class_probabilities": class_probs,
        }
    except Exception as clf_err:
        _clf_cache.clear()
        ml_result = None

    # 3. Hybrid decision:
    # If ML model succeeded and is confident (>= 0.65), use ML
    if ml_result and (ml_result["confidence"] or 0) >= 0.65:
        return ml_result

    # If domain keyword classifier found clear signals (confidence >= 0.65)
    if kw_result and kw_result["confidence"] >= 0.65:
        merged_probs = dict(kw_result.get("class_probabilities") or {})
        if ml_result and ml_result.get("class_probabilities"):
            for k, v in ml_result["class_probabilities"].items():
                if k not in merged_probs:
                    merged_probs[k] = v
        kw_result["class_probabilities"] = merged_probs
        return kw_result

    # Fallback to ML if available, else keyword result
    return ml_result if ml_result else kw_result


# ═══════════════════════════════════════════════════════════════════════
# STAGE 3 — Financial Metric Extraction  (module7 logic inline)
# ═══════════════════════════════════════════════════════════════════════
METRIC_LABELS = {
    "Revenue":          [r"(?<!\w)(?:Total\s+)?Revenue(?!\s+Growth)", r"Turnover", r"Total Sales", r"Sales", r"Total Income"],
    "Gross Profit":     [r"Gross\s+Profit"],
    "Operating Profit": [r"Operating\s+(?:Profit|Income)", r"\bEBIT\b"],
    "Net Income":       [r"Net\s+(?:Income|Profit)", r"Profit\s+After\s+Tax", r"\bPAT\b"],
    "Total Assets":     [r"Total\s+Assets"],
    "Total Liabilities":[r"(?:Total\s+)?Liabilities(?! and)", r"Total\s+Liabilities"],
    "Equity":           [r"(?:Total\s+)?(?:Stockholders|Shareholders)?['’]?\s*Equity", r"Net\s+Worth"],
    "EPS":              [r"Earnings Per Share\s*\(EPS\)", r"Earnings Per Share", r"\bEPS\b"],
    "Debt":             [r"(?:Total\s+|Long.?term\s+|Short.?term\s+)?Debt", r"Borrowings"],
    "Cash Flow":        [r"(?:Net\s+)?Cash\s+Flow(?:\s+from\s+Operations)?", r"Net Cash from Operating", r"Net Increase in Cash"],
    "Current Assets":   [r"(?:Total\s+)?Current\s+Assets(?! and)"],
    "Current Liabilities": [r"(?:Total\s+)?Current\s+Liabilities(?! and)"],
    "Gross Profit Margin": [r"Gross (?:Profit )?Margin"],
    "Operating Expense": [r"(?:Total\s+)?Operating\s+Expenses?"],
    "Total Amount":     [r"Total\s+Amount", r"Amount\s+Due", r"Total\s+Due", r"Grand\s+Total", r"Fee\s+(?:Cleared|Amount)?", r"Towards.*?Fee", r"Amount\s+Paid", r"Net\s+Payable"],
    "Receipt / Invoice No": [r"Receipt\s+No", r"Invoice\s+No"],
}

# Matches currency numbers like: ₹ 46,150.00, Rs. 1,200 crore, $420.0 million, €50M
CURRENCY_PATTERN = re.compile(
    r"((?:Rs\.?|₹|INR|\$|€)\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|Crore|lakh|Lakh|lakhs|Lakhs|Million|Billion|million|billion|trillion))?)"
    r"|([\d,]+(?:\.\d+)?\s?(?:crore|Crore|lakh|Lakh|million|billion|trillion))",
    re.IGNORECASE
)

# Matches any standalone currency string like ₹ 46,150.00 or $1,250.00
CURR_STANDALONE_REGEX = re.compile(r"((?:Rs\.?|₹|INR|\$|€)\s*[\d,]+(?:\.\d+)?)", re.IGNORECASE)

# Matches plain numeric values in tables (e.g. 585.0, 46,150.00, 1,200)
VAL_REGEX = re.compile(
    r"(?:(?:Rs\.?|₹|INR|\$|€)\s*)?([\d]{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(crore|lakhs?|million|billion|trillion)?",
    re.IGNORECASE
)

FY_PATTERN = re.compile(r"\bFY\s?(\d{4})\b")
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def _detect_year(text: str) -> str:
    fy = FY_PATTERN.findall(text)
    if fy:
        return "FY" + Counter(fy).most_common(1)[0][0]
    yr = YEAR_PATTERN.findall(text)
    if yr:
        return Counter(yr).most_common(1)[0][0]
    return "Unknown"


def extract_metrics(text: str) -> dict:
    """
    Extract financial metrics from text. Supports:
      - Formatted currency (₹, Rs, $, € with/without scale words)
      - Plain tabular numbers
      - Adjacent line matching (label on line N, value on line N+1)
      - Standalone invoice / receipt totals
    Returns:
      {document_year, metrics: [{metric, value, source_line}], raw_values: {metric: value_str}}
    """
    doc_year = _detect_year(text)
    records = []
    seen = set()
    raw_values = {}

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    for idx, line in enumerate(lines):
        for canonical, patterns in METRIC_LABELS.items():
            if any(re.search(p, line, re.IGNORECASE) for p in patterns):
                # 1. Look for currency or number on same line
                val = None
                curr_m = CURRENCY_PATTERN.search(line) or CURR_STANDALONE_REGEX.search(line)
                if curr_m:
                    val = curr_m.group(0).strip()
                else:
                    # Look for plain numbers on same line, filtering out 4-digit years
                    for vm in VAL_REGEX.finditer(line):
                        num_s = vm.group(1).replace(",", "")
                        try:
                            num = float(num_s)
                            if 1990 <= num <= 2050 and len(num_s) == 4 and not vm.group(2):
                                continue  # likely year, skip
                            val = vm.group(0).strip()
                            break
                        except Exception:
                            pass

                # 2. If not found on same line, look at next line (common in invoices/receipts/PDF tables)
                if not val and idx + 1 < len(lines):
                    next_line = lines[idx + 1]
                    next_curr = CURRENCY_PATTERN.search(next_line) or CURR_STANDALONE_REGEX.search(next_line)
                    if next_curr:
                        val = next_curr.group(0).strip()
                    else:
                        vm = VAL_REGEX.search(next_line)
                        if vm:
                            val = vm.group(0).strip()

                # Filter out document/reference IDs with leading zeros or > 10 digits without decimals
                if val:
                    clean_digits = re.sub(r"[^\d]", "", val)
                    if (val.startswith("0") and "." not in val) or (len(clean_digits) > 10 and "." not in val):
                        val = None

                if val and (canonical, val) not in seen:
                    seen.add((canonical, val))
                    records.append({"metric": canonical, "value": val, "year": doc_year, "source_line": line})
                    if canonical not in raw_values:
                        raw_values[canonical] = val

    # 3. Fallback for standalone receipt/invoice amounts (e.g. ₹ 46,150.00 on single line)
    explicit_currencies = []
    for line in lines:
        curr_m = CURR_STANDALONE_REGEX.search(line)
        if curr_m:
            explicit_currencies.append((curr_m.group(0).strip(), line))

    if explicit_currencies:
        # Use the prominent or last explicit currency amount (e.g. ₹ 46,150.00)
        prominent_val, prominent_line = explicit_currencies[-1]
        if "Total Amount" not in raw_values or not any(s in raw_values["Total Amount"] for s in ("₹", "$", "€", "Rs", "INR")):
            raw_values["Total Amount"] = prominent_val
            records.append({"metric": "Total Amount", "value": prominent_val, "year": doc_year, "source_line": prominent_line})

    # 4. Map Total Amount -> Revenue for single-transaction documents so charts/KPIs work for all docs
    if "Revenue" not in raw_values and "Total Amount" in raw_values:
        raw_values["Revenue"] = raw_values["Total Amount"]

    return {"document_year": doc_year, "metrics": records, "raw_values": raw_values}


def _parse_value(value_str: str) -> float | None:
    """Convert extracted value string to a float number."""
    if not value_str:
        return None
    s = value_str
    s = re.sub(r"Rs\.?|₹|INR|\$|€", "", s).strip()
    multiplier = 1.0
    for word, mult in [("crore", 1e7), ("lakh", 1e5), ("lakhs", 1e5),
                       ("billion", 1e9), ("million", 1e6), ("trillion", 1e12)]:
        if re.search(word, s, re.IGNORECASE):
            multiplier = mult
            s = re.sub(word, "", s, flags=re.IGNORECASE)
            break
    s = s.replace(",", "").strip()
    try:
        return float(s) * multiplier
    except ValueError:
        return None


# ═══════════════════════════════════════════════════════════════════════
# STAGE 4 — Financial Ratio Computation
# ═══════════════════════════════════════════════════════════════════════
def compute_ratios(raw_values: dict) -> dict:
    """
    Compute financial ratios from extracted raw_values dict.
    Only computes a ratio when BOTH required values exist.
    Never fabricates values.
    """
    def get(key):
        return _parse_value(raw_values.get(key))

    revenue = get("Revenue")
    net_income = get("Net Income")
    gross_profit = get("Gross Profit")
    operating_profit = get("Operating Profit")
    current_assets = get("Current Assets")
    current_liabilities = get("Current Liabilities")
    equity = get("Equity")
    debt = get("Debt")
    total_assets = get("Total Assets")
    total_liabilities = get("Total Liabilities")

    ratios = {}

    # Profit margin
    if revenue and revenue > 0 and net_income is not None:
        ratios["profit_margin_pct"] = round((net_income / revenue) * 100, 2)

    # Gross margin
    if revenue and revenue > 0 and gross_profit is not None:
        ratios["gross_margin_pct"] = round((gross_profit / revenue) * 100, 2)

    # Operating margin
    if revenue and revenue > 0 and operating_profit is not None:
        ratios["operating_margin_pct"] = round((operating_profit / revenue) * 100, 2)

    # Current ratio
    if current_assets and current_liabilities and current_liabilities > 0:
        ratios["current_ratio"] = round(current_assets / current_liabilities, 2)

    # Debt to equity
    eff_debt = debt or (total_liabilities if equity else None)
    eff_equity = equity
    if eff_debt is not None and eff_equity and eff_equity > 0:
        ratios["debt_to_equity"] = round(eff_debt / eff_equity, 2)

    # Asset to equity (leverage)
    if total_assets and equity and equity > 0:
        ratios["asset_to_equity"] = round(total_assets / equity, 2)

    # Financial health rating
    score = 0
    total = 0
    if ratios.get("profit_margin_pct") is not None:
        total += 1
        if ratios["profit_margin_pct"] > 5:
            score += 1
    if ratios.get("current_ratio") is not None:
        total += 1
        if ratios["current_ratio"] >= 1.5:
            score += 1
    if ratios.get("debt_to_equity") is not None:
        total += 1
        if ratios["debt_to_equity"] <= 1.0:
            score += 1

    if total == 0:
        ratios["financial_health"] = "Insufficient Data"
    elif score / total >= 0.67:
        ratios["financial_health"] = "Healthy"
    elif score / total >= 0.34:
        ratios["financial_health"] = "Moderate"
    else:
        ratios["financial_health"] = "Needs Attention"

    # Store raw numeric values for use by later stages
    ratios["_revenue"] = revenue
    ratios["_net_income"] = net_income
    ratios["_gross_profit"] = gross_profit
    ratios["_operating_profit"] = operating_profit
    ratios["_current_assets"] = current_assets
    ratios["_current_liabilities"] = current_liabilities
    ratios["_equity"] = equity
    ratios["_debt"] = debt
    ratios["_total_assets"] = total_assets
    ratios["_total_liabilities"] = total_liabilities

    return ratios


# ═══════════════════════════════════════════════════════════════════════
# STAGE 5 — Extractive Summarization  (module9 logic inline)
# ═══════════════════════════════════════════════════════════════════════
CURRENCY_OR_PCT = re.compile(
    r"(Rs\.?\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|lakh))?"
    r"|₹\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|lakh))?"
    r"|\$\s?[\d,]+(?:\.\d+)?(?:\s?(?:Million|Billion))?"
    r"|\b\d+(?:\.\d+)?\s?%)"
)

RISK_KW   = {"risk","risks","volatility","competition","uncertain","uncertainty",
             "adverse","regulatory","decline","threat","challenge","challenges","litigation"}
PERF_KW   = {"revenue","growth","grew","profit","profitability","performance",
             "highlight","expanded","margin","segment","demand"}

ABBREVS   = ["Rs.", "Pvt.", "Ltd.", "Inc.", "Corp.", "No.", "Dr.", "Mr.", "Mrs.",
             "vs.", "etc.", "FY.", "e.g.", "i.e."]


def _protect_abbrevs(text):
    pmap = {}
    for i, a in enumerate(ABBREVS):
        tok = f"@@A{i}@@"
        pmap[tok] = a
        text = text.replace(a, tok)
    return text, pmap


def _restore_abbrevs(text, pmap):
    for tok, a in pmap.items():
        text = text.replace(tok, a)
    return text


def _segment(text: str):
    protected, pmap = _protect_abbrevs(text)
    raw = [l.strip() for l in protected.split("\n") if l.strip()]
    sentences = []
    for chunk in raw:
        for p in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", chunk):
            p = _restore_abbrevs(p.strip(), pmap)
            if p:
                sentences.append(p)
    return sentences


def _score_sentences(sentences):
    freq = Counter()
    for s in sentences:
        for w in re.findall(r"[A-Za-z]+", s.lower()):
            if w not in STOP_WORDS and len(w) > 2:
                freq[w] += 1
    scored = []
    for i, s in enumerate(sentences):
        words = [w for w in re.findall(r"[A-Za-z]+", s.lower())
                 if w not in STOP_WORDS and len(w) > 2]
        sc = sum(freq[w] for w in words) / len(words) if words else 0.0
        scored.append((i, s, sc))
    return scored


def _top_n(scored, n=3):
    ranked = sorted(scored, key=lambda x: x[2], reverse=True)[:n]
    return [s for _, s, _ in sorted(ranked, key=lambda x: x[0])]


def summarize(text: str) -> dict:
    sentences = _segment(text)
    if not sentences:
        return {
            "executive_summary": [],
            "key_financial_highlights": [],
            "risk_summary": [],
            "business_performance_summary": [],
            "management_discussion_summary": [],
        }

    scored = _score_sentences(sentences)
    # Filter out pure title fragments
    exec_cands = [(i, s, sc) for i, s, sc in scored
                  if not (s.endswith(":") or re.search(r"(Ltd\.?|Inc\.?)[\s-]", s))]
    executive = _top_n(exec_cands or scored, n=3)
    highlights = [s for s in sentences if CURRENCY_OR_PCT.search(s)][:6]
    risk   = [s for s in sentences if any(kw in s.lower() for kw in RISK_KW)][:5]
    perf   = [s for s in sentences if any(kw in s.lower() for kw in PERF_KW)][:5]

    return {
        "executive_summary": executive,
        "key_financial_highlights": highlights,
        "risk_summary": risk,
        "business_performance_summary": perf,
        "management_discussion_summary": [],
    }


# ═══════════════════════════════════════════════════════════════════════
# STAGE 6 — Per-Document RAG Index
# ═══════════════════════════════════════════════════════════════════════
def _simple_stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("es") and not word.endswith(("ses","xes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _tfidf_analyzer(text: str):
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return [_simple_stem(w) for w in words if w not in STOP_WORDS and len(w) > 2]


def _chunk_text(doc_id: str, text: str, size: int = 3):
    raw_lines = [l.strip() for l in text.split("\n") if l.strip()]
    sentences = _segment(text)
    units = raw_lines if len(sentences) < 0.5 * len(raw_lines) else sentences
    chunks = []
    for i in range(0, len(units), size):
        group = units[i:i + size]
        chunks.append({
            "chunk_id": f"{doc_id}::chunk{i // size}",
            "document": doc_id,
            "text": " ".join(group),
            "sentences": group,
        })
    return chunks


def build_rag_index(doc_id: str, text: str) -> str:
    """Build a per-document TF-IDF RAG index. Returns the index directory path."""
    if not SKLEARN_OK:
        return ""
    rag_dir = os.path.join(DATA_DIR, "rag", doc_id)
    os.makedirs(rag_dir, exist_ok=True)
    chunks = _chunk_text(doc_id, text)
    if not chunks:
        return rag_dir

    texts = [c["text"] for c in chunks]
    vectorizer = TfidfVectorizer(analyzer=_tfidf_analyzer, max_features=3000)
    chunk_vectors = vectorizer.fit_transform(texts)

    joblib.dump(vectorizer, os.path.join(rag_dir, "tfidf_vectorizer.joblib"))
    joblib.dump(chunk_vectors, os.path.join(rag_dir, "chunk_vectors.joblib"))
    with open(os.path.join(rag_dir, "chunks.json"), "w") as f:
        json.dump(chunks, f)
    return rag_dir


def ask_question_for_doc(doc_id: str, question: str, top_k: int = 3) -> dict:
    """RAG Q&A on a single document's index."""
    rag_dir = os.path.join(DATA_DIR, "rag", doc_id)
    vec_path = os.path.join(rag_dir, "tfidf_vectorizer.joblib")
    if not os.path.exists(vec_path):
        return {"answer": "No RAG index found for this document. It may still be processing.",
                "source_document": doc_id, "retrieved_chunks": []}
    try:
        vectorizer = joblib.load(vec_path)
        chunk_vectors = joblib.load(os.path.join(rag_dir, "chunk_vectors.joblib"))
        with open(os.path.join(rag_dir, "chunks.json")) as f:
            chunks = json.load(f)

        query_vec = vectorizer.transform([question])
        scores = cosine_similarity(query_vec, chunk_vectors).flatten()
        top_idx = np.argsort(scores)[::-1][:top_k]
        retrieved = [
            {**chunks[i], "score": round(float(scores[i]), 4)}
            for i in top_idx if scores[i] > 0
        ]

        if not retrieved:
            return {"answer": "I could not find this information in the uploaded document.",
                    "source_document": doc_id, "retrieved_chunks": []}

        # Extract best answer sentence
        q_words = set(_simple_stem(w) for w in re.findall(r"[a-z]+", question.lower()))
        best_sentence, best_score = None, -1
        best_chunk = retrieved[0]
        for chunk in retrieved[:2]:
            for sent in (chunk.get("sentences") or _segment(chunk["text"])):
                s_words = set(_simple_stem(w) for w in re.findall(r"[a-z]+", sent.lower()))
                overlap = len(q_words & s_words)
                has_val = bool(CURRENCY_OR_PCT.search(sent))
                sc = overlap + (2 if has_val else 0)
                if sc > best_score:
                    best_score, best_sentence, best_chunk = sc, sent, chunk

        return {
            "question": question,
            "answer": best_sentence or "Relevant content found but no specific value could be pinpointed.",
            "source_document": best_chunk.get("document", doc_id),
            "retrieved_chunks": [
                {"chunk_id": c["chunk_id"], "document": c["document"],
                 "score": c["score"], "text": c["text"]}
                for c in retrieved
            ],
        }
    except Exception as e:
        return {"answer": f"Q&A error: {e}", "source_document": doc_id, "retrieved_chunks": []}


# ═══════════════════════════════════════════════════════════════════════
# STAGE 7 — Anomaly Detection (rule-based on extracted metrics)
# ═══════════════════════════════════════════════════════════════════════
def detect_anomalies(raw_values: dict, ratios: dict) -> list:
    """
    Rule-based anomaly checks on the extracted financial figures.
    Returns list of {type, message, severity} dicts.
    """
    anomalies = []

    def get_num(key):
        return ratios.get(f"_{key}")

    net_income = get_num("net_income")
    revenue = get_num("revenue")
    gross_profit = get_num("gross_profit")
    debt = get_num("debt")
    equity = get_num("equity")
    current_ratio = ratios.get("current_ratio")
    de_ratio = ratios.get("debt_to_equity")
    profit_margin = ratios.get("profit_margin_pct")
    gross_margin = ratios.get("gross_margin_pct")

    # 1. Negative net income
    if net_income is not None and net_income < 0:
        anomalies.append({
            "type": "Negative Net Income",
            "message": f"Net income is negative ({raw_values.get('Net Income', 'N/A')}). Company is operating at a loss.",
            "severity": "high"
        })

    # 2. Very low profit margin
    if profit_margin is not None and 0 < profit_margin < 3:
        anomalies.append({
            "type": "Very Low Profit Margin",
            "message": f"Profit margin is only {profit_margin:.1f}% — extremely thin, leaving little buffer.",
            "severity": "medium"
        })

    # 3. High debt-to-equity
    if de_ratio is not None and de_ratio > 2.0:
        anomalies.append({
            "type": "High Leverage",
            "message": f"Debt-to-equity ratio is {de_ratio:.2f}x — significantly above the 2.0 benchmark.",
            "severity": "high"
        })
    elif de_ratio is not None and de_ratio > 1.5:
        anomalies.append({
            "type": "Elevated Leverage",
            "message": f"Debt-to-equity ratio of {de_ratio:.2f}x is above the commonly used 1.0 benchmark.",
            "severity": "medium"
        })

    # 4. Low current ratio (liquidity risk)
    if current_ratio is not None and current_ratio < 1.0:
        anomalies.append({
            "type": "Liquidity Risk",
            "message": f"Current ratio of {current_ratio:.2f}x is below 1.0 — current liabilities exceed current assets.",
            "severity": "high"
        })
    elif current_ratio is not None and current_ratio < 1.5:
        anomalies.append({
            "type": "Low Liquidity Buffer",
            "message": f"Current ratio of {current_ratio:.2f}x is below the 1.5 benchmark.",
            "severity": "medium"
        })

    # 5. Gross profit less than 20%
    if gross_margin is not None and gross_margin < 20:
        anomalies.append({
            "type": "Low Gross Margin",
            "message": f"Gross margin of {gross_margin:.1f}% may indicate high cost of goods sold.",
            "severity": "medium"
        })

    # 6. Debt exceeds equity substantially
    if debt is not None and equity is not None and equity > 0 and debt > equity * 3:
        anomalies.append({
            "type": "Debt Dominates Equity",
            "message": "Total debt is more than 3× total equity — aggressive leverage.",
            "severity": "high"
        })

    # 7. No key metrics found at all
    if not raw_values:
        anomalies.append({
            "type": "No Financial Data",
            "message": "No standard financial metrics could be extracted from this document.",
            "severity": "info"
        })

    return anomalies


# ═══════════════════════════════════════════════════════════════════════
# STAGE 8 — AI Insights (rule-based from extracted data)
# ═══════════════════════════════════════════════════════════════════════
def generate_insights(raw_values: dict, ratios: dict, anomalies: list) -> dict:
    """Generate 3–7 human-readable insight bullets from extracted data."""
    insights = []
    risk_points = 0
    risk_cap = 0

    def add(status, text, weight=1):
        nonlocal risk_points, risk_cap
        insights.append({"status": status, "text": text})
        risk_cap += weight
        if status == "warning":
            risk_points += weight

    def get_num(key):
        return ratios.get(f"_{key}")

    revenue = get_num("revenue")
    net_income = get_num("net_income")
    gross_profit = get_num("gross_profit")
    current_ratio = ratios.get("current_ratio")
    de_ratio = ratios.get("debt_to_equity")
    profit_margin = ratios.get("profit_margin_pct")
    gross_margin = ratios.get("gross_margin_pct")
    financial_health = ratios.get("financial_health", "Insufficient Data")

    # Revenue presence
    if revenue is not None:
        add("positive", f"Revenue figure extracted: {raw_values.get('Revenue', 'N/A')}. Document contains income statement data.", weight=1)

    # Profitability
    if profit_margin is not None:
        if profit_margin > 15:
            add("positive", f"Strong net profit margin of {profit_margin:.1f}% — company retains a healthy portion of revenue.", weight=2)
        elif profit_margin > 5:
            add("positive", f"Moderate net profit margin of {profit_margin:.1f}%.", weight=1)
        elif profit_margin > 0:
            add("warning", f"Thin profit margin of {profit_margin:.1f}% — limited buffer against cost pressures.", weight=2)
        else:
            add("warning", f"Negative profit margin ({profit_margin:.1f}%) — company is operating at a loss.", weight=3)

    # Gross margin
    if gross_margin is not None and profit_margin != gross_margin:
        if gross_margin > 40:
            add("positive", f"High gross margin of {gross_margin:.1f}% indicates strong pricing power or low COGS.", weight=1)
        elif gross_margin < 20:
            add("warning", f"Low gross margin of {gross_margin:.1f}% — cost of goods sold is consuming most revenue.", weight=2)

    # Liquidity
    if current_ratio is not None:
        if current_ratio >= 2.0:
            add("positive", f"Strong liquidity: current ratio of {current_ratio:.2f}x comfortably covers short-term obligations.", weight=1)
        elif current_ratio >= 1.5:
            add("positive", f"Adequate liquidity: current ratio of {current_ratio:.2f}x.", weight=1)
        elif current_ratio >= 1.0:
            add("warning", f"Liquidity is tight: current ratio of {current_ratio:.2f}x is below the 1.5 benchmark.", weight=2)
        else:
            add("warning", f"Liquidity concern: current ratio of {current_ratio:.2f}x — liabilities exceed assets.", weight=3)

    # Leverage
    if de_ratio is not None:
        if de_ratio <= 0.5:
            add("positive", f"Conservative leverage: D/E ratio of {de_ratio:.2f}x — low debt dependency.", weight=1)
        elif de_ratio <= 1.0:
            add("positive", f"Manageable leverage: D/E ratio of {de_ratio:.2f}x within benchmark.", weight=1)
        elif de_ratio <= 2.0:
            add("warning", f"Elevated leverage: D/E ratio of {de_ratio:.2f}x — debt exceeds equity.", weight=2)
        else:
            add("warning", f"High leverage risk: D/E ratio of {de_ratio:.2f}x — significant debt relative to equity.", weight=3)

    # Anomaly count
    high_anomalies = [a for a in anomalies if a["severity"] == "high"]
    if high_anomalies:
        add("warning", f"{len(high_anomalies)} high-severity financial pattern(s) detected — manual review recommended.", weight=2)

    # No data fallback
    if not insights:
        insights.append({
            "status": "not_computable",
            "text": "Insufficient financial data extracted from this document to generate meaningful insights."
        })

    # Overall risk
    risk_ratio = risk_points / risk_cap if risk_cap else 0
    overall_risk = "High" if risk_ratio >= 0.5 else "Medium" if risk_ratio >= 0.25 else "Low"

    return {
        "insights": insights,
        "overall_risk": overall_risk,
        "risk_ratio": round(risk_ratio, 3),
        "financial_health": financial_health,
    }


# ═══════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════
def run(doc_id: str, file_path: str, original_filename: str, user_id: int | None = None) -> dict:
    """
    Run the complete processing pipeline for one document.

    Returns a dict with keys:
        document_id, filename, status, error,
        extraction, classification, metrics, ratios,
        summary, anomalies, insights
    """
    result = {
        "document_id": doc_id,
        "filename": original_filename,
        "status": "processing",
        "error": None,
        "processed_at": datetime.now().isoformat(),
        "user_id": user_id,
    }

    try:
        # ── Stage 1: Text Extraction ──────────────────────────────
        print(f"[pipeline] [{doc_id}] Stage 1: extracting text...")
        extraction = extract_text(file_path)
        result["extraction"] = extraction
        text = extraction["text"]

        if not text or extraction.get("error"):
            result["status"] = "failed"
            result["error"] = extraction.get("error", "Text extraction produced no content.")
            _persist(doc_id, result, user_id)
            return result

        # ── Stage 2: Classification ───────────────────────────────
        print(f"[pipeline] [{doc_id}] Stage 2: classifying...")
        classification = classify_document(text)
        result["classification"] = classification

        # ── Stage 3: Metric Extraction ────────────────────────────
        print(f"[pipeline] [{doc_id}] Stage 3: extracting metrics...")
        metric_result = extract_metrics(text)
        result["metrics"] = metric_result

        # ── Stage 4: Ratio Computation ────────────────────────────
        print(f"[pipeline] [{doc_id}] Stage 4: computing ratios...")
        ratios = compute_ratios(metric_result["raw_values"])
        result["ratios"] = ratios

        # ── Stage 5: Summarization ────────────────────────────────
        print(f"[pipeline] [{doc_id}] Stage 5: summarizing...")
        summary = summarize(text)
        result["summary"] = summary

        # ── Stage 6: RAG Index ────────────────────────────────────
        print(f"[pipeline] [{doc_id}] Stage 6: building RAG index...")
        rag_dir = build_rag_index(doc_id, text)
        result["rag_dir"] = rag_dir

        # ── Stage 7: Anomaly Detection ────────────────────────────
        print(f"[pipeline] [{doc_id}] Stage 7: detecting anomalies...")
        anomalies = detect_anomalies(metric_result["raw_values"], ratios)
        result["anomalies"] = anomalies

        # ── Stage 8: Insights ─────────────────────────────────────
        print(f"[pipeline] [{doc_id}] Stage 8: generating insights...")
        insights = generate_insights(metric_result["raw_values"], ratios, anomalies)
        result["insights"] = insights

        result["status"] = "completed"
        print(f"[pipeline] [{doc_id}] [OK] Processing complete.")

    except Exception as e:
        result["status"] = "failed"
        result["error"] = str(e)
        result["traceback"] = traceback.format_exc()
        print(f"[pipeline] [{doc_id}] [ERROR] Pipeline error: {e}")

    # ── Persist to DB ─────────────────────────────────────────────
    _persist(doc_id, result, user_id)
    return result


def _persist(doc_id: str, result: dict, user_id: int | None = None):
    """Save processing result to database with user_id."""
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        import database as db
        db.save_doc_result(doc_id, result, user_id=user_id)
    except Exception as e:
        print(f"[pipeline] DB persist error: {e}")
