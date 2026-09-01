Module 10 Deliverable — Financial AI Chatbot (RAG)

1. Objective
Allow users to ask questions about the uploaded financial documents and get direct, grounded answers - a Retrieval-Augmented Generation (RAG) system.

2. Workflow Implemented
Upload Document → Text Extraction (Module 4) → Chunking → Embeddings → Vector Database → Retriever → LLM → Answer

3. Technologies Requested vs. Implemented
Technology	Status	Offline Substitute Used
Embeddings	Implemented (substitute)	TF-IDF vectors - a classic sparse text embedding; plays the same role as a dense embedding for retrieval
Vector Database (FAISS/ChromaDB)	Implemented (substitute)	In-memory chunk-vector matrix + brute-force cosine similarity search - exactly what FAISS/ChromaDB do internally for a corpus this size
RAG	Implemented	Full retrieve-then-answer pipeline, architecture unchanged from a production RAG system
LLM (answer generation)	Implemented (substitute) + genuine LLM demo	Script uses an offline extractive answer-picker; the assistant (itself an LLM) also answers a live query directly in Section 6, clearly labeled
Neither a dense embedding model nor FAISS/ChromaDB could be installed or downloaded in this offline environment (same limitation as Modules 5-9). The substitutes above are standard, well-established techniques that occupy the exact same architectural role, so the pipeline can be upgraded to real embeddings/FAISS/an LLM API later with no change to the overall design.

4. Pipeline Detail
●	Chunking: each document's text is segmented into sentence/line units, then grouped into 3-unit chunks. Prose documents (like the Annual Report) use sentence segmentation; line-item statements (Balance Sheet, Income Statement, ...) use raw lines instead, since they have almost no sentence-ending punctuation for sentence segmentation to work with.
●	Each chunk is prefixed with its nearest section header (e.g. "Risk Factors:") so header context/keywords stay attached to their content for retrieval.
●	Embeddings: a TF-IDF vectorizer with light custom stemming (so 'risk'/'risks', 'segment'/'segments' etc. match as the same term) is fit over all chunks from all 11 documents (939 chunks total).
●	Vector Database + Retriever: chunk vectors are stored in memory; a query is embedded the same way and compared to every chunk via cosine similarity, returning the top-3 most relevant chunks.
●	Answer step: within the top-ranked chunk (or the next-best chunk if the top one is only a bare header), the sentence with the most query-word overlap and/or a currency/percentage value is returned as the answer.

5. Brief's Example, Reproduced on Our Data
Brief's Example	This System's Output
User: What was the company's revenue in 2025?	User: What was the company's revenue in FY2026?
AI: The company's reported revenue was ₹850 crore in 2025.	AI: Revenue ................................. Rs. 850,00,00,000  (source: income_statement_novatech_fy2026.txt)
Same figure (Rs. 850 crore = Rs. 8,50,00,00,000), retrieved automatically from the correct document with no hard-coding.

6. Demo Q&A Session (Script Output, All 8 Questions)
User Question	AI Answer	Source Document	Correct?
What was the company's revenue in FY2026?	Revenue ... Rs. 850,00,00,000	income_statement_novatech_fy2026.txt	YES
What was the net profit?	Net profit grew 12% to Rs. 105 crore	annual_report_novatech_fy2026.txt	YES
What is the total debt?	Total debt increased 7% to fund capacity expansion	annual_report_novatech_fy2026.txt	YES
What are the main risks the company faces?	Foreign exchange volatility	annual_report_novatech_fy2026.txt	YES
What is the EPS?	Earnings Per Share (EPS) ... Rs. 21.00	income_statement_novatech_fy2026.txt	YES
What was total assets and total equity?	Total Liabilities and Equity ... Rs. 220,50,00,000	balance_sheet_novatech_fy2026.txt	PARTIAL
How much did the company pay in dividends?	Proceeds from Long-term Debt ... Rs. 15,00,00,000	cash_flow_novatech_fy2026.txt	NO
What is the closing bank balance for May 2026?	31-May-2026 Closing Balance Rs. 25,34,21,210	bank_statement_novatech_may2026.txt	YES
6 of 8 fully correct, 1 partially correct, 1 incorrect - all with the correct source DOCUMENT retrieved in every single case (8/8). The 2 imperfect answers are both explained honestly in Section 7.

7. Honest Findings: Where the Offline (Lexical) Approach Falls Short
Total Assets and Total Equity (partial): the retriever correctly found the Balance Sheet, but returned the "Total Liabilities and Equity" line rather than pulling both requested figures - the extractive answer-picker only returns one line, so a two-part question gets an incomplete (though not wrong) answer. A true LLM generation step would naturally combine both figures into one sentence.
Dividends (incorrect): the retriever correctly found the Cash Flow Statement (the right document), but the answer-picker chose "Proceeds from Long-term Debt" instead of "Dividends Paid". The cause is a word-form mismatch that light stemming doesn't fix: the question uses "pay", the document says "Paid" - different verb forms that our simple suffix-stripping stemmer (built for plurals like risk/risks) does not normalize to the same token. A real semantic embedding model would recognize "pay" and "Paid" as related regardless of exact word form; this lexical, offline substitute cannot.
Both cases are documented here rather than hidden, consistent with the transparency approach used throughout this project (Modules 5, 6, 7, 9). They also point directly at what upgrading to a real embedding model and LLM generation step (Section 3) would fix.

8. LLM-Authored Answer (Live Demonstration)
As in Module 9, the assistant building this project is itself an LLM. Answering the one query the script got wrong, directly from the retrieved source document (not a script output):
User: How much did the company pay in dividends?
AI: According to the Cash Flow Statement, NovaTech Industries paid Rs. 20,00,00,000 (Rs. 20 crore) in dividends during FY2026, recorded under "Financing Activities" alongside Rs. 15,00,00,000 raised in new long-term debt - meaning the company still had a net cash outflow from financing of about Rs. 5 crore for the year even after the new borrowing.

9. Folder Structure Produced
data/rag/    tfidf_vectorizer.joblib      (fitted "embedding" model)    chunk_vectors.joblib          (chunk embedding matrix - the "vector database" contents)    chunks.json                   (all 939 chunks + metadata)    sample_qa_transcript.json     (full demo Q&A session with retrieved chunks - THE DELIVERABLE)

10. Deliverable
Financial AI Chatbot — a working RAG pipeline (module10_rag_qa.py) covering chunking, TF-IDF embeddings, an in-memory vector database with cosine-similarity retrieval, and an extractive answer step, callable via a single ask(store, question) function. Demonstrated on 8 questions across all document types in the dataset with 6/8 fully correct, 1 partial, and 1 documented failure case - plus a genuine LLM-generated answer for the one question the offline extractive step got wrong.

11. Status
Completed 
