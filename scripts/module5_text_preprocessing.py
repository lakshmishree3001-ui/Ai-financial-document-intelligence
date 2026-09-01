"""
MODULE 5 - Financial Text Preprocessing & Feature Extraction
------------------------------------------------------------
Objective : Prepare financial text for NLP models.

Tasks implemented (per project brief):
    - Remove unnecessary characters
    - Tokenization
    - Stop-word removal
    - Sentence segmentation
    - Named entity recognition (rule-based)
    - Financial terminology extraction

Extracts:
    - Company names
    - Dates
    - Currency
    - Financial metrics
    - Percentages
    - Business segments

IMPORTANT NOTE ON TOOLING:
This environment has no internet access, so heavyweight NLP libraries
that need a network download at install/model-load time (spaCy's
en_core_web_sm, NLTK's punkt/stopwords corpora) are not available.
Instead, this pipeline uses:
    - scikit-learn's built-in ENGLISH_STOP_WORDS list for stop-word
      removal (no download required, ships with the library).
    - A regex-based tokenizer and sentence segmenter.
    - A rule-based ("pattern matching") named-entity/financial-term
      extractor tuned to financial documents (currency formats, date
      formats, percentage formats, common financial statement line
      items, company legal suffixes, and "<x> segment(s)" phrases).
This is a legitimate, well-established fallback approach for financial
NLP preprocessing when transformer/spaCy models aren't available, and
keeps the whole pipeline dependency-light and fully offline.

Input : data/processed/*.txt   (plain cleaned text produced by Module 4)
Output: data/nlp_processed/<name>.json  (tokens, sentences, entities)
        data/nlp_processed/nlp_processing_report.csv (summary)

Note: annual_report.csv is NOT processed here. It is already
structured tabular data (rows/columns), not free text - so free-text
NLP steps like tokenization/NER do not apply to it. It was already
handled correctly in Module 4 as a direct CSV read.
"""

import os
import re
import csv
import json
from datetime import datetime

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
NLP_DIR = os.path.join(BASE_DIR, "data", "nlp_processed")
os.makedirs(NLP_DIR, exist_ok=True)

STOP_WORDS = set(ENGLISH_STOP_WORDS)

# Abbreviations whose "." must NOT be treated as a sentence boundary
ABBREVIATIONS = ["Rs.", "Pvt.", "Ltd.", "Inc.", "Corp.", "No.", "Dr.", "Mr.",
                  "Mrs.", "vs.", "etc.", "FY.", "e.g.", "i.e."]

FINANCIAL_METRIC_KEYWORDS = [
    "Revenue", "Net Income", "Net Profit", "Gross Profit", "Operating Profit",
    "Operating Expenses", "Total Operating Expenses", "EPS", "Earnings Per Share",
    "Total Assets", "Total Liabilities", "Total Equity", "Total Liabilities and Equity",
    "Cash and Cash Equivalents", "Accounts Receivable", "Accounts Payable",
    "Inventory", "Net Cash from Operating Activities", "Net Cash used in Investing Activities",
    "Net Cash used in Financing Activities", "Cost of Goods Sold", "Tax Expense",
    "Interest Expense", "Dividends Paid", "Depreciation & Amortization",
    "Short-term Borrowings", "Long-term Debt", "Share Capital", "Retained Earnings",
    "Subtotal", "GST", "Total Amount Due", "Closing Balance", "Opening Balance",
]

COMPANY_SUFFIX_PATTERN = re.compile(
    r"\b([A-Z][A-Za-z&]*(?:[ ]+[A-Z][A-Za-z&]*){0,4}[ ]+"
    r"(?:Pvt\.?[ ]*Ltd\.?|Ltd\.?|Inc\.?|Corp\.?|LLC|Industries|Corporation))\b"
)

DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}-[A-Za-z]{3,9}-\d{4}\b"),        # 12-Jun-2026
    re.compile(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b"),     # 31 March 2026
    re.compile(r"\bFY ?\d{4}\b"),                            # FY2026
]

