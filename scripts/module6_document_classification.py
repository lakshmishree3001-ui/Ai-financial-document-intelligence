"""
MODULE 6 - Financial Document Classification
------------------------------------------------
Objective : Automatically classify financial documents.

Workflow (per project brief):
    Financial Document -> Text Extraction -> Feature Extraction -> ML Model -> Document Category

Categories (per project brief):
    Annual Report, Balance Sheet, Income Statement, Cash Flow Statement,
    Invoice, Bank Statement, Earnings Report

Algorithms (per project brief):
    Logistic Regression, Random Forest, SVM, XGBoost, BERT/Transformers

TOOLING NOTE (same transparency pattern as Module 5):
This environment has no internet access, so:
    - XGBoost is not installed here (no offline package mirror available)
      and could not be added.
    - BERT/Transformers models (e.g. HuggingFace) require downloading
      pretrained weights from the internet, which is also not possible
      here.
Implemented instead: Logistic Regression, Random Forest, and SVM (all
from scikit-learn, fully offline) - 3 of the 5 requested algorithms,
which is enough to build and evaluate a working classifier and compare
algorithm performance. The script is structured so that adding
XGBoost or a BERT-based classifier later is a matter of adding one
more entry to the MODELS dict / a new feature pipeline - no other
code needs to change.

DATASET SIZE NOTE:
The current dataset has 12 documents across 6 of the 7 required
categories (no "Earnings Report" example exists yet, so the model
cannot learn or predict that class). With only 12 samples total, a
conventional train/test split would leave several classes completely
unseen in one split or the other. Instead, this script:
    1. Trains each model on the full dataset (fit and report training
       accuracy - shows the model CAN learn the current data).
    2. Evaluates with Leave-One-Out Cross-Validation (LOOCV), which is
       the standard, honest way to estimate generalization on very
       small datasets (each document is held out and predicted once).
This is disclosed clearly in the deliverable so results aren't
mistaken for large-scale production accuracy.

Feature extraction: TF-IDF over the cleaned document text (Module 4/5
output). For the one CSV document (annual_report.csv, which has no
free text), a lightweight pseudo-text representation is built from its
column names, so it still has features to classify on.

Output:
    data/models/tfidf_vectorizer.joblib
    data/models/best_model.joblib              (highest LOOCV accuracy)
    data/models/classification_report.csv       (per-model comparison)
    data/models/predictions.csv                 (per-document predictions)
"""

import os
import csv
import json
import joblib
import numpy as np
import pandas as pd

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.svm import SVC
from sklearn.model_selection import LeaveOneOut, cross_val_predict
from sklearn.metrics import accuracy_score, classification_report

