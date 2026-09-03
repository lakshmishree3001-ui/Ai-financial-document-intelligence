# AI Financial Document Intelligence & Analysis System — Ledger

> **Live Demo:** 🌐 [https://ledger-financial-intelligence.onrender.com](https://ledger-financial-intelligence.onrender.com)

## Project Overview

**Ledger** is a full-stack, AI-powered financial document intelligence platform that processes and analyzes financial documents such as annual reports, balance sheets, income statements, bank statements, invoices, and financial research reports.

The system uses AI, Machine Learning, NLP, OCR, and RAG (Retrieval-Augmented Generation) to extract financial information, classify documents, detect anomalies, and generate meaningful insights — all accessible through a secure, authenticated web application.

---

## 🚀 Live Application

| Item | Link |
|---|---|
| 🌐 Live App | [https://ledger-financial-intelligence.onrender.com](https://ledger-financial-intelligence.onrender.com) |
| 📦 GitHub Repo | [lakshmishree3001-ui/AI-Financial-Document-Intelligence](https://github.com/lakshmishree3001-ui/AI-Financial-Document-Intelligence) |
| 🐳 Deployment | Docker on Render (Free Tier) |

---

## Project Objectives

- Process financial documents (PDF, CSV, images)
- Extract text and financial information via OCR
- Classify documents using trained ML models
- Analyze financial statements (profitability, liquidity, leverage)
- Generate concise AI-powered document summaries
- Answer questions from financial documents using RAG
- Detect financial trends and anomalies
- Generate AI-powered financial insights and risk assessments
- Provide a secure, authenticated web interface

---

## Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | HTML5, CSS3, Vanilla JavaScript |
| **Backend** | FastAPI, Uvicorn, Python 3.11 |
| **Auth** | JWT (PyJWT), Argon2 password hashing |
| **ML / NLP** | Scikit-learn, Pandas, NumPy, Joblib |
| **Document Processing** | pdfplumber, PyPDF, pytesseract, Pillow |
| **Database** | SQLite (via Python sqlite3) |
| **Containerization** | Docker |
| **Deployment** | Render.com (Docker, Free Tier) |

---

## Module Progress

### Module 1 — Project Overview & Architecture
**Status: Completed**
- Project objective defined
- System architecture designed
- Architecture diagram created

---

### Module 2 — Environment Setup
**Status: Completed**
- Python virtual environment created
- Required Python libraries installed
- Jupyter Notebook configured
- Tesseract OCR and Docker installed

---

### Module 3 — Financial Document Collection
**Status: Completed**
- Financial documents collected and organized by type
- Raw dataset catalog prepared

Document types: Annual reports, Balance sheets, Income statements, Cash flow statements, Invoices, Bank statements, Financial research

---

### Module 4 — Document Processing & OCR
**Status: Completed**
- PDF text extraction (digital and scanned)
- OCR processing via Tesseract
- Page segmentation and table identification
- Financial documents converted to processable formats

---

### Module 5 — Financial Text Preprocessing & Feature Extraction
**Status: Completed**
- Cleaned unnecessary characters and OCR artifacts
- Sentence segmentation and tokenization
- Stop-word removal and Named Entity Recognition (NER)
- Extraction of: company names, dates, currencies, percentages, financial metrics

---

### Module 6 — Financial Document Classification
**Status: Completed**
- Feature engineering from processed financial text
- ML classification model trained and evaluated
- Best model selected and saved

---

### Module 7 — Financial Document Analysis & Information Extraction
**Status: Completed**
- Key financial entities and metrics extracted
- Structured data prepared for downstream modules
- Verified: Revenue = Rs. 850 crore, Net Income = Rs. 105 crore

---

### Module 8 — Financial Statement Analysis
**Status: Completed**
- Profitability analysis (revenue growth, profit margin, net profit)
- Liquidity analysis (current ratio, cash position)
- Leverage analysis (debt-to-equity ratio, total debt)

---

### Module 9 — Financial Document Summarization
**Status: Completed**
- Generated concise 5-category executive summaries
- Key financial details preserved across all document types

---

### Module 10 — Financial Document Q&A using RAG
**Status: Completed**
- Document text chunked and indexed with TF-IDF vectors
- Cosine similarity-based retrieval
- Extractive answer generation from retrieved passages
- Live Q&A via `/api/qa` endpoint

---

### Module 11 — Financial Trend & Anomaly Detection
**Status: Completed**
- Detected sudden revenue changes and unusual expenses
- Algorithms: Isolation Forest, Statistical Analysis, Autoencoder

---

### Module 12 — AI Financial Insights Engine
**Status: Completed**
- Financial performance indicators analyzed
- Positive trends and risk factors identified
- Overall financial risk rating generated (Low / Medium / High)

---

### Module 13 — API & Financial Dashboard Development
**Status: Completed**

**7 APIs built (FastAPI):**

| API | Endpoint |
|---|---|
| Upload API | `POST /api/upload`, `GET /api/documents` |
| OCR API | `GET /api/ocr/{filename}` |
| Classification API | `GET /api/classify/{filename}` |
| Metrics API | `GET /api/metrics` |
| Summary API | `GET /api/summary/{filename}` |
| Q&A API | `POST /api/qa` |
| Insights API | `GET /api/insights` |

**9 Dashboard components:** Document upload, Classification, Financial KPIs, Revenue charts, Profit charts, Financial ratios, AI summary, AI insights, Document Q&A

---

### Module 14 — Database Deployment & Application Monitoring
**Status: Completed**

**Database (SQLite):**
- `app/database.py` — full SQLite layer using Python's built-in sqlite3
- `documents` table — mirrors the document catalog
- `qa_log` table — every Q&A interaction logged
- `request_log` table — every API request logged (endpoint, status, latency)

**Application Monitoring:**
- HTTP middleware logs every request automatically to `request_log`
- `GET /health` — liveness probe (used by Docker and Render)
- `GET /api/monitoring` — returns total requests, error rate, avg latency, recent Q&A

**Deployment:**
- `app/Dockerfile` — containerizes FastAPI backend
- `Dockerfile.webapp` — containerizes the full web application
- `app/docker-compose.yml` — runs API + dashboard together locally
- `render.yaml` — Render.com deployment config (Docker, free tier)

---

### Module 15 — Final Capstone: Live Deployment & User Authentication
**Status: Completed**

**Live Deployment:**
- Deployed on [Render.com](https://render.com) using Docker (free tier)
- Live URL: **[https://ledger-financial-intelligence.onrender.com](https://ledger-financial-intelligence.onrender.com)**
- Auto-deploys on every push to the `master` branch via GitHub

**Authentication & Security:**
- Full user registration and login system
- Argon2id password hashing (OWASP recommended)
- JWT-based session management (HTTP-only cookies + Authorization header)
- Per-user document isolation — users only access their own uploaded documents
- All API routes protected via FastAPI dependency injection
- Endpoints: `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`

**Full-Stack Web Application (`webapp/`):**
- `main.py` — FastAPI server serving both frontend and all APIs
- `index.html` — Single-page application (no frontend framework)
- `static/app.js` — All client-side logic (upload, charts, Q&A, auth)
- `static/style.css` — Full custom styling

**End-to-End Automated Pipeline:**
Every uploaded document automatically runs:
> Text Extraction → Preprocessing → Classification → Metric Extraction → Financial Ratios → Summarization → RAG Indexing → Anomaly Detection → Insights Generation → Persist to DB

---

## Project Structure

```
AI-Financial-Document-Intelligence/
├── webapp/                   # Frontend + web server
│   ├── main.py               # FastAPI web server (all routes)
│   ├── index.html            # Single-page web application
│   ├── static/
│   │   ├── app.js            # Client-side JavaScript
│   │   └── style.css         # Styling
│   └── requirements.txt
│
├── app/                      # Backend core
│   ├── api.py                # REST API layer
│   ├── auth.py               # Authentication (JWT + Argon2)
│   ├── core.py               # Business logic
│   ├── database.py           # SQLite database layer
│   ├── pipeline.py           # End-to-end document pipeline
│   └── dashboard.py          # Streamlit dashboard
│
├── scripts/                  # AI/ML processing modules (3-12)
│
├── data/
│   └── uploads/              # User-uploaded documents
│
├── docs/                     # Module deliverables & architecture
├── Dockerfile.webapp         # Docker image for Render deployment
├── render.yaml               # Render.com deployment configuration
├── .env.example              # Environment variable template
└── requirements.txt          # Full dependency list
```

---

## Quick Start (Local)

```bash
# 1. Clone the repository
git clone https://github.com/lakshmishree3001-ui/AI-Financial-Document-Intelligence.git
cd AI-Financial-Document-Intelligence

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows

# 3. Install dependencies
pip install -r webapp/requirements.txt

# 4. Set environment variables
copy .env.example .env
# Edit .env with your JWT_SECRET

# 5. Run the app
cd webapp
uvicorn main:app --reload --host 0.0.0.0 --port 8000
# Open http://localhost:8000
```

---

## Docker (Local)

```bash
docker build -f Dockerfile.webapp -t ledger-app .
docker run -p 8000:8000 ledger-app
# Open http://localhost:8000
```

---

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `JWT_SECRET` | Secret key for signing JWT tokens | Built-in fallback |
| `JWT_ALGORITHM` | JWT signing algorithm | `HS256` |
| `TOKEN_EXPIRE_HOURS` | Session duration in hours | `24` |


## Project Overview

This project is an AI-powered system designed to process and analyze financial documents such as annual reports, balance sheets, income statements, bank statements, invoices, and financial research reports.

The system will use AI, Machine Learning, NLP, OCR, RAG, and data analytics to extract financial information and generate useful insights.

## Project Objectives

- Process financial documents
- Extract text and financial information
- Analyze financial statements
- Generate document summaries
- Answer questions from financial documents
- Detect financial trends and anomalies
- Generate AI-powered financial insights
- Provide an interactive financial analytics dashboard

## Technology Stack

- Python
- Jupyter Notebook
- VS Code
- Pandas
- NumPy
- Scikit-learn
- spaCy
- NLTK
- PyPDF
- pdfplumber
- Tesseract OCR
- Transformers
- Sentence Transformers
- FAISS
- FastAPI
- Streamlit
- PostgreSQL
- Docker

## Current Progress

### Module 1 — Project Overview & Architecture
Status: Completed

- Project objective defined
- System architecture designed
- Architecture diagram created

### Module 2 — Environment Setup
Status: Completed

- Python virtual environment created
- Required Python libraries installed
- Jupyter Notebook installed
- Tesseract OCR installed
- PostgreSQL installed
- Docker installed

### Module 3 — Financial Document Collection
Status: Completed 

- Financial documents collected for AI processing
- Raw financial documents organized by document type
- Raw financial document dataset prepared

Document types include:
- Annual reports
- Balance sheets
- Income statements
- Cash flow statements
- Invoices
- Bank statements
- Financial research documents

### Module 4 — Document Processing & OCR
Status: Completed 

- PDF text extraction performed
- Image-to-text processing performed
- OCR processing implemented
- Page segmentation handled
- Tables identified
- Document text cleaned
- Financial documents converted into processed/usable formats

## Module 5 – Financial Text Preprocessing & Feature Extraction
Status: Completed

- Cleaned unnecessary characters and OCR artifacts.
- Performed sentence segmentation and tokenization.
- Removed stop words.
- Applied Named Entity Recognition (NER).
- Extracted financial terminology.
- Extracted financial entities such as company names, dates, currencies, percentages, and financial metrics.

## Module 6 – Financial Document Classification
Status: Completed

- Prepared features from the processed financial text.
- Created training and testing datasets.
- Trained machine learning classification models.
- Compared model performance using evaluation metrics.
- Selected the best-performing model.
- Saved the trained model for future use.

## Module 7 – Financial Document Analysis & Information Extraction
Status: Completed

- Processed classified financial documents.
- Extracted key financial information and relevant entities.
- Identified important financial metrics and values.
- Structured the extracted information for further processing.
- Prepared the extracted data for subsequent modules.

## Module 8 – Financial Statement Analysis
Status: Completed

- Profitability analysis
- Revenue growth
- Profit margin
- Net profit
- Liquidity analysis
- Current ratio
- Cash position
- Leverage analysis
- Debt-to-equity ratio
- Total debt

## Module 9 – Financial Document Summarization
Status: Completed

- Processed lengthy financial documents.
- Identified important financial information.
- Generated concise document summaries.
- Preserved key financial details in the summaries.

## Module 10 – Financial Document Question Answering using RAG
Status: Completed

 Uploaded financial documents.
- Extracted and chunked document text.
- Generated embeddings for document chunks.
- Stored embeddings in a vector database.
- Retrieved relevant information for user questions.
- Used an LLM to generate document-based answers.

## Module 11 – Financial Trend & Anomaly Detection
Status: Completed

- Analyzed financial trends.
- Detected sudden revenue changes.
- Identified unusual expenses.
- Detected abnormal transactions.
- Identified unexpected profit changes.
- Detected significant debt increases.

Algorithms Used:
- Isolation Forest
- Statistical Analysis
- Autoencoder

## Module 12 – AI Financial Insights Engine
Status: Completed 

- Analyzed financial performance indicators.
- Generated meaningful financial insights.
- Identified positive financial trends.
- Highlighted potential financial risks.
- Generated an overall financial risk assessment.

Technologies Used
- LLM
- NLP
- RAG

## Module 13 – API & Financial Dashboard Development
Status: Completed

APIs Developed
- Upload API
- OCR API
- Classification API
- Metrics API
- Summary API
- Q&A API
- Insights API

Dashboard Components
- Document upload
- Document classification
- Financial KPIs
- Revenue charts
- Profit charts
- Financial ratios
- AI summary
- AI insights
- Document Q&A

 Technologies Used
- FastAPI
- Streamlit
- Plotly
