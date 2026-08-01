# Prestral

AI-assisted slide exploration: upload or import a PPTX plus supporting docs, get
hoverable/clickable components, and audience-aware chat.

## Deploy (free)

Branch **`deploy`** is based on **`frontend-vis`**. See **[DEPLOY.md](DEPLOY.md)** — Render free Web Service (one Docker = UI + API).

```bash
git push -u origin deploy
# dashboard.render.com → New → Blueprint → set MISTRAL_API_KEY
```

## Local development

### Backend

```bash
cd Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set MISTRAL_API_KEY
uvicorn app.main:app --reload --port 8000
```

Swagger: http://localhost:8000/docs — full guide: [Backend/README.md](Backend/README.md)

### Frontend

```bash
cd Frontend
cp .env.example .env.local
# VITE_USE_MOCK=false
# VITE_API_TARGET=http://localhost:8000   # optional; Vite proxies /api in dev
npm install
npm run dev
```
