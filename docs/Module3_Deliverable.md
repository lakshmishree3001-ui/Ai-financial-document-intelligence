AI Financial Document Intelligence & Analysis System

Module 3 Deliverable — Raw Financial Document Dataset

1. Objective
Collect a complete set of financial documents that the AI pipeline (Modules 4–13) will process, classify, extract information from, summarize, and analyze.

2. Scope of Work
●	Combined two document sources into a single dataset of 12 financial documents, placed directly in data/raw/: 5 real documents provided directly by the internship mentor, and 7 additional documents (including one scanned copy) used to ensure every required category and edge case is represented.
●	Built a data-collection script (module3_data_collection.py) that scans data/raw/ directly, automatically classifies each file by type (from its filename), and flags scanned/image copies separately - no intermediate staging folder or copy step needed.
●	Organized every document with a unique document ID and logged it in a dataset catalog (manifest) generated directly from the files themselves - not typed by hand.
●	Verified every file opens correctly and inspected its structure (page/row count) before handing off to Module 4.

3. Dataset Summary (12 documents, 6 categories)
Doc ID	Type	Filename	File Type	Pages/Rows	Scanned?
DOC001	Balance Sheet	balance_sheet_f.pdf	PDF	20	No
DOC002	Annual Report	annual_report.csv	CSV	1059	No
DOC003	Annual Report	annual_report_novatech_fy2026.pdf	PDF	1	No
DOC004	Balance Sheet	balance_sheet_novatech_fy2026.pdf	PDF	1	No
DOC005	Bank Statement	bank_statement.pdf	PDF	3	No
DOC006	Bank Statement	bank_statement_novatech_may2026.pdf	PDF	1	No
DOC007	Cash Flow Statement	cash_flow_novatech_fy2026.pdf	PDF	1	No
DOC008	Income Statement	income_statement.pdf	PDF	79	No
DOC009	Income Statement	income_statement_novatech_fy2026.pdf	PDF	1	No
DOC010	Invoice	invoice_f.pdf	PDF	30	No
DOC011	Invoice	invoice_brightedge_inv_2026_00457.pdf	PDF	1	No
DOC012	Invoice	scanned_invoice_brightedge.pdf	PDF	1	Yes

4. Data Sources Used
Real dataset: balance_sheet_f.pdf, annual_report.csv, bank_statement.pdf, income_statement.pdf, and invoice_f.pdf - received directly from the internship mentor as a zipped package, with original filenames preserved in the catalog for traceability.
Supplementary dataset: a second set of documents covering the same 6 categories, including cash_flow_novatech_fy2026. and scanned_invoice_brightedge.pdf - an image-only scan used specifically to exercise and prove out the OCR path implemented in Module 4.
Combining both sources ensures the dataset has at least one example of every required document category, plus one genuinely scanned document.

5. Methodology
●	Step 1: Placed every document  directly into data/raw/ - one flat collection folder, no staging step.
●	Step 2: Wrote a keyword-based classifier that normalizes filenames (handling spaces, underscores, and hyphens) and maps them to one of six document types.
●	Step 3: Flagged any filename containing "scan" as a scanned copy, for OCR-path testing in Module 4.
●	Step 4: Inspected each file programmatically - page count for PDFs (via pypdf), row count for the CSV, plus file size - instead of manually recording details.
●	Step 5: Logged every document into dataset_catalog.csv with ID, filename, type, scanned flag, file type, page/row count, size, source, and collection date.

6. Folder Structure Produced

data/raw/    balance_sheet_f.pdf, annual_report.csv, annual_report_novatech_fy2026.pdf,    balance_sheet_novatech_fy2026.pdf, bank_statement.pdf,    bank_statement_novatech_may2026.pdf, cash_flow_novatech_fy2026.pdf,    income_statement.pdf, income_statement_novatech_fy2026.pdf,    invoice_f.pdf, invoice_brightedge_inv_2026_00457.pdf,    scanned_invoice_brightedge.pdf, dataset_catalog.csv

7. Deliverable
Raw Financial Document Dataset — 12 financial documents (11 PDF + 1 CSV) across all 6 required categories (Balance Sheet, Income Statement, Cash Flow Statement, Annual Report, Invoice, Bank Statement), including one scanned copy, organized under data/raw/ with an accompanying dataset_catalog.csv manifest.

8. Status
Completed 

