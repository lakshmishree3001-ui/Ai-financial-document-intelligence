"""
MODULE 8 - Financial Statement Analysis
------------------------------------------------
Objective : Analyze financial statements automatically.

Analysis (per project brief):
    Profitability : Revenue growth, Profit margin, Net profit
    Liquidity     : Current ratio, Cash position
    Leverage      : Debt-to-equity, Total debt

Example Insight (per project brief):
    Revenue increased by 18%.
    Net profit increased by 12%.
    Debt increased by 7%.
    Overall financial performance: Positive

SCOPE NOTE:
Ratio analysis (current ratio, debt-to-equity, profit margin, etc.)
requires a matched SET of statements for one company/one period -
a Balance Sheet, an Income Statement, and a Cash Flow Statement that
all describe the same entity. Only the NovaTech Industries sample
documents form such a matched set in this dataset. The 4 real
mentor-provided documents (balance_sheet_f.pdf, income_statement.pdf,
bank_statement.pdf, invoice_f.pdf) are independent, unrelated tabular
datasets (different companies/periods/subjects entirely - e.g. global
banking indicators vs. personal transactions vs. retail sales rows),
so they cannot be combined into one statement analysis. This is the
same honest, documented limitation carried over from Modules 5 and 7.

This script therefore runs the full analyzer on the NovaTech
Industries FY2026 statement set, and documents what would be needed
to run it on the real dataset (a matched balance sheet + income
statement + cash flow statement for the same company/period).

Workflow:
    Balance Sheet + Income Statement + Cash Flow Statement + Annual Report (text)
        -> parse individual line items (regex)
        -> compute profitability / liquidity / leverage ratios
        -> pull stated YoY growth figures from the narrative text
        -> rule-based overall performance rating
        -> Financial Analysis Report (JSON + text)

Output:
    data/analysis/financial_analysis_report.json
    data/analysis/financial_analysis_report.txt   (human-readable report - the deliverable)
"""

import os
import re
import json

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
OUT_DIR = os.path.join(BASE_DIR, "data", "analysis")
os.makedirs(OUT_DIR, exist_ok=True)

BALANCE_SHEET_FILE = "balance_sheet_novatech_fy2026.txt"
INCOME_STATEMENT_FILE = "income_statement_novatech_fy2026.txt"
CASH_FLOW_FILE = "cash_flow_novatech_fy2026.txt"
ANNUAL_REPORT_FILE = "annual_report_novatech_fy2026.txt"


def parse_currency_to_number(value_str: str):
    """Convert 'Rs. 220,50,00,000' or 'Rs. 850 crore' etc. to a plain
    float number of rupees."""
    if not value_str:
        return None
    s = value_str.replace("Rs.", "").replace("Rs", "").replace("\u20B9", "").strip()
    multiplier = 1
    if re.search(r"crore", s, re.IGNORECASE):
        multiplier = 1_00_00_000
        s = re.sub(r"crore", "", s, flags=re.IGNORECASE)
    elif re.search(r"lakh", s, re.IGNORECASE):
        multiplier = 1_00_000
        s = re.sub(r"lakh", "", s, flags=re.IGNORECASE)
    s = s.replace(",", "").strip()
    try:
        return float(s) * multiplier
    except ValueError:
        return None


