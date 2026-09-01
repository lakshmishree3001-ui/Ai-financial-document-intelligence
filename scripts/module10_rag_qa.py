"""
MODULE 10 - Financial Document Question Answering using RAG
------------------------------------------------------------
Objective : Allow users to ask questions about uploaded financial documents.

Workflow (per project brief):
    Upload Document -> Text Extraction -> Chunking -> Embeddings ->
    Vector Database -> Retriever -> LLM -> Answer

Technologies (per project brief): RAG, LLM, FAISS/ChromaDB, Embeddings.

TOOLING NOTE (same transparency pattern as Modules 5-9):
This environment has no internet access, so:
    - Dense embedding models (e.g. sentence-transformers) need
      pretrained weights downloaded from the internet - not available.
    - FAISS and ChromaDB are not installed, and cannot be installed
      without internet access to a package index.
    - A live LLM API call for the final "Answer" generation step is
      also not reachable from this offline script.

Implemented instead - each swapped for a well-established, fully
offline equivalent that plays the same role in the pipeline:
    - Embeddings   -> TF-IDF vectors (a classic sparse "embedding" of
                      text into a vector space; same mathematical
                      role as a dense embedding for retrieval purposes).
    - Vector DB     -> an in-memory matrix of chunk vectors + metadata,
                       searched with brute-force cosine similarity
                       (exactly what FAISS/ChromaDB do internally for
                       a corpus this size - a few dozen chunks).
    - LLM (answer)  -> an extractive answer generator (returns the
                       most relevant retrieved sentence rather than a
                       generated one). As in Module 9, the assistant
                       building this project is itself an LLM, so a
                       set of genuinely LLM-generated answers (not
                       script output) is also provided in the Module
                       10 deliverable document, clearly labeled as such.

This script builds the full retrieval half of the pipeline (chunking,
embedding, vector store, retriever) plus a working extractive-QA
"chatbot" function, and is structured so a real embedding model /
vector DB / LLM API can be swapped in later with no change to the
overall architecture.

Output:
    data/rag/chunks.json              (all chunks + metadata)
    data/rag/tfidf_vectorizer.joblib  (fitted "embedding" model)
    data/rag/chunk_vectors.joblib     (chunk embedding matrix)
    data/rag/sample_qa_transcript.json (demo Q&A session - part of the deliverable)
"""

import os
import re
import json
import joblib
import numpy as np

from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
OUT_DIR = os.path.join(BASE_DIR, "data", "rag")
os.makedirs(OUT_DIR, exist_ok=True)

STOP_WORDS = set(ENGLISH_STOP_WORDS)


def simple_stem(word: str) -> str:
    """Very light suffix-stripping so 'risk'/'risks', 'segment'/
    'segments' etc. collapse to the same token. A real stemmer
    (e.g. NLTK's Porter/Snowball) would need NLTK's corpus data,
    which needs internet access - this is the offline substitute,
    same transparency pattern as Modules 5-9."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith("es") and not word.endswith(("ses", "xes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tfidf_analyzer(text: str):
    """Custom analyzer for TfidfVectorizer: tokenize, lightly stem,
    drop stop-words - fixes plural/singular query-vs-document
    mismatches (e.g. query 'risks' vs. document heading 'Risk
    Factors') that plain bag-of-words TF-IDF would otherwise miss."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    stemmed = [simple_stem(w) for w in words]
    return [w for w in stemmed if w not in STOP_WORDS and len(w) > 2]

ABBREVIATIONS = ["Rs.", "Pvt.", "Ltd.", "Inc.", "Corp.", "No.", "Dr.", "Mr.",
                  "Mrs.", "vs.", "etc.", "FY.", "e.g.", "i.e."]

CURRENCY_OR_PCT_PATTERN = re.compile(
    r"(Rs\.?\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|lakh))?"
    r"|\u20B9\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|lakh))?"
    r"|\$\s?[\d,]+(?:\.\d+)?\s?(?:Million|Billion)?"
    r"|\b\d+(?:\.\d+)?\s?%)"
)


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
    lines = join_wrapped_lines(protected)
    sentences = []
    for chunk in lines:
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", chunk)
        for p in parts:
            p = restore_abbreviations(p.strip(), pmap)
            if p:
                sentences.append(p)
    return sentences


# ---------------------------------------------------------------
# STEP 1-2: Text Extraction (already done, Module 4) + Chunking
# ---------------------------------------------------------------
SECTION_HEADER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z\s&/]{2,35}:$")


