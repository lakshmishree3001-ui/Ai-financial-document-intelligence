"""
app/dashboard.py - Streamlit dashboard for the Financial Document
Intelligence Platform (Module 13).

Implements the 9 dashboard components required by the project brief:
    Document upload | Document classification | Financial KPIs |
    Revenue charts | Profit charts | Financial ratios | AI summary |
    AI insights | Document Q&A

Like api.py, all business logic is imported from core.py (already
tested independently - see Module 13 deliverable) - this file is
purely the UI layer: it calls core.py functions and renders the
results with Streamlit widgets and Plotly charts.

TOOLING NOTE:
Streamlit and Plotly are not installed in this sandboxed, offline
environment and cannot be installed here (no internet access to
PyPI). As with api.py, this file is meant to be run by the user on
their own machine:

    pip install streamlit plotly
    streamlit run dashboard.py

This opens the dashboard in a browser at http://localhost:8501
"""

import os
import sys
import tempfile

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core

st.set_page_config(page_title="Financial Document Intelligence", layout="wide")

st.title("📊 AI Financial Document Intelligence Platform")
st.caption("Upload, classify, analyze, summarize, and query financial documents - "
           "backed by Modules 3-12 of the AI Financial Document Intelligence project.")

documents = core.list_documents()
doc_names = [d["filename"] for d in documents]

# =====================================================================
# SIDEBAR: 1. Document upload
# =====================================================================
st.sidebar.header("📁 1. Document Upload")
uploaded_file = st.sidebar.file_uploader(
    "Upload a financial document", type=["pdf", "csv"]
)
if uploaded_file is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp:
        tmp.write(uploaded_file.getbuffer())
        tmp_path = tmp.name
    result = core.upload_document(tmp_path, uploaded_file.name)
    os.remove(tmp_path)
    st.sidebar.success(f"Uploaded as {result['document_id']}: {result['filename']}")
    documents = core.list_documents()
    doc_names = [d["filename"] for d in documents]

st.sidebar.header("📄 Select a Document")
selected_doc = st.sidebar.selectbox("Choose a document to inspect", doc_names)

tabs = st.tabs([
    "🏷️ Classification", "💰 Financial KPIs", "📈 Revenue & Profit Charts",
    "📐 Financial Ratios", "📝 AI Summary", "💡 AI Insights", "💬 Document Q&A",
])

# =====================================================================
# TAB: 2. Document classification
# =====================================================================
with tabs[0]:
    st.subheader("Document Classification")
    if selected_doc:
        extracted = core.get_extracted_text(selected_doc)
        text = extracted.get("text") or " ".join(str(c) for c in extracted.get("columns", []))
        if text:
            result = core.classify_document(text)
            st.metric("Predicted Category", result["predicted_category"])
            st.caption(f"Model used: {result['model_used']}")
            if result["class_probabilities"]:
                proba_df = {"Category": list(result["class_probabilities"].keys()),
                            "Probability": list(result["class_probabilities"].values())}
                fig = px.bar(proba_df, x="Category", y="Probability",
                             title="Class Probabilities", range_y=[0, 1])
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No extracted text available for this document yet.")

# =====================================================================
# TAB: 3. Financial KPIs
# =====================================================================
with tabs[1]:
    st.subheader("Financial KPIs")
    analysis = core.get_financial_analysis()
    if analysis:
        st.caption(f"{analysis['company']} - {analysis['period']}")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Revenue", f"Rs. {analysis['profitability']['revenue']:,.0f}",
                     f"{analysis['profitability']['revenue_growth_pct']:+.0f}% YoY")
        col2.metric("Net Profit", f"Rs. {analysis['profitability']['net_profit']:,.0f}",
                     f"{analysis['profitability']['net_profit_growth_pct']:+.0f}% YoY")
        col3.metric("Profit Margin", f"{analysis['profitability']['profit_margin_pct']:.1f}%")
        col4.metric("Current Ratio", f"{analysis['liquidity']['current_ratio']:.2f}")
        st.metric("Overall Financial Performance", analysis["overall_financial_performance"])
    else:
        st.info("No financial analysis found. Run module8_financial_statement_analysis.py first.")