CURRENCY_PATTERNS = [
    re.compile(r"Rs\.?\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|Crore|lakh|Lakh))?"),
    re.compile(r"\$\s?[\d,]+(?:\.\d+)?\s?(?:Million|Billion|million|billion)?"),
]

PERCENTAGE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s?%")

SEGMENT_PATTERN = re.compile(
    r"((?:[A-Za-z]+[ ]+){0,4})segments?\b", re.IGNORECASE
)


def remove_unnecessary_characters(text: str) -> str:
    """Strip PDF/OCR artifacts and normalize whitespace/punctuation noise."""
    text = re.sub(r"\(cid:\d+\)", " ", text)     # PDF font-encoding tab artifacts
    text = re.sub(r"#{3,}", " ", text)            # spreadsheet-overflow artifacts (Excel ####)
    text = re.sub(r"\.{3,}", " ", text)           # leader dots ("....")
    text = re.sub(r"[^\x20-\x7E\n]", " ", text)   # non-printable / non-ASCII noise
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return text.strip()


def protect_abbreviations(text: str):
    placeholder_map = {}
    for i, abbr in enumerate(ABBREVIATIONS):
        token = f"@@ABBR{i}@@"
        placeholder_map[token] = abbr
        text = text.replace(abbr, token)
    return text, placeholder_map


def restore_abbreviations(text: str, placeholder_map: dict) -> str:
    for token, abbr in placeholder_map.items():
        text = text.replace(token, abbr)
    return text


def join_wrapped_lines(text: str):
    """Merge PDF-wrapped lines back into paragraph-level chunks.

    These documents often have no blank lines between paragraphs at
    all (each wrapped line is just a bare newline), so splitting on
    blank lines alone under-merges. Instead: a line is treated as a
    continuation of the previous one unless the previous line already
    ended with sentence-ending punctuation, or the new line is a
    bullet point (kept as its own unit).
    """
    chunks = []
    buffer = ""
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            if buffer:
                chunks.append(buffer)
                buffer = ""
            continue
        if line.startswith(("-", "*", "\u2022")):
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.append(line)
            continue
        if not buffer:
            buffer = line
        elif buffer.rstrip().endswith((".", "!", "?", ":")):
            chunks.append(buffer)
            buffer = line
        else:
            buffer = buffer + " " + line
    if buffer:
        chunks.append(buffer)
    return chunks


def segment_sentences(text: str):
    """Paragraph-aware sentence segmentation: PDF-wrapped lines are
    first merged into paragraph-level chunks (see join_wrapped_lines),
    then each chunk is split on sentence-ending punctuation, so a
    prose sentence wrapped across two PDF lines isn't cut in half."""
    protected, pmap = protect_abbreviations(text)
    chunks = join_wrapped_lines(protected)

    sentences = []
    for chunk in chunks:
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", chunk)
        for p in parts:
            p = restore_abbreviations(p.strip(), pmap)
            if p:
                sentences.append(p)
    return sentences


def tokenize(text: str):
    """Word-level tokenizer: words and standalone numbers."""
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+(?:[.,]\d+)*", text)


def remove_stopwords(tokens):
    return [t for t in tokens if t.lower() not in STOP_WORDS and len(t) > 1]