def find_preceding_header(sentences, idx):
    """Walk backwards from position idx to find the nearest section
    header line (e.g. 'Risk Factors:') so it can be prepended to the
    chunk - this keeps header context (like the word 'Risk') attached
    to its bullets even though the header itself becomes a separate
    'sentence' during segmentation."""
    for j in range(idx - 1, -1, -1):
        if SECTION_HEADER_PATTERN.match(sentences[j].strip()):
            return sentences[j].rstrip(":")
    return None


def get_sentence_units(text: str):
    """Choose the right granularity per document. Prose documents
    (like the Annual Report) benefit from join_wrapped_lines merging
    PDF-wrapped lines back into real sentences. But line-item
    financial statements (Balance Sheet, Income Statement, ...) have
    almost no sentence-ending punctuation at all, so that same merging
    logic collapses the WHOLE statement into one giant blob - useless
    for pinpointing a single metric. Heuristic: if sentence
    segmentation merged away more than half of the document's raw
    non-empty lines, treat it as tabular and use raw lines instead."""
    raw_lines = [l.strip() for l in text.split("\n") if l.strip()]
    sentences = segment_sentences(text)
    if raw_lines and len(sentences) < 0.5 * len(raw_lines):
        return raw_lines
    return sentences


def chunk_document(filename: str, text: str, sentences_per_chunk: int = 3):
    """Group sentence/line units into overlap-free chunks of N units
    each - small enough to be a focused retrieval unit, large enough
    to keep context (e.g. a metric label plus its value plus its year).
    Each chunk keeps its original unit list (not just the joined text)
    so line/bullet-level structure survives for the answer-extraction
    step, and is prefixed with its nearest section header (if any) so
    header keywords like "Risk" remain attached to their content for
    retrieval."""
    sentences = get_sentence_units(text)
    chunks = []
    for i in range(0, len(sentences), sentences_per_chunk):
        group = sentences[i:i + sentences_per_chunk]
        header = find_preceding_header(sentences, i)
        chunk_text = (f"{header}: " if header else "") + " ".join(group)
        chunks.append({
            "chunk_id": f"{filename}::chunk{i // sentences_per_chunk}",
            "document": filename,
            "section_header": header,
            "text": chunk_text,
            "sentences": group,
        })
    return chunks


