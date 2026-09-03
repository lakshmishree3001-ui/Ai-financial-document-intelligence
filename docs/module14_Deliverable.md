Module 14 Deliverable — Deployment & Document Monitoring

1. Objective
Deploy the AI financial document system and add application monitoring.

2. Database Deployment - SQLite (Built and Verified)
The project used flat CSV/JSON files through Modules 3-13. This module adds a real relational database (app/database.py) - SQLite, built into Python, no server or internet required:
●	documents table - mirrors data/raw/dataset_catalog.csv
●	qa_log table - every question asked through the Q&A API (doubles as monitoring data)
●	request_log table - every API request: endpoint, status, response time
Verified by running python database.py:
"Migrated 12 documents from CSV into SQLite: .../data/app.db" "Verified: 12 rows readable from the documents table." "Sample row: {'document_id': 'DOC001', 'filename': 'annual_report.csv', 'document_type': 'Annual Report', ...}"
api.py's Upload API (GET /api/documents) now reads from this database instead of the CSV directly - a genuine, working database deployment, not just a design note. For a larger production deployment, this SQLite file would be swapped for a managed database (AWS RDS / Azure SQL / Google Cloud SQL) - only database.py would need to change; every caller (core.py, api.py) stays the same.

3. Application Monitoring (Built and Verified)
api.py now includes:
●	A monitoring middleware that logs every request (endpoint, HTTP status, latency in ms) to the request_log table automatically.
●	GET /health - a liveness probe endpoint, the standard mechanism Docker, AWS/Azure/GCP load balancers, and Streamlit Cloud all use to check if an app is alive.
●	GET /api/monitoring - returns total requests, error rate, average latency, and the 5 most recent Q&A interactions.
●	Every question asked through the Q&A API is now also logged to qa_log automatically.
Verified with simulated requests:
{   "total_requests": 3,   "error_requests": 1,   "error_rate_pct": 33.3,   "avg_latency_ms": 118.57,   "recent_qa": [{"question": "What was the revenue?", "answer": "Rs. 850 crore", ...}] }

4. Vector Database Deployment (Design Note)
Module 10's retrieval system currently uses an in-memory TF-IDF vector store (joblib files), sized for this project's ~939 chunks. For a larger-scale cloud deployment, this would be swapped for a managed/deployed vector database - e.g. Pinecone (managed cloud), Weaviate Cloud, or a self-hosted ChromaDB/FAISS service. None of these could be installed in this offline sandbox (same restriction as Modules 5-11), so the current TF-IDF store remains the working implementation; the swap point is isolated to core.py's _load_rag() function, so upgrading later doesn't require changing api.py or dashboard.py.

5. Deployment Instructions (Run These Yourself)
All of the following need to be run BY YOU, on your own machine, with your own internet access and (for cloud options) your own account. None of this can be executed from within this development sandbox.
Option A - Docker (local container, fastest to verify)
●	Install Docker Desktop (docker.com) if you don't have it.
●	In a terminal: cd into the app/ folder.
●	Run: docker compose up --build
●	API available at http://localhost:8000 (docs at /docs, health check at /health). Dashboard at http://localhost:8501.
Option B - Streamlit Community Cloud (simplest path to a genuinely LIVE public app)
●	Create a free GitHub account (github.com) if you don't have one, and a free Streamlit Community Cloud account (share.streamlit.io) - sign in there with your GitHub account.
●	Push this project (the whole AI_Financial_Document_Intelligence folder) to a new GitHub repository.
●	On share.streamlit.io, click "New app", select your repository, and set the main file path to app/dashboard.py.
●	Click Deploy. In a few minutes you'll get a public URL (e.g. https://your-app.streamlit.app) that anyone, including your mentor, can open directly - this is the "Live financial document AI application" the brief asks for.
Option C - AWS (API: Elastic Beanstalk or ECS; simplest is Elastic Beanstalk)
●	Create an AWS account and install the AWS CLI + EB CLI (pip install awsebcli).
●	From the app/ folder: eb init (choose Python platform), then eb create financial-doc-api.
●	EB uses api.py's existing Dockerfile-compatible setup; set the start command to uvicorn api:app --host 0.0.0.0 --port 8000 in the EB console if not auto-detected.
●	For the database, use AWS RDS (PostgreSQL) instead of the local SQLite file for a multi-user deployment - swap the connection in database.py.
Option D - Azure (API: Azure App Service)
●	Create an Azure account and install the Azure CLI.
●	az webapp up --name financial-doc-api --runtime PYTHON:3.11 from the app/ folder.
●	Configure the startup command in the Azure Portal: uvicorn api:app --host 0.0.0.0 --port 8000.
●	For the database, use Azure SQL Database or Azure Database for PostgreSQL for a multi-user deployment.
Option E - Google Cloud (API: Cloud Run, container-based - uses the same Dockerfile)
●	Create a GCP account and install the gcloud CLI.
●	From the app/ folder: gcloud run deploy financial-doc-api --source . --port 8000
●	Cloud Run builds directly from the Dockerfile already provided - no extra config needed.
●	For the database, use Cloud SQL for a multi-user deployment.

6. Folder Structure Produced
app/    database.py         (SQLite database layer - Module 14)    Dockerfile           (container image definition)    docker-compose.yml   (runs API + dashboard together)    api.py               (updated: monitoring middleware, /health, /api/monitoring, DB-backed document list)    README.md            (updated: database, monitoring, and deployment sections) data/    app.db               (the actual SQLite database file, created by running database.py)

7. Deliverable
Live Financial Document AI Application — a deployment-ready platform: a real SQLite database (verified working), application-monitoring middleware and endpoints (verified working with simulated traffic), a Dockerfile + docker-compose.yml for one-command local containerized deployment, and complete step-by-step instructions for 5 deployment paths (Docker, Streamlit Community Cloud, AWS, Azure, Google Cloud) for the student to execute using their own accounts and internet access.

8. Status
Completed 