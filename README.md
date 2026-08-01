# 1st place in The Atlassian X Mistral X AISoc Hack 
source: https://aisoc-atlassian-mistral.devpost.com/project-gallery

# Prestral

Upload a PowerPoint deck plus a supporting document. Hover any region for
doc-grounded context; click to chat in a chosen audience/role. Hosts get a short
session code; viewers join the same deck.

This **`main`** branch is set up for **local development** (localhost).
Cloud deploy notes live in [DEPLOY.md](DEPLOY.md).

| Doc | Contents |
|-----|----------|
| **This file** | Local setup |
| [Backend/README.md](Backend/README.md) | Architecture + API endpoints |
| [Frontend/README.md](Frontend/README.md) | UI architecture + routes |

---

## Prerequisites

- **Python 3.11+** (3.12 recommended)
- **Node.js 20+** and npm
- A **[Mistral API key](https://console.mistral.ai)**
- Optional: **LibreOffice** for pixel-faithful slide PNGs  
  (without it, a Pillow compositor still builds usable slide images)

---

## Quick start (two terminals)

### 1. Backend — http://localhost:8000

```bash
cd Backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set:
#   MISTRAL_API_KEY=sk-...
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Check: http://localhost:8000/health → `{"status":"ok"}`  
Swagger: http://localhost:8000/docs

### 2. Frontend — http://localhost:5173

```bash
cd Frontend
cp .env.example .env.local
# Ensure:
#   VITE_USE_MOCK=false
#   VITE_API_TARGET=http://localhost:8000
npm install
npm run dev
```

Open **http://localhost:5173**

Vite proxies `/api` to the backend in dev. You can also leave `VITE_API_TARGET`
pointing at `http://localhost:8000` (absolute); both work locally.

---

## Try it

1. On the landing page, choose **Host**
2. Upload a `.pptx` and a supporting `.docx` / `.pdf`
3. You’re taken to the **presenter** view (`/present/{code}/0`) with a 6-character code
4. On another tab/device (same machine), **Join** with that code → viewer (`/deck/{code}/0`)
5. Hover hotspots for context; click to chat

Sample decks (if present): `Backend/samples/`

---

## Environment cheat sheet

| Where | Variable | Purpose |
|-------|----------|---------|
| `Backend/.env` | `MISTRAL_API_KEY` | **Required** — embeddings + chat |
| `Backend/.env` | `LIBREOFFICE_PATH` | Optional path to `soffice` |
| `Backend/.env` | `GOOGLE_CLIENT_*` | Optional Drive import |
| `Frontend/.env.local` | `VITE_USE_MOCK` | `false` to hit the real API |
| `Frontend/.env.local` | `VITE_API_TARGET` | Backend origin (dev) |

Never put the Mistral key in a `VITE_*` variable — those are baked into the browser bundle.

---

## Important local behaviour

- **In-memory store** — restarting the backend clears decks, sessions, and Drive connections
- Analysis on upload can take **tens of seconds** (Mistral embed + per-slide LLM)
- CORS is open for local frontend work

---

## Optional helper scripts

`run.sh` / `run.bat` start both processes; prefer the two-terminal flow above on macOS/Linux
(so you see logs clearly). On Windows, adjust paths inside `run.bat` if needed.

---

## Production

See [DEPLOY.md](DEPLOY.md) for a single free Render Web Service (Docker = UI + API).
