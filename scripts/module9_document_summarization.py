"""
MODULE 9 - Financial Document Summarization
------------------------------------------------
Objective : Generate concise summaries of lengthy financial documents.

Features (per project brief):
    - Executive summary
    - Key financial highlights
    - Risk summary
    - Business performance summary
    - Management discussion summary

Example (per project brief):
    200-page Annual Report -> AI Summarization ->
        Executive Summary + Financial Highlights + Major Risks

Technologies (per project brief): Transformers, LLM, NLP.

TOOLING NOTE (same transparency pattern as Modules 5-8):
A transformer/LLM model running INSIDE this offline script would need
either an internet connection (to call an LLM API) or downloaded
pretrained weights (to run a local transformer) - neither is
available in this sandboxed code-execution environment.

This module therefore implements two complementary things, both
documented honestly:

  1. An offline, fully automatable EXTRACTIVE summarizer (this
     script) - a well-established, classic NLP technique (frequency-
     weighted sentence scoring, in the spirit of Luhn's algorithm)
     combined with structural section-header detection (e.g.
     "Chairman's Message:", "Risk Factors:") and keyword matching.
     This is the repeatable "Lab Activity" pipeline component and
     runs on every document with zero external dependencies.

  2. An LLM-AUTHORED abstractive summary of the flagship document
     (the Annual Report), written directly in the Module 9
     deliverable document. Unlike the other "Transformers unavailable"
     notes in Modules 6-8, this one has an honest alternative: the
     assistant building this project *is itself* an LLM, so instead
     of faking a transformer call, it writes the genuine abstractive
     summary by hand - which is exactly what "AI Summarization" in
     the brief's own diagram means. This is clearly labeled as
     LLM-authored (not produced by a script) in the deliverable.

Input : data/processed/*.txt
Output: data/summaries/<name>.json   (per-document extractive summary)
        data/summaries/summarization_report.csv
"""

import os
import re
import csv
import json
from collections import Counter

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
OUT_DIR = os.path.join(BASE_DIR, "data", "summaries")
os.makedirs(OUT_DIR, exist_ok=True)

STOP_WORDS = set(ENGLISH_STOP_WORDS)

ABBREVIATIONS = ["Rs.", "Pvt.", "Ltd.", "Inc.", "Corp.", "No.", "Dr.", "Mr.",
                  "Mrs.", "vs.", "etc.", "FY.", "e.g.", "i.e."]

CURRENCY_OR_PCT_PATTERN = re.compile(
    r"(Rs\.?\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|lakh))?"
    r"|\u20B9\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|lakh))?"
    r"|\$\s?[\d,]+(?:\.\d+)?\s?(?:Million|Billion)?"
    r"|\b\d+(?:\.\d+)?\s?%)"
)

RISK_KEYWORDS = ["risk", "risks", "volatility", "competition", "competitive",
                  "litigation", "uncertain", "uncertainty", "adverse",
                  "exposure", "regulatory", "decline", "declining", "threat",
                  "challenge", "challenges"]

PERFORMANCE_KEYWORDS = ["revenue", "growth", "grew", "profit", "profitability",
                          "performance", "highlight", "highlights", "expanded",
                          "margin", "segment", "market", "demand"]

SECTION_HEADER_MAP = [
    (re.compile(r"chairman.?s message", re.IGNORECASE), "management_discussion"),
    (re.compile(r"management discussion", re.IGNORECASE), "management_discussion"),
    (re.compile(r"^outlook$", re.IGNORECASE), "management_discussion"),
    (re.compile(r"business highlights", re.IGNORECASE), "business_performance"),
    (re.compile(r"risk factors", re.IGNORECASE), "risk_summary"),
]


def protect_abbreviations(text: str):
    pmap = {}
    for i, abbr in enumerate(ABBREVIATIONS):
        token = f"@@ABBR{i}@@"
        pmap[token] = abbr
        text = text.replace(abbr, token)
    return text, pmap


def restore_abbreviations(text: str, pmap: dict) -> str:
    for token, abbr in pmap.items():
        text = text.replace(token, abbr)
    return text


def join_wrapped_lines(text: str):
    chunks, buffer = [], ""
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


def tokenize_words(text: str):
    return re.findall(r"[A-Za-z]+", text.lower())


def score_sentences(sentences):
    """Frequency-weighted sentence scoring (Luhn-style extractive
    summarization): sentences containing more high-frequency,
    non-stopword terms score higher."""
    word_freq = Counter()
    for s in sentences:
        for w in tokenize_words(s):
            if w not in STOP_WORDS and len(w) > 2:
                word_freq[w] += 1

    scores = []
    for i, s in enumerate(sentences):
        words = [w for w in tokenize_words(s) if w not in STOP_WORDS and len(w) > 2]
        if not words:
            scores.append((i, s, 0.0))
            continue
        score = sum(word_freq[w] for w in words) / len(words)
        scores.append((i, s, score))
    return scores


def top_sentences(scored, n=3):
    ranked = sorted(scored, key=lambda x: x[2], reverse=True)[:n]
    ranked_in_order = sorted(ranked, key=lambda x: x[0])
    return [s for _, s, _ in ranked_in_order]


def detect_sections(text: str):
    """Split into (header_line, content_lines) blocks using headers
    that look like 'Word Word:' on their own line."""
    sections = []
    current_header = None
    current_lines = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        is_header = (
            len(line) < 40 and line.endswith(":") and not line.startswith(("-", "*"))
        )
        if is_header:
            if current_header is not None or current_lines:
                sections.append((current_header, current_lines))
            current_header = line.rstrip(":")
            current_lines = []
        else:
            current_lines.append(line)
    if current_header is not None or current_lines:
        sections.append((current_header, current_lines))
    return sections