def build_chunks():
    all_chunks = []
    for filename in sorted(os.listdir(PROCESSED_DIR)):
        if not filename.lower().endswith(".txt"):
            continue
        with open(os.path.join(PROCESSED_DIR, filename), "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        all_chunks.extend(chunk_document(filename, text))
    return all_chunks


# ---------------------------------------------------------------
# STEP 3: Embeddings (TF-IDF, offline substitute for dense embeddings)
# STEP 4: Vector Database (in-memory matrix + brute-force cosine search)
# ---------------------------------------------------------------
class SimpleVectorStore:
    """Minimal offline stand-in for FAISS/ChromaDB: stores chunk
    vectors and metadata, and supports top-k cosine-similarity search -
    exactly what those libraries do under the hood for a small corpus."""

    def __init__(self, vectorizer, chunk_vectors, chunks):
        self.vectorizer = vectorizer
        self.chunk_vectors = chunk_vectors
        self.chunks = chunks

    @classmethod
    def build(cls, chunks):
        texts = [c["text"] for c in chunks]
        vectorizer = TfidfVectorizer(analyzer=tfidf_analyzer, max_features=3000)
        chunk_vectors = vectorizer.fit_transform(texts)
        return cls(vectorizer, chunk_vectors, chunks)

    # STEP 5: Retriever
    def retrieve(self, query: str, top_k: int = 3):
        query_vec = self.vectorizer.transform([query])
        scores = cosine_similarity(query_vec, self.chunk_vectors).flatten()
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [
            {**self.chunks[i], "score": round(float(scores[i]), 4)}
            for i in top_idx if scores[i] > 0
        ]

    def save(self, out_dir):
        joblib.dump(self.vectorizer, os.path.join(out_dir, "tfidf_vectorizer.joblib"))
        joblib.dump(self.chunk_vectors, os.path.join(out_dir, "chunk_vectors.joblib"))
        with open(os.path.join(out_dir, "chunks.json"), "w") as f:
            json.dump(self.chunks, f, indent=2)


# ---------------------------------------------------------------
# STEP 6: "LLM" answer step - offline extractive substitute
# ---------------------------------------------------------------
def extract_best_answer_sentence(retrieved_chunks, query: str):
    """Pick the best candidate sentence from the retrieved chunks,
    respecting retrieval rank but allowing near-ties to be resolved by
    local relevance. Chunks whose retrieval score is within 10% of the
    top score are treated as "equally retrieved" and their candidate
    sentences are pooled together for scoring; a chunk ranked clearly
    below the top one is only consulted if nothing usable comes from
    the top tier. This balances two failure modes seen during testing
    (see Module 10 deliverable, Section 7): trusting a single top
    chunk too rigidly misses the right answer sitting in an
    almost-equally-ranked second chunk, while pooling ALL retrieved
    chunks together lets an incidental one-word overlap in a weakly
    retrieved chunk beat a clearly-better top chunk."""
    query_words = set(simple_stem(w) for w in re.findall(r"[a-z]+", query.lower()))
    if not retrieved_chunks:
        return None, None

    top_score = retrieved_chunks[0].get("score", 0)
    tier = [c for c in retrieved_chunks if c.get("score", 0) >= top_score * 0.9]

    def usable_candidates(chunk):
        return [
            s for s in (chunk.get("sentences") or segment_sentences(chunk["text"]))
            if not SECTION_HEADER_PATTERN.match(s.strip())
        ]

    def best_in(chunks):
        best_sentence, best_score, best_chunk = None, -1, None
        for chunk in chunks:
            for sentence in usable_candidates(chunk):
                sentence_words = set(simple_stem(w) for w in re.findall(r"[a-z]+", sentence.lower()))
                overlap = len(query_words & sentence_words)
                has_value = bool(CURRENCY_OR_PCT_PATTERN.search(sentence))
                score = overlap + (2 if has_value else 0)
                if score > best_score:
                    best_score, best_sentence, best_chunk = score, sentence, chunk
        return best_sentence, best_chunk, best_score

    sentence, chunk, score = best_in(tier)
    if sentence is not None:
        return sentence, chunk

    # nothing usable in the top tier (e.g. it was only a bare header) -
    # fall through to the remaining, clearly-lower-ranked chunks
    remaining = [c for c in retrieved_chunks if c not in tier]
    sentence, chunk, _ = best_in(remaining)
    return sentence, chunk


def ask(store: "SimpleVectorStore", query: str, top_k: int = 3) -> dict:
    """The full RAG pipeline for one question: retrieve -> extract answer."""
    retrieved = store.retrieve(query, top_k=top_k)
    if not retrieved:
        return {
            "question": query,
            "answer": "No relevant information was found in the document set for this question.",
            "source_document": None,
            "retrieved_chunks": [],
        }

    answer_sentence, source_chunk = extract_best_answer_sentence(retrieved, query)
    return {
        "question": query,
        "answer": answer_sentence or "Relevant text was found, but no specific value could be extracted.",
        "source_document": source_chunk["document"] if source_chunk else retrieved[0]["document"],
        "retrieved_chunks": [
            {"chunk_id": c["chunk_id"], "document": c["document"], "score": c["score"], "text": c["text"]}
            for c in retrieved
        ],
    }


DEMO_QUESTIONS = [
    "What was the company's revenue in FY2026?",
    "What was the net profit?",
    "What is the total debt?",
    "What are the main risks the company faces?",
    "What is the earnings per share (EPS)?",
    "What was the total assets and total equity?",
    "How much did the company pay in dividends?",
    "What is the closing bank balance for May 2026?",
]


def main():
    print("[Module 10] Building chunks from data/processed/ ...")
    chunks = build_chunks()
    print(f"[Module 10] Created {len(chunks)} chunks from all processed documents.")

    print("[Module 10] Building TF-IDF embeddings + vector store ...")
    store = SimpleVectorStore.build(chunks)
    store.save(OUT_DIR)
    print(f"[Module 10] Vector store saved to: {OUT_DIR}")

    print("\n[Module 10] Running demo Q&A session ...\n")
    transcript = []
    for question in DEMO_QUESTIONS:
        result = ask(store, question)
        transcript.append(result)
        print(f"User: {question}")
        print(f"AI  : {result['answer']}")
        print(f"      (source: {result['source_document']})\n")

    transcript_path = os.path.join(OUT_DIR, "sample_qa_transcript.json")
    with open(transcript_path, "w") as f:
        json.dump(transcript, f, indent=2)
    print(f"[Module 10] Demo Q&A transcript saved to: {transcript_path}")


if __name__ == "__main__":
    main()
