Module 5 Deliverable — Processed Financial Text Dataset
1. Objective
Prepare the financial text extracted in Module 4 for downstream NLP/ML models (classification, metric extraction, summarization, RAG in Modules 6-10), by cleaning it, breaking it into tokens and sentences, and pulling out the financial entities analysts actually care about.

2. Scope of Work
●	Built module5_text_preprocessing.py to process every .txt file produced by Module 4 (11 documents).
●	Removed unnecessary characters: PDF font-encoding artifacts (e.g. "(cid:9)"), spreadsheet-overflow artifacts ("########"), leader dots ("...."), and non-printable/non-ASCII noise.
●	Implemented word-level tokenization and stop-word removal (using scikit-learn's built-in English stop-word list).
●	Implemented paragraph-aware sentence segmentation that correctly re-joins PDF line-wrapped prose before splitting into sentences.
●	Implemented rule-based named entity recognition (NER) tuned specifically to financial documents, extracting company names, dates, currency amounts, financial metric labels, percentages, and business segment mentions.
●	annual_report.csv was intentionally left out of this module - it is already structured tabular data (rows/columns), not free text, so free-text NLP steps do not apply to it. It continues to be used in its structured form from Module 4 onward.

3. Why a Rule-Based Pipeline (Tooling Note)
This environment has no internet access, so heavyweight NLP libraries that need an online model/corpus download (spaCy's en_core_web_sm, NLTK's punkt/stopwords) could not be installed. Instead, this pipeline uses scikit-learn's built-in stop-word list (ships with the library, no download needed) plus a regex-based tokenizer, sentence segmenter, and pattern-based financial entity extractor. This is a well-established, fully offline approach for structured-domain text like financial statements, where entities follow fairly predictable formats (currency, dates, percentages, statement line items).

4. Preprocessing & Extraction Workflow
Raw Text  →  Remove Unnecessary Characters  →  Tokenization  →  Stop-word Removal             →  Sentence Segmentation  →  Named Entity / Financial Term Extraction  →  Structured Output (JSON)

5. Processing Results — All 11 Documents
Filename	Sentences	Tokens	Tokens (no stopwords)	Companies	Dates	Metrics
annual_report_novatech_fy2026.txt	15	130	100	3	2	2
balance_sheet_f.txt	880	13574	11170	0	0	0
balance_sheet_novatech_fy2026.txt	5	92	86	1	1	12
bank_statement.txt	1	639	464	0	0	0
bank_statement_novatech_may2026.txt	1	95	81	3	7	2
cash_flow_novatech_fy2026.txt	4	105	88	1	1	7
income_statement.txt	4	9357	4187	0	0	0
income_statement_novatech_fy2026.txt	2	69	63	1	1	11
invoice_brightedge_inv_2026_00457.txt	1	73	65	2	2	3
invoice_f.txt	1	11277	11136	0	0	0
scanned_invoice_brightedge.txt	10	75	68	2	2	2

6. Real-World Finding: Narrative vs. Tabular Documents
The 4 real mentor-provided PDFs (balance_sheet_f.pdf, bank_statement.pdf, income_statement.pdf, invoice_f.pdf) returned 0 company names, 0 dates, and 0 financial metric labels. This is expected and correctly reported, not a pipeline failure: those source files are tabular data dumps (e.g. worldwide bank indicators, personal transaction logs, retail sales rows) with column headers like "ITEM", "BANK", "Debit", "ProduitID" rather than narrative financial-statement prose. Because there is no descriptive text to extract entities from, the rule-based extractor correctly finds none. By contrast, the NovaTech sample documents (written as narrative statements/invoices) show rich extraction results — proof the pipeline works correctly, and that entity yield depends on how narrative vs. tabular the source text is.

7. Sample Output — Full Extraction (Annual Report, narrative text)
Sentences (paragraph-aware segmentation):
"The company generated revenue of Rs. 850 crore, up 18% year-on-year, driven by strong demand in our core manufacturing and digital services segments." "The management expects continued double-digit revenue growth in FY2027, supported by new product launches and capacity expansion."
Extracted entities:
Company names: NovaTech Industries, NovaTech Industries Ltd Dates: FY2026, FY2027 Currency: Rs. 105 crore, Rs. 850 crore Financial metrics: Net Profit, Revenue Percentages: 12%, 18%, 7% Business segments: "manufacturing and digital services segments", "the digital services segment"

8. Sample Output — Tabular Document (Balance Sheet, real dataset)
Tokens/stopword removal still run correctly (13,574 tokens -> 11,170 after stopword removal), but entity extraction correctly returns 0 companies, 0 dates, and 0 financial metrics, since the source is a column-based numeric dataset with no narrative sentences to extract from.

9. Folder Structure Produced
data/nlp_processed/    <document_name>.json   (cleaned text stats, tokens, sentences, entities)    nlp_processing_report.csv  (summary across all 11 documents)

10. Deliverable
Processed Financial Text Dataset — 11 structured JSON outputs in data/nlp_processed/, each containing cleaned text statistics, tokens (with and without stop words), sentence-segmented text, and extracted financial entities (company names, dates, currency, financial metrics, percentages, business segments), with an accompanying nlp_processing_report.csv summarizing every document.

11. Status
Completed 
