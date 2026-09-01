"""
MODULE 12 - AI Financial Insights Engine
------------------------------------------------
Objective : Generate human-readable financial insights.

Example (per project brief):
    AI Financial Insights
    (check) Revenue growth is strong.
    (check) Operating margins improved.
    (warn)  Debt increased significantly.
    (warn)  Operating expenses increased faster than revenue.
    Overall Risk: Medium

Technologies (per project brief): LLM, NLP, RAG.

WHAT THIS MODULE ACTUALLY DOES:
This is a SYNTHESIS layer - it doesn't run new analysis from scratch,
it combines the structured outputs already produced by earlier
modules into the brief's exact insight-bullet format:
    - Module 8 (Financial Statement Analysis)  -> profitability/
      liquidity/leverage figures and ratios
    - Module 11 (Anomaly Detection)            -> flagged transaction
      and inflation-panel anomaly counts
    - Module 10 (RAG vector store)             -> re-used, NOT rebuilt,
      to retrieve a real supporting source sentence for each insight
      (this is the "RAG" requirement: every insight is grounded in an
      actual retrieved passage, not just asserted)

TOOLING NOTE (same transparency pattern as Modules 5-11):
    - NLP: rule-based natural-language generation - each insight is
      built from a threshold check on real computed figures, worded
      as a natural sentence. This is a standard, explainable
      "insights-as-code" technique used in real BI/fintech tools.
    - RAG: genuinely re-uses Module 10's saved TF-IDF vector store to
      retrieve real grounding evidence per insight (see above) -
      not a placeholder.
    - LLM: a live model call isn't available in this offline script
      (same limitation as Modules 6-11). As in Modules 9 and 10, the
      assistant building this project is itself an LLM, so a genuine
      LLM-authored narrative version of the insights (richer prose,
      not just template bullets) is provided directly in the Module
      12 deliverable document, clearly labeled as such.

Output:
    data/insights/financial_insights_report.json
    data/insights/financial_insights_report.txt   (brief-format report - the deliverable)
"""

import os
import sys
import json
import joblib
import numpy as np

# The saved TF-IDF vectorizer (Module 10) used a custom analyzer
# function for lightweight stemming. Unpickling it requires that same
# function to be importable under the running script's module
# namespace - re-import it here rather than duplicating the logic.
sys.path.insert(0, os.path.dirname(__file__))
from module10_rag_qa import tfidf_analyzer, simple_stem  # noqa: F401 (needed for unpickling)

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
ANALYSIS_PATH = os.path.join(BASE_DIR, "data", "analysis", "financial_analysis_report.json")
ANOMALY_PATH = os.path.join(BASE_DIR, "data", "anomalies", "anomaly_detection_report.json")
RAG_DIR = os.path.join(BASE_DIR, "data", "rag")
OUT_DIR = os.path.join(BASE_DIR, "data", "insights")
os.makedirs(OUT_DIR, exist_ok=True)


# ---------------------------------------------------------------
# Re-use Module 10's saved RAG store (retriever only - no re-embedding)
# ---------------------------------------------------------------
def load_rag_retriever():
    vectorizer = joblib.load(os.path.join(RAG_DIR, "tfidf_vectorizer.joblib"))
    chunk_vectors = joblib.load(os.path.join(RAG_DIR, "chunk_vectors.joblib"))
    with open(os.path.join(RAG_DIR, "chunks.json"), "r") as f:
        chunks = json.load(f)

    from sklearn.metrics.pairwise import cosine_similarity

    def retrieve(query: str, top_k: int = 1):
        query_vec = vectorizer.transform([query])
        scores = cosine_similarity(query_vec, chunk_vectors).flatten()
        top_idx = np.argsort(scores)[::-1][:top_k]
        return [
            {"document": chunks[i]["document"], "text": chunks[i]["text"], "score": round(float(scores[i]), 4)}
            for i in top_idx if scores[i] > 0
        ]

    return retrieve


