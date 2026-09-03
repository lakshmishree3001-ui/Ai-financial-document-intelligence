# Ledger — AI Financial Document Intelligence (Web App)

A real, professionally designed web application — not a dashboard.
Upload a financial document and it's read, classified, extracted,
analyzed, and made askable, live, through a custom-built interface.

This is the recommended way to present this project: `app/dashboard.py`
(Streamlit) still exists and works, but this `webapp/` is a from-scratch
HTML/CSS/JS frontend served by a FastAPI backend, with full control
over design - built for anyone opening the link, not just for
internal/admin use.

## What's different from the Streamlit dashboard

| | Streamlit dashboard (`app/`) | Web app (`webapp/`) |
|---|---|---|
| Look | Default Streamlit widget styling | Custom-designed, distinctive UI |
| Audience | Fine for internal/demo use | Built to be shown to anyone |
| Deploy target | Streamlit Community Cloud | Render.com (or any Docker host) |
| Frontend | Python-generated widgets | Real HTML/CSS/JS you fully control |

Both use the exact same tested backend (`app/core.py`) - same pipeline,
same accuracy, same results. This is a presentation upgrade, not a
different product.

## Run it locally

```bash
cd webapp
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** in your browser. That's the whole app -
one URL, no separate dashboard/API split to manage.

If you're testing OCR on a scanned PDF, you'll also need Tesseract and
Poppler installed locally:
- macOS: `brew install tesseract poppler`
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr poppler-utils`
- Windows: install Tesseract from its official installer, and Poppler
  via `conda install poppler` or a prebuilt binary on PATH.

## Deploy it for real — Render.com (recommended)

Render's free tier runs a real, always-buildable Python web service
(unlike Streamlit Community Cloud, which only runs Streamlit apps) -
this is the right host for a custom FastAPI app like this one.

1. Push this whole project (including `Dockerfile.webapp` and
   `render.yaml` at the repo root) to GitHub.
2. Go to **render.com**, sign up (free, no credit card needed for the
   free tier), and click **New > Blueprint**.
3. Connect your GitHub repo. Render will detect `render.yaml`
   automatically and configure everything - Docker build, health
   check, port - with no manual setup.
4. Click **Apply**. The first build takes a few minutes (it installs
   Tesseract/Poppler via the Dockerfile, then Python dependencies).
5. You'll get a live URL like `https://ledger-financial-intelligence.onrender.com` -
   this is your real, public, professional web application.

**Free tier note:** Render's free web services spin down after 15
minutes of inactivity and take ~30-50 seconds to wake up on the next
visit - completely normal for a free tier, not a bug. Upgrading to a
paid plan (or pinging the health endpoint periodically) keeps it warm.

**Data persistence note:** the free tier's filesystem resets on
redeploy, so uploaded documents and the SQLite database don't persist
across deploys (they DO persist across normal usage/wake-ups, just not
across a fresh deploy). For a permanent production deployment, add a
Render persistent disk or an external database - noted here as a next
step, not implemented, since it's beyond this project's scope.

## Deploy it - alternative: plain Docker (any host)

```bash
docker build -f Dockerfile.webapp -t ledger-webapp .
docker run -p 8000:8000 ledger-webapp
```

Works identically on any host that runs containers - Railway, Fly.io,
Google Cloud Run, AWS App Runner, a VPS, etc.

## API

The same endpoints as the Module 13/14 API are available under `/api/*`
(see `docs/API_Documentation.docx`), plus this app serves the frontend
itself at `/`. `/health` and `/api/monitoring` work the same way too.

## Design

See the design system directly in `static/style.css` - a "ledger"
visual language (deep green, warm paper background, serif headlines,
monospace figures) chosen to match the subject matter: financial
statements are ledgers, so the interface reads like one.
