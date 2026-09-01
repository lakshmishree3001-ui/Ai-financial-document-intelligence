# Financial Document Intelligence Platform (Module 13)

Interactive API + dashboard on top of Modules 3-12 of this project.

## Structure

```
app/
  core.py          Business logic (no FastAPI/Streamlit/Plotly dependency - tested standalone)
  api.py            FastAPI backend - 7 required APIs
  dashboard.py      Streamlit dashboard - 9 required components
  requirements.txt  Dependencies
```

## Setup (run this on a machine with internet access)

```bash
cd app
pip install -r requirements.txt
```

## Running the API

```bash
uvicorn api:app --reload --port 8000
```

Then open **http://localhost:8000/docs** for the interactive Swagger UI,
which lists and lets you try all 7 APIs:

| API | Endpoint |
|---|---|
| Upload API | `POST /api/upload`, `GET /api/documents` |
| OCR API | `GET /api/ocr/{filename}` |
| Classification API | `GET /api/classify/{filename}` |
| Metrics API | `GET /api/metrics?filename=...` |
| Summary API | `GET /api/summary/{filename}` |
| Q&A API | `POST /api/qa` (body: `{"question": "..."}`) |
| Insights API | `GET /api/insights` |

## Running the dashboard

In a separate terminal (the API does not need to be running - the
dashboard calls `core.py` directly):

```bash
streamlit run dashboard.py
```

Opens at **http://localhost:8501** with 9 components across the sidebar
and tabs: Document upload, Document classification, Financial KPIs,
Revenue charts, Profit charts, Financial ratios, AI summary, AI
insights, and Document Q&A.

## Why this wasn't run inside the development sandbox

FastAPI, Streamlit, and Plotly are not installed in the offline sandbox
this project was built in, and cannot be installed there (no internet
access to PyPI - the same limitation documented for other libraries in
Modules 5-11 of this project). This is expected for this kind of
deliverable: unlike an ML model that must run inside the pipeline, a
dashboard is meant to run on the end user's own machine.

To compensate, every function `api.py` and `dashboard.py` call into
(`core.py`) was tested directly and confirmed working - see the
Module 13 deliverable document, Section 4, for the actual verified
output of all 7 core functions.
