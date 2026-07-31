# Prestral

AI-assisted slide exploration: upload or import a PPTX plus supporting docs, get
hoverable/clickable components, and audience-aware chat.

## Backend (for frontend engineers)

Full API guide, **API key setup**, and flows: **[Backend/README.md](Backend/README.md)**

Interactive Swagger: run the server, then open http://localhost:8000/docs

```bash
cd Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Required: MISTRAL_API_KEY from https://console.mistral.ai
# Optional (Drive): GOOGLE_CLIENT_ID + GOOGLE_CLIENT_SECRET — see Backend/README.md
uvicorn app.main:app --reload --port 8000
```
