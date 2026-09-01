AI Financial Document Intelligence & Analysis System

Module 4 Deliverable — Processed Financial Documents

1. Objective
Extract clean, usable text/data from every document in the combined 12-document dataset, using direct PDF parsing where possible, OCR where a page has no digital text layer, and direct structured reads for tabular (CSV) data.

2. Scope of Work
●	Ran module4_document_processing.py across all 12 documents in data/raw/ (11 PDFs + 1 CSV).
●	Implemented per-page extraction for PDFs: pdfplumber first, with an automatic OCR fallback (Tesseract, via pdftoppm rasterization) for any individual page with negligible extractable text.
●	Implemented direct structured reading for the CSV file: column detection, row counting, and empty-row cleanup.
●	Implemented text cleaning for PDFs: whitespace normalization, blank-line collapsing, line trimming.
●	Produced structured JSON output per document plus a processing report summarizing every file.

3. Processing Workflow
PDF / Image  →  OCR / PDF Parser  →  Raw Text  →  Clean Text  →  Structured Document (JSON) CSV  →  Direct Read  →  Clean Rows  →  Structured Document (JSON)

4. Extraction Method Logic
●	Step 1 (PDF): For each page, attempt direct text-layer extraction with pdfplumber.
●	Step 2 (PDF): If a page's extractable text is under 20 characters, attempt OCR for that specific page only (pdftoppm → 200 DPI JPEG → pytesseract).
●	Step 3 (PDF): If OCR also returns negligible text, the page is recorded as genuinely blank rather than forced through OCR repeatedly.
●	Step 4 (CSV): Read all rows directly, strip whitespace from every cell, and drop fully empty rows.
●	Step 5: Save a structured JSON per document (metadata + content) and, for PDFs, a plain .txt copy.

5. Processing Results — All 12 Documents
Filename	Type	Pages/Rows	Method	Words/Rows	Status
annual_report.csv	CSV	1059	direct_csv_read	1059	SUCCESS
annual_report_novatech_fy2026.pdf	PDF	1	pdf_text_extraction	133	SUCCESS
balance_sheet_f.pdf	PDF	20	pdf_text_extraction	11226	SUCCESS
balance_sheet_novatech_fy2026.pdf	PDF	1	pdf_text_extraction	104	SUCCESS
bank_statement.pdf	PDF	3	pdf_text_extraction	741	SUCCESS
bank_statement_novatech_may2026.pdf	PDF	1	pdf_text_extraction	80	SUCCESS
cash_flow_novatech_fy2026.pdf	PDF	1	pdf_text_extraction	117	SUCCESS
income_statement.pdf	PDF	79	pdf_text_extraction	359	SUCCESS
income_statement_novatech_fy2026.pdf	PDF	1	pdf_text_extraction	84	SUCCESS
invoice_f.pdf	PDF	30	pdf_text_extraction	7050	SUCCESS
invoice_brightedge_inv_2026_00457.pdf	PDF	1	pdf_text_extraction	71	SUCCESS
scanned_invoice_brightedge.pdf	PDF	1	ocr_tesseract	71	SUCCESS

6. OCR Path Verified
scanned_invoice_brightedge.pdf has no digital text layer (it is a flattened image of an invoice). The pipeline correctly detected this — direct extraction returned negligible characters — and automatically fell back to Tesseract OCR for that page, successfully recovering the invoice text (71 words). This confirms the OCR path required by Module 4 is implemented and working, not just simulated.

7. Real-World Data Quality Finding
income_statement.pdf (79 pages, from the real mentor dataset) contained 68 pages with no extractable text. Each was individually checked with the per-page OCR fallback and confirmed genuinely blank (verified visually by rendering the page to an image), not a missed scan. This is a common artifact of documents exported/converted from another format, and is exactly the kind of real-world data-quality issue this module is designed to detect and report rather than silently ignore.

8. Sample Output — Digital PDF (Income Statement, sample set)
Extraction method: pdf_text_extraction
"Revenue ................................. Rs. 850,00,00,000 Cost of Goods Sold ....................... Rs. 510,00,00,000 Gross Profit ............................. Rs. 340,00,00,000 ... Net Income ................................. Rs. 105,00,00,000"

9. Sample Output — OCR Path (Scanned Invoice)
Extraction method: ocr_tesseract
"INVOICE Invoice No: INV-2026-00457 Vendor: BrightEdge Office Supplies Pvt. Ltd. Description Qty Unit Price ==Amount Office Chairs (Ergo Pro) 25 Rs. 8,500 Rs. 2,12,500 ..."
Note: minor OCR artifacts (e.g. "==Amount") are typical of Tesseract on rendered text and will be handled during Module 5 text preprocessing.

10. Sample Output — Real Dataset (Balance Sheet, mentor-provided)
Extraction method: pdf_text_extraction
"ITEM Item BANK Bank COU Country YEA Year Value Flag Codes SI38TE 8.c. Other nAeLt LprovisionAsll banks USA United States 2009 2009 4974.45 4974.452 ..."

11. Sample Output — CSV (Annual Report, mentor-provided)
File type: CSV | Columns: 14 | Rows (cleaned): 1059
Columns: case, cc3, country, year, systemic_crisis, exch_usd, domestic_debt_in_default, sovereign_external_debt_default, gdp_weighted_default, inflation_annual_cpi, independence, currency_crises, inflation_crises, banking_crisis

12. Folder Structure Produced
data/processed/    <document_name>.json   (all 12 documents - structured metadata + content)    <document_name>.txt    (11 PDFs - plain cleaned text)    processing_report.csv  (summary across all 12 documents)

13. Deliverable
Processed Financial Documents — 12 structured JSON outputs (11 with accompanying plain-text files) in data/processed/, generated using a combined PDF text-extraction + per-page OCR + direct CSV pipeline, with an accompanying processing_report.csv confirming all 12 documents processed successfully, including a verified OCR path for the scanned document.

14. Status
Completed 