def extract_entities(text: str) -> dict:
    # Flatten newlines to single spaces so multi-word patterns (company
    # names, "<x> segment" phrases) that wrap across PDF lines are
    # captured as clean, single-line phrases instead of raw text with
    # embedded newlines.
    flat_text = re.sub(r"\s+", " ", text)

    companies = sorted(set(m.strip() for m in COMPANY_SUFFIX_PATTERN.findall(flat_text)))

    dates = set()
    for pattern in DATE_PATTERNS:
        dates.update(pattern.findall(flat_text))
    dates = sorted(dates)

    currency = set()
    for pattern in CURRENCY_PATTERNS:
        currency.update(m.strip() for m in pattern.findall(flat_text))
    currency = sorted(currency)

    percentages = sorted(set(PERCENTAGE_PATTERN.findall(flat_text)))

    metrics_found = sorted(set(
        kw for kw in FINANCIAL_METRIC_KEYWORDS
        if re.search(rf"\b{re.escape(kw)}\b", flat_text, re.IGNORECASE)
    ))

    segments = set()
    for m in SEGMENT_PATTERN.finditer(flat_text):
        phrase = m.group(0).strip()
        phrase = re.sub(r"^(the|our|and|a|an|in)\s+", "", phrase, flags=re.IGNORECASE)
        if phrase:
            segments.add(phrase.lower())
    segments = sorted(segments)

    return {
        "company_names": companies,
        "dates": dates,
        "currency": currency,
        "financial_metrics": metrics_found,
        "percentages": percentages,
        "business_segments": segments,
    }


def process_document(txt_path: str) -> dict:
    filename = os.path.basename(txt_path)
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        raw_text = f.read()

    cleaned = remove_unnecessary_characters(raw_text)
    sentences = segment_sentences(cleaned)
    tokens = tokenize(cleaned)
    tokens_no_stop = remove_stopwords(tokens)
    entities = extract_entities(cleaned)

    return {
        "filename": filename,
        "raw_char_count": len(raw_text),
        "cleaned_char_count": len(cleaned),
        "sentence_count": len(sentences),
        "token_count": len(tokens),
        "token_count_after_stopword_removal": len(tokens_no_stop),
        "stopwords_removed": len(tokens) - len(tokens_no_stop),
        "sentences": sentences,
        "tokens": tokens,
        "tokens_no_stopwords": tokens_no_stop,
        "entities": entities,
        "processed_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def main():
    txt_files = sorted(f for f in os.listdir(PROCESSED_DIR) if f.lower().endswith(".txt"))
    if not txt_files:
        print(f"No .txt files found in {PROCESSED_DIR}. Run module4_document_processing.py first.")
        return

    report_rows = [[
        "filename", "sentences", "tokens", "tokens_after_stopword_removal",
        "company_names_found", "dates_found", "currency_found",
        "financial_metrics_found", "percentages_found", "business_segments_found",
        "status"
    ]]

    for filename in txt_files:
        path = os.path.join(PROCESSED_DIR, filename)
        try:
            result = process_document(path)
            out_name = os.path.splitext(filename)[0] + ".json"
            with open(os.path.join(NLP_DIR, out_name), "w") as jf:
                json.dump(result, jf, indent=2)

            e = result["entities"]
            report_rows.append([
                filename, result["sentence_count"], result["token_count"],
                result["token_count_after_stopword_removal"],
                len(e["company_names"]), len(e["dates"]), len(e["currency"]),
                len(e["financial_metrics"]), len(e["percentages"]), len(e["business_segments"]),
                "SUCCESS"
            ])
            print(f"[OK] {filename} -> {result['sentence_count']} sentences, "
                  f"{result['token_count']} tokens "
                  f"({result['token_count_after_stopword_removal']} after stopword removal), "
                  f"{len(e['company_names'])} companies, {len(e['financial_metrics'])} metrics")

        except Exception as ex:
            report_rows.append([filename, "-", "-", "-", "-", "-", "-", "-", "-", "-", f"FAILED: {ex}"])
            print(f"[FAILED] {filename}: {ex}")

    report_path = os.path.join(NLP_DIR, "nlp_processing_report.csv")
    with open(report_path, "w", newline="") as f:
        csv.writer(f).writerows(report_rows)

    print(f"\n[Module 5] Processed {len(txt_files)} documents.")
    print(f"[Module 5] Structured NLP output saved to: {NLP_DIR}")
    print(f"[Module 5] Processing report: {report_path}")
    print(f"[Module 5] Note: annual_report.csv was skipped intentionally - "
          f"it is structured tabular data, not free text.")


if __name__ == "__main__":
    main()