# =====================================================================
# TAB: 4. Revenue charts + 5. Profit charts
# =====================================================================
with tabs[2]:
    st.subheader("Revenue & Profit Breakdown")
    metrics = core.get_metrics()
    income_metrics = {m["metric"]: m["value"] for m in metrics
                        if m["document"] == "income_statement_novatech_fy2026.txt"}

    def parse_amount(value_str):
        s = value_str.replace("Rs.", "").replace(",", "").strip()
        if "crore" in s.lower():
            return float(s.lower().replace("crore", "").strip()) * 1_00_00_000
        try:
            return float(s)
        except ValueError:
            return None

    if income_metrics:
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Revenue Chart**")
            fig_rev = go.Figure(go.Bar(
                x=["Revenue"], y=[parse_amount(income_metrics.get("Revenue", "0"))],
                marker_color="#2F5496",
            ))
            fig_rev.update_layout(yaxis_title="Rs.", title="Revenue (FY2026)")
            st.plotly_chart(fig_rev, use_container_width=True)

        with col_b:
            st.markdown("**Profit Waterfall**")
            stages = ["Gross Profit", "Operating Profit", "Net Income"]
            values = [parse_amount(income_metrics.get(s, "0")) for s in stages]
            fig_profit = go.Figure(go.Funnel(y=stages, x=values))
            fig_profit.update_layout(title="Profit Progression (FY2026)")
            st.plotly_chart(fig_profit, use_container_width=True)
    else:
        st.info("No income statement metrics found. Run module7_metric_extraction.py first.")

# =====================================================================
# TAB: 6. Financial ratios
# =====================================================================
with tabs[3]:
    st.subheader("Financial Ratios")
    analysis = core.get_financial_analysis()
    if analysis:
        col1, col2 = st.columns(2)
        with col1:
            fig_cr = go.Figure(go.Indicator(
                mode="gauge+number", value=analysis["liquidity"]["current_ratio"],
                title={"text": "Current Ratio"},
                gauge={"axis": {"range": [0, 4]},
                       "steps": [{"range": [0, 1], "color": "#f8d7da"},
                                 {"range": [1, 1.5], "color": "#fff3cd"},
                                 {"range": [1.5, 4], "color": "#d4edda"}]},
            ))
            st.plotly_chart(fig_cr, use_container_width=True)
        with col2:
            fig_de = go.Figure(go.Indicator(
                mode="gauge+number", value=analysis["leverage"]["debt_to_equity"],
                title={"text": "Debt-to-Equity Ratio"},
                gauge={"axis": {"range": [0, 2]},
                       "steps": [{"range": [0, 1], "color": "#d4edda"},
                                 {"range": [1, 1.5], "color": "#fff3cd"},
                                 {"range": [1.5, 2], "color": "#f8d7da"}]},
            ))
            st.plotly_chart(fig_de, use_container_width=True)
    else:
        st.info("No financial analysis found.")

# =====================================================================
# TAB: 7. AI summary
# =====================================================================
with tabs[4]:
    st.subheader("AI Summary")
    if selected_doc:
        summary = core.get_summary(selected_doc)
        if "error" not in summary:
            st.markdown("**Executive Summary**")
            for s in summary.get("executive_summary", []):
                st.write(f"- {s}")
            st.markdown("**Key Financial Highlights**")
            for s in summary.get("key_financial_highlights", []):
                st.write(f"- {s}")
            st.markdown("**Risk Summary**")
            for s in summary.get("risk_summary", []) or ["No risk-related content detected."]:
                st.write(f"- {s}")
            st.markdown("**Business Performance Summary**")
            for s in summary.get("business_performance_summary", []) or ["Not available for this document."]:
                st.write(f"- {s}")
            st.markdown("**Management Discussion Summary**")
            for s in summary.get("management_discussion_summary", []) or ["Not available for this document."]:
                st.write(f"- {s}")
        else:
            st.info(summary["error"])

# =====================================================================
# TAB: 8. AI insights
# =====================================================================
with tabs[5]:
    st.subheader("AI Financial Insights")
    insights = core.get_insights()
    if "error" not in insights:
        for item in insights["insights"]:
            icon = {"positive": "✅", "warning": "⚠️", "not_computable": "❔"}[item["status"]]
            st.write(f"{icon} {item['text']}")
            if item.get("evidence"):
                with st.expander("Source evidence"):
                    st.caption(f"From: {item['evidence']['document']}")
                    st.write(item["evidence"]["text"])
        risk_color = {"Low": "green", "Medium": "orange", "High": "red"}.get(insights["overall_risk"], "gray")
        st.markdown(f"### Overall Risk: :{risk_color}[{insights['overall_risk']}]")
    else:
        st.info(insights["error"])

# =====================================================================
# TAB: 9. Document Q&A
# =====================================================================
with tabs[6]:
    st.subheader("Ask a Question About Your Documents")
    question = st.text_input("Your question", placeholder="What was the company's revenue in FY2026?")
    if st.button("Ask") and question:
        result = core.answer_question(question)
        st.markdown(f"**AI:** {result['answer']}")
        st.caption(f"Source: {result['source_document']}")
        with st.expander("Retrieved passages (RAG)"):
            for chunk in result["retrieved_chunks"]:
                st.write(f"**{chunk['document']}** (score: {chunk['score']})")
                st.write(chunk["text"])
                st.divider()