# ---------------------------------------------------------------
# Rule-based insight generation (NLP: threshold -> natural sentence)
# ---------------------------------------------------------------
def generate_insights(analysis: dict, anomalies: dict, retrieve):
    insights = []
    risk_points = 0
    risk_capacity = 0

    def add(status, text, evidence_query, weight=1):
        nonlocal risk_points, risk_capacity
        evidence = retrieve(evidence_query, top_k=1)
        insights.append({
            "status": status,  # "positive" or "warning"
            "text": text,
            "evidence": evidence[0] if evidence else None,
        })
        risk_capacity += weight
        if status == "warning":
            risk_points += weight

    profitability = analysis["profitability"]
    liquidity = analysis["liquidity"]
    leverage = analysis["leverage"]

    # --- Revenue growth ---
    rg = profitability["revenue_growth_pct"]
    if rg is not None and rg >= 10:
        add("positive", f"Revenue growth is strong (+{rg:.0f}% year-on-year).",
            "revenue growth", weight=2)
    elif rg is not None and rg > 0:
        add("positive", f"Revenue grew modestly (+{rg:.0f}% year-on-year).",
            "revenue growth", weight=2)
    elif rg is not None:
        add("warning", f"Revenue declined ({rg:.0f}% year-on-year).",
            "revenue growth", weight=2)

    # --- Profit margin / operating margin ---
    pm = profitability["profit_margin_pct"]
    npg = profitability["net_profit_growth_pct"]
    if pm is not None and npg is not None and npg > 0:
        add("positive", f"Operating margins improved - net profit grew +{npg:.0f}% "
            f"YoY, with a net profit margin of {pm:.1f}%.",
            "operating margin profit", weight=2)
    elif pm is not None:
        add("warning", f"Profitability is under pressure - net profit margin is {pm:.1f}%.",
            "operating margin profit", weight=2)

    # --- Debt growth (significance threshold) ---
    dg = leverage["total_debt_growth_pct"]
    if dg is not None and dg >= 20:
        add("warning", f"Debt increased significantly (+{dg:.0f}% year-on-year).",
            "total debt increased", weight=3)
    elif dg is not None and dg > 0:
        add("positive", f"Debt increased moderately (+{dg:.0f}% year-on-year), "
            "consistent with funding growth rather than distress.",
            "total debt increased", weight=1)

    # --- Debt-to-equity (leverage health) ---
    de = leverage["debt_to_equity"]
    if de is not None and de <= 1.0:
        add("positive", f"Leverage is manageable - debt-to-equity ratio is {de:.2f}, "
            "well within the commonly used 1.0 benchmark.",
            "debt to equity total equity", weight=2)
    elif de is not None:
        add("warning", f"Leverage is elevated - debt-to-equity ratio is {de:.2f}, "
            "above the commonly used 1.0 benchmark.",
            "debt to equity total equity", weight=2)

    # --- Liquidity (current ratio) ---
    cr = liquidity["current_ratio"]
    if cr is not None and cr >= 1.5:
        add("positive", f"Liquidity position is strong - current ratio of {cr:.2f} "
            "comfortably covers short-term obligations.",
            "current ratio current assets liabilities", weight=1)
    elif cr is not None:
        add("warning", f"Liquidity position is tight - current ratio of {cr:.2f} "
            "is below the commonly used 1.5 benchmark.",
            "current ratio current assets liabilities", weight=2)

    # --- Anomaly signals (from Module 11) ---
    txn = anomalies["bank_transactions"]
    if txn["flagged_transactions"] > 0:
        pct = txn["flagged_transactions"] / txn["total_debit_transactions"] * 100
        add("warning", f"{txn['flagged_transactions']} of {txn['total_debit_transactions']} "
            f"recent transactions ({pct:.0f}%) were flagged as statistically unusual and "
            "warrant manual review.",
            "unusual transaction anomaly", weight=1)

    # --- Operating expenses vs. revenue growth (brief's specific example check) ---
    # NOTE: our income statement is a single-period snapshot with no prior-period
    # operating-expense figure, so this specific YoY comparison cannot be computed
    # from real data here - documented honestly rather than fabricated.
    insights.append({
        "status": "not_computable",
        "text": "Operating expenses vs. revenue growth (YoY) could not be evaluated - "
                "the current dataset has only a single-period Income Statement, so "
                "there is no prior-period operating-expense figure to compare against.",
        "evidence": None,
    })

    # --- Overall risk rating ---
    risk_ratio = risk_points / risk_capacity if risk_capacity else 0
    if risk_ratio >= 0.5:
        overall_risk = "High"
    elif risk_ratio >= 0.25:
        overall_risk = "Medium"
    else:
        overall_risk = "Low"

    return insights, overall_risk, risk_ratio


def format_report(insights, overall_risk, company, period):
    lines = ["AI FINANCIAL INSIGHTS", f"{company} - {period}", ""]
    symbol = {"positive": "[+]", "warning": "[!]", "not_computable": "[?]"}
    for item in insights:
        lines.append(f"{symbol[item['status']]} {item['text']}")
    lines.append("")
    lines.append(f"Overall Risk: {overall_risk}")
    return "\n".join(lines)


def main():
    with open(ANALYSIS_PATH) as f:
        analysis = json.load(f)
    with open(ANOMALY_PATH) as f:
        anomalies = json.load(f)

    retrieve = load_rag_retriever()
    insights, overall_risk, risk_ratio = generate_insights(analysis, anomalies, retrieve)

    report_txt = format_report(insights, overall_risk, analysis["company"], analysis["period"])
    print(report_txt)

    txt_path = os.path.join(OUT_DIR, "financial_insights_report.txt")
    with open(txt_path, "w") as f:
        f.write(report_txt)

    json_report = {
        "company": analysis["company"],
        "period": analysis["period"],
        "insights": insights,
        "overall_risk": overall_risk,
        "risk_ratio": round(risk_ratio, 3),
    }
    json_path = os.path.join(OUT_DIR, "financial_insights_report.json")
    with open(json_path, "w") as f:
        json.dump(json_report, f, indent=2)

    print(f"\n[Module 12] Text report: {txt_path}")
    print(f"[Module 12] JSON report: {json_path}")


if __name__ == "__main__":
    main()