def extract_line_value(text: str, label: str):
    """Find a line like '<label> ..... Rs. X' and return the currency
    string found on it."""
    pattern = re.compile(
        rf"^{re.escape(label)}\b.*?(Rs\.?\s?[\d,]+(?:\.\d+)?(?:\s?(?:crore|lakh))?)",
        re.IGNORECASE | re.MULTILINE,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def extract_growth_percentage(text: str, keyword_pattern: str):
    """Find a sentence like 'Revenue grew 18% ...' or 'Total debt
    increased 7% ...' and return the signed percentage (float)."""
    pattern = re.compile(
        rf"{keyword_pattern}.*?(grew|increased|decreased|declined|fell)\s+(\d+(?:\.\d+)?)%",
        re.IGNORECASE,
    )
    m = pattern.search(text)
    if not m:
        return None
    direction, pct = m.group(1).lower(), float(m.group(2))
    return -pct if direction in ("decreased", "decline", "declined", "fell") else pct


def read_doc(filename: str) -> str:
    path = os.path.join(PROCESSED_DIR, filename)
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def main():
    balance_sheet = read_doc(BALANCE_SHEET_FILE)
    income_statement = read_doc(INCOME_STATEMENT_FILE)
    cash_flow = read_doc(CASH_FLOW_FILE)
    annual_report = read_doc(ANNUAL_REPORT_FILE)

    missing = [f for f, t in [
        (BALANCE_SHEET_FILE, balance_sheet), (INCOME_STATEMENT_FILE, income_statement),
        (CASH_FLOW_FILE, cash_flow), (ANNUAL_REPORT_FILE, annual_report),
    ] if not t]
    if missing:
        print(f"[Module 8] Missing required source documents: {missing}. "
              f"Run Module 4 first.")
        return

    # ---- Parse individual line items ----
    cash_and_equiv = parse_currency_to_number(extract_line_value(balance_sheet, "Cash and Cash Equivalents"))
    accounts_receivable = parse_currency_to_number(extract_line_value(balance_sheet, "Accounts Receivable"))
    inventory = parse_currency_to_number(extract_line_value(balance_sheet, "Inventory"))
    accounts_payable = parse_currency_to_number(extract_line_value(balance_sheet, "Accounts Payable"))
    short_term_borrowings = parse_currency_to_number(extract_line_value(balance_sheet, "Short-term Borrowings"))
    long_term_debt = parse_currency_to_number(extract_line_value(balance_sheet, "Long-term Debt"))
    total_assets = parse_currency_to_number(extract_line_value(balance_sheet, "Total Assets"))
    total_liabilities = parse_currency_to_number(extract_line_value(balance_sheet, "Total Liabilities"))
    total_equity = parse_currency_to_number(extract_line_value(balance_sheet, "Total Equity"))

    revenue = parse_currency_to_number(extract_line_value(income_statement, "Revenue"))
    net_income = parse_currency_to_number(extract_line_value(income_statement, "Net Income"))

    cash_at_end = parse_currency_to_number(extract_line_value(cash_flow, "Cash at End of Year"))

    # ---- Stated YoY growth figures (pulled from the narrative text) ----
    revenue_growth_pct = extract_growth_percentage(annual_report, "Revenue")
    net_profit_growth_pct = extract_growth_percentage(annual_report, "Net profit")
    debt_growth_pct = extract_growth_percentage(annual_report, "(?:Total )?debt")

    # ---- Compute ratios ----
    current_assets = (cash_and_equiv or 0) + (accounts_receivable or 0) + (inventory or 0)
    current_liabilities = (accounts_payable or 0) + (short_term_borrowings or 0)
    current_ratio = round(current_assets / current_liabilities, 2) if current_liabilities else None

    total_debt = (short_term_borrowings or 0) + (long_term_debt or 0)
    debt_to_equity = round(total_debt / total_equity, 2) if total_equity else None

    profit_margin_pct = round((net_income / revenue) * 100, 2) if revenue else None

    # ---- Rule-based overall performance rating ----
    positive_signals = 0
    total_signals = 0
    for value, is_good in [
        (revenue_growth_pct, lambda v: v > 0),
        (net_profit_growth_pct, lambda v: v > 0),
        (current_ratio, lambda v: v >= 1.5),
        (debt_to_equity, lambda v: v <= 1.0),
    ]:
        if value is not None:
            total_signals += 1
            if is_good(value):
                positive_signals += 1

    if total_signals == 0:
        overall = "Insufficient data"
    else:
        ratio = positive_signals / total_signals
        if ratio >= 0.75:
            overall = "Positive"
        elif ratio >= 0.5:
            overall = "Stable / Mixed"
        else:
            overall = "Negative"

    report = {
        "company": "NovaTech Industries Ltd.",
        "period": "FY2026",
        "profitability": {
            "revenue": revenue,
            "revenue_growth_pct": revenue_growth_pct,
            "net_profit": net_income,
            "net_profit_growth_pct": net_profit_growth_pct,
            "profit_margin_pct": profit_margin_pct,
        },
        "liquidity": {
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "current_ratio": current_ratio,
            "cash_and_cash_equivalents": cash_and_equiv,
            "cash_at_end_of_year_per_cash_flow_statement": cash_at_end,
        },
        "leverage": {
            "short_term_borrowings": short_term_borrowings,
            "long_term_debt": long_term_debt,
            "total_debt": total_debt,
            "total_debt_growth_pct": debt_growth_pct,
            "total_equity": total_equity,
            "debt_to_equity": debt_to_equity,
        },
        "overall_financial_performance": overall,
    }

    json_path = os.path.join(OUT_DIR, "financial_analysis_report.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2)

    # ---- Human-readable report (matches the brief's example format) ----
    def fmt_currency(n):
        return f"Rs. {n:,.0f}" if n is not None else "N/A"

    def fmt_pct(n):
        return f"{n:+.1f}%" if n is not None else "N/A"

    lines = []
    lines.append("FINANCIAL ANALYSIS REPORT")
    lines.append(f"Company: {report['company']}")
    lines.append(f"Period : {report['period']}")
    lines.append("")
    lines.append("-- PROFITABILITY --")
    lines.append(f"Revenue: {fmt_currency(revenue)} (YoY {fmt_pct(revenue_growth_pct)})")
    lines.append(f"Net Profit: {fmt_currency(net_income)} (YoY {fmt_pct(net_profit_growth_pct)})")
    lines.append(f"Profit Margin: {profit_margin_pct}%" if profit_margin_pct is not None else "Profit Margin: N/A")
    lines.append("")
    lines.append("-- LIQUIDITY --")
    lines.append(f"Current Assets: {fmt_currency(current_assets)}")
    lines.append(f"Current Liabilities: {fmt_currency(current_liabilities)}")
    lines.append(f"Current Ratio: {current_ratio}" if current_ratio is not None else "Current Ratio: N/A")
    lines.append(f"Cash Position (Cash & Cash Equivalents): {fmt_currency(cash_and_equiv)}")
    lines.append(f"Cash at End of Year (per Cash Flow Statement): {fmt_currency(cash_at_end)}")
    lines.append("")
    lines.append("-- LEVERAGE --")
    lines.append(f"Total Debt: {fmt_currency(total_debt)} (YoY {fmt_pct(debt_growth_pct)})")
    lines.append(f"Total Equity: {fmt_currency(total_equity)}")
    lines.append(f"Debt-to-Equity Ratio: {debt_to_equity}" if debt_to_equity is not None else "Debt-to-Equity Ratio: N/A")
    lines.append("")
    lines.append("-- EXAMPLE-STYLE INSIGHT SUMMARY --")
    if revenue_growth_pct is not None:
        lines.append(f"Revenue increased by {revenue_growth_pct:.0f}%.")
    if net_profit_growth_pct is not None:
        lines.append(f"Net profit increased by {net_profit_growth_pct:.0f}%.")
    if debt_growth_pct is not None:
        lines.append(f"Debt increased by {debt_growth_pct:.0f}%.")
    lines.append(f"Overall financial performance: {overall}")

    txt_path = os.path.join(OUT_DIR, "financial_analysis_report.txt")
    with open(txt_path, "w") as f:
        f.write("\n".join(lines))

    print("\n".join(lines))
    print(f"\n[Module 8] JSON report: {json_path}")
    print(f"[Module 8] Text report: {txt_path}")


if __name__ == "__main__":
    main()
