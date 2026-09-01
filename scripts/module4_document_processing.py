"""
MODULE 4 - Document Processing & OCR
------------------------------------------------
Objective : Extract usable text/data from financial documents.

Workflow (per project brief):
    PDF / Image -> OCR / PDF Parser -> Raw Text -> Clean Text -> Structured Document

UPDATE: now processes the REAL mentor-provided dataset, which includes
both PDFs and one CSV (annual_report.csv). Handling added for both:

  - PDF documents:
        1. Try direct text-layer extraction per page (pdfplumber).
        2. If a page has negligible extractable text, fall back to
           OCR for that specific page (pdftoppm -> pytesseract).
           (Per-page fallback, not whole-document, because a real
           document can freely mix normal pages, blank pages, and
           scanned/image pages.)
        3. Clean the combined text.

  - CSV documents (already-structured tabular data, e.g. annual_report.csv):
        1. Read directly - no OCR/parsing needed, it's already text.
        2. Record column names, row count, and a sample of rows.
        3. "Clean" = drop fully empty rows, strip whitespace from values.

Every processed document gets:
    data/processed/<name>.json   - structured metadata + content
    data/processed/<name>.txt    - plain text (PDFs only)
    data/processed/processing_report.csv - summary across all documents
"""

import os
import re
import csv
import json
import subprocess
import tempfile
import shutil
from datetime import datetime

import pdfplumber
from pypdf import PdfReader
import pytesseract
from PIL import Image

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

BLANK_PAGE_CHAR_THRESHOLD = 20  # below this -> treat page as needing OCR


def clean_text(raw_text: str) -> str:
    text = raw_text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def ocr_single_page(pdf_path: str, page_number: int) -> str:
    """Render one PDF page (1-indexed) to an image and OCR it."""
    tmp_dir = tempfile.mkdtemp()
    try:
        prefix = os.path.join(tmp_dir, "page")
        subprocess.run(
            ["pdftoppm", "-jpeg", "-r", "200", "-f", str(page_number),
             "-l", str(page_number), pdf_path, prefix],
            check=True, capture_output=True,
        )
        images = [f for f in os.listdir(tmp_dir) if f.lower().endswith(".jpg")]
        if not images:
            return ""
        return pytesseract.image_to_string(Image.open(os.path.join(tmp_dir, images[0])))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def process_pdf(pdf_path: str) -> dict:
    filename = os.path.basename(pdf_path)
    num_pages = len(PdfReader(pdf_path).pages)

    page_texts = []
    methods_used = set()
    blank_pages = 0

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if len(text.strip()) < BLANK_PAGE_CHAR_THRESHOLD:
                # try OCR for this specific page (handles scanned pages
                # mixed into an otherwise digital PDF)
                ocr_text = ocr_single_page(pdf_path, i)
                if len(ocr_text.strip()) >= BLANK_PAGE_CHAR_THRESHOLD:
                    page_texts.append(ocr_text)
                    methods_used.add("ocr_tesseract")
                else:
                    # genuinely blank / empty page - keep as empty, don't fabricate
                    page_texts.append("")
                    blank_pages += 1
            else:
                page_texts.append(text)
                methods_used.add("pdf_text_extraction")

    combined_raw = "\n".join(page_texts)
    cleaned = clean_text(combined_raw)

    if not methods_used:
        methods_used.add("none_extracted")

    return {
        "filename": filename,
        "file_type": "PDF",
        "num_pages": num_pages,
        "blank_pages": blank_pages,
        "extraction_method": "+".join(sorted(methods_used)),
        "raw_char_count": len(combined_raw),
        "cleaned_char_count": len(cleaned),
        "word_count": len(cleaned.split()),
        "processed_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "text": cleaned,
    }


def process_csv(csv_path: str) -> dict:
    filename = os.path.basename(csv_path)
    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        rows = list(reader)

    header, data_rows = (rows[0], rows[1:]) if rows else ([], [])

    # Clean: strip whitespace, drop fully-empty rows
    cleaned_rows = []
    for row in data_rows:
        row = [cell.strip() for cell in row]
        if any(cell for cell in row):
            cleaned_rows.append(row)

    sample_rows = cleaned_rows[:5]

    return {
        "filename": filename,
        "file_type": "CSV",
        "num_columns": len(header),
        "columns": header,
        "row_count_raw": len(data_rows),
        "row_count_cleaned": len(cleaned_rows),
        "dropped_empty_rows": len(data_rows) - len(cleaned_rows),
        "sample_rows": sample_rows,
        "processed_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def main():
    files = sorted(f for f in os.listdir(RAW_DIR) if not f.startswith("."))
    files = [f for f in files if f != "dataset_catalog.csv"]

    if not files:
        print(f"No documents found in {RAW_DIR}. Run module3_data_collection.py first.")
        return

    report_rows = [["filename", "file_type", "pages_or_rows",
                     "extraction_method", "word_or_row_count", "status"]]

    for filename in files:
        path = os.path.join(RAW_DIR, filename)
        ext = os.path.splitext(filename)[1].lower()
        try:
            if ext == ".pdf":
                result = process_pdf(path)
                out_base = os.path.splitext(filename)[0]
                with open(os.path.join(PROCESSED_DIR, out_base + ".json"), "w") as jf:
                    json.dump(result, jf, indent=2)
                with open(os.path.join(PROCESSED_DIR, out_base + ".txt"), "w") as tf:
                    tf.write(result["text"])
                report_rows.append([filename, "PDF", result["num_pages"],
                                     result["extraction_method"],
                                     result["word_count"], "SUCCESS"])
                print(f"[OK] {filename} -> {result['extraction_method']} "
                      f"({result['word_count']} words, {result['blank_pages']} blank pages)")

            elif ext == ".csv":
                result = process_csv(path)
                out_base = os.path.splitext(filename)[0]
                with open(os.path.join(PROCESSED_DIR, out_base + ".json"), "w") as jf:
                    json.dump(result, jf, indent=2)
                report_rows.append([filename, "CSV", result["row_count_cleaned"],
                                     "direct_csv_read",
                                     result["row_count_cleaned"], "SUCCESS"])
                print(f"[OK] {filename} -> direct_csv_read "
                      f"({result['row_count_cleaned']} rows, "
                      f"{result['dropped_empty_rows']} empty rows dropped)")

            else:
                report_rows.append([filename, ext.upper(), "-", "-", "-", "SKIPPED (unsupported type)"])
                print(f"[SKIP] {filename}: unsupported file type")

        except Exception as e:
            report_rows.append([filename, ext.upper(), "-", "-", "-", f"FAILED: {e}"])
            print(f"[FAILED] {filename}: {e}")

    report_path = os.path.join(PROCESSED_DIR, "processing_report.csv")
    with open(report_path, "w", newline="") as f:
        csv.writer(f).writerows(report_rows)

    print(f"\n[Module 4] Processed {len(files)} documents.")
    print(f"[Module 4] Structured output saved to: {PROCESSED_DIR}")
    print(f"[Module 4] Processing report: {report_path}")


if __name__ == "__main__":
    main()
