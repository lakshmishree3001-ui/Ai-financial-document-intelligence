"""
MODULE 11 - Financial Trend & Anomaly Detection
------------------------------------------------
Objective : Detect unusual financial patterns.

Detect (per project brief): sudden revenue changes, unusual expenses,
abnormal transactions, unexpected profit changes, significant debt
increases.

Algorithms (per project brief): Isolation Forest, Statistical
Analysis, Autoencoder.

DATA NOTE (important):
Trend/anomaly detection needs a SERIES of data points over time - a
single-snapshot statement (like the NovaTech Balance Sheet or Income
Statement, each covering one period only) has nothing to compare
against. This module therefore runs on the two REAL mentor-provided
datasets that genuinely are time series / multi-record data:
    1. bank_statement.pdf (real) - 107 individual dated transactions
       (Debit/Credit by category) - a direct match for "unusual
       expenses" / "abnormal transactions".
    2. annual_report.csv (real) - a 1059-row, 13-country, multi-year
       (1870-2014) panel of inflation and currency-crisis data - used
       here as a genuine "unexpected large swings" trend dataset.
This is the first module where the real mentor-provided data is
MORE useful than the synthetic NovaTech set, precisely because it has
many records per entity rather than one.

TOOLING NOTE (same transparency pattern as Modules 5-10):
- Isolation Forest and Statistical Analysis (z-score / IQR) are fully
  implemented (scikit-learn + numpy, both offline).
- A true Autoencoder needs a deep-learning framework (TensorFlow/
  PyTorch), neither of which is installed or installable without
  internet access here. Substitute used: PCA reconstruction error.
  A linear autoencoder with tied weights is mathematically equivalent
  to PCA - reconstructing each record from its top principal
  components and scoring by reconstruction error is a standard,
  legitimate offline stand-in for exactly this algorithm, not an
  approximation of a different one.

Output:
    data/anomalies/bank_transaction_anomalies.csv
    data/anomalies/inflation_anomalies.csv
    data/anomalies/anomaly_detection_report.json
"""

import os
import re
import json
import numpy as np
import pandas as pd

from sklearn.ensemble import IsolationForest
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
OUT_DIR = os.path.join(BASE_DIR, "data", "anomalies")
os.makedirs(OUT_DIR, exist_ok=True)

DAYS = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}


# ---------------------------------------------------------------
# PART 1: Real bank transaction anomaly detection
# ---------------------------------------------------------------
def clean_row(line: str) -> str:
    line = re.sub(r"#{3,}", "", line)                       # date-overflow artifact
    line = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", line)          # split merged CamelCase words
    line = re.sub(r"(?<=[A-Za-z])(?=[0-9])", " ", line)       # split letters from digits
    return line.strip()


def parse_transaction_line(line: str):
    tokens = clean_row(line).split()
    if len(tokens) < 4 or tokens[0] not in DAYS:
        return None
    day = tokens[0]
    rest = tokens[1:]
    try:
        balance, credit, debit = float(rest[-1]), float(rest[-2]), float(rest[-3])
    except (ValueError, IndexError):
        return None
    middle = rest[:-3]
    txn_type = middle[0] if middle and middle[0] in ("Debit", "Credit", "None") else None
    category_tokens = middle[1:] if txn_type else middle
    category = " ".join(category_tokens) if category_tokens else "Uncategorized"
    return {"day": day, "type": txn_type or "None", "category": category,
            "debit": debit, "credit": credit, "balance": balance}


def load_bank_transactions() -> pd.DataFrame:
    path = os.path.join(PROCESSED_DIR, "bank_statement.txt")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    records = [parse_transaction_line(l) for l in lines]
    records = [r for r in records if r]
    df = pd.DataFrame(records)
    return df[df["type"] == "Debit"].reset_index(drop=True)  # focus on expenses


def detect_transaction_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- Statistical Analysis: per-category z-score ---
    df["category_mean"] = df.groupby("category")["debit"].transform("mean")
    df["category_std"] = df.groupby("category")["debit"].transform("std").fillna(0)
    df["zscore"] = np.where(
        df["category_std"] > 0,
        (df["debit"] - df["category_mean"]) / df["category_std"],
        0,
    )
    df["stat_anomaly"] = df["zscore"].abs() > 3

    # --- Isolation Forest ---
    category_dummies = pd.get_dummies(df["category"], prefix="cat")
    features = pd.concat([df[["debit"]], category_dummies], axis=1)
    iso = IsolationForest(contamination=0.05, random_state=42)
    df["isoforest_anomaly"] = iso.fit_predict(features) == -1
    df["isoforest_score"] = -iso.score_samples(features)  # higher = more anomalous

    # --- Autoencoder substitute: PCA reconstruction error ---
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)
    n_components = min(3, scaled.shape[1])
    pca = PCA(n_components=n_components, random_state=42)
    reduced = pca.fit_transform(scaled)
    reconstructed = pca.inverse_transform(reduced)
    reconstruction_error = np.mean((scaled - reconstructed) ** 2, axis=1)
    df["autoencoder_reconstruction_error"] = reconstruction_error
    threshold = np.percentile(reconstruction_error, 95)
    df["autoencoder_anomaly"] = reconstruction_error > threshold

    df["flagged_by_n_methods"] = (
        df["stat_anomaly"].astype(int)
        + df["isoforest_anomaly"].astype(int)
        + df["autoencoder_anomaly"].astype(int)
    )
    return df.sort_values("flagged_by_n_methods", ascending=False)


