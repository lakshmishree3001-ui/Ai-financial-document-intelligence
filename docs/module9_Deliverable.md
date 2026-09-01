Module 9 Deliverable — AI Financial Summarization Module

1. Objective
Generate concise summaries of lengthy financial documents: an executive summary, key financial highlights, a risk summary, a business performance summary, and a management discussion summary.

2. Two-Part Approach (and why)
A transformer/LLM model running INSIDE an offline script would need either an internet connection (to call an LLM API) or downloaded pretrained weights (to run a local transformer) - neither is available in this sandboxed environment, the same limitation documented in Modules 6-8. For summarization specifically, there is an honest alternative that doesn't apply to those earlier modules: the assistant building this project is itself an LLM. So this deliverable has two parts:
●	Part A - module9_document_summarization.py: a fully offline, automatable EXTRACTIVE summarizer (frequency-weighted sentence scoring, in the spirit of Luhn's classic algorithm, combined with section-header detection and keyword matching). This is the repeatable "Lab Activity" pipeline that runs on all 11 documents with zero external dependencies - the NLP technology requested in the brief.
●	Part B - an LLM-AUTHORED abstractive summary of the flagship document (the Annual Report), written directly by the assistant reading the source text - not a script output. This is clearly labeled as such below, and is what "AI Summarization" in the brief's own diagram actually refers to.

3. Part A - Extractive Summarization Pipeline (Script)
Workflow: Document Text → Sentence Segmentation → Frequency-Weighted Scoring + Section-Header Detection + Keyword Matching → 5-Category Summary
Filename	Sentences	Exec. Summary	Fin. Highlights	Risk Items	Performance	Mgmt Discussion
annual_report_novatech_fy2026.txt	15	3	4	3	4	4
balance_sheet_f.txt	880	3	0	0	0	0
balance_sheet_novatech_fy2026.txt	5	1	4	0	0	0
bank_statement.txt	1	1	0	0	0	0
bank_statement_novatech_may2026.txt	1	1	1	0	0	0
cash_flow_novatech_fy2026.txt	4	1	2	0	0	0
income_statement.txt	4	1	0	0	4	0
income_statement_novatech_fy2026.txt	2	1	2	0	2	0
invoice_brightedge_inv_2026_00457.txt	1	1	1	0	0	0
invoice_f.txt	1	1	0	0	0	0
scanned_invoice_brightedge.txt	10	3	3	0	0	0

4. Extractive Output — Annual Report (Best Result)
Executive Summary:
"FY2026 was a landmark year for NovaTech Industries." / "Revenue grew 18% to Rs. 850 crore" / "Net profit grew 12% to Rs. 105 crore"
Risk Summary (from the 'Risk Factors' section):
Foreign exchange volatility / Rising raw material costs / Increasing competition in the digital services segment
Business Performance Summary (from the 'Business Highlights' section):
Revenue grew 18% to Rs. 850 crore / Net profit grew 12% to Rs. 105 crore / Expanded into two new international markets / Total debt increased 7% to fund capacity expansion
Management Discussion Summary (from 'Chairman's Message' + 'Outlook'):
"The company generated revenue of Rs. 850 crore, up 18% year-on-year, driven by strong demand in our core manufacturing and digital services segments." / "The management expects continued double-digit revenue growth in FY2027, supported by new product launches and capacity expansion."

5. Honest Finding: Sentence-Based Summarization Doesn't Suit Line-Item Statements
The Balance Sheet, Income Statement, Cash Flow Statement, Invoice, and Bank Statement documents are tables of line items ("Label .... Value"), not narrative prose - most have almost no sentence-ending punctuation at all, so there's little for a sentence-based summarizer to work with (e.g. balance_sheet_novatech_fy2026.txt has only 5 "sentences" for 16 line items). This is expected, not a bug: structured statements are exactly what Module 7's metric extraction is built for; Module 9's summarizer is built for narrative content like the Annual Report, and that's where it performs best. The two modules are complementary, not redundant.
The real mentor-provided documents (balance_sheet_f.pdf, bank_statement.pdf, income_statement.pdf, invoice_f.pdf) show the same 0-content pattern for financial highlights/risk/performance/management-discussion seen in Modules 5 and 7, for the same reason: they are tabular data dumps, not narrative financial disclosure text.

6. Part B - LLM-Authored Abstractive Summary (Annual Report, NovaTech Industries Ltd., FY2026)
Written directly by the assistant from the source document - this is what a transformer/LLM-based summarizer (the technology requested in the brief) would produce, without needing an external API call.
Executive Summary
NovaTech Industries closed FY2026 on a high note, with revenue up 18% to Rs. 850 crore and net profit up 12% to Rs. 105 crore, driven by strong demand across its manufacturing and digital services segments. The company expanded into two new international markets during the year while continuing to invest in capacity, and management is guiding for continued double-digit revenue growth in FY2027.
Key Financial Highlights
●	Revenue: Rs. 850 crore (+18% YoY)
●	Net Profit: Rs. 105 crore (+12% YoY)
●	Total Debt: increased 7% YoY to fund capacity expansion
●	Expanded into two new international markets
Risk Summary
Three risks stand out from management's disclosure: foreign exchange volatility (relevant given the company's new international market exposure), rising raw material costs (a margin pressure point given the manufacturing base), and intensifying competition specifically in the digital services segment - the same segment cited as a key growth driver, so competitive pressure there is worth watching closely.
Business Performance Summary
Growth this year was broad-based rather than one-off: both revenue (+18%) and net profit (+12%) grew at a healthy double-digit pace, and margin improvement (net profit growing faster in absolute terms relative to the cost base) suggests operational efficiency gains, not just top-line growth. International expansion into two new markets adds a second growth lever alongside the core segments.
Management Discussion Summary
Management attributes the year's performance to strong demand and operational efficiency initiatives, and frames the increase in debt as a deliberate, growth-funding decision rather than a distress signal ("to fund capacity expansion"). The outlook is confidently forward-looking, guiding for continued double-digit revenue growth in FY2027 on the back of new product launches and further capacity additions - though this should be read alongside the three risks disclosed above, particularly competitive pressure in the same digital services segment management is counting on for growth.

7. Folder Structure Produced
data/summaries/    <document_name>.json       (per-document extractive summary, all 5 categories)    summarization_report.csv   (summary counts across all 11 documents)

8. Deliverable
AI Financial Summarization Module — the extractive summarization pipeline (module9_document_summarization.py) producing structured 5-category summaries for all 11 documents (data/summaries/), plus an LLM-authored abstractive summary of the flagship Annual Report reproducing the brief's own example: 200-page Annual Report → Executive Summary + Financial Highlights + Major Risks (Section 6, above).

9. Status
Completed 
