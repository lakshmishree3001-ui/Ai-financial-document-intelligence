Module 7 Deliverable — Structured Financial Metrics Dataset

1. Objective
Automatically extract important financial information from the processed documents, in a structured (Metric, Value, Year) form.

2. Metrics Extracted (per project brief)
Revenue, Gross Profit, Operating Profit, Net Income, Assets, Liabilities, Equity, EPS, Debt, Cash Flow

3. Brief's Example, Reproduced on Our Own Data
Input (from annual_report_novatech_fy2026.pdf):
"...generated revenue of Rs. 850 crore, up 18% year-on-year, driven by..."
Output:
Metric: Revenue   |   Value: Rs. 850 crore   |   Year: FY2026
This is the exact record produced by the pipeline for that sentence - matching the brief's required (Metric, Value, Year) output shape.

4. Technologies Requested vs. Implemented
Technology	Status	Notes
NLP	Implemented	Reuses Module 5's cleaned text, tokenization, and sentence output
Named Entity Recognition	Implemented	Reuses Module 5's rule-based currency/date/percentage NER
Regular Expressions	Implemented	Core of this module - pairs each of the 10 metric labels with the nearest currency value per line
Transformers	Not run	A transformer-based financial-NER model needs pretrained weights downloaded from the internet, which is not available in this environment

5. Extraction Workflow
Cleaned Document Text (Module 4/5)    → locate known metric labels (Revenue, Net Income, EPS, Total Assets, ...)    → pair each label with the currency value on the same line    → attach the document's reporting year/period (FY#### pattern, else most common year mentioned)    → Structured (Metric, Value, Year) record

6. Results — All 11 Documents
Filename	Detected Year	Metrics Found
annual_report_novatech_fy2026.txt	FY2026	2
balance_sheet_f.txt	2009	0
balance_sheet_novatech_fy2026.txt	2026	5
bank_statement.txt	2053	0
bank_statement_novatech_may2026.txt	2026	0
cash_flow_novatech_fy2026.txt	FY2026	4
income_statement.txt	2013	0
income_statement_novatech_fy2026.txt	FY2026	5
invoice_brightedge_inv_2026_00457.txt	2026	0
invoice_f.txt	2017	0
scanned_invoice_brightedge.txt	2026	0
Total: 16 structured metric records extracted across the dataset.

7. Sample Extracted Records
Document	Metric	Value	Year
annual_report_novatech_fy2026.txt	Revenue	Rs. 850 crore	FY2026
annual_report_novatech_fy2026.txt	Net Income	Rs. 105 crore	FY2026
income_statement_novatech_fy2026.txt	Gross Profit	Rs. 340,00,00,000	FY2026
income_statement_novatech_fy2026.txt	Operating Profit	Rs. 145,00,00,000	FY2026
income_statement_novatech_fy2026.txt	EPS	Rs. 21.00	FY2026
balance_sheet_novatech_fy2026.txt	Assets	Rs. 220,50,00,000	2026
balance_sheet_novatech_fy2026.txt	Equity	Rs. 134,50,00,000	2026
balance_sheet_novatech_fy2026.txt	Debt	Rs. 55,00,00,000 (+1 more)	2026
cash_flow_novatech_fy2026.txt	Cash Flow	Rs. 113,00,00,000 (+1 more)	FY2026

8. Honest Finding: Why the Provided Documents Show 0 Metrics
balance_sheet_f.pdf, bank_statement.pdf, income_statement.pdf, and invoice_f.pdf all show 0 extracted metrics - consistent with the same finding from Module 5. These 4 real files are tabular/statistical data dumps (e.g. global banking indicators, personal transaction logs, retail sales rows), not narrative financial-statement line items with labels like "Revenue" or "Net Income". There is nothing in that text for the 10 required metric labels to match, so the extractor correctly returns zero rather than guessing.
A related side-effect: the "detected year" for these 4 files (e.g. 2009, 2053, 2013, 2017) is not a meaningful reporting year - it is just the most frequently occurring 4-digit number in a multi-year statistical dataset (balance_sheet_f.pdf alone spans years from the 1800s to 2014). The year-detection heuristic is built for single-period financial statements (which is what the other 7 documents are) and is documented here as not reliable for multi-year tabular datasets.

9. Folder Structure Produced
data/metrics_extracted/    <document_name>.json         (per-document structured metrics + detected year)    financial_metrics_dataset.csv  (master dataset - all documents combined - THE DELIVERABLE)    extraction_summary.csv         (per-document year + metric count)

10. Deliverable
Structured Financial Metrics Dataset — financial_metrics_dataset.csv, containing 16 structured (Document, Metric, Value, Year, Source Line) records extracted from the 11 processed documents, reproducing the brief's required output format for each of the 10 target metrics found in the dataset.

11. Status
Completed 
