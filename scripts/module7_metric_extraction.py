"""
MODULE 7 - Financial Information & Metric Extraction
------------------------------------------------------
Objective : Automatically extract important financial information.

Metrics (per project brief):
    Revenue, Gross Profit, Operating Profit, Net Income, Assets,
    Liabilities, Equity, EPS, Debt, Cash Flow

Example (per project brief):
    Input : "The company generated revenue of Rs. 850 crore in FY2026."
    Output: Metric: Revenue | Value: Rs. 850 crore | Year: FY2026

Technologies (per project brief): NLP, Named Entity Recognition,
Regular Expressions, Transformers.

TOOLING NOTE (same transparency pattern as Modules 5 & 6):
"Transformers" (e.g. a HuggingFace financial-NER model) would need
pretrained weights downloaded from the internet, which is not
available in this environment. Instead, this pipeline builds on the
NLP + rule-based NER work already done in Module 5 (cleaned text,
sentence segmentation, currency/date/percentage extraction) and adds
a targeted Regular-Expression layer that recognizes each of the 10
required metric labels and pairs them with the nearest currency value
and the document's reporting year/period - which is exactly the
(Metric, Value, Year) structure the brief's example asks for.

Workflow:
    Cleaned Document Text (Module 4/5)
        -> locate known metric labels (Revenue, Net Income, EPS, ...)
        -> pair each with the currency value on the same line
        -> attach the document's reporting year/period
        -> Structured (Metric, Value, Year) record

Input : data/processed/*.txt        (cleaned PDF text from Module 4)
Output: data/metrics_extracted/<name>.json   (per-document structured metrics)
        data/metrics_extracted/financial_metrics_dataset.csv  (master dataset - the deliverable)
"""

import os
import re
import csv
import json
from collections import Counter

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
OUT_DIR = os.path.join(BASE_DIR, "data", "metrics_extracted")
os.makedirs(OUT_DIR, exist_ok=True)

# Canonical metric -> ordered list of label patterns to look for
# (more specific labels first so e.g. "Net Income" isn't shadowed by
# a looser pattern).
METRIC_LABELS = {
    "Revenue": [r"Revenue"],
    "Gross Profit": [r"Gross Profit"],
    "Operating Profit": [r"Operating Profit", r"Operating Income"],
    "Net Income": [r"Net Income", r"Net Profit"],
    "Assets": [r"Total Assets"],
    "Liabilities": [r"Total Liabilities(?! and Equity)"],
    "Equity": [r"Total Equity"],
    "EPS": [r"Earnings Per Share \(EPS\)", r"Earnings Per Share", r"\bEPS\b"],
    "Debt": [r"Long-term Debt", r"Short-term Borrowings", r"Total Debt"],
    "Cash Flow": [r"Net Cash from Operating Activities",
                  r"Net Increase in Cash", r"Cash Flow"],
}

CURRENCY_PATTERN = re.compile(
    r"(Rs\.?\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|Crore|lakh|Lakh))?"
    r"|\u20B9\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|Crore|lakh|Lakh))?"
    r"|\$\s?[\d,]+(?:\.\d+)?\s?(?:Million|Billion|million|billion)?)"
)

FY_PATTERN = re.compile(r"\bFY ?(\d{4})\b")
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


def detect_document_year(text: str) -> str:
    """Best-effort single reporting year/period for the whole document
    (reasonable for the single-period statements in this dataset)."""
    fy_matches = FY_PATTERN.findall(text)
    if fy_matches:
        most_common = Counter(fy_matches).most_common(1)[0][0]
        return f"FY{most_common}"
    year_matches = YEAR_PATTERN.findall(text)
    if year_matches:
        return Counter(year_matches).most_common(1)[0][0]
    return "Unknown"


def extract_metrics_from_line(line: str):
    """Return list of (canonical_metric, label_matched, value) found
    on this single line."""
    found = []
    currency_match = CURRENCY_PATTERN.search(line)
    if not currency_match:
        return found  # no value on this line -> nothing to pair

    value = currency_match.group(0).strip()
    for canonical_metric, patterns in METRIC_LABELS.items():
        for pattern in patterns:
            label_match = re.search(pattern, line, re.IGNORECASE)
            if label_match:
                found.append((canonical_metric, label_match.group(0), value))
                break  # one label match per metric per line is enough
    return found


def process_document(txt_path: str) -> dict:
    filename = os.path.basename(txt_path)
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    doc_year = detect_document_year(text)
    records = []
    seen = set()  # avoid duplicate (metric, value) pairs from repeated lines

    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        for canonical_metric, label_matched, value in extract_metrics_from_line(line):
            key = (canonical_metric, value)
            if key in seen:
                continue
            seen.add(key)
            records.append({
                "metric": canonical_metric,
                "label_matched": label_matched,
                "value": value,
                "year": doc_year,
                "source_line": line,
            })

    return {
        "filename": filename,
        "document_year": doc_year,
        "metrics_found": len(records),
        "metrics": records,
    }


def main():
    txt_files = sorted(f for f in os.listdir(PROCESSED_DIR) if f.lower().endswith(".txt"))
    if not txt_files:
        print(f"No .txt files found in {PROCESSED_DIR}. Run module4_document_processing.py first.")
        return

    master_rows = [["document", "metric", "value", "year", "source_line"]]
    summary_rows = [["filename", "document_year", "metrics_found"]]

    for filename in txt_files:
        path = os.path.join(PROCESSED_DIR, filename)
        result = process_document(path)

        out_name = os.path.splitext(filename)[0] + ".json"
        with open(os.path.join(OUT_DIR, out_name), "w") as jf:
            json.dump(result, jf, indent=2)

        for rec in result["metrics"]:
            master_rows.append([
                filename, rec["metric"], rec["value"], rec["year"], rec["source_line"]
            ])
        summary_rows.append([filename, result["document_year"], result["metrics_found"]])

        print(f"[OK] {filename} -> {result['metrics_found']} metrics found "
              f"(year: {result['document_year']})")

    master_path = os.path.join(OUT_DIR, "financial_metrics_dataset.csv")
    with open(master_path, "w", newline="") as f:
        csv.writer(f).writerows(master_rows)

    summary_path = os.path.join(OUT_DIR, "extraction_summary.csv")
    with open(summary_path, "w", newline="") as f:
        csv.writer(f).writerows(summary_rows)

    total_metrics = len(master_rows) - 1
    print(f"\n[Module 7] Processed {len(txt_files)} documents, "
          f"extracted {total_metrics} structured metric records.")
    print(f"[Module 7] Structured financial metrics dataset: {master_path}")
    print(f"[Module 7] Per-document summary: {summary_path}")


if __name__ == "__main__":
    main()