# ---------------------------------------------------------------
# PART 2: Real inflation/currency panel anomaly detection
# ---------------------------------------------------------------
def detect_inflation_anomalies() -> pd.DataFrame:
    df = pd.read_csv(os.path.join(RAW_DIR, "annual_report.csv"))
    df = df.copy()

    # --- Statistical Analysis: per-country z-score on inflation ---
    df["country_mean_inflation"] = df.groupby("country")["inflation_annual_cpi"].transform("mean")
    df["country_std_inflation"] = df.groupby("country")["inflation_annual_cpi"].transform("std").fillna(0)
    df["inflation_zscore"] = np.where(
        df["country_std_inflation"] > 0,
        (df["inflation_annual_cpi"] - df["country_mean_inflation"]) / df["country_std_inflation"],
        0,
    )
    df["stat_anomaly"] = df["inflation_zscore"].abs() > 3

    # --- Isolation Forest on inflation + exchange rate jointly ---
    features = df[["inflation_annual_cpi", "exch_usd"]].fillna(0)
    iso = IsolationForest(contamination=0.03, random_state=42)
    df["isoforest_anomaly"] = iso.fit_predict(features) == -1

    df["flagged_by_n_methods"] = df["stat_anomaly"].astype(int) + df["isoforest_anomaly"].astype(int)
    anomalies = df[df["flagged_by_n_methods"] > 0].sort_values(
        "inflation_annual_cpi", ascending=False
    )
    return anomalies[["country", "year", "inflation_annual_cpi", "exch_usd",
                       "banking_crisis", "inflation_zscore", "stat_anomaly",
                       "isoforest_anomaly", "flagged_by_n_methods"]]


# ---------------------------------------------------------------
# PART 3: Brief's own illustrative example, reproduced
# ---------------------------------------------------------------
def brief_example_check():
    previous_month = 10_00_000   # Rs. 10 Lakh
    current_month = 38_00_000    # Rs. 38 Lakh
    pct_change = ((current_month - previous_month) / previous_month) * 100
    alert = pct_change > 50  # simple statistical threshold rule
    return {
        "previous_month_expense": previous_month,
        "current_month_expense": current_month,
        "pct_change": round(pct_change, 1),
        "ai_alert": "Unusual expense increase detected." if alert else "No anomaly detected.",
    }


def main():
    print("[Module 11] Detecting anomalies in real bank transaction data ...")
    txns = load_bank_transactions()
    txn_anomalies = detect_transaction_anomalies(txns)
    txn_path = os.path.join(OUT_DIR, "bank_transaction_anomalies.csv")
    txn_anomalies.to_csv(txn_path, index=False)
    n_flagged = (txn_anomalies["flagged_by_n_methods"] > 0).sum()
    print(f"[Module 11] {len(txns)} debit transactions analyzed; "
          f"{n_flagged} flagged by at least one method.")

    print("\n[Module 11] Detecting anomalies in real inflation/currency panel data ...")
    inflation_anomalies = detect_inflation_anomalies()
    inflation_path = os.path.join(OUT_DIR, "inflation_anomalies.csv")
    inflation_anomalies.to_csv(inflation_path, index=False)
    print(f"[Module 11] {len(inflation_anomalies)} country-year records flagged as anomalies.")
    print("[Module 11] Top 5 flagged records:")
    print(inflation_anomalies.head(5)[["country", "year", "inflation_annual_cpi", "banking_crisis"]]
          .to_string(index=False))

    example = brief_example_check()
    print(f"\n[Module 11] Brief's example reproduced: "
          f"Rs. {example['previous_month_expense']:,} -> Rs. {example['current_month_expense']:,} "
          f"({example['pct_change']}% change) -> {example['ai_alert']}")

    report = {
        "bank_transactions": {
            "total_debit_transactions": int(len(txns)),
            "flagged_transactions": int(n_flagged),
            "algorithms_used": ["statistical_zscore", "isolation_forest", "pca_reconstruction_error"],
        },
        "inflation_panel": {
            "total_records": 1059,
            "flagged_records": int(len(inflation_anomalies)),
            "algorithms_used": ["statistical_zscore", "isolation_forest"],
        },
        "brief_example_reproduction": example,
    }
    report_path = os.path.join(OUT_DIR, "anomaly_detection_report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n[Module 11] Transaction anomalies: {txn_path}")
    print(f"[Module 11] Inflation anomalies: {inflation_path}")
    print(f"[Module 11] Summary report: {report_path}")


if __name__ == "__main__":
    main()