BASE_DIR = os.path.join(os.path.dirname(__file__), "..")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
MODELS_DIR = os.path.join(BASE_DIR, "data", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

CATALOG_PATH = os.path.join(RAW_DIR, "dataset_catalog.csv")

ALL_CATEGORIES = [
    "Annual Report", "Balance Sheet", "Income Statement",
    "Cash Flow Statement", "Invoice", "Bank Statement", "Earnings Report",
]

MODELS = {
    "logistic_regression": LogisticRegression(max_iter=1000, random_state=42),
    "random_forest": RandomForestClassifier(n_estimators=200, random_state=42),
    "svm": SVC(kernel="linear", probability=True, random_state=42),
}

# Algorithms requested in the brief but not runnable offline in this
# environment - kept here purely for transparent reporting.
UNAVAILABLE_ALGORITHMS = {
    "xgboost": "Package not installed and no internet access to install it in this environment.",
    "bert_transformers": "Requires downloading pretrained model weights (e.g. HuggingFace hub), which needs internet access not available here.",
}


def load_csv_pseudo_text(csv_path: str) -> str:
    """CSV documents have no free text - build a lightweight text
    representation from column names + a few sample values so the
    document still has features for the text-based classifier."""
    df = pd.read_csv(csv_path, nrows=20)
    columns_text = " ".join(str(c) for c in df.columns)
    sample_text = " ".join(df.astype(str).values.flatten()[:100])
    return f"{columns_text} {columns_text} {sample_text}"  # weight columns higher


def load_dataset():
    catalog = pd.read_csv(CATALOG_PATH)
    texts, labels, filenames = [], [], []

    for _, row in catalog.iterrows():
        filename = row["filename"]
        doc_type = row["document_type"]
        if doc_type not in ALL_CATEGORIES:
            continue  # skip Unclassified, if any

        if filename.lower().endswith(".pdf"):
            txt_path = os.path.join(PROCESSED_DIR, os.path.splitext(filename)[0] + ".txt")
            if not os.path.exists(txt_path):
                continue
            with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        elif filename.lower().endswith(".csv"):
            csv_path = os.path.join(RAW_DIR, filename)
            text = load_csv_pseudo_text(csv_path)
        else:
            continue

        texts.append(text)
        labels.append(doc_type)
        filenames.append(filename)

    return filenames, texts, labels


def main():
    filenames, texts, labels = load_dataset()
    print(f"[Module 6] Loaded {len(texts)} documents across "
          f"{len(set(labels))} categories: {sorted(set(labels))}")

    missing = set(ALL_CATEGORIES) - set(labels)
    if missing:
        print(f"[Module 6] NOTE: no training examples for: {sorted(missing)} "
              f"- the model cannot learn or predict these categories yet.")

    # ---- Feature extraction (TF-IDF) ----
    vectorizer = TfidfVectorizer(
        lowercase=True, stop_words="english",
        max_features=2000, ngram_range=(1, 2), min_df=1,
    )
    X = vectorizer.fit_transform(texts)
    y = np.array(labels)

    print(f"[Module 6] TF-IDF feature matrix: {X.shape[0]} documents x {X.shape[1]} features")

    # ---- Train + evaluate each model ----
    results_rows = [["algorithm", "training_accuracy", "loocv_accuracy", "notes"]]
    loocv = LeaveOneOut()
    model_scores = {}

    for name, model in MODELS.items():
        model.fit(X, y)
        train_acc = accuracy_score(y, model.predict(X))

        try:
            loo_preds = cross_val_predict(model, X, y, cv=loocv)
            loo_acc = accuracy_score(y, loo_preds)
        except Exception as e:
            loo_preds = None
            loo_acc = None

        model_scores[name] = loo_acc if loo_acc is not None else train_acc
        results_rows.append([
            name, f"{train_acc:.3f}",
            f"{loo_acc:.3f}" if loo_acc is not None else "N/A",
            "Trained on full 12-doc dataset; LOOCV = generalization estimate",
        ])
        print(f"[{name}] training_accuracy={train_acc:.3f}  "
              f"loocv_accuracy={loo_acc if loo_acc is not None else 'N/A'}")

    for algo, reason in UNAVAILABLE_ALGORITHMS.items():
        results_rows.append([algo, "N/A", "N/A", f"NOT RUN - {reason}"])
        print(f"[{algo}] NOT RUN - {reason}")

    # ---- Pick best model by LOOCV accuracy ----
    best_name = max(model_scores, key=model_scores.get)
    best_model = MODELS[best_name]
    print(f"\n[Module 6] Best model by LOOCV accuracy: {best_name} "
          f"({model_scores[best_name]:.3f})")

    # ---- Save artifacts ----
    joblib.dump(vectorizer, os.path.join(MODELS_DIR, "tfidf_vectorizer.joblib"))
    joblib.dump(best_model, os.path.join(MODELS_DIR, "best_model.joblib"))
    with open(os.path.join(MODELS_DIR, "model_type.txt"), "w") as f:
        f.write(best_name)

    report_path = os.path.join(MODELS_DIR, "classification_report.csv")
    with open(report_path, "w", newline="") as f:
        csv.writer(f).writerows(results_rows)

    # ---- Per-document predictions (using the best model, full-data fit) ----
    preds = best_model.predict(X)
    pred_rows = [["filename", "true_category", "predicted_category", "correct"]]
    for fname, true_label, pred_label in zip(filenames, y, preds):
        pred_rows.append([fname, true_label, pred_label, "YES" if true_label == pred_label else "NO"])

    pred_path = os.path.join(MODELS_DIR, "predictions.csv")
    with open(pred_path, "w", newline="") as f:
        csv.writer(f).writerows(pred_rows)

    # ---- Full classification report (best model, LOOCV predictions) ----
    loo_preds = cross_val_predict(best_model, X, y, cv=loocv)
    report_text = classification_report(y, loo_preds, zero_division=0)
    with open(os.path.join(MODELS_DIR, "loocv_classification_report.txt"), "w") as f:
        f.write(f"Best model: {best_name}\n\n")
        f.write("Leave-One-Out Cross-Validation Classification Report\n")
        f.write(report_text)

    print(f"\n[Module 6] Vectorizer + model saved to: {MODELS_DIR}")
    print(f"[Module 6] Comparison report: {report_path}")
    print(f"[Module 6] Predictions: {pred_path}")


if __name__ == "__main__":
    main()
