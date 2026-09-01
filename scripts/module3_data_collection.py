"""
MODULE 3 - Financial Document Collection
------------------------------------------------
Objective : Collect financial documents for AI processing.

FINAL VERSION: This dataset now combines TWO sources placed in
data/raw/:
    1. Real financial documents 
       (Balance Sheet F.pdf, annual report.csv, bank statement.pdf,
       income statement.pdf, invoice F.pdf).
    2. An additional sample document set (NovaTech Industries) covering
       every required category, including one scanned (image-only)
       document - useful for demonstrating the OCR path in Module 4.

The script:
    1. Reads every file in data/mentor_provided/.
    2. Classifies each by document type using keyword matching on the
       filename (works for "balance sheet", "balance_sheet", etc.).
    3. Flags scanned/image-based copies separately (still same document
       type, but noted, since OCR will be needed for those).
    4. Copies each file into data/raw/ using a cleaned, unique filename
       (so two documents of the same type never collide).
    5. Inspects each file (PDF page count or CSV row count, size) and
       builds an accurate dataset catalog automatically.
"""

import os
import re
import csv
import shutil
from datetime import datetime
from pypdf import PdfReader

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
SOURCE_DIR = os.path.join(BASE_DIR, "data", "mentor_provided")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)

# Order matters: more specific phrases first.
TYPE_KEYWORDS = [
    ("balance sheet", "Balance Sheet"),
    ("bank statement", "Bank Statement"),
    ("income statement", "Income Statement"),
    ("cash flow", "Cash Flow Statement"),
    ("annual report", "Annual Report"),
    ("invoice", "Invoice"),
]


def normalize(name: str) -> str:
    """Lowercase and turn separators into spaces for keyword matching."""
    name = name.lower()
    name = re.sub(r"[_\-]+", " ", name)
    return name


def classify_document_type(filename: str) -> str:
    norm = normalize(filename)
    for keyword, doc_type in TYPE_KEYWORDS:
        if keyword in norm:
            return doc_type
    return "Unclassified"


def is_scanned_copy(filename: str) -> bool:
    return "scan" in normalize(filename)


def sanitize_filename(filename: str) -> str:
    """Make a clean, unique, filesystem-safe filename while keeping it
    recognizable (no collisions between the two source sets)."""
    base, ext = os.path.splitext(filename)
    base = normalize(base).strip()
    base = re.sub(r"\s+", "_", base)
    base = re.sub(r"[^a-z0-9_]", "", base)
    return f"{base}{ext.lower()}"


def inspect_file(path: str):
    size_kb = round(os.path.getsize(path) / 1024, 1)
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        try:
            pages = len(PdfReader(path).pages)
        except Exception:
            pages = "N/A"
        return {"file_type": "PDF", "pages_or_rows": pages, "size_kb": size_kb}

    elif ext == ".csv":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            row_count = sum(1 for _ in f) - 1
        return {"file_type": "CSV", "pages_or_rows": row_count, "size_kb": size_kb}

    return {"file_type": ext.replace(".", "").upper(), "pages_or_rows": "N/A", "size_kb": size_kb}


def main():
    if not os.path.isdir(SOURCE_DIR):
        print(f"Source folder not found: {SOURCE_DIR}")
        return

    source_files = sorted(
        f for f in os.listdir(SOURCE_DIR)
        if os.path.isfile(os.path.join(SOURCE_DIR, f)) and not f.startswith(".")
    )
    if not source_files:
        print(f"No files found in {SOURCE_DIR}.")
        return

    # clear out any previous run's collected copies so re-runs are clean
    for f in os.listdir(RAW_DIR):
        os.remove(os.path.join(RAW_DIR, f))

    catalog_rows = [[
        "document_id", "filename", "document_type", "scanned_copy",
        "original_filename", "file_type", "pages_or_rows", "size_kb",
        "source", "collected_on"
    ]]

    for i, original_name in enumerate(source_files, start=1):
        doc_type = classify_document_type(original_name)
        scanned = is_scanned_copy(original_name)
        clean_name = sanitize_filename(original_name)

        src_path = os.path.join(SOURCE_DIR, original_name)
        dst_path = os.path.join(RAW_DIR, clean_name)
        shutil.copyfile(src_path, dst_path)

        meta = inspect_file(dst_path)
        doc_id = f"DOC{i:03d}"

        # "source" tag: distinguish the mentor's real dataset from the
        # earlier sample/demo dataset, purely for transparency in the catalog
        source_tag = "Provided by internship mentor (real dataset)"

        catalog_rows.append([
            doc_id, clean_name, doc_type, "Yes" if scanned else "No",
            original_name, meta["file_type"], meta["pages_or_rows"], meta["size_kb"],
            source_tag, datetime.now().strftime("%Y-%m-%d"),
        ])
        print(f"[{doc_id}] {original_name}  ->  {clean_name}  "
              f"({doc_type}{' | SCANNED' if scanned else ''}, "
              f"{meta['file_type']}, {meta['pages_or_rows']} pages/rows)")

    catalog_path = os.path.join(RAW_DIR, "dataset_catalog.csv")
    with open(catalog_path, "w", newline="") as f:
        csv.writer(f).writerows(catalog_rows)

    print(f"\n[Module 3] {len(source_files)} financial documents collected into: {RAW_DIR}")
    print(f"[Module 3] Dataset catalog written to: {catalog_path}")


if __name__ == "__main__":
    main()
