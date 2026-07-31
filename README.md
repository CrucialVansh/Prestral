# Prestral

AI-assisted slide exploration: upload a PPTX deck plus a deeper supporting document,
and get per-component context for hoverable/clickable overlays plus Q&A.

## Backend

See [Backend/README.md](Backend/README.md) for setup and API docs.

```bash
cd Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set MISTRAL_API_KEY
uvicorn app.main:app --reload --port 8000
```