def extract_by_headers(text: str):
    """Map recognized section headers to our 3 header-driven summary
    categories (management_discussion, business_performance, risk_summary).
    Each section's raw lines are re-joined into proper sentences
    (reusing the same wrapped-line logic as the whole-document pass)
    so wrapped prose isn't returned as fragmented half-lines."""
    raw_result = {"management_discussion": [], "business_performance": [], "risk_summary": []}
    for header, lines in detect_sections(text):
        if not header:
            continue
        for pattern, category in SECTION_HEADER_MAP:
            if pattern.search(header):
                raw_result[category].extend(lines)
                break

    result = {}
    for category, lines in raw_result.items():
        if not lines:
            result[category] = []
            continue
        result[category] = segment_sentences("\n".join(lines))
    return result


CORPORATE_STOPWORD_NOISE = {"ltd", "inc", "co", "con", "cry", "de", "eg", "ie"}


def looks_like_title_fragment(sentence: str) -> bool:
    """Heuristic: genuine prose almost always contains at least one
    common function word (the, a, of, in, and, ...); bare document
    titles/headers (e.g. 'Company Ltd. - Annual Report') typically
    don't - except for a few corporate-suffix words ('ltd', 'inc',
    'co') that happen to be in the stop-word list too, so those are
    excluded from the check. A sentence ending in ':' (a header) or
    containing a 'Ltd. -' / 'Inc. -' style title separator is also
    treated as a title fragment."""
    s = sentence.strip()
    if s.endswith(":"):
        return True
    if re.search(r"(Ltd\.?|Inc\.?|Corp\.?|Pvt\.?)\s*-\s*", s):
        return True
    words = set(tokenize_words(s))
    meaningful_stopwords = (words & STOP_WORDS) - CORPORATE_STOPWORD_NOISE
    return len(meaningful_stopwords) == 0


def extract_by_keywords(sentences, keywords, max_items=5):
    matches = []
    for s in sentences:
        s_lower = s.lower()
        if any(kw in s_lower for kw in keywords):
            matches.append(s)
    return matches[:max_items]


def extract_financial_highlights(sentences, max_items=6):
    matches = [s for s in sentences if CURRENCY_OR_PCT_PATTERN.search(s)]
    return matches[:max_items]


def summarize_document(txt_path: str) -> dict:
    filename = os.path.basename(txt_path)
    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    sentences = segment_sentences(text)
    scored = score_sentences(sentences)

    # 1. Executive summary: top frequency-ranked sentences, doc order
    #    (excluding bare title/header fragments - see looks_like_title_fragment)
    exec_candidates = [entry for entry in scored if not looks_like_title_fragment(entry[1])]
    if not exec_candidates:
        exec_candidates = scored
    executive_summary = top_sentences(exec_candidates, n=3)

    # 2. Key financial highlights: currency/percentage-bearing sentences
    financial_highlights = extract_financial_highlights(sentences)

    # 3-5. Header-driven extraction with keyword fallback
    header_sections = extract_by_headers(text)

    risk_summary = header_sections["risk_summary"] or \
        extract_by_keywords(sentences, RISK_KEYWORDS)
    business_performance = header_sections["business_performance"] or \
        extract_by_keywords(sentences, PERFORMANCE_KEYWORDS)
    management_discussion = header_sections["management_discussion"]
    # (no generic keyword fallback for management discussion - it's
    # inherently structural; without a "Chairman's Message"/"Outlook"
    # style section, there is no genuine management commentary to pull)

    return {
        "filename": filename,
        "total_sentences": len(sentences),
        "executive_summary": executive_summary,
        "key_financial_highlights": financial_highlights,
        "risk_summary": risk_summary,
        "business_performance_summary": business_performance,
        "management_discussion_summary": management_discussion,
    }


def main():
    txt_files = sorted(f for f in os.listdir(PROCESSED_DIR) if f.lower().endswith(".txt"))
    if not txt_files:
        print(f"No .txt files found in {PROCESSED_DIR}. Run module4_document_processing.py first.")
        return

    report_rows = [["filename", "sentences", "executive_summary_items",
                     "financial_highlights", "risk_items", "performance_items",
                     "management_discussion_items"]]

    for filename in txt_files:
        path = os.path.join(PROCESSED_DIR, filename)
        result = summarize_document(path)

        out_name = os.path.splitext(filename)[0] + ".json"
        with open(os.path.join(OUT_DIR, out_name), "w") as jf:
            json.dump(result, jf, indent=2)

        report_rows.append([
            filename, result["total_sentences"],
            len(result["executive_summary"]), len(result["key_financial_highlights"]),
            len(result["risk_summary"]), len(result["business_performance_summary"]),
            len(result["management_discussion_summary"]),
        ])
        print(f"[OK] {filename} -> exec={len(result['executive_summary'])}, "
              f"highlights={len(result['key_financial_highlights'])}, "
              f"risk={len(result['risk_summary'])}, "
              f"performance={len(result['business_performance_summary'])}, "
              f"mgmt_discussion={len(result['management_discussion_summary'])}")

    report_path = os.path.join(OUT_DIR, "summarization_report.csv")
    with open(report_path, "w", newline="") as f:
        csv.writer(f).writerows(report_rows)

    print(f"\n[Module 9] Summarized {len(txt_files)} documents.")
    print(f"[Module 9] Structured summaries saved to: {OUT_DIR}")
    print(f"[Module 9] Report: {report_path}")


if __name__ == "__main__":
    main()
