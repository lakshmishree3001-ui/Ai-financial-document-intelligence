Module 8 Deliverable — Financial Analysis Report

1. Objective
Analyze financial statements automatically - profitability, liquidity, and leverage - and produce an overall performance rating.

2. Scope Note (Important)
Ratio analysis needs a matched SET of statements describing the same company and period (a Balance Sheet + Income Statement + Cash Flow Statement that all belong together). Only the NovaTech Industries FY2026 sample documents form such a matched set in this dataset. The 4 real mentor-provided documents (balance_sheet_f.pdf, income_statement.pdf, bank_statement.pdf, invoice_f.pdf) are independent, unrelated tabular datasets - different subjects entirely (global banking indicators, personal transactions, retail sales rows) - and cannot be combined into one company's statement analysis. This is the same honest, documented limitation carried over from Modules 5 and 7.
This module therefore runs the full analyzer on the NovaTech Industries FY2026 statement set (Balance Sheet + Income Statement + Cash Flow Statement + Annual Report narrative), which together provide everything the brief's analysis requires. To run this on the real dataset, a matched balance sheet + income statement + cash flow statement for the same company and period would be needed.

3. Analysis Workflow
Balance Sheet + Income Statement + Cash Flow Statement + Annual Report (text)    → parse individual line items (regex)    → compute profitability / liquidity / leverage ratios    → pull stated year-on-year growth figures from the narrative text    → rule-based overall performance rating    → Financial Analysis Report

4. Brief's Example Insight, Reproduced Exactly on Our Data
Brief's Example	This Module's Output (NovaTech FY2026)
Revenue increased by 18%.	Revenue increased by 18%.
Net profit increased by 12%.	Net profit increased by 12%.
Debt increased by 7%.	Debt increased by 7%.
Overall financial performance: Positive	Overall financial performance: Positive
These growth percentages were pulled directly from the annual report's own narrative text ("Revenue grew 18% to Rs. 850 crore", "Net profit grew 12%...", "Total debt increased 7%...") - the same numbers the brief's example is clearly built from.

5. Profitability Analysis
Metric	Value
Revenue	Rs. 8,50,00,00,000 (Rs. 850 crore)
Revenue Growth (YoY, stated in report)	+18.0%
Net Profit	Rs. 1,05,00,00,000 (Rs. 105 crore)
Net Profit Growth (YoY, stated in report)	+12.0%
Profit Margin (Net Profit / Revenue)	12.35%

6. Liquidity Analysis
Metric	Value
Current Assets (Cash + Receivables + Inventory)	Rs. 85,50,00,000
Current Liabilities (Payables + Short-term Borrowings)	Rs. 31,00,00,000
Current Ratio	2.76
Cash Position (Cash & Cash Equivalents, Balance Sheet)	Rs. 45,00,00,000
Cash at End of Year (Cash Flow Statement)	Rs. 90,00,00,000
A current ratio of 2.76 means the company has Rs. 2.76 of current assets for every Rs. 1 of current liabilities - comfortably above the commonly used 1.5 healthy-liquidity benchmark.

7. Leverage Analysis
Metric	Value
Total Debt (Short-term + Long-term)	Rs. 67,00,00,000
Total Debt Growth (YoY, stated in report)	+7.0%
Total Equity	Rs. 1,34,50,00,000
Debt-to-Equity Ratio	0.50
A debt-to-equity ratio of 0.50 means the company has 50 paise of debt for every rupee of equity - well within the commonly used 1.0 manageable-leverage benchmark.

8. Overall Performance Rating Logic
The analyzer checks 4 signals: revenue growth > 0, net profit growth > 0, current ratio ≥ 1.5, and debt-to-equity ≤ 1.0. If at least 75% of available signals are positive, the rating is "Positive"; 50-74% is "Stable / Mixed"; below 50% is "Negative".
Result for NovaTech FY2026: all 4 signals were positive (4/4 = 100%) → Overall financial performance: Positive.

9. Folder Structure Produced
data/analysis/    financial_analysis_report.json   (structured report - all figures + ratios)    financial_analysis_report.txt    (human-readable report - THE DELIVERABLE)

10. Deliverable
Financial Analysis Report — financial_analysis_report.txt / .json, covering profitability (revenue growth, profit margin, net profit), liquidity (current ratio, cash position), and leverage (debt-to-equity, total debt) for NovaTech Industries Ltd. (FY2026), with a rule-based overall performance rating that reproduces the brief's example output exactly.

11. Status
Completed 
